"""Tarik tema YouTube — logika murni untuk satu pekerjaan penarikan bertahap.

Peneliti mengisi kata kunci + periode, lalu menekan satu tombol. Server lalu
mengerjakan sendiri, langkah demi langkah:

1. ``search``   — `search.list` per kata kunci, video yang TERBIT dalam periode
   (100 unit kuota per halaman, 50 video per halaman);
2. ``details``  — `videos.list` untuk judul, deskripsi, jumlah komentar
   (1 unit per 50 video); video yang judul/deskripsinya tidak memuat kata
   kuncinya dibuang, sisanya diurutkan dari yang paling ramai;
3. ``comments`` — `commentThreads` per video, satu halaman (100 utas) per
   langkah, ditambah balasan bila diminta.

Seluruh keadaan pekerjaan hidup di satu dict (``config`` baris `data_sources`
berkonektor ``youtube_theme``) supaya fitur ini tidak butuh migrasi Supabase
dan pekerjaan bisa dilanjutkan sesudah server tidur atau dideploy ulang.
Modul ini tidak menyentuh jaringan maupun database; yang memanggil YouTube ada
di ``app/connectors/youtube_theme.py`` dan pekerjanya di
``app/routers/theme_pulls.py``.

Batas yang melekat dan wajib ikut dibaca:

- Hasil pencarian diurutkan algoritma YouTube, bukan sampel. Korpus yang
  besar tetap korpus yang dipilih mesin peringkat.
- Penyaring kata kunci pada judul/deskripsi membuang video di luar tema, tetapi
  juga bisa membuang video relevan yang judulnya tidak menyebut kata kuncinya.
- Komentar yang sudah dihapus pemilik kanal tidak pernah terlihat.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

KEY = "youtube_theme"

#: Zona waktu periode. Offset tetap (tanpa DST).
WIB_HOURS = 7

MAX_QUERIES = 5
MAX_QUERY_LENGTH = 120
DEFAULT_MAX_VIDEOS = 50
MAX_MAX_VIDEOS = 300
#: Periode terpanjang. `search.list` hanya mengembalikan ±500 video per kueri;
#: periode yang lebih panjang tidak menambah cakupan, cuma mengencerkannya.
MAX_PERIOD_DAYS = 366
#: Halaman `search.list` per kata kunci (50 video per halaman, 100 unit).
MAX_SEARCH_PAGES_PER_QUERY = 4
SEARCH_UNITS = 100
SEARCH_PAGE_SIZE = 50

STATUS_SEARCHING = "searching"
STATUS_DETAILS = "details"
STATUS_COLLECTING = "collecting"
STATUS_WAITING_QUOTA = "waiting_quota"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_STOPPED = "stopped"

#: Status yang masih perlu dikerjakan pekerja.
ACTIVE = frozenset({STATUS_SEARCHING, STATUS_DETAILS, STATUS_COLLECTING, STATUS_WAITING_QUOTA})
FINAL = frozenset({STATUS_DONE, STATUS_FAILED, STATUS_STOPPED})

VIDEO_PENDING = "pending"
VIDEO_DONE = "done"
VIDEO_SKIPPED = "skipped"

METHOD = (
    "YouTube Data API v3 resmi: search.list (video terbit dalam periode, "
    "regionCode=ID, relevanceLanguage=id, urut relevansi), penyaring kata kunci "
    "pada judul+deskripsi, lalu commentThreads (+ comments.list untuk balasan)"
)

LIMITATIONS = (
    "Video dipilih algoritma peringkat YouTube, bukan sampel acak.",
    "Penyaring judul/deskripsi bisa membuang video relevan yang tidak menyebut kata kuncinya.",
    "Komentar yang dihapus pemilik kanal atau moderator tidak pernah terlihat.",
    "Komentar YouTube bersifat self-selected; tidak mewakili penduduk.",
)


class ThemeError(ValueError):
    """Permintaan penarikan tidak sah. Pesannya untuk ditampilkan ke pengguna."""


@dataclass(frozen=True, slots=True)
class ThemeRequest:
    queries: tuple[str, ...]
    start: date
    end: date
    max_videos: int
    include_replies: bool
    comments_until_now: bool
    keyword_filter: bool


def split_queries(raw: str) -> tuple[str, ...]:
    """Kata kunci dipisah koma atau baris baru; kosong dan ganda dibuang."""
    seen: list[str] = []
    for part in re.split(r"[,\n;]", raw):
        q = " ".join(part.split())
        if q and q.lower() not in (s.lower() for s in seen):
            seen.append(q)
    return tuple(seen)


def parse_request(
    *,
    queries: str,
    start: date,
    end: date,
    max_videos: int,
    include_replies: bool,
    comments_until_now: bool,
    keyword_filter: bool,
    today: date,
) -> ThemeRequest:
    """Periksa dan normalkan isian formulir. Melempar ThemeError."""
    qs = split_queries(queries)
    if not qs:
        raise ThemeError("Isi minimal satu kata kunci.")
    if len(qs) > MAX_QUERIES:
        raise ThemeError(f"Paling banyak {MAX_QUERIES} kata kunci per penarikan.")
    for q in qs:
        if len(q) > MAX_QUERY_LENGTH:
            raise ThemeError(f"Kata kunci maksimal {MAX_QUERY_LENGTH} karakter.")
    if end < start:
        raise ThemeError("Tanggal selesai tidak boleh sebelum tanggal mulai.")
    if start > today:
        raise ThemeError("Tanggal mulai tidak boleh di masa depan.")
    if (end - start).days + 1 > MAX_PERIOD_DAYS:
        raise ThemeError(f"Periode paling panjang {MAX_PERIOD_DAYS} hari.")
    if not 1 <= max_videos <= MAX_MAX_VIDEOS:
        raise ThemeError(f"Jumlah video harus 1–{MAX_MAX_VIDEOS}.")
    return ThemeRequest(
        queries=qs,
        start=start,
        end=min(end, today),
        max_videos=max_videos,
        include_replies=include_replies,
        comments_until_now=comments_until_now,
        keyword_filter=keyword_filter,
    )


def window_utc(start: date, end: date) -> tuple[datetime, datetime]:
    """Periode WIB inklusif → [awal, akhir) dalam UTC."""
    offset = timedelta(hours=WIB_HOURS)
    lo = datetime(start.year, start.month, start.day, tzinfo=UTC) - offset
    hi = datetime(end.year, end.month, end.day, tzinfo=UTC) + timedelta(days=1) - offset
    return lo, hi


def rfc3339(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def initial_state(req: ThemeRequest, *, label: str, now: datetime) -> dict[str, Any]:
    """Keadaan awal pekerjaan, siap disimpan di kolom JSON."""
    return {
        "label": label,
        "queries": list(req.queries),
        "start": req.start.isoformat(),
        "end": req.end.isoformat(),
        "max_videos": req.max_videos,
        "include_replies": req.include_replies,
        "comments_until_now": req.comments_until_now,
        "keyword_filter": req.keyword_filter,
        "status": STATUS_SEARCHING,
        "status_before_wait": None,
        "query_index": 0,
        "search_page": 0,
        "search_token": None,
        "candidates": [],
        "detail_index": 0,
        "videos": [],
        "video_index": 0,
        "comment_token": None,
        "units": 0,
        "received": 0,
        "stored": 0,
        "outside_window": 0,
        "dropped_by_filter": 0,
        "error": None,
        "notes": [],
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "finished_at": None,
        "resume_at": None,
    }


def comment_window(state: dict[str, Any]) -> tuple[datetime, datetime | None]:
    """Batas waktu komentar yang disimpan; akhir None = sampai sekarang."""
    lo, hi = window_utc(date.fromisoformat(state["start"]), date.fromisoformat(state["end"]))
    return lo, None if state.get("comments_until_now") else hi


def in_window(published: datetime, lo: datetime, hi: datetime | None) -> bool:
    return published >= lo and (hi is None or published < hi)


_WORD = re.compile(r"\w+", re.UNICODE)


def relevant(title: str, description: str, queries: list[str] | tuple[str, ...]) -> bool:
    """Judul+deskripsi memuat SEMUA kata dari minimal satu kata kunci.

    Pencocokan per kata, bukan frasa utuh: "gibran mundur" cocok dengan
    "Gibran resmi mundur dari kursi wapres".
    """
    words = set(_WORD.findall(f"{title} {description}".lower()))
    for q in queries:
        needed = set(_WORD.findall(q.lower()))
        if needed and needed <= words:
            return True
    return False


def add_candidates(state: dict[str, Any], video_ids: list[str]) -> int:
    """Tambahkan ID video hasil pencarian tanpa ganda. Mengembalikan jumlah yang baru."""
    known = set(state["candidates"])
    fresh = [v for v in video_ids if v and v not in known]
    state["candidates"].extend(fresh)
    return len(fresh)


def candidate_cap(state: dict[str, Any]) -> int:
    """Berapa kandidat yang cukup sebelum berhenti mencari.

    Dua kali target: sebagian kandidat akan gugur di penyaring kata kunci.
    """
    target = int(state["max_videos"])
    return target * 2 if state.get("keyword_filter", True) else target


def advance_search(state: dict[str, Any], *, next_token: str | None) -> None:
    """Sesudah satu halaman pencarian: ke halaman berikut, kueri berikut, atau tahap detail."""
    state["search_page"] += 1
    enough = len(state["candidates"]) >= candidate_cap(state)
    if next_token and state["search_page"] < MAX_SEARCH_PAGES_PER_QUERY and not enough:
        state["search_token"] = next_token
        return
    state["search_token"] = None
    state["search_page"] = 0
    state["query_index"] += 1
    if enough or state["query_index"] >= len(state["queries"]):
        state["status"] = STATUS_DETAILS


def search_page_size(state: dict[str, Any]) -> int:
    room = candidate_cap(state) - len(state["candidates"])
    return max(1, min(SEARCH_PAGE_SIZE, room))


def next_detail_batch(state: dict[str, Any], size: int = 50) -> list[str]:
    i = int(state["detail_index"])
    return list(state["candidates"][i : i + size])


def accept_details(state: dict[str, Any], details: list[dict[str, Any]], batch_len: int) -> None:
    """Simpan detail satu batch; sesudah batch terakhir, saring + urutkan + potong."""
    keep_filter = bool(state.get("keyword_filter", True))
    for d in details:
        if keep_filter and not relevant(d["title"], d.get("description", ""), state["queries"]):
            state["dropped_by_filter"] += 1
            continue
        state["videos"].append(
            {
                "id": d["id"],
                "title": d["title"][:200],
                "channel": d.get("channel", "")[:120],
                "published_at": d.get("published_at"),
                "comment_count": int(d.get("comment_count") or 0),
                "state": VIDEO_PENDING,
                "got": 0,
                "note": None,
            }
        )
    state["detail_index"] += batch_len
    if state["detail_index"] >= len(state["candidates"]):
        videos = sorted(state["videos"], key=lambda v: -v["comment_count"])
        state["videos"] = videos[: int(state["max_videos"])]
        for v in state["videos"]:
            if v["comment_count"] == 0:
                v["state"] = VIDEO_SKIPPED
                v["note"] = "tanpa komentar"
        state["candidates"] = []
        state["video_index"] = 0
        state["comment_token"] = None
        state["status"] = STATUS_COLLECTING
        if not state["videos"]:
            state["notes"].append("Tidak ada video yang cocok dengan kata kunci di periode ini.")
        settle_video_index(state)


def settle_video_index(state: dict[str, Any]) -> None:
    """Majukan ke video berikutnya yang belum selesai; tandai selesai bila habis."""
    videos = state["videos"]
    while (
        state["video_index"] < len(videos)
        and videos[state["video_index"]]["state"] != VIDEO_PENDING
    ):
        state["video_index"] += 1
        state["comment_token"] = None
    if state["video_index"] >= len(videos):
        state["status"] = STATUS_DONE


def finish_video(state: dict[str, Any], *, skipped_note: str | None = None) -> None:
    video = state["videos"][state["video_index"]]
    video["state"] = VIDEO_SKIPPED if skipped_note else VIDEO_DONE
    if skipped_note:
        video["note"] = skipped_note
    state["comment_token"] = None
    settle_video_index(state)


def next_quota_reset(now: datetime) -> datetime:
    """Kapan kuota harian YouTube pasti sudah pulih.

    Kuota dipulihkan tengah malam waktu Pasifik (00.00 PST = 08.00 UTC, 00.00
    PDT = 07.00 UTC). 08.05 UTC berikutnya selalu sesudah keduanya, tanpa
    perlu basis data zona waktu.
    """
    candidate = now.astimezone(UTC).replace(hour=8, minute=5, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def wait_for_quota(state: dict[str, Any], now: datetime) -> None:
    if state["status"] != STATUS_WAITING_QUOTA:
        state["status_before_wait"] = state["status"]
    state["status"] = STATUS_WAITING_QUOTA
    state["resume_at"] = next_quota_reset(now).isoformat()


def quota_ready(state: dict[str, Any], now: datetime) -> bool:
    """Pekerjaan yang menunggu kuota boleh lanjut sekarang?"""
    if state["status"] != STATUS_WAITING_QUOTA:
        return True
    resume = state.get("resume_at")
    return resume is None or datetime.fromisoformat(resume) <= now


def leave_quota_wait(state: dict[str, Any]) -> None:
    if state["status"] == STATUS_WAITING_QUOTA:
        state["status"] = state.get("status_before_wait") or STATUS_COLLECTING
        state["status_before_wait"] = None
        state["resume_at"] = None


@dataclass(frozen=True, slots=True)
class Progress:
    status: str
    videos_total: int
    videos_done: int
    videos_skipped: int
    comments_expected: int
    received: int
    stored: int
    units: int
    current_video: str | None


def progress(state: dict[str, Any]) -> Progress:
    videos = state.get("videos") or []
    idx = int(state.get("video_index") or 0)
    current = None
    if state.get("status") in ACTIVE and 0 <= idx < len(videos):
        current = videos[idx]["title"]
    return Progress(
        status=str(state.get("status")),
        videos_total=len(videos),
        videos_done=sum(1 for v in videos if v["state"] == VIDEO_DONE),
        videos_skipped=sum(1 for v in videos if v["state"] == VIDEO_SKIPPED),
        comments_expected=sum(int(v["comment_count"]) for v in videos),
        received=int(state.get("received") or 0),
        stored=int(state.get("stored") or 0),
        units=int(state.get("units") or 0),
        current_video=current,
    )


def estimate_units(state: dict[str, Any]) -> int:
    """Perkiraan kasar sisa kuota: 1 unit per 100 komentar, balasan dihitung lagi."""
    videos = state.get("videos") or []
    remaining = 0
    for v in videos:
        if v["state"] != VIDEO_PENDING:
            continue
        left = max(0, int(v["comment_count"]) - int(v["got"]))
        remaining += left // 100 + 1
    if state.get("include_replies"):
        remaining = int(remaining * 1.3)
    return remaining
