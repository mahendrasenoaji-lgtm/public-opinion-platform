"""Tes untuk .github/scripts/collect_signals.py (K9, docs/progress.md).

Skrip itu dijalankan GitHub Actions, bukan bagian dari paket pop-api, dan
sengaja tanpa dependensi pip (lihat docstring modulnya) -- jadi diimpor di
sini lewat path file langsung, bukan `import` biasa. Server HTTP palsu di
bawah memakai stdlib `http.server` saja, konsisten dengan skrip yang dites.

Semua `time.sleep` di modul dites di-nolkan lewat fixture `no_sleep` supaya
jalur retry/backoff diverifikasi tanpa membuat suite lambat sungguhan.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3] / ".github" / "scripts" / "collect_signals.py"
)
_spec = importlib.util.spec_from_file_location("collect_signals", _SCRIPT_PATH)
assert _spec and _spec.loader
collect_signals = importlib.util.module_from_spec(_spec)
sys.modules["collect_signals"] = collect_signals
_spec.loader.exec_module(collect_signals)


def _b64(obj: dict[str, Any]) -> str:
    raw = json.dumps(obj).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _make_token(**claims: Any) -> str:
    header = _b64({"alg": "none", "typ": "JWT"})
    payload = _b64(claims)
    return f"{header}.{payload}.sig"


def _collector_token(project_id: str = "proj-1", days_left: int = 100) -> str:
    exp = int((datetime.now(UTC) + timedelta(days=days_left)).timestamp())
    return _make_token(type="collector", prj=project_id, exp=exp)


def _collect_response(**overrides: Any) -> dict[str, Any]:
    base = {
        "sources_total": 1,
        "sources_ok": 1,
        "sources_failed": 0,
        "sources_inactive": 0,
        "stored_total": 5,
        "coverage_gaps": 0,
        "results": [
            {
                "label": "Antara nasional",
                "ok": True,
                "error": None,
                "coverage_gap": False,
                "offered": 50,
                "matched": 5,
                "result": {"stored": 5},
            }
        ],
    }
    base.update(overrides)
    return base


class _FakeServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _make_handler(routes: dict[tuple[str, str], Any]) -> type[BaseHTTPRequestHandler]:
    """`routes[(method, path)]` bisa `(status, body)`, callable() -> (status, body),
    atau list dari keduanya yang dikonsumsi berurutan (untuk menguji retry)."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:  # senyapkan log default
            pass

        def _handle(self, method: str) -> None:
            key = (method, self.path.split("?")[0])
            entry = routes.get(key)
            if entry is None:
                self.send_response(404)
                self.end_headers()
                return
            if callable(entry):
                status, body = entry()
            elif isinstance(entry, list):
                status, body = entry.pop(0) if len(entry) > 1 else entry[0]
            else:
                status, body = entry
            payload = body.encode() if isinstance(body, str) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802 (nama method BaseHTTPRequestHandler)
            self._handle("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._handle("POST")

    return Handler


@pytest.fixture
def fake_server() -> Any:
    servers: list[_FakeServer] = []

    def _start(routes: dict[tuple[str, str], Any]) -> str:
        handler = _make_handler(routes)
        server = _FakeServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}"

    yield _start
    for s in servers:
        s.shutdown()
        s.server_close()


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(collect_signals.time, "sleep", lambda _seconds: None)


# --- _claims -----------------------------------------------------------


def test_claims_decodes_payload_without_verifying_signature() -> None:
    token = _make_token(type="collector", prj="proj-x", exp=123)
    assert collect_signals._claims(token) == {"type": "collector", "prj": "proj-x", "exp": 123}


# --- wake ----------------------------------------------------------------


def test_wake_succeeds_first_try(fake_server: Any) -> None:
    base = fake_server({("GET", "/health"): (200, "ok")}) + "/v1"
    assert collect_signals.wake(base) is True


def test_wake_retries_then_succeeds(fake_server: Any) -> None:
    responses = [(503, "sleeping"), (503, "sleeping"), (200, "ok")]
    base = fake_server({("GET", "/health"): responses}) + "/v1"
    assert collect_signals.wake(base) is True


