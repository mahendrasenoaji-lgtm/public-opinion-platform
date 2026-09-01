"""Unggahan manual — data yang sudah dimiliki organisasi.

Ada karena kenyataannya sebagian besar lembaga riset di Indonesia sudah membeli
ekspor data dari vendor listening, atau punya arsip liputan sendiri. Memaksa
mereka menyambung ulang lewat API hanya untuk memakai platform ini adalah
hambatan tanpa manfaat.

Konektor ini tidak menarik apa pun. Datanya masuk lewat
`POST /projects/{id}/signals/ingest`, dan tetap melewati pipeline yang sama
(dedup, deteksi bahasa, sentimen) supaya angkanya sebanding dengan yang
dikumpulkan konektor lain.

Kewajiban yang pindah ke pengguna, dan disebut apa adanya di UI: memastikan
data yang diunggah memang boleh mereka pakai. Platform ini tidak bisa
memverifikasi lisensi sebuah ekspor.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from app.connectors.base import Connector, ConnectorError, RawItem, register
from app.models.measurement import SignalSource


@register
class ManualConnector(Connector):
    """Penanda sumber untuk data yang diunggah pengguna."""

    key: ClassVar[str] = "manual"
    label: ClassVar[str] = "Unggahan manual / ekspor vendor"
    source: ClassVar[SignalSource] = SignalSource.SOCIAL
    requires_credential: ClassVar[str | None] = None
    config_fields: ClassVar[tuple[str, ...]] = ()
    notes: ClassVar[str] = (
        "Data dikirim lewat POST /signals/ingest, bukan ditarik terjadwal. "
        "Pastikan lisensi data yang diunggah memang mengizinkan pemakaian ini — "
        "platform tidak bisa memverifikasinya untuk Anda."
    )

    async def fetch(
        self,
        config: dict[str, object],
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[RawItem]:
        raise ConnectorError(
            "Konektor 'manual' tidak menarik data. Kirim datanya lewat "
            "POST /projects/{project_id}/signals/ingest."
        )
