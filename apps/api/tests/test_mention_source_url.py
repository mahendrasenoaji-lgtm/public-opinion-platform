"""Tes murni untuk pemulihan URL sumber satu mention (`_recover_source_url`).

Dipisah dari `test_mentions_router.py` karena tidak butuh Postgres sama
sekali: berkas itu seluruhnya ter-skip tanpa `TEST_DATABASE_URL_APP`, dan
batas antara "memulihkan" dan "menebak" terlalu penting untuk ikut hilang
saat database tidak tersedia.

Latar: sebagian besar feed RSS Indonesia menulis `<guid>` yang persis sama
dengan `<link>` -- URL artikelnya. `connectors/rss.py` menyimpan guid itu ke
`external_id` sejak awal, sementara kolom `url` baru ada 2026-09-11, sehingga
item-item lama tampil "tidak ada URL sumber" padahal URL-nya ada di kolom
sebelah. Diperiksa 2026-09-12 terhadap keempat feed yang dipakai proyek
riset pengguna (Antara, CNBC Indonesia, Republika, Sindonews): keempatnya
guid == link == URL artikel.
"""

from __future__ import annotations

import pytest

from app.routers.signals import _recover_source_url


def test_kolom_url_menang_atas_guid() -> None:
    """Kolom `url` yang terisi tidak boleh pernah ditimpa hasil pemulihan."""
    assert _recover_source_url(
        "https://contoh.id/yang-tersimpan", "https://contoh.id/guid-berbeda"
    ) == ("https://contoh.id/yang-tersimpan", "kolom_url")


def test_guid_url_dipulihkan_saat_kolom_url_kosong() -> None:
    """Kasus nyata: item RSS yang diingest sebelum kolom `url` ada."""
    permalink = "https://www.antaranews.com/berita/123/karhutla-habitat-gajah-sumsel"
    assert _recover_source_url(None, permalink) == (permalink, "guid_feed")


@pytest.mark.parametrize(
    "external_id",
    [
        "1749169",  # id numerik
        "tag:contoh.id,2026:artikel-1",  # tag URI, bukan URL yang bisa dibuka
        "@akun_media",  # handle dari konektor non-RSS
        "ftp://contoh.id/berkas",  # skema bukan web
        "www.contoh.id/tanpa-skema",  # tanpa skema: TIDAK dirangkai sendiri
        "",
    ],
)
def test_guid_bukan_url_absolut_tidak_pernah_ditebak(external_id: str) -> None:
    """Batas yang membedakan PEMULIHAN dari TEBAKAN.

    Tidak ada yang dirangkai, ditempel ke domain, atau dicarikan padanan.
    Kalau guid-nya bukan URL absolut, jawabannya "tidak tahu" -- dan UI
    menampilkan "tidak ada URL sumber", bukan tautan yang mungkin salah.
    """
    assert _recover_source_url(None, external_id) == (None, None)


def test_url_kosong_diperlakukan_sama_seperti_none() -> None:
    """String kosong bukan URL. Tanpa ini, `url=""` akan lolos sebagai
    "tersimpan" dan menghasilkan tautan ke halaman kosong."""
    permalink = "https://contoh.id/artikel"
    assert _recover_source_url("", permalink) == (permalink, "guid_feed")
    assert _recover_source_url("", "bukan-url") == (None, None)
