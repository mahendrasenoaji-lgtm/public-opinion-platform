"""Konfigurasi pytest bersama, dijalankan sebelum modul tes mana pun diimpor.

`RATE_LIMIT_ENABLED=false` di sini -- bukan cuma di `.github/workflows/ci.yml`
-- supaya tes lolos konsisten baik dijalankan lewat CI maupun lokal
(`make test-db` + `pytest`) tanpa developer perlu ingat menyetel env var itu
sendiri. `setdefault` (bukan assignment langsung) supaya CI atau siapa pun
yang SENGAJA ingin menguji rate limiter tetap bisa override dengan menyetel
env var itu sendiri sebelum pytest jalan.

Ketahuan perlu ada file ini 2026-09-11: `RateLimitMiddleware` yang baru
dipasang di `app/main.py` mengunci request per-IP, dan TestClient/AsyncClient
memakai satu "IP" palsu yang sama untuk SEMUA request di seluruh suite --
113 tes gagal dengan 429 begitu middleware itu terpasang tanpa jalan keluar
ini, sesuatu yang tidak pernah terjadi di lalu lintas produksi sungguhan.
"""

from __future__ import annotations

import os

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
