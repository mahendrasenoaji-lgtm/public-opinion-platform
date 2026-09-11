"""Perhatian publik lewat Wikimedia Pageviews API.

## Apa yang diukur ini, dan apa yang TIDAK

Yang diukur: berapa kali sebuah artikel Wikipedia dibuka manusia per hari.
Itu ukuran PERHATIAN — berapa banyak orang mencari tahu tentang suatu topik.

Yang TIDAK diukur: sikap. Naiknya tampilan halaman "Badan Gizi Nasional" tidak
berarti dukungan terhadap programnya naik; kenaikan justru paling sering
terjadi saat ada kontroversi. Membaca deret ini sebagai persetujuan adalah
kesalahan yang persis dilarang CLAUDE.md §3 — dan karena itu `source`-nya
`DIGITAL` ("perilaku terukur, bukan pernyataan"), bukan `SURVEY`.

## Kenapa konektor ini ada

Sampai sekarang `/forecast/baseline` selalu membalas `insufficient_data`:
seed hanya punya satu snapshot per metrik, dan gelombang survei kedua butuh
responden manusia sungguhan (docs/progress.md, "Langkah berikutnya" poin 5 —
di luar wewenang agen, dan memfabrikasinya melanggar R1).

Model state-space di `services/timeseries.py` tidak menuntut data survei. Ia
menuntut DERET. Pageviews memberi deret harian nyata, gratis, tanpa kunci,
mundur sampai 2015 — jadi modelnya bisa di-fit dan diperiksa perilakunya
hari ini, di atas angka yang benar-benar terjadi. Itu bukan pengganti survei
gelombang kedua; ia menutup pertanyaan yang berbeda ("apakah model ini
bekerja pada deret nyata") sambil yang satunya menunggu.

## Batas legal

Wikimedia REST API adalah API resmi dan terbuka, tanpa kunci. Kebijakannya
meminta `User-Agent` yang mengidentifikasi pemanggil dan bisa dihubungi —
itu dipenuhi di `USER_AGENT` di bawah, dan sengaja BUKAN string peramban.
Tidak ada rate limit yang dilewati: satu permintaan mengambil seluruh rentang
sekaligus, bukan satu per hari.

Parsing dipisah dari pengambilan (`parse_pageviews` adalah fungsi murni)
supaya bisa dites tanpa jaringan.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import ClassVar
from urllib.parse import quote

import httpx

from app.connectors.base import ConnectorError, require
from app.connectors.metrics import MetricConnector, RawObservation, register_metric
from app.models.measurement import SignalSource

REQUEST_TIMEOUT = 20.0

#: Wikimedia meminta User-Agent yang menyebut siapa pemanggilnya. Sengaja
#: BUKAN string peramban — menyamar sebagai Chrome dilarang di paket ini
#: (lihat connectors/base.py).
USER_AGENT = "AIPublicOpinionPlatform/0.1 (+public opinion research; contact via platform admin)"

_BASE = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"

#: `user` membuang lalu lintas bot dan perayap. Tanpa ini, deretnya didominasi
#: mesin dan tidak ada hubungannya dengan perhatian manusia.
_AGENT = "user"
_ACCESS = "all-access"

#: Proyek yang diizinkan. Bukan pembatasan teknis — pembatasan metodologis:
#: platform ini mengukur opini publik Indonesia, dan mencampur id.wikipedia
#: dengan en.wikipedia dalam satu deret menggabungkan dua populasi pembaca
#: yang berbeda tanpa cara memisahkannya kembali.
ALLOWED_PROJECTS = ("id.wikipedia", "en.wikipedia", "jv.wikipedia", "su.wikipedia")


def _parse_timestamp(raw: str) -> date | None:
    """Timestamp API berbentuk YYYYMMDDHH (jam selalu '00' untuk granularitas harian)."""
    if not raw or len(raw) < 8:
        return None
    try:
        return datetime.strptime(raw[:8], "%Y%m%d").date()
    except ValueError:
        return None


def parse_pageviews(payload: bytes, *, metric: str, method: str) -> list[RawObservation]:
    """Ubah respons Pageviews API menjadi RawObservation. Fungsi murni — inti yang dites.

    Hari dengan timestamp cacat dibuang, bukan ditebak: menempatkan tampilan
    halaman di tanggal yang salah menggeser seluruh hubungannya dengan
    kejadian yang mau dijelaskan.

    Setiap pengamatan berdurasi satu hari, jadi `period_start == period_end`.
    """
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        raise ConnectorError(f"respons Wikimedia bukan JSON yang valid: {e}") from e

    if not isinstance(data, dict):
        raise ConnectorError("respons Wikimedia bukan objek JSON")

    items = data.get("items")
    if not isinstance(items, list):
        raise ConnectorError("respons Wikimedia tidak memuat daftar 'items'")

    observations: list[RawObservation] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        day = _parse_timestamp(str(item.get("timestamp", "")))
        views = item.get("views")
        if day is None or not isinstance(views, int | float) or isinstance(views, bool):
            continue
        observations.append(
            RawObservation(
                metric=metric,
                period_start=day,
                period_end=day,
                value=float(views),
                source=SignalSource.DIGITAL,
                method=method,
                breakdown={
                    "article": str(item.get("article", "")),
                    "project": str(item.get("project", "")),
                    "agent": str(item.get("agent", "")),
                },
            )
        )

    observations.sort(key=lambda o: o.period_end)
    return observations


def metric_name(article: str) -> str:
    """Nama deret yang stabil antar pengambilan.

    Diawali `pageviews_` supaya tidak pernah bertabrakan dengan metrik survei
    (`poi`, `trust`, `approval`) di tabel yang sama — kalau bertabrakan,
    `/forecast/baseline?metric=poi` akan mencampur tampilan halaman ke dalam
    riwayat Public Opinion Index, dan itu melanggar R1 di tempat paling mahal.
    """
    slug = article.strip().replace(" ", "_").lower()
    return f"pageviews_{slug}"


@register_metric
class WikipediaPageviewsConnector(MetricConnector):
    """Perhatian publik harian dari Wikimedia Pageviews API."""

    key: ClassVar[str] = "wikipedia_pageviews"
    label: ClassVar[str] = "Wikipedia — tampilan halaman harian"
    source: ClassVar[SignalSource] = SignalSource.DIGITAL
    requires_credential: ClassVar[str | None] = None
    config_fields: ClassVar[tuple[str, ...]] = ("project", "article")
    notes: ClassVar[str] = (
        "Mengukur PERHATIAN, bukan sikap. Naiknya tampilan halaman tidak "
        "berarti dukungan naik — lonjakan paling sering terjadi saat ada "
        "kontroversi. Jangan dibandingkan langsung dengan angka survei: ini "
        "perilaku terukur dari pembaca Wikipedia, bukan sampel probabilistik "
        "dari populasi."
    )

    async def fetch_series(
        self,
        config: dict[str, object],
        *,
        start: date,
        end: date,
    ) -> list[RawObservation]:
        cfg = require(config, self.config_fields)
        project, article = cfg["project"], cfg["article"]

        if project not in ALLOWED_PROJECTS:
            raise ConnectorError(
                f"proyek Wikipedia '{project}' tidak diizinkan. Yang tersedia: "
                f"{', '.join(ALLOWED_PROJECTS)}"
            )
        if end < start:
            raise ConnectorError(f"rentang terbalik: {start} sampai {end}")

        # `safe=""` penting: judul artikel Indonesia sering memuat "/" dan
        # spasi, dan tanpa ini keduanya lolos mentah ke path URL lalu
        # memecah rutenya jadi segmen yang salah.
        url = (
            f"{_BASE}/{project}/{_ACCESS}/{_AGENT}/{quote(article.replace(' ', '_'), safe='')}"
            f"/daily/{start:%Y%m%d}/{end:%Y%m%d}"
        )

        try:
            async with httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            ) as client:
                response = await client.get(url)
                # 404 di API ini berarti "artikel tidak punya data pada rentang
                # ini", bukan kesalahan server. Dibedakan supaya pengguna
                # dapat pesan yang bisa ditindaklanjuti (salah ejaan judul)
                # alih-alih kegagalan generik.
                if response.status_code == 404:
                    raise ConnectorError(
                        f"Wikipedia tidak punya data tampilan halaman untuk "
                        f"'{article}' di {project} pada rentang itu. Periksa "
                        f"ejaan judul artikelnya — harus persis seperti di URL "
                        f"Wikipedia, termasuk huruf besar-kecilnya."
                    )
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ConnectorError(
                f"Wikimedia menolak permintaan ({e.response.status_code})"
            ) from e
        except httpx.HTTPError as e:
            raise ConnectorError(f"deret tampilan halaman tidak bisa diambil: {e}") from e

        return parse_pageviews(
            response.content,
            metric=metric_name(article),
            method=f"Wikimedia Pageviews API · {project} · agen {_AGENT} · harian",
        )
