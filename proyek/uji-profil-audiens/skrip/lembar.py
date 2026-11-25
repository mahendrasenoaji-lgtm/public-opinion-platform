"""Menulis lembar penilaian (xlsx) untuk satu penilai. Tanpa keluaran sistem."""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "apps" / "api"))
from app.services.profiling import AGE_BANDS, INTERESTS  # noqa: E402

TIDAK = "tidak bisa ditentukan"
GENDER_OPS = ["L", "P", TIDAK]
UMUR_OPS = [*AGE_BANDS, TIDAK]
YAKIN_OPS = ["yakin", "ragu"]
MINAT = list(INTERESTS)

PETUNJUK = [
    "LEMBAR PENILAIAN — set uji Profil Audiens (P11, profil-id-1)",
    "",
    "Kerjakan SENDIRI. Jangan membandingkan jawaban dengan penilai lain sampai keduanya selesai.",
    "Setiap baris = satu akun YouTube (nama akun disamarkan). Kolom B berisi komentar akun itu.",
    "Nilailah HANYA dari isi komentar. Jangan mencari akun di YouTube.",
    "",
    "GENDER (kolom C): isi L atau P hanya bila komentar memberi bukti tentang DIRI PENULIS,",
    "  mis. 'saya ibu dua anak', 'istri saya' (→ L), 'suami saya' (→ P), 'sebagai bapak'.",
    "  Gaya bahasa saja ('bro', 'sis', kasar/halus) BUKAN bukti. Ragu atau tanpa bukti → 'tidak bisa ditentukan'.",
    "  Kolom D: 'yakin' atau 'ragu' (khusus bila Anda tetap memilih L/P).",
    "UMUR (kolom E): kelompok umur hanya bila ada bukti (menyebut umur, 'anak SMA', 'pensiunan', 'mahasiswa',",
    "  'cucu saya'). Tanpa bukti → 'tidak bisa ditentukan'. Kolom F: 'yakin' atau 'ragu'.",
    "MINAT (kolom G dst.): isi 1 bila komentar menunjukkan penulis SENDIRI tertarik/terlibat pada bidang itu",
    "  (mis. sering bicara motornya sendiri, hobi main gim). Topik video yang sedang dikomentari BUKAN minat:",
    "  mengeluh harga bensin di video BBM ≠ minat otomotif; menyebut 'martabak' sebagai olok-olok ≠ minat kuliner.",
    "  Kosongkan bila tidak ada.",
    "BUKTI: salin kata/kalimat pendek yang jadi dasar penilaian. CATATAN: bebas.",
    "",
    "Pilihan umur: " + ", ".join(AGE_BANDS),
    "Kategori minat: " + ", ".join(MINAT),
    "Hampir semua akun memang akan 'tidak bisa ditentukan' — itu jawaban yang sah dan justru penting.",
]


def tulis_lembar(path: Path, sampel: list[dict], penilai: int, max_komentar: int) -> None:
    wb = Workbook()
    ws0 = wb.active
    ws0.title = "Petunjuk"
    for i, line in enumerate(PETUNJUK, 1):
        ws0.cell(i, 1, line)
    ws0["A1"].font = Font(bold=True, size=13)
    ws0.column_dimensions["A"].width = 120

    ws = wb.create_sheet("Penilaian")
    head = ["id", "komentar akun", "gender", "yakin gender", "umur", "yakin umur",
            *[f"minat: {m}" for m in MINAT], "bukti", "catatan"]
    ws.append(head)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DDEBF7")
        c.alignment = Alignment(wrap_text=True, vertical="top")
    for s in sampel:
        kom = s["komentar"][:max_komentar]
        teks = "\n".join(f"[{i}] {t[:600]}" for i, t in enumerate(kom, 1))
        if len(s["komentar"]) > max_komentar:
            teks += f"\n(… {len(s['komentar']) - max_komentar} komentar lain tidak ditampilkan)"
        ws.append([s["id"], teks])
    n = len(sampel) + 1
    last_minat = 6 + len(MINAT)

    def dv(ops: list[str], col: str) -> None:
        v = DataValidation(type="list", formula1='"' + ",".join(ops) + '"', allow_blank=True)
        ws.add_data_validation(v)
        v.add(f"{col}2:{col}{n}")

    from openpyxl.utils import get_column_letter as L
    dv(GENDER_OPS, "C"); dv(YAKIN_OPS, "D"); dv(UMUR_OPS, "E"); dv(YAKIN_OPS, "F")
    dv(["1"], f"G")
    for ci in range(8, last_minat + 1):
        dv(["1"], L(ci))
    widths = {"A": 7, "B": 90, "C": 12, "D": 9, "E": 14, "F": 9}
    for col, wdt in widths.items():
        ws.column_dimensions[col].width = wdt
    for ci in range(7, last_minat + 1):
        ws.column_dimensions[L(ci)].width = 10
    ws.column_dimensions[L(last_minat + 1)].width = 30
    ws.column_dimensions[L(last_minat + 2)].width = 25
    for row in ws.iter_rows(min_row=2, max_row=n):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "C2"
    ws0.cell(len(PETUNJUK) + 2, 1, f"Penilai {penilai}. Jumlah akun: {len(sampel)}.").font = Font(bold=True)
    wb.save(path)
