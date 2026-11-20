"""Tes murni "Tarik tema": validasi, tahapan, kuota, dan pembacaan respons YouTube.

Tanpa jaringan dan tanpa database.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.connectors import youtube_theme as yt
from app.services import theme_pull as tp

TODAY = date(2026, 11, 20)


def _req(**kw: object) -> tp.ThemeRequest:
    args: dict[str, object] = {
        "queries": "gibran mundur, pengunduran diri gibran",
        "start": date(2026, 11, 10),
        "end": date(2026, 11, 17),
        "max_videos": 3,
        "include_replies": True,
        "comments_until_now": False,
        "keyword_filter": True,
        "today": TODAY,
    }
    args.update(kw)
    return tp.parse_request(**args)  # type: ignore[arg-type]


def _state(**kw: object) -> dict[str, object]:
    return tp.initial_state(_req(**kw), label="uji", now=datetime(2026, 11, 20, tzinfo=UTC))


# ------------------------------------------------------------ validasi ----


def test_split_queries_dedups_and_trims() -> None:
    assert tp.split_queries(" a  b ,A B\nc;; ") == ("a b", "c")


@pytest.mark.parametrize(
    ("kw", "msg"),
    [
        ({"queries": " , "}, "minimal satu"),
        ({"queries": "a,b,c,d,e,f"}, "Paling banyak"),
        ({"end": date(2026, 11, 1)}, "tidak boleh sebelum"),
        ({"start": date(2026, 12, 1), "end": date(2026, 12, 2)}, "masa depan"),
        ({"start": date(2025, 1, 1)}, "paling panjang"),
        ({"max_videos": 0}, "Jumlah video"),
    ],
)
def test_parse_request_rejects(kw: dict[str, object], msg: str) -> None:
    with pytest.raises(tp.ThemeError, match=msg):
        _req(**kw)


def test_end_in_future_is_clamped_to_today() -> None:
    assert _req(end=date(2026, 12, 31)).end == TODAY


def test_window_is_wib_inclusive() -> None:
    lo, hi = tp.window_utc(date(2026, 11, 10), date(2026, 11, 17))
    assert lo == datetime(2026, 11, 9, 17, tzinfo=UTC)
    assert hi == datetime(2026, 11, 17, 17, tzinfo=UTC)
    assert tp.rfc3339(lo) == "2026-11-09T17:00:00Z"


def test_relevant_needs_all_words_of_one_query() -> None:
    qs = ["gibran mundur", "pemakzulan"]
    assert tp.relevant("Gibran resmi MUNDUR", "", qs)
    assert tp.relevant("Sidang", "wacana pemakzulan", qs)
    assert not tp.relevant("Gibran kunjungi Solo", "", qs)


# ------------------------------------------------------------- tahapan ----


def test_search_moves_through_pages_queries_then_details() -> None:
    s = _state()  # max_videos 3, filter → cap 6
    tp.add_candidates(s, ["a", "b"])
    tp.advance_search(s, next_token="T2")
    assert s["status"] == tp.STATUS_SEARCHING and s["search_token"] == "T2"
    tp.add_candidates(s, ["b", "c"])  # b ganda
    assert s["candidates"] == ["a", "b", "c"]
    tp.advance_search(s, next_token=None)
    assert s["query_index"] == 1 and s["search_token"] is None
    tp.advance_search(s, next_token="X")
    tp.advance_search(s, next_token=None)
    assert s["status"] == tp.STATUS_DETAILS


def test_search_stops_early_when_enough_candidates() -> None:
    s = _state()
    tp.add_candidates(s, list("abcdef"))
    tp.advance_search(s, next_token="more")
    assert s["status"] == tp.STATUS_DETAILS


def test_search_page_size_respects_remaining_room() -> None:
    s = _state()
    tp.add_candidates(s, list("abcd"))
    assert tp.search_page_size(s) == 2


def test_details_filter_sort_cap_and_skip_empty() -> None:
    s = _state()
    s["status"] = tp.STATUS_DETAILS
    s["candidates"] = ["v1", "v2", "v3", "v4", "v5"]
    details = [
        {"id": "v1", "title": "Gibran mundur", "comment_count": 10},
        {"id": "v2", "title": "Resep soto", "comment_count": 999},
        {"id": "v3", "title": "pengunduran diri gibran", "comment_count": 500},
        {"id": "v4", "title": "gibran mundur sore", "comment_count": 0},
        {"id": "v5", "title": "gibran mundur? live", "comment_count": 50},
    ]
    tp.accept_details(s, details, 5)
    assert s["dropped_by_filter"] == 1
    assert [v["id"] for v in s["videos"]] == ["v3", "v5", "v1"]  # top 3 by comments
    assert s["status"] == tp.STATUS_COLLECTING and s["candidates"] == []


def test_zero_comment_video_skipped_and_done_when_nothing_left() -> None:
    s = _state(max_videos=1)
    s["candidates"] = ["v1"]
    tp.accept_details(s, [{"id": "v1", "title": "gibran mundur", "comment_count": 0}], 1)
    assert s["videos"][0]["state"] == tp.VIDEO_SKIPPED
    assert s["status"] == tp.STATUS_DONE


def test_no_matching_videos_finishes_with_note() -> None:
    s = _state()
    s["candidates"] = []
    tp.accept_details(s, [], 0)
    assert s["status"] == tp.STATUS_DONE
    assert "Tidak ada video" in s["notes"][0]


def test_finish_video_advances_and_completes() -> None:
    s = _state()
    s["status"] = tp.STATUS_COLLECTING
    s["videos"] = [
        {"id": "a", "title": "A", "comment_count": 5, "state": "pending", "got": 0, "note": None},
        {"id": "b", "title": "B", "comment_count": 5, "state": "pending", "got": 0, "note": None},
    ]
    s["comment_token"] = "tok"
    tp.finish_video(s)
    assert s["video_index"] == 1 and s["comment_token"] is None
    tp.finish_video(s, skipped_note="komentar dimatikan")
    assert s["videos"][1]["state"] == tp.VIDEO_SKIPPED
    assert s["status"] == tp.STATUS_DONE
    p = tp.progress(s)
    assert (p.videos_done, p.videos_skipped, p.current_video) == (1, 1, None)


def test_comment_window_until_now() -> None:
    lo, hi = tp.comment_window(_state())
    assert hi is not None
    assert tp.in_window(lo, lo, hi) and not tp.in_window(hi, lo, hi)
    _, open_end = tp.comment_window(_state(comments_until_now=True))
    assert open_end is None


# --------------------------------------------------------------- kuota ----


def test_quota_reset_is_next_0805_utc() -> None:
    assert tp.next_quota_reset(datetime(2026, 11, 20, 3, 0, tzinfo=UTC)) == datetime(
        2026, 11, 20, 8, 5, tzinfo=UTC
    )
    assert tp.next_quota_reset(datetime(2026, 11, 20, 9, 0, tzinfo=UTC)) == datetime(
        2026, 11, 21, 8, 5, tzinfo=UTC
    )


def test_quota_wait_round_trip_restores_stage() -> None:
    s = _state()
    s["status"] = tp.STATUS_COLLECTING
    now = datetime(2026, 11, 20, 3, 0, tzinfo=UTC)
    tp.wait_for_quota(s, now)
    tp.wait_for_quota(s, now)  # dua kali tidak menimpa tahap asal
    assert s["status"] == tp.STATUS_WAITING_QUOTA
    assert not tp.quota_ready(s, now)
    assert tp.quota_ready(s, datetime(2026, 11, 20, 8, 6, tzinfo=UTC))
    tp.leave_quota_wait(s)
    assert s["status"] == tp.STATUS_COLLECTING and s["resume_at"] is None


def test_estimate_units() -> None:
    s = _state(include_replies=False)
    s["videos"] = [
        {"id": "a", "title": "A", "comment_count": 250, "state": "pending", "got": 50,
         "note": None},
        {"id": "b", "title": "B", "comment_count": 999, "state": "done", "got": 999, "note": None},
    ]
    assert tp.estimate_units(s) == 3


# ------------------------------------------------- respons YouTube API ----


def _comment(cid: str, text: str, author: str = "Budi", likes: int = 1) -> dict[str, object]:
    return {
        "id": cid,
        "snippet": {
            "textOriginal": text,
            "authorDisplayName": author,
            "likeCount": likes,
            "publishedAt": "2026-11-12T03:00:00Z",
        },
    }


def test_parse_threads_inline_and_incomplete_replies() -> None:
    payload = {
        "items": [
            {
                "snippet": {"topLevelComment": _comment("t1", "utama"), "totalReplyCount": 1},
                "replies": {"comments": [_comment("r1", "balas", author="Ani")]},
            },
            {
                "snippet": {"topLevelComment": _comment("t2", "ramai"), "totalReplyCount": 9},
                "replies": {"comments": [_comment("r2", "satu saja")]},
            },
            {"snippet": {"topLevelComment": _comment("t3", ""), "totalReplyCount": 0}},
        ]
    }
    items, incomplete = yt.parse_threads(payload, "VID")
    assert [i.external_id for i in items] == ["t1", "r1", "t2"]
    reply = items[1]
    assert reply.conversation_id == "t1" and reply.reply_to_handle == "Budi"
    assert reply.url == "https://www.youtube.com/watch?v=VID&lc=r1"
    assert items[0].engagement == 2  # 1 suka + 1 balasan
    assert incomplete == [("t2", "Budi", 9)]


def test_parse_videos_and_search_ids() -> None:
    vids = yt.parse_videos(
        {
            "items": [
                {
                    "id": "v1",
                    "snippet": {"title": "T", "channelTitle": "C", "publishedAt": "x"},
                    "statistics": {"commentCount": "12"},
                },
                {"id": "v2", "snippet": {}},
            ]
        }
    )
    assert vids == [
        {
            "id": "v1",
            "title": "T",
            "description": "",
            "channel": "C",
            "published_at": "x",
            "comment_count": 12,
        }
    ]
    ids, tok = yt.parse_search_ids(
        {"items": [{"id": {"videoId": "a"}}, {"id": {"channelId": "c"}}], "nextPageToken": "N"}
    )
    assert (ids, tok) == (["a"], "N")


@pytest.mark.parametrize(
    ("status", "body", "kind"),
    [
        (403, '{"reason": "quotaExceeded"}', yt.QuotaExceeded),
        (403, '{"reason": "commentsDisabled"}', yt.VideoUnavailable),
        (404, "videoNotFound", yt.VideoUnavailable),
        (500, "oops", yt.ConnectorError),
    ],
)
def test_classify_error(status: int, body: str, kind: type[Exception]) -> None:
    err = yt.classify_error(status, body)
    assert type(err) is kind
