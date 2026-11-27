"""Persistent SQLite editorial memory store with 8-state lifecycle & audit log."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "editorial_memory.db"
DEFAULT_HISTORY_JSON = ROOT_DIR / "data" / "published_history.json"

VALID_STATES: tuple[str, ...] = (
    "pesquisado",
    "selecionado",
    "apresentado",
    "aprovado",
    "roteirizado",
    "produzido",
    "publicado",
    "descartado",
)

STATE_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "pesquisado": ("selecionado", "apresentado", "descartado"),
    "selecionado": ("apresentado", "aprovado", "descartado", "pesquisado"),
    "apresentado": ("aprovado", "descartado", "selecionado"),
    "aprovado": ("roteirizado", "descartado", "apresentado"),
    "roteirizado": ("produzido", "descartado", "aprovado"),
    "produzido": ("publicado", "descartado", "roteirizado"),
    "publicado": ("publicado",),  # idempotent metadata refresh only
    "descartado": ("pesquisado",),  # explicit resurrection allowed if substantive update
}

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS editorial_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    program TEXT NOT NULL DEFAULT 'segunda',
    category TEXT NOT NULL DEFAULT '',
    primary_source TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    entities_json TEXT NOT NULL DEFAULT '[]',
    keywords_json TEXT NOT NULL DEFAULT '[]',
    facts_json TEXT NOT NULL DEFAULT '[]',
    verification_json TEXT NOT NULL DEFAULT '{}',
    maturity TEXT NOT NULL DEFAULT 'unverified',
    novelty_score REAL NOT NULL DEFAULT 0.0,
    visual_brief_json TEXT NOT NULL DEFAULT '{}',
    state TEXT NOT NULL DEFAULT 'pesquisado'
        CHECK (state IN ('pesquisado','selecionado','apresentado','aprovado','roteirizado','produzido','publicado','descartado')),
    video_id TEXT NOT NULL DEFAULT '',
    supersedes_id INTEGER REFERENCES editorial_items(id),
    embedding_blob BLOB,
    embedding_model TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_editorial_items_state ON editorial_items(state);
CREATE INDEX IF NOT EXISTS idx_editorial_items_program ON editorial_items(program);

CREATE TABLE IF NOT EXISTS state_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES editorial_items(id) ON DELETE CASCADE,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL DEFAULT 'editor-chefe',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_state_transitions_item ON state_transitions(item_id);

CREATE TABLE IF NOT EXISTS publications (
    video_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    file_path TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL DEFAULT '',
    style_name TEXT NOT NULL DEFAULT '',
    style_family TEXT NOT NULL DEFAULT '',
    engines_json TEXT NOT NULL DEFAULT '[]',
    materials_json TEXT NOT NULL DEFAULT '[]',
    opus5_refs_json TEXT NOT NULL DEFAULT '[]',
    lessons TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS editorial_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    video_id TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL,
    action_rule TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(text: str) -> str:
    """Create a normalized deterministic slug from a topic title or repo name."""
    cleaned = "".join(c.lower() if c.isalnum() else "-" for c in (text or "").strip())
    parts = [p for p in cleaned.split("-") if p]
    return "-".join(parts)[:96] or f"item-{int(datetime.now(timezone.utc).timestamp())}"


def _json_loads(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except Exception:
        return fallback


class EditorialMemoryStore:
    """SQLite persistence layer for editorial discovery, lifecycle, publications & lessons."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH, history_json_path: Path = DEFAULT_HISTORY_JSON):
        self.db_path = Path(db_path)
        self.history_json_path = Path(history_json_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def _row_to_item(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "slug": row["slug"],
            "title": row["title"],
            "summary": row["summary"],
            "program": row["program"],
            "category": row["category"],
            "primary_source": row["primary_source"],
            "source_url": row["source_url"],
            "entities": _json_loads(row["entities_json"], []),
            "keywords": _json_loads(row["keywords_json"], []),
            "facts": _json_loads(row["facts_json"], []),
            "verification": _json_loads(row["verification_json"], {}),
            "maturity": row["maturity"],
            "novelty_score": row["novelty_score"],
            "visual_brief": _json_loads(row["visual_brief_json"], {}),
            "state": row["state"],
            "video_id": row["video_id"],
            "supersedes_id": row["supersedes_id"],
            "embedding_model": row["embedding_model"],
            "has_embedding": row["embedding_blob"] is not None,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def upsert_item(
        self,
        *,
        slug: str | None = None,
        title: str,
        summary: str = "",
        program: str = "segunda",
        category: str = "",
        primary_source: str = "",
        source_url: str = "",
        entities: list[str] | None = None,
        keywords: list[str] | None = None,
        facts: list[dict[str, Any]] | None = None,
        verification: dict[str, Any] | None = None,
        maturity: str = "unverified",
        novelty_score: float = 0.0,
        visual_brief: dict[str, Any] | None = None,
        initial_state: str = "pesquisado",
        video_id: str = "",
        supersedes_id: int | None = None,
        actor: str = "editor-chefe",
        reason: str = "created",
    ) -> dict[str, Any]:
        if initial_state not in VALID_STATES:
            raise ValueError(f"Estado invalido: {initial_state}")
        now = _utc_now()
        norm_slug = slugify(slug or title)
        entities_json = json.dumps(entities or [], ensure_ascii=False)
        keywords_json = json.dumps(keywords or [], ensure_ascii=False)
        facts_json = json.dumps(facts or [], ensure_ascii=False)
        verification_json = json.dumps(verification or {}, ensure_ascii=False)
        visual_json = json.dumps(visual_brief or {}, ensure_ascii=False)

        with self.connect() as conn:
            existing = conn.execute(
                "SELECT * FROM editorial_items WHERE slug = ?",
                (norm_slug,),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE editorial_items
                       SET title = COALESCE(NULLIF(?, ''), title),
                           summary = COALESCE(NULLIF(?, ''), summary),
                           program = COALESCE(NULLIF(?, ''), program),
                           category = COALESCE(NULLIF(?, ''), category),
                           primary_source = COALESCE(NULLIF(?, ''), primary_source),
                           source_url = COALESCE(NULLIF(?, ''), source_url),
                           entities_json = CASE WHEN ? != '[]' THEN ? ELSE entities_json END,
                           keywords_json = CASE WHEN ? != '[]' THEN ? ELSE keywords_json END,
                           facts_json = CASE WHEN ? != '[]' THEN ? ELSE facts_json END,
                           verification_json = CASE WHEN ? != '{}' THEN ? ELSE verification_json END,
                           maturity = COALESCE(NULLIF(?, ''), maturity),
                           novelty_score = CASE WHEN ? > 0 THEN ? ELSE novelty_score END,
                           visual_brief_json = CASE WHEN ? != '{}' THEN ? ELSE visual_brief_json END,
                           video_id = COALESCE(NULLIF(?, ''), video_id),
                           updated_at = ?
                     WHERE id = ?
                    """,
                    (
                        title,
                        summary,
                        program,
                        category,
                        primary_source,
                        source_url,
                        entities_json,
                        entities_json,
                        keywords_json,
                        keywords_json,
                        facts_json,
                        facts_json,
                        verification_json,
                        verification_json,
                        maturity,
                        novelty_score,
                        novelty_score,
                        visual_json,
                        visual_json,
                        video_id,
                        now,
                        existing["id"],
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM editorial_items WHERE id = ?",
                    (existing["id"],),
                ).fetchone()
                return self._row_to_item(row)

            cur = conn.execute(
                """
                INSERT INTO editorial_items (
                    slug, title, summary, program, category, primary_source, source_url,
                    entities_json, keywords_json, facts_json, verification_json, maturity,
                    novelty_score, visual_brief_json, state, video_id, supersedes_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    norm_slug,
                    title.strip(),
                    summary.strip(),
                    program,
                    category,
                    primary_source,
                    source_url,
                    entities_json,
                    keywords_json,
                    facts_json,
                    verification_json,
                    maturity,
                    float(novelty_score or 0.0),
                    visual_json,
                    initial_state,
                    video_id,
                    supersedes_id,
                    now,
                    now,
                ),
            )
            item_id = int(cur.lastrowid)
            conn.execute(
                """
                INSERT INTO state_transitions (item_id, from_state, to_state, reason, actor, created_at)
                VALUES (?, '', ?, ?, ?, ?)
                """,
                (item_id, initial_state, reason, actor, now),
            )
            row = conn.execute("SELECT * FROM editorial_items WHERE id = ?", (item_id,)).fetchone()
            return self._row_to_item(row)

    def get_item(self, item_id_or_slug: int | str) -> dict[str, Any] | None:
        with self.connect() as conn:
            if isinstance(item_id_or_slug, int) or str(item_id_or_slug).isdigit():
                row = conn.execute(
                    "SELECT * FROM editorial_items WHERE id = ?",
                    (int(item_id_or_slug),),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM editorial_items WHERE slug = ?",
                    (slugify(str(item_id_or_slug)),),
                ).fetchone()
            return self._row_to_item(row) if row else None

    def list_items(
        self,
        *,
        states: tuple[str, ...] | list[str] | None = None,
        program: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM editorial_items WHERE 1=1"
        params: list[Any] = []
        if states:
            placeholders = ",".join("?" for _ in states)
            query += f" AND state IN ({placeholders})"
            params.extend(states)
        if program:
            query += " AND program = ?"
            params.append(program)
        query += " ORDER BY updated_at DESC, id DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_item(r) for r in rows]

    def transition(
        self,
        item_id_or_slug: int | str,
        to_state: str,
        *,
        reason: str = "",
        actor: str = "editor-chefe",
        video_id: str = "",
        force: bool = False,
    ) -> dict[str, Any]:
        if to_state not in VALID_STATES:
            raise ValueError(f"Estado alvo invalido '{to_state}'. Validos: {', '.join(VALID_STATES)}")
        item = self.get_item(item_id_or_slug)
        if not item:
            raise KeyError(f"Item nao encontrado: {item_id_or_slug}")
        from_state = item["state"]
        allowed = STATE_TRANSITIONS.get(from_state, ())
        if not force and to_state != from_state and to_state not in allowed:
            raise ValueError(
                f"Transicao nao permitida '{from_state}' -> '{to_state}'. "
                f"Permitidas a partir de '{from_state}': {', '.join(allowed)}"
            )
        now = _utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE editorial_items
                   SET state = ?,
                       video_id = COALESCE(NULLIF(?, ''), video_id),
                       updated_at = ?
                 WHERE id = ?
                """,
                (to_state, video_id, now, item["id"]),
            )
            conn.execute(
                """
                INSERT INTO state_transitions (item_id, from_state, to_state, reason, actor, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (item["id"], from_state, to_state, reason or f"{from_state} -> {to_state}", actor, now),
            )
        return self.get_item(item["id"])  # type: ignore[return-value]

    def get_transitions(self, item_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM state_transitions WHERE item_id = ? ORDER BY id ASC",
                (item_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_verification(
        self,
        item_id: int,
        verification: dict[str, Any],
        maturity: str,
        facts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        now = _utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE editorial_items
                   SET verification_json = ?,
                       maturity = ?,
                       facts_json = CASE WHEN ? IS NOT NULL THEN ? ELSE facts_json END,
                       updated_at = ?
                 WHERE id = ?
                """,
                (
                    json.dumps(verification, ensure_ascii=False),
                    maturity,
                    json.dumps(facts, ensure_ascii=False) if facts is not None else None,
                    json.dumps(facts, ensure_ascii=False) if facts is not None else "[]",
                    now,
                    item_id,
                ),
            )
        return self.get_item(item_id)  # type: ignore[return-value]

    def save_visual_brief(self, item_id: int, brief: dict[str, Any]) -> dict[str, Any]:
        now = _utc_now()
        with self.connect() as conn:
            conn.execute(
                "UPDATE editorial_items SET visual_brief_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(brief, ensure_ascii=False), now, item_id),
            )
        return self.get_item(item_id)  # type: ignore[return-value]

    def save_embedding(self, item_id: int, blob: bytes, model_name: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE editorial_items SET embedding_blob = ?, embedding_model = ? WHERE id = ?",
                (sqlite3.Binary(blob), model_name, item_id),
            )

    def fetch_raw_embeddings(self, states: tuple[str, ...] | None = None) -> list[sqlite3.Row]:
        query = "SELECT id, slug, title, summary, entities_json, keywords_json, state, video_id, embedding_blob, embedding_model FROM editorial_items"
        params: list[Any] = []
        if states:
            placeholders = ",".join("?" for _ in states)
            query += f" WHERE state IN ({placeholders})"
            params.extend(states)
        with self.connect() as conn:
            return conn.execute(query, params).fetchall()

    def record_publication(
        self,
        *,
        video_id: str,
        title: str,
        url: str = "",
        file_path: str = "",
        published_at: str = "",
        style_name: str = "",
        style_family: str = "",
        engines: list[str] | None = None,
        materials: list[str] | None = None,
        opus5_refs: list[str] | None = None,
        lessons: str = "",
    ) -> None:
        now = _utc_now()
        pub_at = published_at or now
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO publications (
                    video_id, title, url, file_path, published_at,
                    style_name, style_family, engines_json, materials_json,
                    opus5_refs_json, lessons, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    title = excluded.title,
                    url = COALESCE(NULLIF(excluded.url, ''), publications.url),
                    file_path = COALESCE(NULLIF(excluded.file_path, ''), publications.file_path),
                    published_at = COALESCE(NULLIF(excluded.published_at, ''), publications.published_at),
                    style_name = COALESCE(NULLIF(excluded.style_name, ''), publications.style_name),
                    style_family = COALESCE(NULLIF(excluded.style_family, ''), publications.style_family),
                    engines_json = CASE WHEN excluded.engines_json != '[]' THEN excluded.engines_json ELSE publications.engines_json END,
                    materials_json = CASE WHEN excluded.materials_json != '[]' THEN excluded.materials_json ELSE publications.materials_json END,
                    opus5_refs_json = CASE WHEN excluded.opus5_refs_json != '[]' THEN excluded.opus5_refs_json ELSE publications.opus5_refs_json END,
                    lessons = COALESCE(NULLIF(excluded.lessons, ''), publications.lessons)
                """,
                (
                    video_id,
                    title,
                    url,
                    file_path,
                    pub_at,
                    style_name,
                    style_family,
                    json.dumps(engines or [], ensure_ascii=False),
                    json.dumps(materials or [], ensure_ascii=False),
                    json.dumps(opus5_refs or [], ensure_ascii=False),
                    lessons,
                    now,
                ),
            )
            if lessons.strip():
                existing_ins = conn.execute(
                    "SELECT id FROM editorial_insights WHERE video_id = ? AND summary = ?",
                    (video_id, lessons.strip()),
                ).fetchone()
                if not existing_ins:
                    conn.execute(
                        """
                        INSERT INTO editorial_insights (category, video_id, summary, action_rule, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        ("production_lesson", video_id, lessons.strip(), "", now),
                    )

    def add_insight(
        self,
        *,
        category: str,
        summary: str,
        action_rule: str = "",
        video_id: str = "",
    ) -> dict[str, Any]:
        now = _utc_now()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO editorial_insights (category, video_id, summary, action_rule, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (category.strip(), video_id.strip(), summary.strip(), action_rule.strip(), now),
            )
            row = conn.execute("SELECT * FROM editorial_insights WHERE id = ?", (cur.lastrowid,)).fetchone()
            return dict(row)

    def list_insights(self, limit: int = 30) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM editorial_insights ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_publications(self, limit: int = 30) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM publications ORDER BY published_at DESC, created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            results: list[dict[str, Any]] = []
            for r in rows:
                results.append(
                    {
                        "video_id": r["video_id"],
                        "title": r["title"],
                        "url": r["url"],
                        "file_path": r["file_path"],
                        "published_at": r["published_at"],
                        "style_name": r["style_name"],
                        "style_family": r["style_family"],
                        "engines": _json_loads(r["engines_json"], []),
                        "materials": _json_loads(r["materials_json"], []),
                        "opus5_refs": _json_loads(r["opus5_refs_json"], []),
                        "lessons": r["lessons"],
                    }
                )
            return results

    def migrate_from_published_history(self, history_path: Path | None = None) -> dict[str, int]:
        """Idempotently import all videos & topics from published_history.json into SQLite."""
        src = Path(history_path or self.history_json_path)
        if not src.exists():
            return {"videos": 0, "topics_imported": 0}
        data = json.loads(src.read_text(encoding="utf-8"))
        videos = data.get("videos", [])
        imported_topics = 0
        for v in videos:
            vid = str(v.get("video_id", "")).strip()
            if not vid:
                continue
            style = v.get("visual_style") or {}
            self.record_publication(
                video_id=vid,
                title=v.get("title", ""),
                url=v.get("url", ""),
                file_path=v.get("file", ""),
                published_at=v.get("published_at", ""),
                style_name=style.get("name", ""),
                style_family=style.get("family", ""),
                engines=style.get("engines", []),
                materials=style.get("materials", []),
                opus5_refs=style.get("opus5_refs", []),
                lessons=v.get("lessons", ""),
            )
            for t in v.get("topics", []):
                if isinstance(t, str):
                    t_slug = slugify(t)
                    t_title = t
                    t_cat = ""
                    t_entities = [t]
                    t_kw: list[str] = []
                else:
                    t_title = str(t.get("title") or t.get("slug") or "").strip()
                    t_slug = slugify(str(t.get("slug") or t_title))
                    t_cat = str(t.get("category") or "")
                    t_entities = list(t.get("entities") or [])
                    t_kw = list(t.get("keywords") or [])
                if not t_title:
                    continue
                existed = self.get_item(t_slug)
                item = self.upsert_item(
                    slug=t_slug,
                    title=t_title,
                    summary=f"Publicado em {vid}: {t_title}",
                    program="segunda" if "GitHub" in v.get("title", "") or "/" in " ".join(t_entities) else "domingo",
                    category=t_cat,
                    primary_source="published_history",
                    source_url=v.get("url", ""),
                    entities=t_entities,
                    keywords=t_kw,
                    maturity="verified_release",
                    initial_state="publicado",
                    video_id=vid,
                    actor="migration",
                    reason=f"Migrated from {src.name} ({vid})",
                )
                if item["state"] != "publicado":
                    self.transition(
                        item["id"],
                        "publicado",
                        reason=f"Synced published video {vid}",
                        actor="migration",
                        video_id=vid,
                        force=True,
                    )
                if not existed:
                    imported_topics += 1
        return {"videos": len(videos), "topics_imported": imported_topics}

    def stats(self) -> dict[str, Any]:
        with self.connect() as conn:
            state_counts = {
                row["state"]: row["cnt"]
                for row in conn.execute(
                    "SELECT state, COUNT(*) AS cnt FROM editorial_items GROUP BY state"
                ).fetchall()
            }
            pubs = conn.execute("SELECT COUNT(*) FROM publications").fetchone()[0]
            ins = conn.execute("SELECT COUNT(*) FROM editorial_insights").fetchone()[0]
            trans = conn.execute("SELECT COUNT(*) FROM state_transitions").fetchone()[0]
        return {
            "db_path": str(self.db_path),
            "by_state": state_counts,
            "total_items": sum(state_counts.values()),
            "publications": pubs,
            "insights": ins,
            "state_transitions": trans,
        }
