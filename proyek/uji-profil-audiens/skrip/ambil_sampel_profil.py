"""Ambil set uji berlabel P11 (profil-id-1): ±300 akun, dua penilai, buta.

Kenapa berstrata, bukan acak murni: di Gibran hanya 13 dari 165 ribu akun yang
gendernya diestimasi. Sampel acak 300 akun hampir pasti tidak memuat satu pun
estimasi gender, jadi presisi tidak bisa diukur. Strata:

  A  semua akun yang punya estimasi gender ATAU umur      -> presisi gender/umur
  B  acak dari akun yang punya estimasi minat             -> presisi minat
  C  akun dengan "kata ganti + kata peran" tapi tanpa
     estimasi (kandidat yang ditolak sistem)              -> yang terlewat
  D  acak dari semua akun                                 -> cakupan & recall

Angka populasi dihitung ulang dengan bobot (populasi strata / sampel strata) di
`hitung_akurasi.py`. Penilai TIDAK melihat strata maupun keluaran sistem.

Keluaran (semua di-gitignore: berisi teks komentar per akun):
  lembar_penilai_1.xlsx, lembar_penilai_2.xlsx   urutan acak berbeda
  kunci_sistem.csv                               keluaran sistem + strata
  ringkasan_sampel.json                          ukuran strata (boleh di-commit)

Jalankan dari akar repo:
  python proyek/uji-profil-audiens/skrip/ambil_sampel_profil.py
"""

from __future__ import annotations

import csv
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.services import profiling as pf  # noqa: E402

OUT = Path(__file__).resolve().parents[1]
SEED = 20261124
MAX_KOMENTAR = 40

PROYEK = {
    "gibran": ROOT / "proyek/gibran-mundur-youtube/komentar_youtube_gibran_mundur_10-17nov2026.csv",
    "bbm_bali": ROOT / "proyek/bbm-bali-youtube/komentar_youtube_bbm_bali_11-20okt2026.csv",
}
# Kuota per proyek per strata (A diambil semua).
KUOTA = {
    "B": {"gibran": 60, "bbm_bali": 40},
    "C": {"gibran": 25, "bbm_bali": 15},
    "D": {"gibran": 100, "bbm_bali": 40},
}

_PRON = set("saya sy sya aku aq ak gue gua gw gwe ane".split())
_ROLE1 = {r for r in pf._ROLES if " " not in r} | {"umur", "usia", "thn", "tahun", "th"}


def kandidat_peran(text: str) -> bool:
    toks = pf.normalize(text).split()
    for i, t in enumerate(toks):
        if t in _PRON and any(w in _ROLE1 for w in toks[i + 1 : i + 5]):
            return True
    return False


def baca(path: Path) -> dict[str, list[str]]:
    by: dict[str, list[str]] = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            a, t = row.get("author_hash"), (row.get("text") or "").strip()
            if a and t:
                by[a].append(t)
    return by


def main() -> None:
    rng = random.Random(SEED)
    sampel: list[dict] = []
    ringkasan: dict = {"seed": SEED, "model_version": pf.MODEL_VERSION, "proyek": {}}

    for proyek, path in PROYEK.items():
        by = baca(path)
        prof = pf.Profiler()
        prof.add((a, t) for a, ts in by.items() for t in ts)
        profiles = prof.profiles()

        def est(a: str):
            return profiles.get(a)

        A = [a for a, p in profiles.items() if p.gender.value or p.age.value]
        B_pop = [a for a, p in profiles.items() if p.interests and a not in A]
        C_pop = [
            a for a in by
            if a not in A and a not in B_pop and any(kandidat_peran(t) for t in by[a])
        ]
        taken = set(A)
        B = rng.sample(sorted(B_pop), min(KUOTA["B"][proyek], len(B_pop)))
        taken |= set(B)
        C = rng.sample(sorted(C_pop), min(KUOTA["C"][proyek], len(C_pop)))
        taken |= set(C)
        D_pop = sorted(by)  # semua akun; yang sudah terambil di strata lain dilewati
        D = [a for a in rng.sample(D_pop, len(D_pop)) if a not in taken][: KUOTA["D"][proyek]]

        ringkasan["proyek"][proyek] = {
            "akun": len(by),
            "komentar": sum(len(v) for v in by.values()),
            "populasi": {"A": len(A), "B": len(B_pop), "C": len(C_pop), "D": len(by)},
            "sampel": {"A": len(A), "B": len(B), "C": len(C), "D": len(D)},
        }
        for strata, accts in (("A", A), ("B", B), ("C", C), ("D", D)):
            for a in accts:
                p = est(a)
                sampel.append({
                    "proyek": proyek,
                    "strata": strata,
                    "author_hash": a,
                    "komentar": by[a],
                    "sys_gender": (p.gender.value if p else None) or "",
                    "sys_umur": (p.age.value if p else None) or "",
                    "sys_minat": ";".join(e.value for e in p.interests) if p else "",
                    "sys_penanda_minat": ";".join(
                        f"{e.value}:{'|'.join(e.evidence)}" for e in p.interests
                    ) if p else "",
                })

    rng.shuffle(sampel)
    for i, s in enumerate(sampel, 1):
        s["id"] = f"U{i:03d}"

    with (OUT / "kunci_sistem.csv").open("w", encoding="utf-8", newline="") as f:
        cols = ["id", "proyek", "strata", "author_hash", "n_komentar",
                "sys_gender", "sys_umur", "sys_minat", "sys_penanda_minat"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for s in sampel:
            w.writerow({**s, "n_komentar": len(s["komentar"])})

    ringkasan["total_sampel"] = len(sampel)
    (OUT / "ringkasan_sampel.json").write_text(json.dumps(ringkasan, indent=2, ensure_ascii=False))

    sys.path.insert(0, str(Path(__file__).parent))
    from lembar import tulis_lembar
    for n in (1, 2):
        urut = sampel[:]
        random.Random(SEED + n).shuffle(urut)
        tulis_lembar(OUT / f"lembar_penilai_{n}.xlsx", urut, n, MAX_KOMENTAR)
    print(json.dumps(ringkasan, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
