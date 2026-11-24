"""Hitung kesepakatan penilai dan akurasi profil-id-1 dari dua lembar yang sudah diisi.

  python proyek/uji-profil-audiens/skrip/hitung_akurasi.py [lembar1] [lembar2]

Langkah:
1. Kesepakatan antarpenilai (persen setuju + kappa Cohen) per atribut.
2. Label acuan = jawaban yang SAMA dari kedua penilai. Yang berbeda ditulis ke
   `adjudikasi.csv`; isi kolom `final` di sana (bersama-sama), jalankan lagi, dan
   jawaban `final` dipakai sebagai acuan.
3. Presisi sistem: dari akun yang diberi estimasi oleh sistem, berapa yang sesuai
   acuan. "Ketat": acuan 'tidak bisa ditentukan' dihitung salah. "Longgar": akun
   itu dikeluarkan dari penyebut.
4. Cakupan & recall: dari strata D (acak dari semua akun) — berapa persen akun
   yang menurut manusia bisa ditentukan, dan berapa dari itu yang ditangkap sistem.
5. Minat dihitung dua kali: mentah, dan dengan kata topik proyek dikecualikan
   (KECUALI di bawah), sama seperti analis memakai kolom "Kecualikan kata topik".

Keluaran: `hasil_akurasi.json` + `hasil_akurasi.md` (boleh di-commit: angka agregat saja).
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).parent))
from lembar import MINAT, TIDAK  # noqa: E402

OUT = Path(__file__).resolve().parents[1]
KECUALI = {"gibran": {"martabak"}, "bbm_bali": {"motor", "mobil"}}


def baca_lembar(path: Path) -> dict[str, dict]:
    ws = load_workbook(path, read_only=True)["Penilaian"]
    rows = ws.iter_rows(values_only=True)
    head = [str(h) for h in next(rows)]
    out = {}
    for r in rows:
        d = dict(zip(head, r))
        if not d.get("id"):
            continue
        g = (str(d.get("gender") or "").strip()) or TIDAK
        u = (str(d.get("umur") or "").strip()) or TIDAK
        m = {k for k in MINAT if str(d.get(f"minat: {k}") or "").strip() in {"1", "1.0", "x", "X"}}
        out[str(d["id"])] = {"gender": g, "umur": u, "minat": m}
    return out


def kappa(a: list, b: list) -> float | None:
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def pct(x: int, n: int) -> float | None:
    return round(100 * x / n, 1) if n else None


def main() -> None:
    p1 = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "lembar_penilai_1.xlsx"
    p2 = Path(sys.argv[2]) if len(sys.argv) > 2 else OUT / "lembar_penilai_2.xlsx"
    r1, r2 = baca_lembar(p1), baca_lembar(p2)
    with (OUT / "kunci_sistem.csv").open(encoding="utf-8") as f:
        kunci = {r["id"]: r for r in csv.DictReader(f)}
    ids = sorted(kunci)
    missing = [i for i in ids if i not in r1 or i not in r2]
    if missing:
        sys.exit(f"{len(missing)} id tidak ada di salah satu lembar, mis. {missing[:5]}")

    hasil: dict = {"n_akun": len(ids), "kesepakatan": {}}
    for attr in ("gender", "umur"):
        a = [r1[i][attr] for i in ids]
        b = [r2[i][attr] for i in ids]
        hasil["kesepakatan"][attr] = {
            "setuju_pct": pct(sum(x == y for x, y in zip(a, b)), len(ids)),
            "kappa": kappa(a, b),
            "ditentukan_penilai1": sum(x != TIDAK for x in a),
            "ditentukan_penilai2": sum(x != TIDAK for x in b),
        }
    for m in MINAT:
        a = [m in r1[i]["minat"] for i in ids]
        b = [m in r2[i]["minat"] for i in ids]
        hasil["kesepakatan"][f"minat:{m}"] = {
            "setuju_pct": pct(sum(x == y for x, y in zip(a, b)), len(ids)),
            "kappa": kappa(a, b), "positif_p1": sum(a), "positif_p2": sum(b),
        }

    # --- acuan + adjudikasi
    final: dict[tuple[str, str], str] = {}
    adj_path = OUT / "adjudikasi.csv"
    if adj_path.exists():
        with adj_path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if (r.get("final") or "").strip():
                    final[(r["id"], r["atribut"])] = r["final"].strip()
    acuan: dict[str, dict] = {}
    beda: list[dict] = []
    for i in ids:
        ac: dict = {}
        for attr in ("gender", "umur"):
            x, y = r1[i][attr], r2[i][attr]
            if x == y:
                ac[attr] = x
            elif (i, attr) in final:
                ac[attr] = final[(i, attr)]
            else:
                ac[attr] = None
                beda.append({"id": i, "atribut": attr, "penilai1": x, "penilai2": y, "final": ""})
        mins = set()
        for m in MINAT:
            x, y = m in r1[i]["minat"], m in r2[i]["minat"]
            key = (i, f"minat:{m}")
            if x == y:
                if x:
                    mins.add(m)
            elif key in final:
                if final[key] in {"1", "ya"}:
                    mins.add(m)
            else:
                beda.append({"id": i, "atribut": f"minat:{m}", "penilai1": int(x), "penilai2": int(y), "final": ""})
                mins = None if mins is None else mins | {f"?{m}"}
        ac["minat"] = mins
        acuan[i] = ac
    with adj_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "atribut", "penilai1", "penilai2", "final"])
        w.writeheader()
        for (i, attr), v in final.items():
            w.writerow({"id": i, "atribut": attr, "penilai1": "", "penilai2": "", "final": v})
        w.writerows(beda)
    hasil["belum_diadjudikasi"] = len(beda)

    # --- presisi gender/umur (semua akun yang diberi estimasi; strata A = sensus)
    sys_key = {"gender": "sys_gender", "umur": "sys_umur"}
    for attr in ("gender", "umur"):
        diberi = [i for i in ids if kunci[i][sys_key[attr]] and acuan[i][attr] is not None]
        benar = sum(acuan[i][attr] == kunci[i][sys_key[attr]] for i in diberi)
        tentu = [i for i in diberi if acuan[i][attr] != TIDAK]
        benar_l = sum(acuan[i][attr] == kunci[i][sys_key[attr]] for i in tentu)
        # cakupan & recall dari strata D
        d = [i for i in ids if kunci[i]["strata"] == "D" and acuan[i][attr] is not None]
        d_tentu = [i for i in d if acuan[i][attr] != TIDAK]
        d_tangkap = sum(kunci[i][sys_key[attr]] == acuan[i][attr] for i in d_tentu)
        hasil[f"sistem_{attr}"] = {
            "n_diberi_estimasi": len(diberi),
            "presisi_ketat_pct": pct(benar, len(diberi)),
            "presisi_longgar_pct": pct(benar_l, len(tentu)),
            "n_strata_D": len(d),
            "manusia_bisa_tentukan_D_pct": pct(len(d_tentu), len(d)),
            "recall_D_pct": pct(d_tangkap, len(d_tentu)),
            "n_manusia_tentukan_D": len(d_tentu),
        }

    # --- minat
    def sys_minat(i: str, kecuali: bool) -> set[str]:
        ev = kunci[i]["sys_penanda_minat"]
        out = set()
        for part in filter(None, ev.split(";")):
            cat, words = part.split(":", 1)
            ws_ = set(words.split("|"))
            if kecuali:
                ws_ -= KECUALI.get(kunci[i]["proyek"], set())
            if ws_:
                out.add(cat)
        return out

    for label, kec in (("mentah", False), ("kata_topik_dikecualikan", True)):
        tp = fp = fn_d = tp_d = 0
        for i in ids:
            ref = acuan[i]["minat"]
            if ref is None or any(x.startswith("?") for x in ref):
                continue
            s = sys_minat(i, kec)
            tp += len(s & ref)
            fp += len(s - ref)
            if kunci[i]["strata"] == "D":
                tp_d += len(s & ref)
                fn_d += len(ref - s)
        hasil[f"sistem_minat_{label}"] = {
            "estimasi_benar": tp, "estimasi_salah": fp,
            "presisi_pct": pct(tp, tp + fp),
            "recall_D_pct": pct(tp_d, tp_d + fn_d), "minat_manusia_di_D": tp_d + fn_d,
        }

    (OUT / "hasil_akurasi.json").write_text(json.dumps(hasil, indent=2, ensure_ascii=False))
    md = ["# Hasil set uji P11 (profil-id-1)", "", f"Akun: {len(ids)}. Belum diadjudikasi: {len(beda)} butir.", ""]
    md += ["## Kesepakatan penilai", "", "| Atribut | Setuju | Kappa |", "|---|---|---|"]
    for k, v in hasil["kesepakatan"].items():
        md.append(f"| {k} | {v['setuju_pct']}% | {v['kappa']} |")
    md += ["", "## Sistem", ""]
    for k in ("sistem_gender", "sistem_umur", "sistem_minat_mentah", "sistem_minat_kata_topik_dikecualikan"):
        md.append(f"- **{k}**: " + ", ".join(f"{a}={b}" for a, b in hasil[k].items()))
    md += ["", "Catatan: n kecil (gender/umur ±20 akun) → selang kepercayaan lebar; sebutkan n setiap kali angka dikutip."]
    (OUT / "hasil_akurasi.md").write_text("\n".join(md) + "\n")
    print(json.dumps(hasil, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
