"""Publikasi hasil riset: slug, alur status, dan snapshot yang aman dibuka.

Rencana: `docs/rencana-situs-publikasi.md`. Fungsi murni, tanpa I/O.

Snapshot adalah salinan BEKU bahan `/laporan` pada saat draf dibuat. Angka di
artikel tidak ikut berubah bila data dashboard dinilai ulang. Sebelum disimpan,
snapshot dibersihkan: teks dan tautan konten warga (SOCIAL) dibuang, karena
kutipan utuh bisa dicari dan menunjuk ke penulisnya (CLAUDE.md bagian 3,
UU PDP). Judul dan tautan berita (MEDIA) tetap, karena itu terbitan redaksi.
"""

from __future__ import annotations

import re
import secrets
import unicodedata
from copy import deepcopy
from typing import Any, Final, Literal

Status = Literal["draft", "review", "published"]

STATUSES: Final[tuple[Status, ...]] = ("draft", "review", "published")

#: Peran yang boleh menerbitkan. Usulan di rencana: hanya Research Director
#: (dan Super Admin). Mengubahnya adalah keputusan pemilik produk.
PUBLISHER_ROLES: Final[frozenset[str]] = frozenset({"SUPER_ADMIN", "RESEARCH_DIRECTOR"})

#: Transisi yang sah. Artikel terbit tidak bisa kembali menjadi draf: yang ada
#: adalah ralat, supaya jejaknya tercatat.
TRANSITIONS: Final[dict[Status, frozenset[Status]]] = {
    "draft": frozenset({"review"}),
    "review": frozenset({"draft", "published"}),
    "published": frozenset(),
}

SNAPSHOT_VERSION: Final = 1
MAX_SLUG_BASE: Final = 80

SNAPSHOT_NOTE: Final = (
    "Angka dibekukan saat draf dibuat dan tidak berubah bila data dinilai ulang. "
    "Teks dan tautan konten warga tidak disertakan; yang tampil hanya agregat."
)


def slugify(title: str) -> str:
    """Huruf kecil ASCII dan tanda hubung; kosong menjadi 'artikel'."""
    # Buang tanda diakritik saja; tanda baca non-ASCII (mis. tanda pisah) tetap
    # menjadi pemisah, tidak hilang begitu saja.
    plain = "".join(
        ch for ch in unicodedata.normalize("NFKD", title) if not unicodedata.combining(ch)
    )
    base = re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")[:MAX_SLUG_BASE].strip("-")
    return base or "artikel"


def new_slug(title: str) -> str:
    """Slug dengan akhiran acak supaya tidak bertabrakan antarorganisasi."""
    return f"{slugify(title)}-{secrets.token_hex(3)}"


def can_transition(current: Status, target: Status) -> bool:
    return target in TRANSITIONS[current]


def check_transition(current: Status, target: Status, role: str) -> None:
    """Lempar ValueError/PermissionError bila perpindahan status tidak sah."""
    if not can_transition(current, target):
        raise ValueError(f"Status tidak bisa berpindah dari {current} ke {target}.")
    if target == "published" and role not in PUBLISHER_ROLES:
        raise PermissionError("Hanya Research Director yang boleh menerbitkan.")


def normalize_tags(tags: list[str]) -> list[str]:
    """Huruf kecil, tanpa duplikat, urutan dipertahankan, maksimal 8."""
    seen: list[str] = []
    for raw in tags:
        tag = slugify(raw) if raw.strip() else ""
        if tag and tag != "artikel" and tag not in seen:
            seen.append(tag)
    return seen[:8]