def test_wake_times_out_when_never_healthy(
    fake_server: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(collect_signals, "WAKE_TIMEOUT_SECONDS", 0.05)
    base = fake_server({("GET", "/health"): (503, "sleeping")}) + "/v1"
    assert collect_signals.wake(base) is False


# --- collect ---------------------------------------------------------------


def test_collect_reports_success_with_markdown_table(fake_server: Any) -> None:
    token = _collector_token(project_id="proj-1")
    body = _collect_response()
    base = fake_server(
        {("POST", "/v1/projects/proj-1/signals/collect-all"): (200, body)}
    ) + "/v1"

    ok, lines = collect_signals.collect(base, token, since_days=2)

    assert ok is True
    joined = "\n".join(lines)
    assert "Proyek `proj-1`" in joined
    assert "1 berhasil, **0 gagal**" in joined
    assert "Antara nasional" in joined
    assert "5" in joined  # tersimpan baru


def test_collect_returns_not_ok_when_a_source_fails(fake_server: Any) -> None:
    token = _collector_token(project_id="proj-1")
    body = _collect_response(
        sources_ok=1,
        sources_failed=1,
        results=[
            _collect_response()["results"][0],
            {
                "label": "Republika",
                "ok": False,
                "error": "timeout",
                "coverage_gap": False,
                "offered": None,
                "matched": None,
                "result": None,
            },
        ],
    )
    base = fake_server(
        {("POST", "/v1/projects/proj-1/signals/collect-all"): (200, body)}
    ) + "/v1"

    ok, lines = collect_signals.collect(base, token, since_days=2)

    assert ok is False
    assert "GAGAL: timeout" in "\n".join(lines)


def test_collect_fails_when_project_has_no_sources(
    fake_server: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    token = _collector_token(project_id="proj-1")
    body = _collect_response(sources_total=0, sources_ok=0, results=[])
    base = fake_server(
        {("POST", "/v1/projects/proj-1/signals/collect-all"): (200, body)}
    ) + "/v1"

    ok, _lines = collect_signals.collect(base, token, since_days=2)

    assert ok is False
    assert "tidak punya sumber data terdaftar" in capsys.readouterr().out


def test_collect_retries_once_on_5xx_then_succeeds(fake_server: Any) -> None:
    token = _collector_token(project_id="proj-1")
    responses = [(502, "bad gateway"), (200, json.dumps(_collect_response()))]
    base = fake_server(
        {("POST", "/v1/projects/proj-1/signals/collect-all"): responses}
    ) + "/v1"

    ok, _lines = collect_signals.collect(base, token, since_days=2)

    assert ok is True


def test_collect_gives_up_after_two_attempts_on_5xx(fake_server: Any) -> None:
    token = _collector_token(project_id="proj-1")
    base = fake_server(
        {("POST", "/v1/projects/proj-1/signals/collect-all"): (503, "still sleeping")}
    ) + "/v1"

    ok, lines = collect_signals.collect(base, token, since_days=2)

    assert ok is False
    assert "GAGAL (503)" in "\n".join(lines)


def test_collect_rejects_token_that_is_not_type_collector(
    capsys: pytest.CaptureFixture[str],
) -> None:
    token = _make_token(type="viewer", prj="proj-1", exp=9999999999)

    ok, lines = collect_signals.collect("http://unused/v1", token, since_days=2)

    assert ok is False
    assert lines == []
    assert "bukan token pengumpul" in capsys.readouterr().out


def test_collect_warns_when_token_near_expiry(
    fake_server: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    token = _collector_token(project_id="proj-1", days_left=5)
    base = fake_server(
        {("POST", "/v1/projects/proj-1/signals/collect-all"): (200, _collect_response())}
    ) + "/v1"

    collect_signals.collect(base, token, since_days=2)

    assert "kedaluwarsa" in capsys.readouterr().out


# --- main --------------------------------------------------------------


def test_main_writes_summary_and_returns_zero_on_full_success(
    fake_server: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    token = _collector_token(project_id="proj-1")
    base_url = fake_server(
        {
            ("GET", "/health"): (200, "ok"),
            ("POST", "/v1/projects/proj-1/signals/collect-all"): (200, _collect_response()),
        }
    )
    summary_file = tmp_path / "summary.md"
    monkeypatch.setenv("POP_API_BASE", base_url + "/v1")
    monkeypatch.setenv("POP_COLLECTOR_TOKENS", token)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

    assert collect_signals.main() == 0
    content = summary_file.read_text(encoding="utf-8")
    assert "## Pengumpulan sinyal" in content
    assert "proj-1" in content


def test_main_returns_nonzero_when_a_source_fails(
    fake_server: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = _collector_token(project_id="proj-1")
    failing = _collect_response(
        sources_ok=0,
        sources_failed=1,
        results=[
            {
                "label": "Republika",
                "ok": False,
                "error": "403",
                "coverage_gap": False,
                "offered": None,
                "matched": None,
                "result": None,
            }
        ],
    )
    base_url = fake_server(
        {
            ("GET", "/health"): (200, "ok"),
            ("POST", "/v1/projects/proj-1/signals/collect-all"): (200, failing),
        }
    )
    monkeypatch.setenv("POP_API_BASE", base_url + "/v1")
    monkeypatch.setenv("POP_COLLECTOR_TOKENS", token)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    assert collect_signals.main() == 1


def test_main_returns_error_when_env_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("POP_API_BASE", raising=False)
    monkeypatch.delenv("POP_COLLECTOR_TOKENS", raising=False)

    assert collect_signals.main() == 1
    assert "belum diset" in capsys.readouterr().out


def test_main_returns_error_when_api_never_wakes(
    fake_server: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(collect_signals, "WAKE_TIMEOUT_SECONDS", 0.05)
    base_url = fake_server({("GET", "/health"): (503, "sleeping")})
    monkeypatch.setenv("POP_API_BASE", base_url + "/v1")
    monkeypatch.setenv("POP_COLLECTOR_TOKENS", _collector_token())
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    assert collect_signals.main() == 1


def test_main_handles_multiple_tokens_independently(
    fake_server: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_a = _collector_token(project_id="proj-a")
    token_b = _collector_token(project_id="proj-b")
    base_url = fake_server(
        {
            ("GET", "/health"): (200, "ok"),
            ("POST", "/v1/projects/proj-a/signals/collect-all"): (
                200,
                _collect_response(),
            ),
            ("POST", "/v1/projects/proj-b/signals/collect-all"): (
                200,
                _collect_response(sources_failed=1, sources_ok=0),
            ),
        }
    )
    monkeypatch.setenv("POP_API_BASE", base_url + "/v1")
    monkeypatch.setenv("POP_COLLECTOR_TOKENS", f"{token_a}\n{token_b}\n")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    # proj-b gagal -> keseluruhan run harus dianggap gagal (exit non-nol),
    # meski proj-a berhasil -- inilah yang membuat email GitHub terkirim.
    assert collect_signals.main() == 1
