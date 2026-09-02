"""Konektor sumber data (Phase 2).

Mengimpor paket ini mendaftarkan seluruh konektor bawaan ke registry di
`base.py` — impor modulnya di bawah memang untuk efek samping `@register`,
bukan karena namanya dipakai di sini.

Batas legal yang mengikat semua konektor ada di docstring `base.py`. Baca itu
sebelum menambah konektor baru.
"""

from app.connectors import manual, rss, x, youtube  # noqa: F401 — daftarkan via @register
from app.connectors.base import (
    Connector,
    ConnectorError,
    ConnectorInfo,
    CredentialMissing,
    RawItem,
    available,
    get_connector,
    register,
)

__all__ = [
    "Connector",
    "ConnectorError",
    "ConnectorInfo",
    "CredentialMissing",
    "RawItem",
    "available",
    "get_connector",
    "register",
]
