from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "liquor.db"


def build_database():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            )
            """
        )
        cursor.execute("DELETE FROM users")
        cursor.execute("DELETE FROM products")
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            ("admin", "password"),
        )
        cursor.executemany(
            "INSERT INTO products (name) VALUES (?)",
            [
                ("Macallan 18",),
                ("Dom Pérignon Vintage",),
                ("Hennessy XO",),
                ("Johnnie Walker Blue Label",),
                ("Château Margaux 2015",),
                ("Ardbeg Uigeadail",),
            ],
        )
        conn.commit()


if __name__ == "__main__":
    build_database()
    print(f"Database ready at {DB_PATH}")