"""DataSource, Mention, Topic — tabel sinyal Phase 2.

Tabelnya sudah ada di db/schema.sql sejak awal proyek; yang belum ada sampai
sekarang cuma pemetaan ORM-nya, karena belum ada kode yang menulis ke sana.

Kolom `mentions.embedding` dan `topics.centroid` (keduanya `vector(1024)`,
pgvector) SENGAJA tidak dipetakan di sini. Dua alasan, keduanya bukan
kemalasan:

1. Memetakannya butuh dependensi `pgvector` untuk SQLAlchemy — dependensi baru
   yang harus ikut ke Render, dan belum ada yang memakainya.
2. Belum ada yang mengisinya. Topic discovery tahap ini memakai TF-IDF
   (`services/topics.py`), bukan embedding, dan metodenya dilaporkan apa adanya
   lewat field `method`. Menyimpan vektor TF-IDF ke kolom bernama `embedding`
   akan membuat metadata berbohong soal metode yang dipakai — persis yang
   dilarang R1.

Begitu provider embedding sungguhan dikonfigurasi, tambahkan pemetaannya di
sini bersama perubahan `services/topics.py` yang memakainya, dan ubah label
metodenya di commit yang sama.
"""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, Text, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.measurement import SignalSource


def _signal_source_column() -> SAEnum:
    """Enum Postgres native `signal_source`, bukan String.

    Diulang dari measurement.py dengan sengaja lewat helper: memetakan kolom
    ini sebagai String adalah bug #4 yang tercatat di docs/roadmap.md
    (`WHERE source = 'SOCIAL'` gagal dengan "operator does not exist"). Satu
    tempat untuk membuatnya, supaya tidak salah lagi di tabel berikutnya.
    """
    return SAEnum(
        SignalSource,
        name="signal_source",
        create_type=False,
        values_callable=lambda e: [m.value for m in e],
    )


class DataSource(Base):
    """Satu konektor yang aktif untuk satu proyek.

    `config` menyimpan parameter konektor (kueri pencarian, URL feed, channel
    id). JANGAN menyimpan kunci API di sini — kunci hidup di environment
    deployment, bukan di baris database yang ikut ter-backup dan ter-ekspor.
    """

    __tablename__ = "data_sources"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[SignalSource] = mapped_column(_signal_source_column(), nullable=False)
    connector: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Mention(Base):
    """Satu unit percakapan atau liputan.

    `author_hash` — akun disimpan sebagai hash berkunci, bukan handle mentah
    (CLAUDE.md §3: jangan simpan identitas bersama isinya). Yang bisa dilakukan
    dengan hash: menghitung berapa banyak akun berbeda, dan seberapa terpusat
    percakapannya. Yang tidak bisa: mengembalikannya jadi nama akun.
    """

    __tablename__ = "mentions"
    __table_args__ = (UniqueConstraint("project_id", "connector", "external_id"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[SignalSource] = mapped_column(_signal_source_column(), nullable=False)
    connector: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    author_hash: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    lang: Mapped[str | None] = mapped_column(Text, default="id")
    engagement: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reach_est: Mapped[int | None] = mapped_column(Integer)
    province_code: Mapped[str | None] = mapped_column(Text)
    sentiment: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    emotion: Mapped[dict | None] = mapped_column(JSON)
    topic_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    narrative_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TopicReviewStatus(str, enum.Enum):  # noqa: UP042 -- lihat catatan
    # ConfidenceBand di app/models/governance.py: enum lokal supaya app/models
    # tidak bergantung ke app/ai, dan cocok dengan tipe Postgres native
    # `review_status` yang sama dipakai ai_outputs.human_review.
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class Topic(Base):
    """Klaster percakapan hasil `services/topics.py`.

    `volume` adalah jumlah mention di klaster ini, bukan persentase — persentase
    dihitung saat penyajian supaya penyebutnya (total mention pada periode yang
    ditanyakan) selalu eksplisit.

    `reviewed_label`/`review_status` adalah verifikasi manusia ATAS label
    kata-kunci otomatis -- lihat routers/topics.py:review_topic(). Label asli
    (`label`) tidak pernah ditimpa; yang disunting manusia disimpan terpisah
    supaya keduanya bisa dibandingkan.
    """

    __tablename__ = "topics"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"),
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reviewed_label: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[TopicReviewStatus] = mapped_column(
        SAEnum(
            TopicReviewStatus,
            name="review_status",
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=TopicReviewStatus.PENDING,
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
