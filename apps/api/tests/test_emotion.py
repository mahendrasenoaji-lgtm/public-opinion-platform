"""Tes services/emotion.py (`emosi-id-2`)."""

from __future__ import annotations

from app.services import emotion


class TestMarkers:
    def test_ejaan_informal_dan_emoji(self) -> None:
        assert emotion.emotions("kecewaaa bgt sama pemerintah 😡") == {
            "sadness": 0.5,
            "anger": 0.5,
        }

    def test_negasi_satu_kata_melewati_penanda(self) -> None:
        assert emotion.emotions("saya tidak marah kok") == {}
        assert emotion.emotions("gak takut") == {}

    def test_frasa_dua_kata_dinilai_utuh(self) -> None:
        assert emotion.emotions("terima kasih pak") == {"joy": 1.0}
        assert emotion.emotions("dasar tidak tahu malu") == {"disgust": 1.0}
        assert emotion.emotions("semoga cepat normal, mudah-mudahan") == {"anticipation": 1.0}

    def test_kata_penyusun_frasa_tidak_dihitung_sendiri(self) -> None:
        assert emotion.emotions("harganya naik lagi, biasa saja") == {}

    def test_emoji_tertawa_dan_kata_ambigu_tidak_dihitung(self) -> None:
        assert emotion.emotions("wkwk 😂🤣 gila parah, nanti minta mundur") == {}

    def test_teks_tanpa_penanda_kosong(self) -> None:
        assert emotion.emotions("antre di spbu sejak pagi") == {}
        assert emotion.emotions("") == {}

    def test_penanda_berulang_dihitung_sekali(self) -> None:
        hits = emotion.markers("marah marah marah 😡😡😡")
        assert [(h.key, h.marker) for h in hits] == [("anger", "marah"), ("anger", "😡")]

    def test_kunci_selalu_dari_keys(self) -> None:
        for text in ("pecat saja", "takut", "sedih", "jijik", "bangga", "setuju", "semoga"):
            (key,) = emotion.emotions(text)
            assert key in emotion.KEYS


class TestAnalyse:
    def test_satu_lintasan_sama_dengan_per_teks(self) -> None:
        texts = ["marah sekali", "antre", "semoga cepat 🙏", "marah dan kecewa"]
        shares, top = emotion.analyse(texts)
        assert shares == [emotion.emotions(t) for t in texts]
        assert top["anger"] == [("marah", 2)]
        assert top["anticipation"] == [("semoga", 1), ("🙏", 1)]
        assert top == emotion.top_markers(texts)
        assert set(top) == set(emotion.KEYS)