def _strip_social_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sisakan waktu dan jumlah interaksi; buang teks dan tautan."""
    return [
        {"engagement": i.get("engagement"), "published_at": i.get("published_at")} for i in items
    ]


def sanitize_report(report: dict[str, Any]) -> dict[str, Any]:
    """Salinan laporan yang aman dibuka ke publik.

    Konten teratas dari sumber SOCIAL kehilangan `text` dan `source_url`.
    Liputan pada hari yang sama (`same_day_media`) adalah berita, jadi tetap.
    """
    out = deepcopy(report)
    for source in out.get("sources", []):
        if source.get("source") != "SOCIAL":
            continue
        for peak in source.get("peaks", []):
            peak["top_content"] = _strip_social_items(peak.get("top_content", []))
    return out


def build_snapshot(
    *,
    report: dict[str, Any],
    project_name: str,
    frozen_at: str,
    timezone: str,
) -> dict[str, Any]:
    """Bungkus laporan yang sudah dibersihkan beserta keterangan pembekuannya."""
    clean = sanitize_report(report)
    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "frozen_at": frozen_at,
        "project_name": project_name,
        "period_start": clean.get("period_start"),
        "period_end": clean.get("period_end"),
        "timezone": timezone,
        "note": SNAPSHOT_NOTE,
        "report": clean,
    }


def snapshot_has_social_text(snapshot: dict[str, Any]) -> bool:
    """Penjaga: benar bila masih ada teks/tautan konten warga di snapshot."""
    for source in snapshot.get("report", {}).get("sources", []):
        if source.get("source") != "SOCIAL":
            continue
        for peak in source.get("peaks", []):
            for item in peak.get("top_content", []):
                if item.get("text") or item.get("source_url"):
                    return True
    return False


# ------------------------------------------------------------ snapshot kinerja ----

KINERJA_NOTE: Final = (
    "Angka dibekukan saat draf dibuat dan tidak berubah bila isian kinerja diubah. Skor "
    "indikator diisi penilai dengan bukti; indikator tanpa data dicatat tidak tersedia, "
    "tidak ditebak."
)

#: Kolom ringkasan situs yang ikut dibekukan. Daftar butir, catatan pembacaan,
#: dan alamat halaman daftar tidak ikut: yang diterbitkan hanya angka keaktifan.
SITE_FIELDS: Final[tuple[str, ...]] = (
    "subject",
    "base_url",
    "feed_kind",
    "n_window",
    "n_30",
    "last_published",
    "days_since_last",
    "longest_gap_days",
    "median_gap_days",
    "status",
    "quiet",
)


def in_period(period: str, start: str, end: str) -> bool:
    """Benar bila bulan `YYYY-MM` berada di antara bulan tanggal `start` dan `end`."""
    return start[:7] <= period <= end[:7]


def public_sites(sites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ringkasan situs tanpa daftar butir dan catatan pembacaan."""
    return [{k: s.get(k) for k in SITE_FIELDS} for s in sites]


def public_coding(reliability: dict[str, Any], *, threshold: float) -> dict[str, Any]:
    """Hasil pengodean isi yang aman diterbitkan.

    Halaman kerja menampilkan sebaran yang belum diuji kesepakatannya; artikel
    terbit tidak. Sebaran hanya ikut bila alpha variabel itu sudah dihitung dan
    minimal `threshold` (ambang sementara Krippendorff).
    """
    alpha = {v["code"]: v.get("alpha") for v in reliability.get("variables", [])}
    distributions = [
        d
        for d in reliability.get("distributions", [])
        if alpha.get(d["code"]) is not None and alpha[d["code"]] >= threshold
    ]
    keep = (
        "method",
        "n_posts",
        "n_coded",
        "n_double_coded",
        "n_coders",
        "double_share",
        "target_double_share",
        "meets_target",
        "variables",
        "limitations",
    )
    return {**{k: reliability.get(k) for k in keep}, "distributions": distributions}


def build_kinerja_snapshot(
    *,
    kinerja: dict[str, Any],
    project_name: str,
    frozen_at: str,
    period_start: str,
    period_end: str,
    timezone: str,
) -> dict[str, Any]:
    """Snapshot artikel kinerja komunikasi.

    `report` tetap ada dengan sumber kosong supaya pembaca snapshot lama (halaman
    /pers, ekspor CSV dan Word) tidak perlu cabang khusus untuk tetap aman; isi
    kinerja ada di kunci `kinerja`.
    """
    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "kind": "kinerja",
        "frozen_at": frozen_at,
        "project_name": project_name,
        "period_start": period_start,
        "period_end": period_end,
        "timezone": timezone,
        "note": KINERJA_NOTE,
        "report": {"sources": [], "methods": {}, "limitations": []},
        "kinerja": kinerja,
    }
