import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

import topic_store
from topic_aggregator import (
    NEWS_SOURCE_NAMES,
    ProviderError,
    _fetch_abc_news_rss,
    _fetch_google_news_rss,
    _make_item,
    _parse_news_feed,
    _request_feed,
    analyze_items,
    fetch_topic,
    filter_feed_items,
    validate_topic,
)


class TopicAggregatorTests(unittest.TestCase):
    def test_validate_topic_normalizes_whitespace_and_rejects_empty_or_long(self):
        self.assertEqual(validate_topic("  clean   energy "), "clean energy")
        with self.assertRaises(ValueError):
            validate_topic("  ")
        with self.assertRaises(ValueError):
            validate_topic("x" * 201)

    def test_make_item_cleans_text_and_rejects_invalid_urls(self):
        item = _make_item(
            category="News",
            source="Example",
            title="A &amp; B",
            text="<b>Summary</b>",
            url="https://example.com/article",
        )
        self.assertIsNotNone(item)
        self.assertEqual(item.title, "A & B")
        self.assertEqual(item.text, "Summary")
        self.assertIsNone(
            _make_item(
                category="News",
                source="Example",
                title="No URL",
                text="",
                url="javascript:alert(1)",
            )
        )

    def test_fetch_topic_rejects_unknown_provider(self):
        for removed_source in ("Unknown", "Web & News", "Reddit", "YouTube"):
            with self.subTest(source=removed_source):
                with self.assertRaises(ValueError):
                    fetch_topic("topic", [removed_source])

    def test_only_public_no_key_news_sources_are_available(self):
        self.assertEqual(
            NEWS_SOURCE_NAMES,
            (
                "Google News RSS",
                "BBC News RSS",
                "ABC News RSS",
                "NPR News RSS",
            ),
        )

    def test_google_news_rss_fetches_by_topic_and_parses_publisher(self):
        feed = """<?xml version="1.0"?>
        <rss><channel><item>
          <title>Energy update</title>
          <link>https://news.example/article</link>
          <description>Details &amp; context</description>
          <source>Example News</source>
          <pubDate>Tue, 10 Nov 2026 01:02:03 GMT</pubDate>
        </item></channel></rss>"""
        with patch("topic_aggregator._request_feed", return_value=feed) as request:
            items, warnings = _fetch_google_news_rss("energy")

        self.assertEqual(warnings, [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source, "Example News")
        self.assertEqual(items[0].text, "Details & context")
        self.assertEqual(
            request.call_args.kwargs["params"]["q"],
            "energy",
        )

    def test_publisher_rss_filters_to_topic_and_supports_atom_links(self):
        feed = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Energy transition update</title>
            <link href="https://abc.example/energy" />
            <summary>New energy policy announced</summary>
            <updated>2026-11-10T01:02:03Z</updated>
          </entry>
          <entry>
            <title>Sports results</title>
            <link href="https://abc.example/sport" />
            <summary>Local match results</summary>
          </entry>
        </feed>"""
        with patch("topic_aggregator._request_feed", return_value=feed):
            items, warnings = _fetch_abc_news_rss("energy")

        self.assertEqual(warnings, [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source, "ABC News Australia")
        self.assertEqual(items[0].url, "https://abc.example/energy")
        self.assertEqual(items[0].published_at, "2026-11-10T01:02:03+00:00")

    def test_parse_news_feed_rejects_invalid_xml(self):
        with self.assertRaisesRegex(ProviderError, "invalid RSS/Atom"):
            _parse_news_feed("<broken", source="Test")

    def test_request_feed_reports_http_401_instead_of_returning_empty_data(self):
        response = Mock(status_code=401, ok=False, headers={})
        with patch("topic_aggregator.requests.get", return_value=response):
            with self.assertRaisesRegex(ProviderError, "HTTP 401"):
                _request_feed("https://news.example/feed.xml")

    def test_fetch_topic_records_source_selection_and_version(self):
        with patch(
            "topic_aggregator._fetch_google_news_rss",
            return_value=([], []),
        ):
            result = fetch_topic("energy", ["Google News RSS"])

        self.assertEqual(result["source_version"], 2)
        self.assertEqual(result["sources"], ["Google News RSS"])

    def test_filter_feed_items_matches_phrase_case_insensitively_and_preserves_order(self):
        items = [
            {"id": "first", "title": "Electric Vehicle Update", "text": "Battery news"},
            {"id": "second", "title": "Market notes", "text": "electric vehicle charging"},
            {"id": "third", "title": "Unrelated", "text": "Other topic"},
        ]

        self.assertEqual(
            [item["id"] for item in filter_feed_items(items, " ELECTRIC   VEHICLE ")],
            ["first", "second"],
        )
        self.assertEqual(filter_feed_items(items, "  "), items)
        self.assertEqual(filter_feed_items(items, "not found"), [])

    def test_filter_feed_items_searches_source_and_category(self):
        items = [
            {"id": "news", "title": "Update", "text": "", "source": "Daily Journal", "category": "News"},
            {"id": "comment", "title": "Update", "text": "", "source": "Forum", "category": "Community Comments"},
        ]

        self.assertEqual(
            [item["id"] for item in filter_feed_items(items, "daily journal")],
            ["news"],
        )
        self.assertEqual(
            [item["id"] for item in filter_feed_items(items, "community comments")],
            ["comment"],
        )

    def test_ai_analysis_without_key_keeps_unfiltered_items(self):
        items = [{"id": "one", "category": "News", "source": "Test", "title": "x", "text": "y"}]
        summary, remaining, error = analyze_items("topic", items, api_key="")
        self.assertIsNone(summary)
        self.assertEqual(remaining, items)
        self.assertIsNotNone(error)

    def test_ai_analysis_parses_summary_and_filters_only_known_item_ids(self):
        items = [
            {
                "id": "keep",
                "category": "News",
                "source": "Test",
                "title": "Relevant",
                "text": "Useful detail",
            },
            {
                "id": "remove",
                "category": "News",
                "source": "Test",
                "title": "Spam",
                "text": "Irrelevant promotion",
            },
        ]
        response = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"overall_sentiment":"Mixed",'
                            '"key_takeaways":["A balanced takeaway"],'
                            '"filtered_out_ids":["remove","not-in-results"],'
                            '"rationale":"Opinions differ."}'
                        )
                    }
                }
            ]
        }
        with patch("topic_aggregator._request_json", return_value=response):
            summary, remaining, error = analyze_items(
                "topic", items, api_key="test-key"
            )
        self.assertIsNone(error)
        self.assertEqual(summary["overall_sentiment"], "Mixed")
        self.assertEqual(summary["key_takeaways"], ["A balanced takeaway"])
        self.assertEqual([item["id"] for item in remaining], ["keep"])

    def test_daily_store_round_trip_and_topic_normalization(self):
        with tempfile.TemporaryDirectory() as directory:
            test_path = Path(directory) / "cache.db"
            with patch.object(topic_store, "DB_PATH", test_path):
                result = {"topic": "Test topic", "items": [], "fetched_at": "now"}
                topic_store.save_daily_result("Test   Topic", result, date(2026, 1, 2))
                loaded = topic_store.get_daily_result(" test topic ", date(2026, 1, 2))
                self.assertEqual(loaded, result)
                self.assertIsNone(topic_store.get_daily_result("test topic", date(2026, 1, 3)))


if __name__ == "__main__":
    unittest.main()
