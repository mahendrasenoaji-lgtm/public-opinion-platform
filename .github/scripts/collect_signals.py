#!/usr/bin/env python3
"""Pemicu pengumpulan terjadwal — dijalankan GitHub Actions (collect-signals.yml).

Skrip ini TIDAK mengambil feed apa pun. Ia hanya membangunkan API di Render
lalu memanggil `POST /projects/{id}/signals/collect-all` untuk setiap token
pengumpul yang diberikan. Pengambilan, penyaringan, dedup, dan penyimpanan
terjadi di API — di satu tempat, dengan konektor yang sama yang dites CI.

Kenapa begitu (2026-09-15): akumulasi harian MBG sebelumnya berupa skrip yang
mengambil feed dari sandbox routine cloud. Empat hari berturut-turut semua feed
membalas 403 dari jaringan sandbox, dan routine tetap berstatus "berhasil".
Dua pelajaran yang dikodekan di sini:

1. Status sukses harus berarti data masuk. Skrip keluar dengan kode non-nol
   bila ADA sumber yang gagal, supaya run GitHub Actions merah dan GitHub
   mengirim email — bukan hijau dengan 0 artikel.
2. "Tidak ada artikel baru" dan "tidak bisa membaca feed" harus terlihat
   berbeda. Ringkasan menampilkan per sumber: berapa ditawarkan feed, berapa
   cocok tema, berapa tersimpan, dan apakah ada celah cakupan.

Hanya pustaka standar — tidak ada `pip install` yang bisa gagal duluan.

Env:
  POP_API_BASE          mis. https://pop-api-ptug.onrender.com/v1
  POP_COLLECTOR_TOKENS  satu token pengumpul per baris (secret)
  POP_SINCE_DAYS        opsional, default 2
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime

#: Render free tier tidur setelah ~15 menit sepi; bangun terukur 93 detik
#: pada 2026-09-15. Batas ini memberi ruang dua kali lipat lebih.
WAKE_TIMEOUT_SECONDS = 240
#: collect-all mengambil semua feed bersamaan (masing-masing timeout 20 dtk)
#: lalu menyimpan berurutan. 180 detik jauh di atas yang pernah terukur.
COLLECT_TIMEOUT_SECONDS = 180
#: Peringatkan jauh sebelum token kedaluwarsa, bukan pada hari ia berhenti.
EXPIRY_WARNING_DAYS = 21

USER_AGENT = "pop-scheduled-collector (+github actions)"


def _request(
    method: str, url: str, *, token: str | None = None, timeout: float
) -> tuple[int, str]:
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", USER_AGENT)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def _claims(token: str) -> dict:
    """Baca klaim JWT TANPA verifikasi — hanya untuk project_id dan tanggal kedaluwarsa.

    Verifikasi adalah tugas API. Di sini klaim cuma dipakai menyusun URL dan
    memberi peringatan dini; token palsu tetap akan ditolak server.
    """
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return dict(json.loads(base64.urlsafe_b64decode(payload)))


def _annotate(level: str, message: str) -> None:
    print(f"::{level}::{message}")


def wake(base: str) -> bool:
    health = base.rsplit("/v1", 1)[0] + "/health"
    deadline = time.monotonic() + WAKE_TIMEOUT_SECONDS
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        started = time.monotonic()
        try:
            status, _ = _request("GET", health, timeout=120)
        except (urllib.error.URLError, TimeoutError) as e:
            status = 0
            print(f"  health percobaan {attempt}: {e}")
        if status == 200:
            print(f"API bangun (percobaan {attempt}, {time.monotonic() - started:.0f} dtk)")
            return True
        print(f"  health percobaan {attempt}: status {status}")
        time.sleep(10)
    return False


def collect(base: str, token: str, since_days: int) -> tuple[bool, list[str]]:
    """Satu proyek. Return (semua_sumber_ok, baris_ringkasan_markdown)."""
    claims = _claims(token)
    project_id = claims.get("prj")
    if not project_id or claims.get("type") != "collector":
        _annotate("error", "Salah satu POP_COLLECTOR_TOKENS bukan token pengumpul.")
        return False, []

    expires = datetime.fromtimestamp(int(claims["exp"]), tz=UTC)
    days_left = (expires - datetime.now(UTC)).days
    if days_left < EXPIRY_WARNING_DAYS:
        _annotate(
            "warning",
            f"Token pengumpul proyek {project_id} kedaluwarsa {expires:%Y-%m-%d} "
            f"({days_left} hari lagi). Terbitkan ulang dan perbarui secret.",
        )

    url = f"{base}/projects/{project_id}/signals/collect-all?since_days={since_days}"
    status, body = 0, ""
    for attempt in (1, 2):
        try:
            status, body = _request("POST", url, token=token, timeout=COLLECT_TIMEOUT_SECONDS)
        except (urllib.error.URLError, TimeoutError) as e:
            status, body = 0, str(e)
        # 502/503/504 dari proxy Render saat instance baru bangun: coba sekali lagi.
        if status not in (0, 502, 503, 504):
            break
        print(f"  collect-all percobaan {attempt}: status {status}, diulang")
        time.sleep(15)

    if status != 200:
        _annotate("error", f"collect-all proyek {project_id} gagal: {status} {body[:300]}")
        return False, [f"**Proyek `{project_id}` — GAGAL ({status})**", "", body[:500], ""]

    data = json.loads(body)
    lines = [
        f"### Proyek `{project_id}`",
        "",
        f"Sumber: {data['sources_ok']} berhasil, **{data['sources_failed']} gagal**, "
        f"{data['sources_inactive']} nonaktif · tersimpan baru: **{data['stored_total']}** · "
        f"celah cakupan: {data['coverage_gaps']} · token berlaku s.d. {expires:%Y-%m-%d}",
        "",
        "| Sumber | Status | Ditawarkan feed | Cocok tema | Tersimpan baru | Celah |",
        "|---|---|---:|---:|---:|---|",
    ]
    for r in data["results"]:
        stored = r["result"]["stored"] if r["result"] else "–"
        status_cell = "ok" if r["ok"] else f"GAGAL: {r['error']}"
        gap = "YA" if r["coverage_gap"] else ""
        offered = r["offered"] if r["offered"] is not None else "–"
        matched = r["matched"] if r["matched"] is not None else "–"
        lines.append(
            f"| {r['label']} | {status_cell} | {offered} | {matched} | {stored} | {gap} |"
        )
        print(
            f"  {str(r['label'])[:48]:<48} {'ok' if r['ok'] else 'GAGAL':<5} "
            f"ditawarkan={offered} cocok={matched} tersimpan={stored}"
            + (f" error={r['error']}" if not r["ok"] else "")
            + (" CELAH" if r["coverage_gap"] else "")
        )
        if not r["ok"]:
            _annotate("error", f"{r['label']}: {r['error']}")
        if r["coverage_gap"]:
            _annotate(
                "warning",
                f"{r['label']}: item tertua di feed lebih baru dari pengambilan "
                "sebelumnya — ada berita yang terlewat. Rapatkan jadwal.",
            )
    lines.append("")

    if data["sources_total"] == 0:
        _annotate("error", f"Proyek {project_id} tidak punya sumber data terdaftar.")
        return False, lines
    return data["sources_failed"] == 0, lines


def main() -> int:
    base = os.environ.get("POP_API_BASE", "").rstrip("/")
    tokens = [t.strip() for t in os.environ.get("POP_COLLECTOR_TOKENS", "").splitlines()]
    tokens = [t for t in tokens if t]
    since_days = int(os.environ.get("POP_SINCE_DAYS") or "2")

    if not base or not tokens:
        _annotate("error", "POP_API_BASE atau POP_COLLECTOR_TOKENS belum diset.")
        return 1

    if not wake(base):
        _annotate("error", f"API tidak bangun dalam {WAKE_TIMEOUT_SECONDS} detik.")
        return 1

    all_ok = True
    summary = [f"## Pengumpulan sinyal — {datetime.now(UTC):%Y-%m-%d %H:%M} UTC", ""]
    for token in tokens:
        ok, lines = collect(base, token, since_days)
        all_ok = all_ok and ok
        summary.extend(lines)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("\n".join(summary) + "\n")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
