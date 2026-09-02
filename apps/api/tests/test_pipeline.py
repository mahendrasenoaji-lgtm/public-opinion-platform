"""Tes prepare_batch() — fungsi murni, tanpa database.

Fokus di sini adalah hashing reply_to_handle/quote_of_handle, karena
aritmetika dedup/bahasa/sentimen sudah ditutupi test_ingestion.py dan lewat
tes router ingest yang sudah ada.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.services.ingestion import hash_author
from app.services.pipeline import IncomingItem, prepare_batch

SALT = "salt-tes"
WAKTU = datetime(2026, 8, 25, tzinfo=UTC)


def _item(**overrides: object) -> IncomingItem:
    base: dict[str, object] = {
        "external_id": "1",
        "text": "pendapat warga tentang kebijakan ini cukup panjang untuk lolos deteksi",
        "published_at": WAKTU,
    }
    base.update(overrides)
    return IncomingItem(**base)  # type: ignore[arg-type]


class TestRelasiBalasanKutipan:
    def test_reply_to_handle_di_hash_sama_seperti_author(self) -> None:
        item = _item(author_handle="a", reply_to_handle="b")
        report = prepare_batch([item], author_salt=SALT)
        p = report.prepared[0]
        assert p.author_hash == hash_author("a", salt=SALT)
        assert p.reply_to_hash == hash_author("b", salt=SALT)

    def test_quote_of_handle_di_hash(self) -> None:
        item = _item(author_handle="a", quote_of_handle="c")
        report = prepare_batch([item], author_salt=SALT)
        assert report.prepared[0].quote_of_hash == hash_author("c", salt=SALT)

    def test_tanpa_relasi_hash_none(self) -> None:
        item = _item(author_handle="a")
        report = prepare_batch([item], author_salt=SALT)
        p = report.prepared[0]
        assert p.reply_to_hash is None
        assert p.quote_of_hash is None

    def test_conversation_id_diteruskan_apa_adanya(self) -> None:
        item = _item(conversation_id="convo-1")
        report = prepare_batch([item], author_salt=SALT)
        assert report.prepared[0].conversation_id == "convo-1"

    def test_salt_berbeda_menghasilkan_hash_reply_berbeda(self) -> None:
        item = _item(reply_to_handle="b")
        a = prepare_batch([item], author_salt="salt-a").prepared[0]
        b = prepare_batch([item], author_salt="salt-b").prepared[0]
        assert a.reply_to_hash != b.reply_to_hash
