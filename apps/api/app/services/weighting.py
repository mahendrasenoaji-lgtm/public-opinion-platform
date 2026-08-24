"""Bobot pasca-stratifikasi via raking (iterative proportional fitting).

Menghitung bobot per responden supaya komposisi sampel tertimbang cocok dengan
target populasi (biasanya dari BPS) pada beberapa variabel sekaligus — usia,
gender, wilayah, dst. Berbeda dari pembobotan sel tunggal di
`stratum_balance` (sampling.py), yang cuma menangani satu variabel: raking
menyesuaikan bobot bergantian per variabel sampai marginal tertimbang sampel
mendekati target pada semua variabel sekaligus, tanpa butuh sel gabungan
(mis. "perempuan, 18-24, Jawa Barat") yang sering kosong pada sampel kecil.

Bobot mentah bisa meledak kalau satu sel sangat kecil di sampel — makanya
fungsi ini juga memangkas bobot ekstrem dan melaporkan berapa banyak yang
dipangkas. Kalau raking tidak konvergen, hasilnya tetap dikembalikan sebagai
estimasi terbaik, bukan dibuang — tapi peringatannya wajib ditampilkan di UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

#: Variabel yang boleh dipakai untuk raking. Harus cocok dengan kolom
#: kategorikal di model Respondent (survey.py).
RAKEABLE_VARIABLES = {
    "age_band",
    "gender",
    "education",
    "occupation",
    "province_code",
    "urbanicity",
}


@dataclass(frozen=True, slots=True)
class RakingResult:
    weights: dict[str, float]
    iterations: int
    converged: bool
    trimmed_count: int
    max_weight: float
    min_weight: float
    warnings: list[str] = field(default_factory=list)


def rake_weights(
    respondents: dict[str, dict[str, str | None]],
    targets: dict[str, dict[str, float]],
    *,
    max_iterations: int = 25,
    tolerance: float = 0.001,
    trim_ratio: float = 3.0,
) -> RakingResult:
    """Hitung bobot pasca-stratifikasi dengan raking.

    `respondents`: {id: {variabel: kategori, ...}, ...} — satu entri per
    responden, nilai kategori boleh None (data demografis hilang).
    `targets`: {variabel: {kategori: proporsi_populasi, ...}, ...} — proporsi
    tiap variabel harus berjumlah mendekati 1.0, diambil dari sensus/BPS.

    Bobot awal 1.0 untuk semua responden, lalu disesuaikan bergantian per
    variabel: kategori yang under-represented di sampel tertimbang mendapat
    bobot naik, yang over-represented turun. Diulang sampai konvergen atau
    `max_iterations` habis.
    """
    if not respondents:
        raise ValueError("respondents tidak boleh kosong")
    if not targets:
        raise ValueError("targets tidak boleh kosong")

    unknown_vars = set(targets) - RAKEABLE_VARIABLES
    if unknown_vars:
        raise ValueError(
            f"variabel tidak dikenal untuk raking: {', '.join(sorted(unknown_vars))}. "
            f"Pilih dari: {', '.join(sorted(RAKEABLE_VARIABLES))}"
        )

    for var, dist in targets.items():
        total = sum(dist.values())
        if not 0.98 <= total <= 1.02:
            raise ValueError(
                f"target proporsi untuk '{var}' berjumlah {total:.3f}, harus mendekati 1.0"
            )

    ids = list(respondents.keys())
    weight = {i: 1.0 for i in ids}
    warnings: list[str] = []

    # Validasi cakupan: kategori tanpa target diabaikan dari raking pada
    # variabel itu; kategori dengan target tapi tanpa responden tidak bisa
    # dihitung sama sekali. Keduanya dilaporkan, tidak disembunyikan.
    for var, dist in targets.items():
        seen = {respondents[i].get(var) for i in ids}
        missing_targets = {c for c in seen if c is not None and c not in dist}
        if missing_targets:
            warnings.append(
                f"'{var}': kategori pada data tanpa target populasi, diabaikan dari "
                f"raking variabel ini: {', '.join(sorted(missing_targets))}"
            )
        empty_categories = [c for c in dist if not any(respondents[i].get(var) == c for i in ids)]
        if empty_categories:
            warnings.append(
                f"'{var}': target populasi ada untuk kategori tanpa responden sama sekali: "
                f"{', '.join(sorted(empty_categories))} — bobot untuk sel ini tidak dapat dihitung"
            )

    converged = False
    iterations_used = 0

    for iteration in range(1, max_iterations + 1):
        max_change = 0.0
        degenerate = False

        for var, dist in targets.items():
            total_weight = sum(weight.values())
            if total_weight <= 0:
                degenerate = True
                break
            for category, target_share in dist.items():
                members = [i for i in ids if respondents[i].get(var) == category]
                if not members:
                    continue
                current_weight_sum = sum(weight[i] for i in members)
                if current_weight_sum <= 0:
                    continue
                current_share = current_weight_sum / total_weight
                factor = target_share / current_share
                max_change = max(max_change, abs(factor - 1.0))
                for i in members:
                    weight[i] *= factor

        if degenerate:
            warnings.append("bobot merosot ke nol selama iterasi; raking dihentikan lebih awal")
            break

        iterations_used = iteration
        if max_change < tolerance:
            converged = True
            break

    if not converged and not warnings_has_degenerate(warnings):
        warnings.append(
            f"raking tidak konvergen dalam {max_iterations} iterasi; bobot dipakai "
            "sebagai estimasi terbaik, bukan hasil final — pertimbangkan menambah "
            "max_iterations atau menyederhanakan jumlah variabel"
        )

    # Normalisasi: rata-rata bobot = 1.0, supaya sampel efektif (Kish) tidak
    # bergeser secara artifisial hanya karena raking.
    _renormalise(weight, ids)

    # Pangkas bobot ekstrem — praktik standar supaya satu-dua responden dari
    # sel kecil tidak mendominasi estimasi populasi.
    trimmed_count = 0
    med = median(weight.values())
    if med > 0:
        cap = med * trim_ratio
        for i in ids:
            if weight[i] > cap:
                weight[i] = cap
                trimmed_count += 1
        if trimmed_count:
            warnings.append(
                f"{trimmed_count} bobot dipangkas ke {trim_ratio}× median untuk mencegah "
                "satu responden mendominasi estimasi"
            )
            _renormalise(weight, ids)

    return RakingResult(
        weights=weight,
        iterations=iterations_used,
        converged=converged,
        trimmed_count=trimmed_count,
        max_weight=round(max(weight.values()), 4),
        min_weight=round(min(weight.values()), 4),
        warnings=warnings,
    )


def _renormalise(weight: dict[str, float], ids: list[str]) -> None:
    mean_weight = sum(weight.values()) / len(ids)
    if mean_weight > 0:
        for i in ids:
            weight[i] /= mean_weight


def warnings_has_degenerate(warnings: list[str]) -> bool:
    """True kalau raking sudah berhenti karena bobot merosot ke nol —
    peringatan non-konvergensi generik jadi berlebihan kalau ini terjadi."""
    return any("merosot ke nol" in w for w in warnings)
