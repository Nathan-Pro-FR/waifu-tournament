import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("La variable DATABASE_URL est manquante dans le fichier .env")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Table des personnages (waifus)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS waifus (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    series TEXT NOT NULL,
                    image_url TEXT,
                    proposed_by BIGINT NOT NULL,
                    wins INTEGER DEFAULT 0
                )
            """)
            # Table des duels
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS duels (
                    id SERIAL PRIMARY KEY,
                    waifu1_id INTEGER NOT NULL REFERENCES waifus (id),
                    waifu2_id INTEGER NOT NULL REFERENCES waifus (id),
                    status TEXT DEFAULT 'open',
                    winner_id INTEGER REFERENCES waifus (id)
                )
            """)
            # Table des votes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS votes (
                    duel_id INTEGER NOT NULL REFERENCES duels (id),
                    user_id BIGINT NOT NULL,
                    waifu_id INTEGER NOT NULL REFERENCES waifus (id),
                    PRIMARY KEY (duel_id, user_id)
                )
            """)
        conn.commit()


def add_waifu(name: str, series: str, image_url: Optional[str], user_id: int) -> bool:
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO waifus (name, series, image_url, proposed_by) VALUES (%s, %s, %s, %s)",
                    (name.strip(), series.strip(), image_url, user_id),
                )
            conn.commit()
        return True
    except psycopg2.IntegrityError:
        return False


def get_all_waifus() -> List[dict]:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM waifus ORDER BY wins DESC, name ASC")
            return cursor.fetchall()


def create_duel(waifu1_id: int, waifu2_id: int) -> Optional[int]:
    if waifu1_id == waifu2_id:
        return None
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE duels SET status = 'closed' WHERE status = 'open'")
            cursor.execute(
                "INSERT INTO duels (waifu1_id, waifu2_id, status) VALUES (%s, %s, 'open') RETURNING id",
                (waifu1_id, waifu2_id),
            )
            duel_id = cursor.fetchone()["id"]
        conn.commit()
        return duel_id


def get_active_duel() -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM duels WHERE status = 'open' ORDER BY id DESC LIMIT 1")
            duel = cursor.fetchone()
            if not duel:
                return None

            cursor.execute("SELECT * FROM waifus WHERE id = %s", (duel["waifu1_id"],))
            w1 = cursor.fetchone()
            cursor.execute("SELECT * FROM waifus WHERE id = %s", (duel["waifu2_id"],))
            w2 = cursor.fetchone()

            cursor.execute(
                "SELECT COUNT(*) AS count FROM votes WHERE duel_id = %s AND waifu_id = %s",
                (duel["id"], w1["id"]),
            )
            v1 = cursor.fetchone()["count"]

            cursor.execute(
                "SELECT COUNT(*) AS count FROM votes WHERE duel_id = %s AND waifu_id = %s",
                (duel["id"], w2["id"]),
            )
            v2 = cursor.fetchone()["count"]

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
        with conn.cursor() as cursor:
            if status == "open":
                cursor.execute("UPDATE duels SET status = 'closed' WHERE status = 'open'")
            cursor.execute("UPDATE duels SET status = %s WHERE id = %s", (status, duel_id))
            updated = cursor.rowcount > 0
        conn.commit()
        return updated


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
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE duels SET status = 'closed', winner_id = %s WHERE id = %s",
                (winner_id, duel["id"]),
            )
            if winner_id:
                cursor.execute("UPDATE waifus SET wins = wins + 1 WHERE id = %s", (winner_id,))
        conn.commit()

    duel["winner_id"] = winner_id
    return duel


def cast_vote(duel_id: int, user_id: int, waifu_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT status FROM duels WHERE id = %s", (duel_id,))
            duel = cursor.fetchone()
            if not duel or duel["status"] != "open":
                return False

            cursor.execute(
                """
                INSERT INTO votes (duel_id, user_id, waifu_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (duel_id, user_id) DO UPDATE SET waifu_id = EXCLUDED.waifu_id
                """,
                (duel_id, user_id, waifu_id),
            )
        conn.commit()
        return True
