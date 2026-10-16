from __future__ import annotations

import hashlib
import json
import math
import socket
import sqlite3
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus

from app.config import settings
from app.paths import ROOT, STORAGE_DIR, ensure_runtime_dirs


class StorageError(RuntimeError):
    pass


class StorageAdapter:
    """Default SQLite store. MySQL / PostgreSQL are optional plugins."""

    def __init__(self, driver: str | None = None, embedder: Callable[[str], list[float]] | None = None) -> None:
        ensure_runtime_dirs()
        self.driver = (driver or settings.storage_driver or "sqlite").lower()
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._sql_conn: Any = None
        self._embedder = embedder
        self.db_path = self._resolve_sqlite_path()
        self.connect()
        self._ensure_session_columns()

    def _ensure_session_columns(self):
        with self._lock:
            if self.driver == 'sqlite':
                columns={row['name'] for row in self._conn.execute('PRAGMA table_info(chat_records)')}
                if 'thread_id' not in columns:
                    self._conn.execute('ALTER TABLE chat_records ADD COLUMN thread_id TEXT')
                self._conn.execute('CREATE INDEX IF NOT EXISTS chat_records_session ON chat_records(thread_id, persona)')
                self._conn.commit()
            else:
                with self._sql_conn.cursor() as cur:
                    if self.driver in {'postgres','postgresql'}:
                        cur.execute('ALTER TABLE chat_records ADD COLUMN IF NOT EXISTS thread_id VARCHAR(128)')
                    else:
                        cur.execute("SHOW COLUMNS FROM chat_records LIKE 'thread_id'")
                        if not cur.fetchone():
                            cur.execute('ALTER TABLE chat_records ADD COLUMN thread_id VARCHAR(128)')

    def set_embedder(self, embedder: Callable[[str], list[float]]) -> None:
        self._embedder = embedder

    def _embed(self, text: str) -> list[float]:
        if self._embedder is not None:
            try:
                return list(self._embedder(text))
            except Exception:
                pass
        return _embed_text(text)

    def _resolve_sqlite_path(self) -> Path:
        raw = settings.get("storage", {}).get("sqlite", {}).get("path", "data/storage/agent.db")
        path = Path(raw)
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def connect(self) -> None:
        if self.driver == "sqlite":
            self._connect_sqlite()
            return
        if self.driver in {"mysql", "postgresql", "postgres"}:
            self._connect_sql_plugin()
            return
        raise StorageError(f"unsupported storage driver: {self.driver}")

    def _connect_sqlite(self) -> None:
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_sqlite_schema()

    def _connect_sql_plugin(self) -> None:
        try:
            import pymysql  # type: ignore
        except Exception:
            pymysql = None
        try:
            import psycopg2  # type: ignore
            import psycopg2.extras  # type: ignore
        except Exception:
            psycopg2 = None

        cfg = settings.get("storage", {}).get(self.driver if self.driver != "postgres" else "postgresql", {})
        if self.driver in {"postgresql", "postgres"}:
            if psycopg2 is None:
                raise StorageError("PostgreSQL plugin missing. Install psycopg2-binary first.")
            self._sql_conn = psycopg2.connect(
                host=cfg.get("host", "127.0.0.1"),
                port=int(cfg.get("port", 5432)),
                user=cfg.get("user", "postgres"),
                password=cfg.get("password", ""),
                dbname=cfg.get("database", "shizukuagent"),
            )
            self._sql_conn.autocommit = True
            self._init_postgres_schema()
            return

        if pymysql is None:
            raise StorageError("MySQL plugin missing. Install pymysql first.")
        self._sql_conn = pymysql.connect(
            host=cfg.get("host", "127.0.0.1"),
            port=int(cfg.get("port", 3306)),
            user=cfg.get("user", "root"),
            password=cfg.get("password", ""),
            database=cfg.get("database", "shizukuagent"),
            charset="utf8mb4",
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )
        self._init_mysql_schema()

    def _init_sqlite_schema(self) -> None:
        assert self._conn is not None
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chat_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                persona TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                persona TEXT NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                embedding TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checkpoints (
                thread_id TEXT NOT NULL,
                persona TEXT NOT NULL,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (thread_id, persona)
            );
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def _init_mysql_schema(self) -> None:
        sql = """
        CREATE TABLE IF NOT EXISTS chat_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            persona VARCHAR(64) NOT NULL,
            role VARCHAR(32) NOT NULL,
            content LONGTEXT NOT NULL,
            created_at VARCHAR(64) NOT NULL
        );
        CREATE TABLE IF NOT EXISTS memories (
            id INT AUTO_INCREMENT PRIMARY KEY,
            persona VARCHAR(64) NOT NULL,
            kind VARCHAR(32) NOT NULL,
            content LONGTEXT NOT NULL,
            metadata LONGTEXT,
            embedding LONGTEXT,
            created_at VARCHAR(64) NOT NULL
        );
        CREATE TABLE IF NOT EXISTS checkpoints (
            thread_id VARCHAR(128) NOT NULL,
            persona VARCHAR(64) NOT NULL,
            state_json LONGTEXT NOT NULL,
            updated_at VARCHAR(64) NOT NULL,
            PRIMARY KEY (thread_id, persona)
        );
        CREATE TABLE IF NOT EXISTS kv_store (
            `key` VARCHAR(191) PRIMARY KEY,
            value LONGTEXT NOT NULL,
            updated_at VARCHAR(64) NOT NULL
        );
        """
        with self._sql_conn.cursor() as cur:
            for statement in [item.strip() for item in sql.split(";") if item.strip()]:
                cur.execute(statement)

    def _init_postgres_schema(self) -> None:
        sql = """
        CREATE TABLE IF NOT EXISTS chat_records (
            id SERIAL PRIMARY KEY,
            persona TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS memories (
            id SERIAL PRIMARY KEY,
            persona TEXT NOT NULL,
            kind TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT,
            embedding TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS checkpoints (
            thread_id TEXT NOT NULL,
            persona TEXT NOT NULL,
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (thread_id, persona)
        );
        CREATE TABLE IF NOT EXISTS kv_store (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
        with self._sql_conn.cursor() as cur:
            cur.execute(sql)

    def _now(self) -> str:
        return datetime.utcnow().isoformat(timespec="seconds") + "Z"

    def add_chat_record(self, persona: str, role: str, content: str, thread_id: str | None = None) -> int:
        with self._lock:
            if self.driver == "sqlite":
                assert self._conn is not None
                cur = self._conn.execute(
                    "INSERT INTO chat_records(persona, role, content, created_at, thread_id) VALUES (?, ?, ?, ?, ?)",
                    (persona, role, content, self._now(), thread_id),
                )
                self._conn.commit()
                return int(cur.lastrowid)
            with self._sql_conn.cursor() as cur:
                placeholder = "%s"
                cur.execute(
                    f"INSERT INTO chat_records(persona, role, content, created_at, thread_id) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})",
                    (persona, role, content, self._now(), thread_id),
                )
                return int(getattr(cur, "lastrowid", 0) or 0)

    def list_records(self, limit: int = 200, offset: int = 0, persona: str | None = None, query: str = '') -> list[dict[str, Any]]:
        clauses, args = [], []
        if persona is not None:
            clauses.append('persona = ?')
            args.append(persona)
        if query:
            clauses.append('(content LIKE ? OR role LIKE ?)')
            args.extend([f'%{query}%', f'%{query}%'])
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        sql = 'SELECT id, persona, role, content, created_at FROM chat_records' + where + ' ORDER BY id DESC LIMIT ? OFFSET ?'
        args.extend([max(1, min(limit, 500)), max(0, offset)])
        with self._lock:
            if self.driver == "sqlite":
                assert self._conn is not None
                rows = self._conn.execute(
                    sql, args,
                ).fetchall()
                return [dict(row) for row in rows]
            with self._sql_conn.cursor() as cur:
                cur.execute(
                    sql.replace('?', '%s'), args,
                )
                rows = cur.fetchall()
                return [dict(row) for row in rows]

    def record_groups(self, query: str = '') -> list[dict[str, Any]]:
        sql = 'SELECT persona, COUNT(*) AS total FROM chat_records'
        args = []
        if query:
            sql += ' WHERE (content LIKE ? OR role LIKE ?)'
            args = [f'%{query}%', f'%{query}%']
        sql += ' GROUP BY persona ORDER BY persona'
        with self._lock:
            if self.driver == 'sqlite':
                return [dict(row) for row in self._conn.execute(sql, args).fetchall()]
            with self._sql_conn.cursor() as cur:
                cur.execute(sql.replace('?', '%s'), args)
                return [dict(row) for row in cur.fetchall()]

    def delete_record(self, record_id: int) -> bool:
        with self._lock:
            if self.driver == "sqlite":
                assert self._conn is not None
                cur = self._conn.execute("DELETE FROM chat_records WHERE id = ?", (record_id,))
                self._conn.commit()
                return cur.rowcount > 0
            with self._sql_conn.cursor() as cur:
                cur.execute("DELETE FROM chat_records WHERE id = %s", (record_id,))
                return True

    def clear_records(self) -> None:
        with self._lock:
            if self.driver == "sqlite":
                assert self._conn is not None
                self._conn.execute("DELETE FROM chat_records")
                self._conn.commit()
                return
            with self._sql_conn.cursor() as cur:
                cur.execute("DELETE FROM chat_records")

    def delete_first_n(self, n: int) -> int:
        records = self.list_records(limit=n, offset=0)
        deleted = 0
        for record in records:
            if self.delete_record(int(record["id"])):
                deleted += 1
        return deleted

    def add_memory(self, persona: str, content: str, kind: str = "long_term", metadata: dict[str, Any] | None = None) -> int:
        embedding = json.dumps(self._embed(content), ensure_ascii=False)
        payload = json.dumps(metadata or {}, ensure_ascii=False)
        with self._lock:
            if self.driver == "sqlite":
                assert self._conn is not None
                cur = self._conn.execute(
                    "INSERT INTO memories(persona, kind, content, metadata, embedding, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (persona, kind, content, payload, embedding, self._now()),
                )
                self._conn.commit()
                return int(cur.lastrowid)
            with self._sql_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO memories(persona, kind, content, metadata, embedding, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                    (persona, kind, content, payload, embedding, self._now()),
                )
                return int(getattr(cur, "lastrowid", 0) or 0)

    def list_memories(self, persona: str | None = None, kind: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query = "SELECT id, persona, kind, content, metadata, created_at FROM memories"
        conds: list[str] = []
        args: list[Any] = []
        if persona:
            conds.append("persona = ?")
            args.append(persona)
        if kind:
            conds.append("kind = ?")
            args.append(kind)
        if conds:
            query += " WHERE " + " AND ".join(conds)
        query += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            if self.driver == "sqlite":
                assert self._conn is not None
                rows = self._conn.execute(query, args).fetchall()
                result = []
                for row in rows:
                    item = dict(row)
                    item["metadata"] = _safe_json(item.get("metadata"))
                    result.append(item)
                return result
            sql = query.replace("?", "%s")
            with self._sql_conn.cursor() as cur:
                cur.execute(sql, args)
                rows = cur.fetchall()
                result = []
                for row in rows:
                    item = dict(row)
                    item["metadata"] = _safe_json(item.get("metadata"))
                    result.append(item)
                return result

    def search_memories(
        self,
        query: str,
        persona: str | None = None,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        if top_k <= 0:
            return []
        with self._lock:
            sql = "SELECT id, persona, kind, content, metadata, embedding, created_at FROM memories"
            args: list[Any] = []
            if persona:
                sql += " WHERE persona = ?"
                args.append(persona)
            if self.driver == "sqlite":
                assert self._conn is not None
                rows = self._conn.execute(sql, args).fetchall()
            else:
                with self._sql_conn.cursor() as cur:
                    cur.execute(sql.replace("?", "%s"), args)
                    rows = cur.fetchall()
        # No network request for an empty corpus; never hold the DB lock
        # while waiting on the embedding provider or scoring the snapshot.
        if not rows:
            return []
        query_vec = self._embed(query)
        scored = []
        for row in rows:
            item = dict(row)
            vec = _safe_json(item.get("embedding")) or []
            item["score"] = _cosine(query_vec, vec)
            item["metadata"] = _safe_json(item.get("metadata"))
            item.pop("embedding", None)
            scored.append(item)
        scored.sort(key=lambda x: x.get("score", 0), reverse=True)
        return [item for item in scored if item.get("score", 0) >= min_score][:top_k]

    def reindex_memories(self, persona: str | None = None, kind: str | None = None) -> int:
        """Recompute embeddings for existing memories using the current embedder."""
        items = self.list_memories(persona=persona, kind=kind, limit=100000)
        updated = 0
        for item in items:
            embedding = json.dumps(self._embed(item.get("content") or ""), ensure_ascii=False)
            with self._lock:
                if self.driver == "sqlite":
                    assert self._conn is not None
                    self._conn.execute(
                        "UPDATE memories SET embedding = ? WHERE id = ?",
                        (embedding, item["id"]),
                    )
                    self._conn.commit()
                    updated += 1
                else:
                    with self._sql_conn.cursor() as cur:
                        cur.execute(
                            "UPDATE memories SET embedding = %s WHERE id = %s",
                            (embedding, item["id"]),
                        )
                        updated += 1
        return updated

    def save_checkpoint(self, thread_id: str, persona: str, state: dict[str, Any]) -> None:
        payload = json.dumps(state, ensure_ascii=False)
        with self._lock:
            if self.driver == "sqlite":
                assert self._conn is not None
                self._conn.execute(
                    """
                    INSERT INTO checkpoints(thread_id, persona, state_json, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(thread_id, persona) DO UPDATE SET
                        state_json=excluded.state_json,
                        updated_at=excluded.updated_at
                    """,
                    (thread_id, persona, payload, self._now()),
                )
                self._conn.commit()
                return
            with self._sql_conn.cursor() as cur:
                if self.driver in {"postgresql", "postgres"}:
                    cur.execute(
                        """
                        INSERT INTO checkpoints(thread_id, persona, state_json, updated_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (thread_id, persona) DO UPDATE SET
                            state_json=EXCLUDED.state_json,
                            updated_at=EXCLUDED.updated_at
                        """,
                        (thread_id, persona, payload, self._now()),
                    )

                else:
                    cur.execute('INSERT INTO checkpoints(thread_id, persona, state_json, updated_at) VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE state_json=VALUES(state_json),updated_at=VALUES(updated_at)',(thread_id,persona,payload,self._now()))

    def delete_session(self, thread_id: str, persona: str) -> dict:
        """Delete session rows, checkpoint and explicitly session-owned memories.

        Older records lack a thread key. Match only unambiguous legacy rows,
        never delete another session's records merely because the text matches.
        """
        with self._lock:
            connection=self._conn if self.driver=='sqlite' else self._sql_conn
            if self.driver in {'postgres','postgresql'}:
                from psycopg2.extras import RealDictCursor
                cur=connection.cursor(cursor_factory=RealDictCursor)
            else:cur=connection.cursor()
            def execute(sql,args=()):
                cur.execute(sql if self.driver=='sqlite' else sql.replace('?', '%s'),args)
                return cur
            try:
                checkpoints=[dict(row) for row in execute('SELECT thread_id,state_json FROM checkpoints WHERE persona=?',(persona,)).fetchall()]
                target=next((_safe_json(row['state_json']) for row in checkpoints if row['thread_id']==thread_id),{}) or {}
                messages=target.get('messages',[])
                # Previous versions copied a session onto persona:<id>.
                aliases=[row['thread_id'] for row in checkpoints if row['thread_id']==f'persona:{persona}' and row['thread_id']!=thread_id and messages and (_safe_json(row['state_json']) or {}).get('messages')==messages]
                other_content={(m.get('role'),m.get('content')) for row in checkpoints if row['thread_id'] not in [thread_id,*aliases] for m in (_safe_json(row['state_json']) or {}).get('messages',[])}
                deleted=execute('DELETE FROM chat_records WHERE thread_id=? AND persona=?',(thread_id,persona)).rowcount
                unresolved=0
                for message in messages:
                    if message.get('record_id'):
                        deleted+=execute('DELETE FROM chat_records WHERE id=? AND persona=? AND (thread_id=? OR thread_id IS NULL)',(message['record_id'],persona,thread_id)).rowcount
                    elif (message.get('role'),message.get('content')) not in other_content:
                        rows=execute('SELECT id FROM chat_records WHERE persona=? AND role=? AND content=? AND thread_id IS NULL',(persona,message.get('role'),message.get('content'))).fetchall()
                        if len(rows)==1:
                            deleted+=execute('DELETE FROM chat_records WHERE id=?',(dict(rows[0])['id'],)).rowcount
                        elif rows:unresolved+=len(rows)
                    else:
                        unresolved+=execute('SELECT COUNT(*) AS total FROM chat_records WHERE persona=? AND role=? AND content=? AND thread_id IS NULL',(persona,message.get('role'),message.get('content'))).fetchone()['total']
                for thread in [thread_id,*aliases]:
                    execute('DELETE FROM checkpoints WHERE thread_id=? AND persona=?',(thread,persona))
                memories=0
                for row in execute('SELECT id,metadata FROM memories WHERE persona=?',(persona,)).fetchall():
                    item=dict(row)
                    if (_safe_json(item['metadata']) or {}).get('thread_id')==thread_id:
                        memories+=execute('DELETE FROM memories WHERE id=?',(item['id'],)).rowcount
                connection.commit()
                return {'records':deleted,'memories':memories,'legacy_unresolved':unresolved}
            except Exception:
                connection.rollback()
                raise
            finally:cur.close()

    def load_checkpoint(self, thread_id: str, persona: str) -> dict[str, Any] | None:
        with self._lock:
            if self.driver == "sqlite":
                assert self._conn is not None
                row = self._conn.execute(
                    "SELECT state_json FROM checkpoints WHERE thread_id = ? AND persona = ?",
                    (thread_id, persona),
                ).fetchone()
                return _safe_json(row["state_json"]) if row else None
            with self._sql_conn.cursor() as cur:
                cur.execute(
                    "SELECT state_json FROM checkpoints WHERE thread_id = %s AND persona = %s",
                    (thread_id, persona),
                )
                row = cur.fetchone()
                if not row:
                    return None
                value = row["state_json"] if isinstance(row, dict) else row[0]
                return _safe_json(value)

    def set_kv(self, key: str, value: Any) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        with self._lock:
            if self.driver == "sqlite":
                assert self._conn is not None
                self._conn.execute(
                    """
                    INSERT INTO kv_store(key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                    """,
                    (key, payload, self._now()),
                )
                self._conn.commit()
                return
            with self._sql_conn.cursor() as cur:
                if self.driver in {"postgresql", "postgres"}:
                    cur.execute(
                        """
                        INSERT INTO kv_store(key, value, updated_at)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at
                        """,
                        (key, payload, self._now()),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO kv_store(`key`, value, updated_at)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE value=VALUES(value), updated_at=VALUES(updated_at)
                        """,
                        (key, payload, self._now()),
                    )

    def get_kv(self, key: str, default: Any = None) -> Any:
        with self._lock:
            if self.driver == "sqlite":
                assert self._conn is not None
                row = self._conn.execute("SELECT value FROM kv_store WHERE key = ?", (key,)).fetchone()
                return _safe_json(row["value"]) if row else default
            with self._sql_conn.cursor() as cur:
                column = "`key`" if self.driver == "mysql" else "key"
                cur.execute(f"SELECT value FROM kv_store WHERE {column} = %s", (key,))
                row = cur.fetchone()
                if not row:
                    return default
                value = row["value"] if isinstance(row, dict) else row[0]
                parsed = _safe_json(value)
                return default if parsed is None else parsed

    def status(self) -> dict[str, Any]:
        sqlite_path = None
        if self.driver == "sqlite":
            try:
                sqlite_path = self.db_path.relative_to(ROOT).as_posix()
            except ValueError:
                sqlite_path = self.db_path.name
        return {
            "driver": self.driver,
            "sqlite_path": sqlite_path,
            "ready": True,
        }


def probe_database(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    data = dict(cfg or {})
    engine = str(data.get("engine") or settings.storage_driver or "sqlite").lower()
    host = str(data.get("host") or "")
    port = int(data.get("port") or (5432 if engine.startswith("postgres") else 3306 if engine == "mysql" else 0))
    result = {
        "engine": engine,
        "host": host,
        "port": port,
        "ping": {"ok": False, "detail": "未执行"},
        "tcp": {"ok": False, "detail": "未执行"},
        "db_login": {"ok": False, "detail": "未执行"},
        "overall_ok": False,
    }
    if engine == "sqlite":
        raw = data.get("database") or settings.get("storage", {}).get("sqlite", {}).get("path") or "data/storage/agent.db"
        path = Path(str(raw))
        if not path.is_absolute():
            path = ROOT / path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(path))
            conn.execute("SELECT 1")
            conn.close()
            result["mode"] = "local-file"
            result["path"] = str(path)
            result["file"] = {"ok": True, "detail": f"SQLite 文件可读写：{path}"}
            result["overall_ok"] = True
        except Exception as exc:
            result["mode"] = "local-file"
            result["path"] = str(path)
            result["file"] = {"ok": False, "detail": str(exc)}
        return result

    if not host:
        result["ping"] = {"ok": False, "detail": "host 为空"}
        result["tcp"] = {"ok": False, "detail": "host 为空"}
        result["db_login"] = {"ok": False, "detail": "host 为空"}
        return result

    try:
        cmd = ["ping", "-n", "1", "-w", "2000", host] if os_is_windows() else ["ping", "-c", "1", "-W", "2", host]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5, check=False)
        result["ping"] = {"ok": proc.returncode == 0, "detail": "ping 成功" if proc.returncode == 0 else ((proc.stderr or proc.stdout or "ping 失败")[:200])}
    except Exception as exc:
        result["ping"] = {"ok": False, "detail": f"ping 异常: {exc}"}

    try:
        with socket.create_connection((host, port), timeout=3):
            result["tcp"] = {"ok": True, "detail": f"TCP {host}:{port} 可达"}
    except Exception as exc:
        result["tcp"] = {"ok": False, "detail": f"TCP 连接失败: {exc}"}

    try:
        if engine.startswith("postgres"):
            import psycopg2  # type: ignore

            conn = psycopg2.connect(
                host=host,
                port=port,
                user=data.get("user") or "postgres",
                password=data.get("password") or "",
                dbname=data.get("database") or "shizukuagent",
                connect_timeout=5,
            )
            conn.close()
        else:
            import pymysql  # type: ignore

            conn = pymysql.connect(
                host=host,
                port=port,
                user=data.get("user") or "root",
                password=data.get("password") or "",
                database=data.get("database") or "shizukuagent",
                connect_timeout=5,
            )
            conn.close()
        result["db_login"] = {"ok": True, "detail": "数据库登录成功"}
    except Exception as exc:
        result["db_login"] = {"ok": False, "detail": f"数据库登录失败: {exc}"}
    result["overall_ok"] = bool(result["tcp"]["ok"] and result["db_login"]["ok"])
    return result


def os_is_windows() -> bool:
    import os

    return os.name == "nt"


def run_sql(query: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    sql = (query or "").strip()
    if not sql:
        return {"success": False, "error": "SQL 为空"}
    lowered = sql.lstrip().lower()
    if not lowered.startswith(("select", "show", "pragma", "explain", "describe", "desc")):
        return {"success": False, "error": "控制台只允许 SELECT / SHOW / PRAGMA / EXPLAIN"}
    data = dict(cfg or settings.get("database") or {})
    engine = str(data.get("engine") or settings.storage_driver or "sqlite").lower()
    try:
        if engine == "sqlite":
            raw = data.get("database") or settings.get("storage", {}).get("sqlite", {}).get("path") or "data/storage/agent.db"
            path = Path(str(raw))
            if not path.is_absolute():
                path = ROOT / path
            conn = sqlite3.connect(str(path))
            conn.row_factory = sqlite3.Row
            cur = conn.execute(sql)
            rows = [dict(row) for row in cur.fetchall()]
            conn.close()
            return {"success": True, "data": rows, "rowcount": len(rows)}
        if engine.startswith("postgres"):
            import psycopg2
            import psycopg2.extras

            conn = psycopg2.connect(
                host=data.get("host") or "127.0.0.1",
                port=int(data.get("port") or 5432),
                user=data.get("user") or "postgres",
                password=data.get("password") or "",
                dbname=data.get("database") or "shizukuagent",
                connect_timeout=5,
            )
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                rows = list(cur.fetchall())
            conn.close()
            return {"success": True, "data": rows, "rowcount": len(rows)}
        import pymysql

        conn = pymysql.connect(
            host=data.get("host") or "127.0.0.1",
            port=int(data.get("port") or 3306),
            user=data.get("user") or "root",
            password=data.get("password") or "",
                database=data.get("database") or "shizukuagent",
            connect_timeout=5,
            cursorclass=pymysql.cursors.DictCursor,
        )
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = list(cur.fetchall())
        conn.close()
        return {"success": True, "data": rows, "rowcount": len(rows)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _safe_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def _embed_text(text: str) -> list[float]:
    tokens = [part.lower() for part in text.replace("\n", " ").split() if part]
    buckets = [0.0] * 32
    if not tokens:
        return buckets
    for token in tokens:
        digest = hashlib.md5(token.encode("utf-8")).hexdigest()
        idx = int(digest[:8], 16) % 32
        buckets[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in buckets)) or 1.0
    return [v / norm for v in buckets]


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    norm_left = math.sqrt(sum(a * a for a in left)) or 1.0
    norm_right = math.sqrt(sum(b * b for b in right)) or 1.0
    return float(dot / (norm_left * norm_right))


_STORAGE: StorageAdapter | None = None


def get_storage() -> StorageAdapter:
    global _STORAGE
    if _STORAGE is None:
        _STORAGE = StorageAdapter()
    return _STORAGE
