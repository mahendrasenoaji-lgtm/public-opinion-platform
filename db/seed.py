"""Seed data demo — sintetis, bukan hasil survei nyata.

Menghasilkan satu organisasi, satu proyek, 12 gelombang survei, ~8.900
responden, snapshot metrik nasional dan provinsi, narasi, segmen, dan timeline.

Jalankan: python db/seed.py

Semua dashboard yang berjalan di atas data ini WAJIB menampilkan penanda
"Demo data sintetis" (CLAUDE.md §7).
"""

from __future__ import annotations

import os
import random
import uuid
from datetime import date, timedelta

import psycopg

random.seed(20260820)

DSN = os.environ["DATABASE_URL"].replace("+asyncpg", "").replace("postgresql+psycopg", "postgresql")

# Proporsi populasi kasar untuk pembobotan; ganti dengan angka BPS terbaru
# sebelum dipakai untuk apa pun selain demo.
PROVINCES = [
    # kode, nama, share populasi, poi, trust, approval, isu, delta
    ("31", "DKI Jakarta", 0.037, 64, 59, 66, "Biaya transportasi", -6.1),
    ("32", "Jawa Barat", 0.180, 69, 65, 71, "Harga pangan", -4.4),
    ("33", "Jawa Tengah", 0.135, 75, 72, 79, "Harga pangan", -1.2),
    ("34", "DI Yogyakarta", 0.014, 76, 71, 82, "Pendidikan", 1.8),
    ("35", "Jawa Timur", 0.151, 73, 70, 76, "Lapangan kerja", -2.0),
    ("36", "Banten", 0.044, 66, 61, 68, "Biaya transportasi", -5.3),
    ("51", "Bali", 0.016, 78, 74, 80, "Pariwisata", 0.6),
    ("12", "Sumatera Utara", 0.055, 70, 66, 72, "Harga pangan", -3.1),
    ("16", "Sumatera Selatan", 0.032, 71, 67, 73, "Harga pangan", -2.4),
    ("14", "Riau", 0.024, 68, 63, 70, "Lapangan kerja", -3.9),
    ("64", "Kalimantan Timur", 0.014, 74, 69, 77, "Infrastruktur", 0.9),
    ("73", "Sulawesi Selatan", 0.033, 72, 68, 74, "Layanan kesehatan", -1.4),
    ("52", "Nusa Tenggara Barat", 0.020, 67, 62, 69, "Harga pangan", -4.8),
    ("53", "Nusa Tenggara Timur", 0.020, 65, 60, 67, "Akses layanan", -2.7),
    ("94", "Papua", 0.017, 61, 55, 63, "Akses layanan", -1.1),
    ("81", "Maluku", 0.007, 69, 64, 71, "Harga pangan", -2.2),
]

AGE_BANDS = [("18-24", 0.18), ("25-34", 0.24), ("35-44", 0.21), ("45-54", 0.19), ("55+", 0.18)]
EDU = ["SD/sederajat", "SMP/sederajat", "SMA/sederajat", "Diploma", "Sarjana", "Pascasarjana"]
URBAN = [("urban", 0.57), ("rural", 0.43)]

DIMENSIONS = [
    ("sentiment", "Sentiment", "SOCIAL", 61),
    ("approval", "Approval", "SURVEY", 74),
    ("trust", "Trust", "SURVEY", 68),
    ("satisfaction", "Satisfaction", "SURVEY", 71),
    ("issue_perception", "Issue Perception", "MEDIA", 58),
    ("confidence", "Confidence", "SURVEY", 66),
]

POI_SERIES = [77.1, 76.4, 76.9, 75.2, 74.6, 73.8, 72.9, 72.0, 71.2, 71.6, 72.1, 72.4]
SURVEY_SERIES = [74, 73, 75, 72, 71, 70, 69, 68, 67, 68, 68, 68]
SOCIAL_SERIES = [58, 57, 55, 52, 50, 47, 44, 43, 40, 39, 41, 41]
MEDIA_SERIES = [63, 62, 62, 60, 59, 58, 56, 55, 54, 54, 55, 55]

NARRATIVES = [
    ("A", "Kebijakan meningkatkan kesejahteraan", "MEDIA", 42.0, 3.0, 0.34, 71),
    ("B", "Kebijakan menaikkan biaya hidup", "SOCIAL", 31.0, 14.0, -0.48, 58),
    ("C", "Komunikasi pemerintah belum jelas", "SOCIAL", 19.0, 9.0, -0.29, 33),
    ("D", "Implementasi berjalan bertahap", "MEDIA", 8.0, -2.0, 0.11, 24),
]

