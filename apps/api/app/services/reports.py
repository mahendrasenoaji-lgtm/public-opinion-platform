"""Report generator — ringkasan proyek sebagai PDF (Phase 4, item pertama).

Fungsi murni: menerima data yang SUDAH diambil pemanggil (router), tidak
melakukan query database atau panggilan jaringan sendiri — konsisten dengan
aturan CLAUDE.md §4 ("services tidak boleh mengimpor routers/connectors/ai").
Bisa dites tanpa database dan tanpa server PDF eksternal (reportlab murni
Python, tidak butuh binary sistem seperti wkhtmltopdf/LaTeX).

Bukan keluaran LLM — angka statistik/agregat apa adanya dari layer lain
proyek ini (segments, risk, signals, dst), jadi TIDAK dibungkus `AIEnvelope`
(R2 cuma wajib untuk keluaran generatif). Yang tetap wajib mengikuti R1:
setiap metrik yang dicetak membawa `source` dan `method`-nya sendiri, bukan
angka telanjang tanpa provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

#: Warna sumber — HARUS sinkron dengan token R1 di `apps/web/lib/tokens.ts`.
#: Jangan tambah warna sumber baru di sini tanpa menambah enum SignalSource
#: di backend DAN token di frontend (lihat CLAUDE.md §2 R1).
_SOURCE_COLORS = {
    "SURVEY": colors.HexColor("#4DA3FF"),
    "SOCIAL": colors.HexColor("#FF7A45"),
    "MEDIA": colors.HexColor("#9B8AFB"),
    "DIGITAL": colors.HexColor("#6B7280"),
}

_MUTED = colors.HexColor("#6B7280")


@dataclass(frozen=True, slots=True)
class ReportMetric:
    """Satu metrik dalam laporan. `source`/`method` wajib — lihat R1."""

    label: str
    source: str
    method: str
    value: str | None = None
    insufficient_data: bool = False
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ReportSection:
    title: str
    metrics: list[ReportMetric] = field(default_factory=list)
    #: Catatan bebas di bawah tabel metrik — dipakai untuk keterbatasan
    #: (mis. "skor risiko ditahan karena cakupan bobot < 60%").
    limitations: list[str] = field(default_factory=list)


def build_summary_pdf(
    *,
    project_name: str,
    is_demo: bool,
    generated_at: datetime,
    sections: list[ReportSection],
) -> bytes:
    """Render laporan ringkasan proyek menjadi PDF, dikembalikan sebagai bytes.

    `is_demo` menentukan apakah watermark "DATA DEMO SINTETIS" dicetak di
    setiap halaman (R7 — dashboard yang jalan di atas seed wajib menandainya,
    aturan yang sama juga berlaku untuk laporan yang diekspor darinya).
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title=f"Laporan Ringkasan — {project_name}",
        #: Kompresi dimatikan SENGAJA: dokumen ini kecil (beberapa KB), dan
        #: konten yang bisa dicari mentah lewat byte string mempermudah tes
        #: regresi (lihat tests/test_reports.py) serta audit manual tanpa
        #: perlu parser PDF terpisah.
        pageCompression=0,
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], spaceAfter=4 * mm)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], spaceBefore=6 * mm, spaceAfter=2 * mm)
    small = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=8, textColor=_MUTED)
    note_style = ParagraphStyle("Note", parent=styles["BodyText"], fontSize=9, textColor=_MUTED)
    #: Sel tabel HARUS pakai Paragraph, bukan string mentah — Table reportlab
    #: tidak word-wrap string biasa, teks panjang akan tumpang tindih ke sel
    #: sebelahnya alih-alih turun baris (ketahuan lewat verifikasi visual PDF
    #: sungguhan, bukan cuma "tidak error").
    cell_style = ParagraphStyle("Cell", parent=styles["BodyText"], fontSize=8.5, leading=10)
    cell_head = ParagraphStyle("CellHead", parent=cell_style, fontName="Helvetica-Bold")

    story: list[Flowable] = [Paragraph(project_name, h1)]
    if is_demo:
        story.append(
            Paragraph(
                "⚠ DATA DEMO SINTETIS — bukan hasil pengumpulan data nyata.", note_style
            )
        )
    story.append(
        Paragraph(
            f"Dibuat otomatis {generated_at.strftime('%d %B %Y %H:%M')} UTC — "
            "cuplikan titik waktu ini, bukan langganan yang diperbarui sendiri.",
            small,
        )
    )
    story.append(Spacer(1, 4 * mm))

    for section in sections:
        story.append(Paragraph(section.title, h2))

        if not section.metrics:
            story.append(Paragraph("Tidak ada data untuk bagian ini.", note_style))
            continue

        header = [Paragraph(h, cell_head) for h in ("Metrik", "Nilai", "Sumber", "Metode")]
        rows: list[list[Paragraph]] = [header]
        for m in section.metrics:
            value_text = "data tidak cukup" if m.insufficient_data else (m.value or "—")
            value_style = (
                ParagraphStyle("ValueMuted", parent=cell_style, textColor=_MUTED)
                if m.insufficient_data
                else cell_style
            )
            source_style = ParagraphStyle(
                "Source",
                parent=cell_style,
                textColor=_SOURCE_COLORS.get(m.source, _MUTED),
            )
            rows.append(
                [
                    Paragraph(m.label, cell_style),
                    Paragraph(value_text, value_style),
                    Paragraph(m.source, source_style),
                    Paragraph(m.method, cell_style),
                ]
            )

        table = Table(rows, colWidths=[50 * mm, 45 * mm, 22 * mm, 53 * mm], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(table)

        for lim in section.limitations:
            story.append(Spacer(1, 1.5 * mm))
            story.append(Paragraph(f"⚠ {lim}", note_style))

        story.append(Spacer(1, 3 * mm))

    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "Warna kolom Sumber: Survei probabilistik (biru) — bisa digeneralisasi ke "
            "populasi. Percakapan sosial (oranye) — self-selected, tidak representatif. "
            "Liputan media (ungu) — agenda redaksi, bukan opini pembaca.",
            small,
        )
    )
    story.append(
        Paragraph(
            "Laporan ini agregasi statistik, bukan keluaran AI generatif — tidak ada "
            "klaim kausal atau interpretatif di luar apa yang tercantum di tabel di atas.",
            small,
        )
    )

    doc.build(story)
    return buf.getvalue()
