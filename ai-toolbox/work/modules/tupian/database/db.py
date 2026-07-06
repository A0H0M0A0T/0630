"""
SQLite 数据库 — 历史记录存储
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional

DB_PATH = "history.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_source TEXT NOT NULL,
            image_thumb TEXT,
            result_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.commit()
    conn.close()


def save_record(image_source: str, result: dict, image_thumb: Optional[str] = None) -> int:
    """保存识别记录，返回记录 ID"""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO history (image_source, image_thumb, result_json) VALUES (?, ?, ?)",
        (image_source, image_thumb, json.dumps(result, ensure_ascii=False)),
    )
    conn.commit()
    record_id = cursor.lastrowid
    conn.close()
    return record_id


def get_all_records(page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    """分页获取历史记录"""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        "SELECT * FROM history ORDER BY id DESC LIMIT ? OFFSET ?",
        (page_size, offset),
    ).fetchall()
    conn.close()

    items = []
    for row in rows:
        item = dict(row)
        if item["result_json"]:
            item["result_json"] = json.loads(item["result_json"])
        items.append(item)

    return items, total


def get_record(record_id: int) -> Optional[dict]:
    """获取单条记录"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM history WHERE id = ?", (record_id,)).fetchone()
    conn.close()
    if row:
        item = dict(row)
        if item["result_json"]:
            item["result_json"] = json.loads(item["result_json"])
        return item
    return None


def delete_record(record_id: int) -> bool:
    """删除单条记录"""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM history WHERE id = ?", (record_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted
