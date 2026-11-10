"""Small SQLite cache for daily topic searches."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).with_name("topic_aggregator.db")


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DB_PATH, timeout=10)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_topic_results (
                topic_key TEXT NOT NULL,
                run_date TEXT NOT NULL,
                topic TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                result_json TEXT NOT NULL,
                PRIMARY KEY (topic_key, run_date)
            )
            """
        )
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _topic_key(topic: str) -> str:
    return " ".join(topic.casefold().split())


def get_daily_result(topic: str, run_date: date | None = None) -> dict[str, Any] | None:
    run_date = run_date or date.today()
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT result_json
            FROM daily_topic_results
            WHERE topic_key = ? AND run_date = ?
            """,
            (_topic_key(topic), run_date.isoformat()),
        ).fetchone()
    return json.loads(row[0]) if row else None


def save_daily_result(
    topic: str,
    result: dict[str, Any],
    run_date: date | None = None,
) -> None:
    run_date = run_date or date.today()
    fetched_at = result.get("fetched_at", "")
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO daily_topic_results
                (topic_key, run_date, topic, fetched_at, result_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(topic_key, run_date) DO UPDATE SET
                topic = excluded.topic,
                fetched_at = excluded.fetched_at,
                result_json = excluded.result_json
            """,
            (
                _topic_key(topic),
                run_date.isoformat(),
                topic,
                fetched_at,
                json.dumps(result, ensure_ascii=False),
            ),
        )
