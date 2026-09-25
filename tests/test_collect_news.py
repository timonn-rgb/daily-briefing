from datetime import datetime, timezone

from briefing.collect_news import collect_news, dedupe, parse_feed, rank_and_cap

NOW = datetime(2026, 9, 26, 4, 0, tzinfo=timezone.utc)
FEED = {"name": "BBC World", "url": "https://example.com/rss", "region": "world"}


def rss(items: str) -> bytes:
    return f"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>{items}</channel></rss>""".encode()


def item(title, link="https://example.com/a", date="Fri, 25 Sep 2026 20:00:00 GMT", desc="Short summary."):
    link_tag = f"<link>{link}</link>" if link else ""
    title_tag = f"<title>{title}</title>" if title else ""
    return f"<item>{title_tag}{link_tag}<pubDate>{date}</pubDate><description>{desc}</description></item>"


def test_parse_feed_keeps_recent_items_only():
    raw = rss(item("Recent story") + item("Old story", date="Tue, 22 Sep 2026 10:00:00 GMT"))
    items = parse_feed(FEED, raw, NOW)
    assert [i["title"] for i in items] == ["Recent story"]
    assert items[0]["sources"] == [{"name": "BBC World", "url": "https://example.com/a"}]
    assert items[0]["published"] == "2026-09-25T20:00:00+00:00"
    assert items[0]["summary"] == "Short summary."


def test_parse_feed_skips_entries_without_title_or_link():
    raw = rss(item("") + item("No link", link=None) + item("Good"))
    assert [i["title"] for i in parse_feed(FEED, raw, NOW)] == ["Good"]


def test_parse_feed_strips_html_and_skips_non_http_links():
    raw = rss(
        item("Markets &amp; &lt;b&gt;bonds&lt;/b&gt;", desc="&lt;p&gt;Rates &amp;amp; yields&lt;/p&gt;")
        + item("Evil", link="javascript:alert(1)")
    )
    items = parse_feed(FEED, raw, NOW)
    assert [i["title"] for i in items] == ["Markets & bonds"]
    assert items[0]["summary"] == "Rates & yields"


def test_undated_items_are_kept():
    raw = rss("<item><title>No date</title><link>https://example.com/x</link></item>")
    items = parse_feed(FEED, raw, NOW)
    assert items[0]["published"] is None


def test_dedupe_merges_same_story_across_feeds():
    a = {"title": "Fed holds interest rates steady amid inflation worries - Reuters", "summary": "",
         "published": None, "region": "world", "sources": [{"name": "Reuters", "url": "https://r/1"}]}
    b = {"title": "Fed holds interest rates steady amid inflation worries", "summary": "More detail.",
         "published": None, "region": "world", "sources": [{"name": "BBC World", "url": "https://b/1"}]}
    c = {"title": "Earthquake strikes northern Japan", "summary": "", "published": None,
         "region": "asia", "sources": [{"name": "NHK", "url": "https://n/1"}]}
    merged = dedupe([a, b, c])
    assert len(merged) == 2
    assert [s["name"] for s in merged[0]["sources"]] == ["Reuters", "BBC World"]
    assert merged[0]["summary"] == "More detail."


def test_rank_and_cap_prefers_multi_source_then_newest_and_assigns_ids():
    items = [
        {"title": "old single", "published": "2026-09-25T01:00:00+00:00", "sources": [{"name": "A", "url": "u"}]},
        {"title": "new single", "published": "2026-09-25T20:00:00+00:00", "sources": [{"name": "A", "url": "u"}]},
        {"title": "double", "published": "2026-09-25T00:00:00+00:00",
         "sources": [{"name": "A", "url": "u"}, {"name": "B", "url": "v"}]},
    ]
    ranked = rank_and_cap(items, 2)
    assert [i["title"] for i in ranked] == ["double", "new single"]
    assert [i["id"] for i in ranked] == ["h001", "h002"]


def test_garbage_feed_counts_as_failed():
    cfg = {"feeds": [FEED, {"name": "Broken", "url": "https://broken", "region": "world"},
                     {"name": "Down", "url": "https://down", "region": "world"}]}

    def fetch(url):
        if url == "https://down":
            raise ConnectionError("timeout")
        if url == "https://broken":
            return b"<html>Service unavailable</html>"
        return rss(item("Working story"))

    headlines, stats = collect_news(cfg, NOW, fetch=fetch)
    assert [h["title"] for h in headlines] == ["Working story"]
    assert stats["feeds_ok"] == 1 and stats["feeds_total"] == 3
    assert len(stats["errors"]) == 2
