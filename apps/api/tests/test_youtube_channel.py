"""Tes fungsi murni pengambil kanal YouTube resmi (tanpa jaringan)."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.connectors import youtube_channel as ytc
from app.connectors.base import ConnectorError

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
CHANNEL_ID = "UC" + "a" * 22


def _channel_payload(**stats: object) -> dict:
    return {
        "items": [
            {
                "id": CHANNEL_ID,
                "snippet": {"title": "Kanal Resmi", "customUrl": "@kanalresmi"},
                "statistics": {"subscriberCount": "120000", **stats},
                "contentDetails": {"relatedPlaylists": {"uploads": "UU" + "a" * 22}},
            }
        ]
    }


# ------------------------------------------------------------ masukan ----


@pytest.mark.parametrize(
    ("raw", "cid", "handle"),
    [
        ("@kanalresmi", None, "@kanalresmi"),
        ("kanalresmi", None, "@kanalresmi"),
        ("  @Kanal.Resmi-1 ", None, "@Kanal.Resmi-1"),
        (CHANNEL_ID, CHANNEL_ID, None),
        ("https://www.youtube.com/@kanalresmi/videos", None, "@kanalresmi"),
        (f"https://youtube.com/channel/{CHANNEL_ID}", CHANNEL_ID, None),
    ],
)
def test_masukan_kanal_dinormalkan(raw: str, cid: str | None, handle: str | None) -> None:
    ref = ytc.parse_channel_input(raw)
    assert ref.channel_id == cid
    assert ref.handle == handle


@pytest.mark.parametrize("raw", ["Kementerian Contoh Republik", "ab", "https://example.com/x"])
def test_nama_bebas_ditolak_bukan_dicari(raw: str) -> None:
    with pytest.raises(ConnectorError):
        ytc.parse_channel_input(raw)


# ------------------------------------------------------------- kanal ----


def test_kanal_dibaca_lengkap() -> None:
    ch = ytc.parse_channel(_channel_payload())
    assert ch is not None
    assert ch.channel_id == CHANNEL_ID
    assert ch.handle == "@kanalresmi"
    assert ch.subscribers == 120000
    assert ch.uploads_playlist.startswith("UU")


def test_pelanggan_tersembunyi_dicatat_kosong() -> None:
    ch = ytc.parse_channel(_channel_payload(hiddenSubscriberCount=True))
    assert ch is not None and ch.subscribers is None


def test_kanal_tidak_ada_mengembalikan_none() -> None:
    assert ytc.parse_channel({"items": []}) is None
    assert ytc.parse_channel({}) is None


# ------------------------------------------------------------- video ----


def test_playlist_melewati_video_privat() -> None:
    items = ytc.parse_playlist_items(
        {
            "items": [
                {"contentDetails": {"videoId": "v1", "videoPublishedAt": "2026-11-10T01:00:00Z"}},
                {"contentDetails": {"videoId": "v2"}},  # privat: tanpa tanggal
            ]
        }
    )
    assert [v for v, _ in items] == ["v1"]


@pytest.mark.parametrize(
    ("iso", "seconds"),
    [("PT45S", 45), ("PT1M2S", 62), ("PT1H", 3600), ("P1DT1S", 86401), ("", None), ("P", None)],
)
def test_durasi(iso: str, seconds: int | None) -> None:
    assert ytc.parse_duration(iso) == seconds


def test_angka_tersembunyi_kosong_bukan_nol() -> None:
    videos = ytc.parse_videos(
        {
            "items": [
                {
                    "id": "v1",
                    "snippet": {"title": "Siaran pers", "publishedAt": "2026-11-10T01:00:00Z"},
                    "statistics": {"viewCount": "1500", "likeCount": "40", "commentCount": "0"},
                },
                {
                    "id": "v2",
                    "snippet": {
                        "title": "Rapat langsung",
                        "publishedAt": "2026-11-09T01:00:00Z",
                        "liveBroadcastContent": "none",
                    },
                    "statistics": {"viewCount": "900"},  # suka disembunyikan, komentar mati
                    "liveStreamingDetails": {"actualStartTime": "2026-11-09T01:00:00Z"},
                },
            ]
        }
    )
    v1, v2 = videos
    assert (v1.views, v1.likes, v1.comments, v1.kind) == (1500, 40, 0, "video")
    assert (v2.views, v2.likes, v2.comments, v2.kind) == (900, None, None, "siaran langsung")


def test_pilih_yang_baru_dan_tandai_batas() -> None:
    cutoff = NOW - timedelta(days=30)
    items = [
        ("a", NOW - timedelta(days=1)),
        ("b", NOW - timedelta(days=10)),
        ("c", NOW - timedelta(days=40)),
    ]
    assert ytc.select_recent(items, cutoff, room=5) == (["a", "b"], True, False)
    assert ytc.select_recent(items, cutoff, room=1) == (["a"], True, True)
    assert ytc.select_recent(items[:2], cutoff, room=5) == (["a", "b"], False, False)


def test_baris_simpan_tanpa_share_dan_memakai_handle() -> None:
    ch = ytc.parse_channel(_channel_payload())
    assert ch is not None
    video = ytc.VideoStats("v1", "Judul", NOW, "video", 10, 2, 1)
    rows = ytc.to_post_rows(ytc.ChannelFetch(ch, [video], 3, False), NOW)
    assert rows == [
        {
            "platform": "youtube",
            "account": "@kanalresmi",
            "external_id": "v1",
            "url": "https://www.youtube.com/watch?v=v1",
            "posted_at": NOW,
            "kind": "video",
            "caption": "Judul",
            "likes": 2,
            "comments": 1,
            "shares": None,
            "views": 10,
            "followers": 120000,
            "captured_at": NOW,
        }
    ]


# ------------------------------------------- alur lengkap (mock HTTP) ----


async def test_alur_lengkap_dengan_transport_tiruan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "kunci-tes")
    from app.config import get_settings

    get_settings.cache_clear()
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path.rsplit("/", 1)[-1]
        calls.append(path)
        if path == "channels":
            assert request.url.params["forHandle"] == "@kanalresmi"
            return httpx.Response(200, json=_channel_payload())
        if path == "playlistItems":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"contentDetails": {"videoId": vid, "videoPublishedAt": ts}}
                        for vid, ts in (
                            ("v1", "2026-11-13T00:00:00Z"),
                            ("v2", "2026-06-01T00:00:00Z"),
                        )
                    ],
                    "nextPageToken": "lagi",
                },
            )
        assert path == "videos"
        assert request.url.params["id"] == "v1"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "v1",
                        "snippet": {"title": "Baru", "publishedAt": "2026-11-13T00:00:00Z"},
                        "statistics": {"viewCount": "5"},
                    }
                ]
            },
        )

    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            out = await ytc.fetch_channel_uploads(
                "@kanalresmi", since_days=90, max_videos=10, now=NOW, client=client
            )
    finally:
        get_settings.cache_clear()

    # Video Juni lebih tua dari 90 hari: halaman berikutnya tidak diminta.
    assert calls == ["channels", "playlistItems", "videos"]
    assert out.quota_units == 3
    assert [v.video_id for v in out.videos] == ["v1"]
    assert out.truncated is False


async def test_kanal_tidak_ditemukan_jadi_pesan_jelas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "kunci-tes")
    from app.config import get_settings

    get_settings.cache_clear()
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"items": []}))
    try:
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ConnectorError, match="tidak ditemukan"):
                await ytc.fetch_channel_uploads("@tidakada", now=NOW, client=client)
    finally:
        get_settings.cache_clear()
