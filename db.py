import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from werkzeug.security import generate_password_hash
from flask import current_app, g


SEEDED_USERS = ("alice", "ben", "chloe", "diego", "emma", "farah")

SEEDED_ITEMS = (
    ("Blue stainless steel water bottle", "A blue insulated bottle with a small mountain sticker.", "Main Library, 2nd floor", "water-bottle-blue", "alice", 0),
    ("Black wireless earbuds case", "Black charging case, earbuds were not inside.", "Student Center, food court", "earbuds-case-black", "ben", 0),
    ("Student ID card", "Campus ID belonging to Jordan Lee; turned in as found.", "North Gym, basketball court", "student-id-card", "chloe", 1),
    ("TI-84 graphing calculator", "Silver TI-84 Plus with initials M.P. on the back.", "Science Building, Room 214", "graphing-calculator", "diego", 0),
    ("Gray university hoodie", "Medium gray hoodie with the campus logo on the front.", "Dining Hall, patio", "gray-campus-hoodie", "emma", 0),
    ("Keys with a red carabiner", "Three keys and a small red carabiner.", "West Parking Lot, near the bike racks", "keys-red-carabiner", "farah", 1),
    ("Introduction to Psychology textbook", "Ninth edition, with handwritten notes inside.", "Main Library, 1st floor", "psychology-textbook", "alice", 0),
    ("USB-C laptop charger", "White 65W charger and cable, lightly scuffed.", "Engineering Building, lounge", "usb-c-laptop-charger", "ben", 0),
    ("Purple water bottle", "Reusable purple bottle with a silver lid.", "Campus Recreation Center, locker room", "purple-water-bottle", "chloe", 1),
    ("Brown leather wallet", "Slim wallet with a few cards; no cash visible.", "Student Center, front entrance", "brown-leather-wallet", "diego", 0),
    ("Wireless mouse", "Small black wireless mouse with USB receiver attached.", "Business Building, Room 108", "wireless-mouse", "emma", 0),
    ("Red knit beanie", "Red winter hat left on a chair.", "Arts Building, auditorium", "red-knit-beanie", "farah", 1),
    ("Set of earbuds", "White wireless earbuds in a clear silicone case.", "Library Cafe", "white-earbuds", "alice", 0),
    ("Blue spiral notebook", "College-ruled notebook with a blue cover and name inside.", "Lecture Hall C, row 6", "blue-spiral-notebook", "ben", 0),
    ("Silver laptop sleeve", "13-inch padded sleeve with a small zipper pocket.", "Student Center, study area", "silver-laptop-sleeve", "chloe", 1),
    ("Umbrella, black and compact", "Foldable black umbrella with a wooden handle.", "Dining Hall, east entrance", "black-umbrella", "diego", 0),
    ("Calculus textbook", "Calculus: Early Transcendentals, eighth edition.", "Science Building, lobby", "calculus-textbook", "emma", 0),
    ("Green insulated travel mug", "Green travel mug with a flip-top lid.", "Main Library, help desk", "green-travel-mug", "farah", 1),
    ("Student ID in clear holder", "Campus ID in a transparent badge holder with a blue strap.", "North Gym, front desk", "id-clear-holder", "alice", 0),
    ("Black over-ear headphones", "Foldable headphones with a padded headband.", "Music Building, practice rooms", "black-headphones", "ben", 0),
    ("Pair of silver hoop earrings", "Small pair of silver-colored hoop earrings.", "Student Center, auditorium", "silver-hoop-earrings", "chloe", 1),
    ("Laptop power adapter", "Black laptop adapter marked 90W, no computer attached.", "Engineering Building, lab 3", "black-power-adapter", "diego", 0),
    ("Yellow rain jacket", "Lightweight yellow rain jacket, size small.", "Campus Shuttle Stop, Library", "yellow-rain-jacket", "emma", 0),
    ("Blue calculator pouch", "Zippered blue pouch containing pencils and an eraser.", "Business Building, Room 220", "blue-calculator-pouch", "farah", 1),
    ("Textbook: World History", "Hardcover world history textbook with a green cover.", "Dining Hall, second floor", "world-history-textbook", "alice", 0),
)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db():
    database_path = current_app.config["DATABASE"]
    if database_path != ":memory:":
        Path(database_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                location TEXT NOT NULL,
                date_found TEXT NOT NULL,
                photo_url TEXT NOT NULL DEFAULT '',
                returned INTEGER NOT NULL DEFAULT 0 CHECK (returned IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        item_count = connection.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        if item_count == 0:
            for username in SEEDED_USERS:
                connection.execute(
                    "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash("password123")),
                )

            user_ids = {
                row["username"]: row["id"]
                for row in connection.execute(
                    "SELECT id, username FROM users WHERE username IN (?, ?, ?, ?, ?, ?)",
                    SEEDED_USERS,
                )
            }
            today = date.today()
            now = datetime.now(timezone.utc)
            for index, (title, description, location, photo_seed, username, returned) in enumerate(SEEDED_ITEMS):
                found_on = today - timedelta(days=(index * 7) % 30)
                created_at = (now - timedelta(minutes=index)).strftime("%Y-%m-%d %H:%M:%S")
                connection.execute(
                    """
                    INSERT INTO items
                        (user_id, title, description, location, date_found, photo_url, returned, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_ids[username],
                        title,
                        description,
                        location,
                        found_on.isoformat(),
                        f"https://picsum.photos/seed/{photo_seed}/400/300",
                        returned,
                        created_at,
                    ),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