SEGMENTS = [
    ("Supporters", 24.0, 62, 81, {"age": "45+", "geo": "Jawa non-urban", "concern": "Pendidikan"}),
    ("Soft Supporters", 21.0, 18, 63, {"age": "35-44", "geo": "Kota menengah", "concern": "Harga pangan"}),
    ("Neutral", 17.0, 2, 54, {"age": "25-34", "geo": "Merata", "concern": "Lapangan kerja"}),
    ("Concerned", 19.0, -31, 44, {"age": "25-34", "geo": "Urban Jawa", "concern": "Biaya transportasi"}),
    ("Oppositional", 11.0, -67, 22, {"age": "18-24", "geo": "Urban besar", "concern": "Harga pangan"}),
    ("Volatile", 8.0, -6, 47, {"age": "18-24", "geo": "Luar Jawa", "concern": "Biaya transportasi"}),
]

TIMELINE = [
    (date(2026, 6, 1), "event", "Pengumuman kebijakan", None, None),
    (date(2026, 6, 3), "signal", "Sentiment positif menguat", "+8%", "sentiment"),
    (date(2026, 6, 7), "signal", "Narasi negatif mulai terbentuk", "Narasi B", "narrative_b"),
    (date(2026, 6, 10), "signal", "Percakapan opinion leader meningkat", "x3,4", "amplification"),
    (date(2026, 6, 12), "media", "Pickup media arus utama", "142 artikel", "media_volume"),
    (date(2026, 6, 15), "alert", "Opinion Index turun", "-7,0", "poi"),
]


def weighted(choices):
    keys = [k for k, _ in choices]
    weights = [w for _, w in choices]
    return random.choices(keys, weights=weights, k=1)[0]


