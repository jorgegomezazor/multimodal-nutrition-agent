import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "nutrivision.db"

_COLS_USER = ["email", "age", "sex", "weight_kg", "height_cm",
              "activity_level", "objective", "allergies"]
_COLS_LOG = ["id", "meal_type", "calories", "protein_g", "carbs_g",
             "fat_g", "ingredients_json"]


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db() -> None:
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                email          TEXT PRIMARY KEY,
                age            INTEGER DEFAULT 25,
                sex            TEXT    DEFAULT 'hombre',
                weight_kg      REAL    DEFAULT 70.0,
                height_cm      REAL    DEFAULT 170.0,
                activity_level TEXT    DEFAULT 'moderado',
                objective      TEXT    DEFAULT 'mantenimiento',
                allergies      TEXT    DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meal_logs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                email            TEXT    NOT NULL,
                date             TEXT    NOT NULL,
                meal_type        TEXT    NOT NULL,
                calories         REAL    DEFAULT 0,
                protein_g        REAL    DEFAULT 0,
                carbs_g          REAL    DEFAULT 0,
                fat_g            REAL    DEFAULT 0,
                ingredients_json TEXT    DEFAULT '[]',
                FOREIGN KEY (email) REFERENCES users(email)
            )
        """)
        conn.commit()


def upsert_user(email: str, data: dict) -> None:
    with _conn() as conn:
        conn.execute("""
            INSERT INTO users (email, age, sex, weight_kg, height_cm,
                               activity_level, objective, allergies)
            VALUES (:email, :age, :sex, :weight_kg, :height_cm,
                    :activity_level, :objective, :allergies)
            ON CONFLICT(email) DO UPDATE SET
                age            = excluded.age,
                sex            = excluded.sex,
                weight_kg      = excluded.weight_kg,
                height_cm      = excluded.height_cm,
                activity_level = excluded.activity_level,
                objective      = excluded.objective,
                allergies      = excluded.allergies
        """, {"email": email, **data})
        conn.commit()


def get_user(email: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    if row is None:
        return None
    return dict(zip(_COLS_USER, row))


def add_meal(
    email: str,
    date: str,
    meal_type: str,
    calories: float,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    ingredients: list,
) -> None:
    with _conn() as conn:
        conn.execute("""
            INSERT INTO meal_logs
                (email, date, meal_type, calories, protein_g, carbs_g, fat_g, ingredients_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (email, date, meal_type, calories, protein_g, carbs_g, fat_g,
              json.dumps(ingredients, ensure_ascii=False)))
        conn.commit()


def get_today_meals(email: str, date: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("""
            SELECT id, meal_type, calories, protein_g, carbs_g, fat_g, ingredients_json
            FROM meal_logs
            WHERE email = ? AND date = ?
            ORDER BY id
        """, (email, date)).fetchall()
    return [dict(zip(_COLS_LOG, r)) for r in rows]


def delete_meal(meal_id: int) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM meal_logs WHERE id = ?", (meal_id,))
        conn.commit()


def get_daily_summaries(email: str, limit: int = 30) -> list[dict]:
    """Totales diarios de los últimos `limit` días."""
    with _conn() as conn:
        rows = conn.execute("""
            SELECT date,
                   SUM(calories)  AS calories,
                   SUM(protein_g) AS protein_g,
                   SUM(carbs_g)   AS carbs_g,
                   SUM(fat_g)     AS fat_g,
                   COUNT(*)       AS meal_count
            FROM meal_logs
            WHERE email = ?
            GROUP BY date
            ORDER BY date DESC
            LIMIT ?
        """, (email, limit)).fetchall()
    cols = ["date", "calories", "protein_g", "carbs_g", "fat_g", "meal_count"]
    return [dict(zip(cols, r)) for r in rows]
