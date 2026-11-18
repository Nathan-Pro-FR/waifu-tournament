import sqlite3
from typing import Optional, List, Tuple

DB_NAME = "tournament.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        # Table des personnages (waifus)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS waifus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                series TEXT NOT NULL,
                image_url TEXT,
                proposed_by INTEGER NOT NULL,
                wins INTEGER DEFAULT 0
            )
        """)
        # Table des duels
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS duels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                waifu1_id INTEGER NOT NULL,
                waifu2_id INTEGER NOT NULL,
                status TEXT DEFAULT 'open', -- 'open' ou 'closed'
                winner_id INTEGER,
                FOREIGN KEY (waifu1_id) REFERENCES waifus (id),
                FOREIGN KEY (waifu2_id) REFERENCES waifus (id)
            )
        """)
        # Table des votes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                duel_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                waifu_id INTEGER NOT NULL,
                PRIMARY KEY (duel_id, user_id),
                FOREIGN KEY (duel_id) REFERENCES duels (id),
                FOREIGN KEY (waifu_id) REFERENCES waifus (id)
            )
        """)
        conn.commit()


def add_waifu(name: str, series: str, image_url: Optional[str], user_id: int) -> bool:
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO waifus (name, series, image_url, proposed_by) VALUES (?, ?, ?, ?)",
                (name.strip(), series.strip(), image_url, user_id),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def get_all_waifus() -> List[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM waifus ORDER BY wins DESC, name ASC").fetchall()


def create_duel(waifu1_id: int, waifu2_id: int) -> Optional[int]:
    if waifu1_id == waifu2_id:
        return None
    with get_connection() as conn:
        # Ferme automatiquement tout autre duel ouvert pour éviter les conflits
        conn.execute("UPDATE duels SET status = 'closed' WHERE status = 'open'")
        cursor = conn.execute(
            "INSERT INTO duels (waifu1_id, waifu2_id, status) VALUES (?, ?, 'open')",
            (waifu1_id, waifu2_id),
        )
        conn.commit()
        return cursor.lastrowid


def get_active_duel() -> Optional[dict]:
    with get_connection() as conn:
        duel = conn.execute("SELECT * FROM duels WHERE status = 'open' ORDER BY id DESC LIMIT 1").fetchone()
        if not duel:
            return None

        w1 = conn.execute("SELECT * FROM waifus WHERE id = ?", (duel["waifu1_id"],)).fetchone()
        w2 = conn.execute("SELECT * FROM waifus WHERE id = ?", (duel["waifu2_id"],)).fetchone()

        v1 = conn.execute(
            "SELECT COUNT(*) FROM votes WHERE duel_id = ? AND waifu_id = ?", (duel["id"], w1["id"])
        ).fetchone()[0]
        v2 = conn.execute(
            "SELECT COUNT(*) FROM votes WHERE duel_id = ? AND waifu_id = ?", (duel["id"], w2["id"])
        ).fetchone()[0]

        return {
            "id": duel["id"],
            "status": duel["status"],
            "waifu1": dict(w1),
            "waifu2": dict(w2),
            "votes1": v1,
            "votes2": v2,
        }


def set_duel_status(duel_id: int, status: str) -> bool:
    with get_connection() as conn:
        if status == "open":
            conn.execute("UPDATE duels SET status = 'closed' WHERE status = 'open'")
        cursor = conn.execute("UPDATE duels SET status = ? WHERE id = ?", (status, duel_id))
        conn.commit()
        return cursor.rowcount > 0


def close_active_duel() -> Optional[dict]:
    duel = get_active_duel()
    if not duel:
        return None

    w1, w2 = duel["waifu1"], duel["waifu2"]
    v1, v2 = duel["votes1"], duel["votes2"]

    winner_id = None
    if v1 > v2:
        winner_id = w1["id"]
    elif v2 > v1:
        winner_id = w2["id"]

    with get_connection() as conn:
        conn.execute(
            "UPDATE duels SET status = 'closed', winner_id = ? WHERE id = ?",
            (winner_id, duel["id"]),
        )
        if winner_id:
            conn.execute("UPDATE waifus SET wins = wins + 1 WHERE id = ?", (winner_id,))
        conn.commit()

    duel["winner_id"] = winner_id
    return duel


def cast_vote(duel_id: int, user_id: int, waifu_id: int) -> bool:
    with get_connection() as conn:
        duel = conn.execute("SELECT status FROM duels WHERE id = ?", (duel_id,)).fetchone()
        if not duel or duel["status"] != "open":
            return False

        conn.execute(
            """
            INSERT INTO votes (duel_id, user_id, waifu_id)
            VALUES (?, ?, ?)
            ON CONFLICT(duel_id, user_id) DO UPDATE SET waifu_id = excluded.waifu_id
            """,
            (duel_id, user_id, waifu_id),
        )
        conn.commit()
        return True
