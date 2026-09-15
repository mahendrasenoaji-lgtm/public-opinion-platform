"""Konektor sumber data (Phase 2).

Mengimpor paket ini mendaftarkan seluruh konektor bawaan ke registry di
`base.py` — impor modulnya di bawah memang untuk efek samping `@register`,
bukan karena namanya dipakai di sini.

Batas legal yang mengikat semua konektor ada di docstring `base.py`. Baca itu
sebelum menambah konektor baru.
"""

from app.connectors import (  # noqa: F401 — diimpor untuk efek samping @register
    manual,
    openmeteo,
    rss,
    wikipedia,
    x,
    youtube,
)
from app.connectors.base import (
    Connector,
    ConnectorError,
    ConnectorInfo,
    CredentialMissing,
    FetchStats,
    RawItem,
    available,
    get_connector,
    register,
)
from app.connectors.metrics import (
    MetricConnector,
    RawObservation,
    available_metrics,
    get_metric_connector,
    register_metric,
)

__all__ = [
    "Connector",
    "ConnectorError",
    "ConnectorInfo",
    "CredentialMissing",
    "FetchStats",
    "MetricConnector",
    "RawItem",
    "RawObservation",
    "available",
    "available_metrics",
    "get_connector",
    "get_metric_connector",
    "register",
    "register_metric",
]
