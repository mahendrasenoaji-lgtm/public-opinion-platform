"""Tes app/services/reports.py — murni, tanpa database (Phase 4, item pertama)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.services.reports import ReportMetric, ReportSection, build_summary_pdf


def _pdf(**overrides) -> bytes:
    defaults = dict(
        project_name="Proyek Uji",
        is_demo=False,
        generated_at=datetime(2026, 9, 11, tzinfo=UTC),
        sections=[
            ReportSection(
                title="Public Segments",
                metrics=[
                    ReportMetric(
                        label="Segmen A",
                        source="SURVEY",
                        method="latent_class",
                        value="24% populasi",
                    )
                ],
            )
        ],
    )
    defaults.update(overrides)
    return build_summary_pdf(**defaults)


def test_menghasilkan_pdf_valid() -> None:
    pdf = _pdf()
    assert pdf[:5] == b"%PDF-", "output harus header PDF yang valid"
    assert len(pdf) > 500


def test_bagian_tanpa_metrik_tidak_membuat_pdf_gagal() -> None:
    """Proyek kosong (baru dibuat, belum ada segmen) tetap harus bisa dilaporkan."""
    pdf = build_summary_pdf(
        project_name="Proyek Baru",
        is_demo=False,
        generated_at=datetime(2026, 9, 11, tzinfo=UTC),
        sections=[ReportSection(title="Public Segments", metrics=[])],
    )
    assert pdf[:5] == b"%PDF-"


def test_insufficient_data_tidak_mencetak_nilai_palsu() -> None:
    """Metrik yang ditahan (insufficient_data) tidak boleh membawa `value`
    yang seolah-olah angka sungguhan — konsisten dengan CLAUDE.md §3.

    Kompresi PDF sengaja dimatikan di `build_summary_pdf` (`pageCompression=0`)
    supaya tes ini bisa mencari teks lewat byte mentah tanpa parser PDF
    terpisah.
    """
    pdf = build_summary_pdf(
        project_name="Proyek",
        is_demo=False,
        generated_at=datetime(2026, 9, 11, tzinfo=UTC),
        sections=[
            ReportSection(
                title="Polarization Index",
                metrics=[
                    ReportMetric(
                        label="Skor polarisasi",
                        source="SURVEY",
                        method="bimodalitas",
                        value="90 -- SHOULDNOTAPPEAR",  # diabaikan kalau insufficient_data
                        insufficient_data=True,
                    )
                ],
            )
        ],
    )
    assert b"cukup" in pdf, "'data tidak cukup' harus tercetak untuk metrik yang ditahan"
    assert b"SHOULDNOTAPPEAR" not in pdf, (
        "value asli tidak boleh tercetak sama sekali kalau insufficient_data=True"
    )


def test_watermark_demo_hanya_muncul_kalau_is_demo() -> None:
    pdf_demo = _pdf(is_demo=True)
    pdf_asli = _pdf(is_demo=False)
    # Watermark menambah konten -> ukuran berbeda. Bukti definitif ada di
    # verifikasi visual (docs/deployment-status.md), ini cuma jaring pengait
    # regresi murah (perubahan kode yang menghapus cabang if is_demo akan
    # membuat kedua ukuran identik).
    assert len(pdf_demo) != len(pdf_asli)
