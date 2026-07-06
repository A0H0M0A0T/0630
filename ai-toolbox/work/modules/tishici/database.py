"""
Database module - SQLite storage for generated prompts with similarity checking
"""
import sqlite3
import os
import re
from typing import List, Tuple, Optional


class PromptDatabase:
    """SQLite database for storing and matching prompt history with similarity."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "prompts.db")
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                params TEXT DEFAULT '',
                copy_count INTEGER DEFAULT 0
            )
        """)
        # Add copy_count column if upgrading from old schema
        try:
            self.conn.execute("ALTER TABLE prompts ADD COLUMN copy_count INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_prompts_content ON prompts(prompt)
        """)
        self.conn.commit()

    def add_prompt(self, prompt: str, params: str = "") -> int:
        cursor = self.conn.execute(
            "INSERT INTO prompts (prompt, params, copy_count) VALUES (?, ?, 0)",
            (prompt, params)
        )
        self.conn.commit()
        return cursor.lastrowid

    def add_prompts_batch(self, prompts: List[str], params: str = "") -> List[int]:
        ids = []
        for p in prompts:
            cur = self.conn.execute(
                "INSERT INTO prompts (prompt, params, copy_count) VALUES (?, ?, 0)",
                (p, params)
            )
            ids.append(cur.lastrowid)
        self.conn.commit()
        return ids

    def increment_copy_count(self, pid: int):
        """Increment the copy count for a prompt."""
        self.conn.execute(
            "UPDATE prompts SET copy_count = copy_count + 1 WHERE id = ?", (pid,)
        )
        self.conn.commit()

    def get_copy_count(self, pid: int) -> int:
        cursor = self.conn.execute(
            "SELECT copy_count FROM prompts WHERE id = ?", (pid,)
        )
        row = cursor.fetchone()
        return row[0] if row else 0

    def get_all_prompts(self, order_by: str = "id DESC") -> List[Tuple[int, str, str, str, int]]:
        """Returns (id, prompt, created_at, params, copy_count)"""
        safe_order = "copy_count DESC" if "copy" in order_by else "id DESC"
        cursor = self.conn.execute(
            f"SELECT id, prompt, created_at, params, copy_count FROM prompts ORDER BY {safe_order}"
        )
        return cursor.fetchall()

    def get_prompt_by_id(self, pid: int) -> Optional[Tuple[str, int]]:
        cursor = self.conn.execute(
            "SELECT prompt, copy_count FROM prompts WHERE id = ?", (pid,)
        )
        row = cursor.fetchone()
        return row if row else None

    def count_prompts(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM prompts")
        return cursor.fetchone()[0]

    def count_total_copies(self) -> int:
        cursor = self.conn.execute("SELECT COALESCE(SUM(copy_count), 0) FROM prompts")
        return cursor.fetchone()[0]

    def search_prompts(self, keyword: str) -> List[Tuple[int, str, str, str, int]]:
        cursor = self.conn.execute(
            "SELECT id, prompt, created_at, params, copy_count FROM prompts WHERE prompt LIKE ? ORDER BY id DESC",
            (f"%{keyword}%",)
        )
        return cursor.fetchall()

    def delete_prompt(self, pid: int):
        self.conn.execute("DELETE FROM prompts WHERE id = ?", (pid,))
        self.conn.commit()

    def delete_prompts_batch(self, pids: List[int]):
        """批量删除多个提示词"""
        if not pids:
            return
        placeholders = ",".join(["?"] * len(pids))
        self.conn.execute(f"DELETE FROM prompts WHERE id IN ({placeholders})", pids)
        self.conn.commit()

    def clear_all(self):
        self.conn.execute("DELETE FROM prompts")
        self.conn.execute("DELETE FROM sqlite_sequence WHERE name='prompts'")
        self.conn.commit()

    def close(self):
        self.conn.close()


class SimilarityChecker:
    """Semantic similarity checker using character overlap and TF-like scoring."""

    @staticmethod
    def _tokenize(text: str) -> set:
        """Extract meaningful tokens from Chinese/English mixed text."""
        text = text.lower()
        chinese_chars = set(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = set(re.findall(r'\b[a-z]{2,}\b', text))
        numbers = set(re.findall(r'\d+', text))
        return chinese_chars | english_words | numbers

    @staticmethod
    def _ngram_tokenize(text: str, n: int = 2) -> set:
        """Generate character n-grams for more granular similarity."""
        cleaned = re.sub(r'\s+', '', text.lower())
        return {cleaned[i:i + n] for i in range(len(cleaned) - n + 1)}

    @classmethod
    def similarity_score(cls, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts as a percentage (0.0 - 1.0).
        Combines token overlap and n-gram overlap for robustness.
        """
        if not text1 or not text2:
            return 0.0

        tokens1 = cls._tokenize(text1)
        tokens2 = cls._tokenize(text2)
        if not tokens1 or not tokens2:
            return 0.0

        token_intersection = tokens1 & tokens2
        token_union = tokens1 | tokens2
        token_sim = len(token_intersection) / len(token_union) if token_union else 0

        ngrams1 = cls._ngram_tokenize(text1, 3)
        ngrams2 = cls._ngram_tokenize(text2, 3)
        ngram_intersection = ngrams1 & ngrams2
        ngram_union = ngrams1 | ngrams2
        ngram_sim = len(ngram_intersection) / len(ngram_union) if ngram_union else 0

        final_score = 0.3 * token_sim + 0.7 * ngram_sim
        return min(final_score, 1.0)

    @classmethod
    def find_max_similarity(cls, new_prompt: str, existing_prompts: List[str]) -> Tuple[float, Optional[str]]:
        """Find the maximum similarity between a new prompt and all existing prompts."""
        if not existing_prompts:
            return 0.0, None

        max_sim = 0.0
        max_prompt = None

        for existing in existing_prompts:
            sim = cls.similarity_score(new_prompt, existing)
            if sim > max_sim:
                max_sim = sim
                max_prompt = existing

        return max_sim, max_prompt


if __name__ == "__main__":
    db = PromptDatabase(":memory:")
    db.add_prompt("测试提示词1")
    db.add_prompt("测试提示词2")
    print(f"Count: {db.count_prompts()}")
    print(f"Copies: {db.count_total_copies()}")

    checker = SimilarityChecker()
    s = checker.similarity_score("测试提示词1", "测试提示词1")
    print(f"Same text similarity: {s:.2%}")
    print("DB module OK")
