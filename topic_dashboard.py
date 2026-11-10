"""Streamlit UI for the Daily Topic Aggregator."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import streamlit as st

from topic_aggregator import (
    NEWS_SOURCE_NAMES,
    SOURCE_VERSION,
    analyze_items,
    fetch_topic,
    filter_feed_items,
    validate_topic,
)
from topic_store import get_daily_result, save_daily_result

st.set_page_config(
    page_title="Daily Topic Brief",
    page_icon="🗞️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: #f5f7fb; }
    [data-testid="stSidebar"] { background: #101827; }
    [data-testid="stSidebar"] * { color: #e8edf5; }
    .hero-kicker { color: #526179; font-size: .82rem; font-weight: 700;
                   letter-spacing: .12em; text-transform: uppercase; }
    .hero-title { color: #101827; font-size: 2.45rem; font-weight: 750;
                  letter-spacing: -.04em; margin: .15rem 0 .25rem; }
    .hero-subtitle { color: #63718a; margin-bottom: 1.2rem; }
    div[data-testid="stMetric"] {
      background: white; border: 1px solid #e4e9f1; border-radius: 14px;
      padding: 14px 18px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _secret(name: str) -> str:
    value = os.getenv(name, "")
    if value:
        return value
    try:
        value = st.secrets.get(name, "")
    except st.errors.StreamlitSecretNotFoundError:
        value = ""
    return str(value).strip()


def _demo_result(topic: str) -> dict[str, Any]:
    """Clearly labeled, fictional records for previewing the layout."""
    records = [
        {
            "id": "sample-news-1",
            "category": "News",
            "source": "Sample article",
            "title": f"How {topic} is shaping today's discussion",
            "text": "A fictional preview article used to demonstrate the dashboard layout.",
            "url": "https://example.com/sample-news",
            "published_at": None,
        },
        {
            "id": "sample-news-2",
            "category": "News",
            "source": "Sample analysis",
            "title": "Explainers and perspectives from across the web",
            "text": "This placeholder is not a real search result or a factual claim.",
            "url": "https://example.com/sample-analysis",
            "published_at": None,
        },
    ]
    return {
        "topic": topic,
        "items": records,
        "summary": {
            "overall_sentiment": "Mixed",
            "key_takeaways": [
                "The sample includes both opportunities and concerns.",
                "Look for corroboration across independent news sources.",
                "These fictional preview points are not findings about the topic.",
            ],
            "rationale": "Synthetic preview content only; no sources were queried.",
        },
        "provider_errors": {},
        "provider_warnings": {},
        "ai_error": None,
        "fetched_at": datetime.now().astimezone().isoformat(),
        "is_preview": True,
    }


def _render_item(item: dict[str, Any]) -> None:
    with st.container(border=True):
        st.caption(
            f"{item.get('source', 'Source')} "
            + (f"· {item['published_at']}" if item.get("published_at") else "")
        )
        st.markdown(f"**{item.get('title') or 'Comment'}**")
        if item.get("text"):
            st.write(item["text"])
        st.link_button("Open source", item["url"])


def _render_result(result: dict[str, Any]) -> None:
    if result.get("is_preview"):
        st.warning(
            "Preview mode — all displayed records and summary points are fictional "
            "examples. No web sources were queried."
        )

    items = result.get("items", [])
    summary = result.get("summary")
    search_query = st.text_input(
        "Search this feed",
        type="search",
        placeholder="Search titles, text, sources, or categories",
        key="feed_search",
    )
    visible_items = filter_feed_items(items, search_query or "")
    if search_query:
        st.caption(f"Showing {len(visible_items)} of {len(items)} feed items")

    st.markdown("### Daily overview")
    with st.container(border=True):
        if summary:
            st.metric("Overall sentiment", summary["overall_sentiment"])
            if summary.get("rationale"):
                st.caption(summary["rationale"])
            for takeaway in summary.get("key_takeaways", []):
                st.markdown(f"- {takeaway}")
        else:
            st.info(
                result.get("ai_error")
                or "AI summary is unavailable. Configure OPENAI_API_KEY to enable it."
            )

    if result.get("provider_errors"):
        with st.expander("Source connection issues", expanded=True):
            for source, error in result["provider_errors"].items():
                st.error(f"**{source}:** {error}")
    if result.get("provider_warnings"):
        with st.expander("Source notes"):
            for source, messages in result["provider_warnings"].items():
                for message in messages:
                    st.warning(f"**{source}:** {message}")

    st.markdown("### News feed")
    st.metric("Articles", len(visible_items))
    if search_query and not visible_items:
        st.info(f'No articles match "{search_query}". Clear the search to see all articles.')
    elif not visible_items:
        st.info("No articles were returned. Check source notes or try another topic.")
    else:
        for item in visible_items:
            _render_item(item)

    fetched_at = result.get("fetched_at")
    if fetched_at:
        st.caption(f"Last fetched: {fetched_at}")


def _render_app() -> None:
    credentials = {
        "OPENAI_API_KEY": _secret("OPENAI_API_KEY"),
        "OPENAI_MODEL": _secret("OPENAI_MODEL"),
    }

    with st.sidebar:
        st.markdown("## 🗞️ Daily brief")
        st.caption("Public news feeds · no source signup or API key required")
        st.markdown("**Public news feeds**")
        for source in NEWS_SOURCE_NAMES:
            st.write(source)
        st.caption(
            "Reviews and public comments are not included: their sources require "
            "restricted APIs or account access."
        )
        st.markdown("**OpenAI summary**")
        if credentials["OPENAI_API_KEY"]:
            st.success("API key configured")
            st.caption("A live source is also needed to summarize real results.")
        else:
            st.caption("Optional; add OPENAI_API_KEY to enable summaries.")

    st.markdown('<div class="hero-kicker">Your web briefing</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-title">Daily Topic Aggregator</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">A topic-focused news brief from public feeds, '
        "with an optional AI-generated summary.</div>",
        unsafe_allow_html=True,
    )

    if "topic_result" not in st.session_state:
        st.session_state.topic_result = _demo_result("AI regulation")
    if "topic_value" not in st.session_state:
        st.session_state.topic_value = "AI regulation"

    with st.form("topic_search", clear_on_submit=False):
        topic = st.text_input(
            "Topic of the day",
            value=st.session_state.topic_value,
            max_chars=200,
            placeholder="For example: electric vehicle charging",
        )
        selected = []
        for start in range(0, len(NEWS_SOURCE_NAMES), 3):
            source_columns = st.columns(min(3, len(NEWS_SOURCE_NAMES) - start))
            for column, source in zip(
                source_columns, NEWS_SOURCE_NAMES[start : start + 3]
            ):
                with column:
                    enabled = st.checkbox(
                        source,
                        value=True,
                        help="Public feed; no account or API key required.",
                    )
                    if enabled:
                        selected.append(source)
        use_cache = st.checkbox("Use today's cached results when available", value=True)
        submitted = st.form_submit_button(
            "Search public news feeds",
            type="primary",
            use_container_width=True,
        )

    preview_col, _ = st.columns([1, 4])
    with preview_col:
        if st.button("Load preview examples", use_container_width=True):
            try:
                normalized = validate_topic(topic)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state.topic_value = normalized
                st.session_state.feed_search = ""
                st.session_state.topic_result = _demo_result(normalized)
                st.rerun()

    if submitted:
        try:
            normalized = validate_topic(topic)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state.topic_value = normalized
            if not selected:
                st.error(
                    "Select at least one public news source or use the preview examples."
                )
            else:
                cached = get_daily_result(normalized) if use_cache else None
                if cached:
                    cached_sources = cached.get("sources")
                    sources_match = (
                        isinstance(cached_sources, list)
                        and all(isinstance(source, str) for source in cached_sources)
                        and set(cached_sources) == set(selected)
                    )
                    if (
                        cached.get("source_version") != SOURCE_VERSION
                        or not sources_match
                    ):
                        cached = None
                if cached:
                    st.session_state.feed_search = ""
                    st.session_state.topic_result = cached
                    st.toast("Loaded today's cached results.")
                else:
                    with st.spinner("Searching selected sources and preparing the brief…"):
                        result = fetch_topic(normalized, selected)
                        summary, filtered_items, ai_error = analyze_items(
                            normalized,
                            result["items"],
                            api_key=credentials["OPENAI_API_KEY"],
                            model=credentials["OPENAI_MODEL"],
                        )
                        result.update(
                            {
                                "items": filtered_items,
                                "summary": summary,
                                "ai_error": ai_error,
                                "is_preview": False,
                            }
                        )
                        if not result["provider_errors"]:
                            save_daily_result(normalized, result)
                        st.session_state.feed_search = ""
                        st.session_state.topic_result = result

    if st.session_state.topic_result:
        current_result = st.session_state.topic_result
        if credentials["OPENAI_API_KEY"] and current_result.get("is_preview"):
            st.info(
                "OpenAI is configured. This is sample preview content, so it has "
                "not been sent for analysis. Search a public news feed to generate "
                "a summary from live results."
            )
        elif credentials["OPENAI_API_KEY"] and not current_result.get("items"):
            st.info(
                "OpenAI is configured, but there are no live news items to summarize."
            )
        if (
            credentials["OPENAI_API_KEY"]
            and not current_result.get("is_preview")
            and current_result.get("items")
        ):
            button_label = (
                "Refresh AI summary"
                if current_result.get("summary")
                else "Generate AI summary"
            )
            st.caption(
                "AI analysis sends up to 35 collected item excerpts to OpenAI. "
                "This may use your OpenAI API quota."
            )
            if st.button(button_label, type="secondary"):
                with st.spinner("Analyzing the collected feed with OpenAI…"):
                    summary, filtered_items, ai_error = analyze_items(
                        current_result["topic"],
                        current_result["items"],
                        api_key=credentials["OPENAI_API_KEY"],
                        model=credentials["OPENAI_MODEL"],
                    )
                current_result.update(
                    {
                        "summary": summary,
                        "items": filtered_items,
                        "ai_error": ai_error,
                    }
                )
                st.session_state.topic_result = current_result
                if not current_result.get("provider_errors"):
                    save_daily_result(current_result["topic"], current_result)
                st.rerun()

        _render_result(current_result)


_render_app()
