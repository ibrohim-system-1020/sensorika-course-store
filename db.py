import os, sqlite3, hashlib, hmac
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "app.db"
DB_PATH.parent.mkdir(exist_ok=True)


def connect():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def _ensure_order_columns(cur):
    """Eski database bo'lsa ham yangi demo-payment ustunlarini qo'shadi."""
    existing = {r["name"] for r in cur.execute("PRAGMA table_info(orders)").fetchall()}
    additions = {
        "payment_method": "TEXT",
        "payment_last4": "TEXT",
        "payment_ref": "TEXT",
        "payment_submitted_at": "DATETIME",
    }
    for name, col_type in additions.items():
        if name not in existing:
            cur.execute(f"ALTER TABLE orders ADD COLUMN {name} {col_type}")


def init_db():
    con = connect()
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        telegram_id INTEGER,
        is_admin INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS courses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        price INTEGER NOT NULL,
        channel_title TEXT NOT NULL,
        is_active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        invite_link TEXT,
        paid_at DATETIME,
        used_at DATETIME,
        payment_method TEXT,
        payment_last4 TEXT,
        payment_ref TEXT,
        payment_submitted_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """)
    _ensure_order_columns(cur)

    admin = cur.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    if not admin:
        cur.execute(
            "INSERT INTO users(full_name, username, password_hash, is_admin) VALUES(?,?,?,1)",
            ("Administrator", "admin", hash_password("admin123")),
        )

    count = cur.execute("SELECT COUNT(*) c FROM courses").fetchone()["c"]
    if count == 0:
        cur.executemany(
            "INSERT INTO courses(title,description,price,channel_title) VALUES(?,?,?,?)",
            [
                ("Python Foundation", "Python asoslari, masalalar, mini-loyihalar va testlar.", 149000, "Python Foundation | Yopiq kanal"),
                ("Frontend Start", "HTML, CSS, JavaScript va responsive web sahifalar.", 179000, "Frontend Start | Yopiq kanal"),
                ("Telegram Bot PRO", "Aiogram 3 yordamida real Telegram botlar yaratish.", 229000, "Telegram Bot PRO | Yopiq kanal"),
            ],
        )
    con.commit()
    con.close()