def main() -> None:
    with psycopg.connect(DSN, autocommit=False) as conn, conn.cursor() as cur:
        org_id = uuid.uuid4()
        cur.execute(
            "INSERT INTO organizations (id, name, slug, plan) VALUES (%s,%s,%s,'enterprise')",
            (org_id, "Demo Riset Nasional", f"demo-{org_id.hex[:6]}"),
        )
        cur.execute("SET LOCAL app.current_org = %s", (str(org_id),))

        user_id = uuid.uuid4()
        cur.execute(
            """INSERT INTO users (id, org_id, email, full_name, role, password_hash)
               VALUES (%s,%s,%s,%s,'RESEARCH_DIRECTOR',%s)""",
            (user_id, org_id, "direktur@demo.id", "Direktur Riset", "!seed-no-login"),
        )

        project_id = uuid.uuid4()
        cur.execute(
            """INSERT INTO projects (id, org_id, name, objective, created_by, is_demo)
               VALUES (%s,%s,%s,%s,%s,true)""",
            (
                project_id,
                org_id,
                "Persepsi Kebijakan Nasional 2026",
                "Mengukur persepsi, kepercayaan, dan kekhawatiran publik terhadap "
                "paket kebijakan biaya hidup.",
                user_id,
            ),
        )

        # --- 12 gelombang survei -------------------------------------------
        start = date(2026, 5, 4)
        survey_ids = []
        for wave in range(1, 13):
            sid = uuid.uuid4()
            survey_ids.append(sid)
            f_from = start + timedelta(days=7 * (wave - 1))
            cur.execute(
                """INSERT INTO surveys
                   (id, org_id, project_id, wave, title, sampling_method, target_n,
                    fielded_from, fielded_to, sampling_params)
                   VALUES (%s,%s,%s,%s,%s,'MULTISTAGE',%s,%s,%s,
                           '{"confidence":0.95,"margin_of_error":0.03,"design_effect":1.6}')""",
                (sid, org_id, project_id, wave, f"Gelombang {wave}", 780,
                 f_from, f_from + timedelta(days=4)),
            )

        # Responden hanya untuk gelombang terakhir agar seed tetap ringan;
        # gelombang lain diwakili metric_snapshots.
        last = survey_ids[-1]
        rows = []
        for i in range(780):
            prov = random.choices(
                [p[0] for p in PROVINCES], weights=[p[2] for p in PROVINCES], k=1
            )[0]
            share = next(p[2] for p in PROVINCES if p[0] == prov)
            rows.append(
                (
                    uuid.uuid4(), org_id, last, f"R{i:05d}",
                    weighted(AGE_BANDS), random.choice(["L", "P"]),
                    random.choice(EDU), prov, weighted(URBAN),
                    round(random.uniform(0.7, 1.4), 4),
                    random.randint(380, 1450),
                    random.randint(62, 100),
                )
            )
        cur.executemany(
            """INSERT INTO respondents
               (id, org_id, survey_id, anon_code, age_band, gender, education,
                province_code, urbanicity, weight, duration_sec, quality_score)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            rows,
        )

        # Tandai sebagian sebagai perlu ditinjau — flag, bukan vonis.
        cur.execute(
            """UPDATE respondents SET quality_flags = ARRAY['SPEEDING']::quality_flag[]
               WHERE survey_id = %s AND duration_sec < 430""",
            (last,),
        )

        # --- snapshot metrik nasional --------------------------------------
        snaps = []
        for i in range(12):
            p_end = start + timedelta(days=7 * i + 4)
            p_start = p_end - timedelta(days=4)
            for metric, series, source, method in (
                ("poi", POI_SERIES, "SURVEY", "rata-rata tertimbang dimensi"),
                ("survey_positive", SURVEY_SERIES, "SURVEY", "multistage random sampling, CATI"),
                ("social_positive", SOCIAL_SERIES, "SOCIAL", "klasifikasi NLP atas mention API resmi"),
                ("media_positive", MEDIA_SERIES, "MEDIA", "klasifikasi stance tingkat artikel"),
            ):
                v = series[i]
                ci = 1.04 if source == "SURVEY" else None
                snaps.append(
                    (uuid.uuid4(), org_id, project_id, metric, source, method,
                     p_start, p_end, v,
                     round(v - ci, 3) if ci else None,
                     round(v + ci, 3) if ci else None,
                     8940 if source == "SURVEY" else None, None, None)
                )

        # dimensi POI pada periode terakhir
        p_end = start + timedelta(days=7 * 11 + 4)
        for key, label, source, value in DIMENSIONS:
            snaps.append(
                (uuid.uuid4(), org_id, project_id, key, source,
                 "agregasi item terverifikasi", p_end - timedelta(days=4), p_end,
                 value, None, None, 8940 if source == "SURVEY" else None, None, None)
            )

        # per provinsi
        for code, name, share, poi, trust, approval, issue, delta in PROVINCES:
            n = int(8940 * share * random.uniform(0.85, 1.15))
            for metric, value in (("poi", poi), ("trust", trust), ("approval", approval)):
                margin = round(98 / max(n, 1) ** 0.5, 2)
                snaps.append(
                    (uuid.uuid4(), org_id, project_id, metric, "SURVEY",
                     "estimasi area kecil, pembobotan pasca-stratifikasi",
                     p_end - timedelta(days=4), p_end, value,
                     value - margin, value + margin, n, code, None)
                )

        cur.executemany(
            """INSERT INTO metric_snapshots
               (id, org_id, project_id, metric, source, method, period_start,
                period_end, value, ci_low, ci_high, effective_n, province_code, segment)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            snaps,
        )

        cur.executemany(
            """INSERT INTO narratives
               (id, org_id, project_id, code, statement, origin_source, volume_pct,
                momentum_7d, sentiment, media_pickup, unclustered_pct)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,6.2)""",
            [(uuid.uuid4(), org_id, project_id, *n) for n in NARRATIVES],
        )

        cur.executemany(
            """INSERT INTO segments
               (id, org_id, project_id, name, size_pct, sentiment, trust, profile,
                method, entropy)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'latent_class',0.82)""",
            [
                (uuid.uuid4(), org_id, project_id, name, size, sent, trust,
                 psycopg.types.json.Json(profile))
                for name, size, sent, trust, profile in SEGMENTS
            ],
        )

        cur.executemany(
            """INSERT INTO timeline_events
               (id, org_id, project_id, occurred_at, kind, label, value_note, associated_metric)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            [(uuid.uuid4(), org_id, project_id, d, kind, label, note, metric)
             for d, kind, label, note, metric in TIMELINE],
        )

        cur.execute(
            """INSERT INTO data_quality_scores
               (id, org_id, project_id, dataset, completeness, duplicate,
                response_qual, consistency, sample_balance, metadata_score, overall)
               VALUES (%s,%s,%s,'survey_w12',96,99,87,92,81,94,90)""",
            (uuid.uuid4(), org_id, project_id),
        )

        conn.commit()

    print(f"Seed selesai.\n  organization : {org_id}\n  project      : {project_id}")
    print("  Data ini SINTETIS. Jangan disajikan sebagai hasil survei nyata.")


if __name__ == "__main__":
    main()
