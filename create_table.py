import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
)
""")

# Create income table
cursor.execute("""
CREATE TABLE IF NOT EXISTS income (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT,
    amount REAL,
    category TEXT,
    date TEXT
)
""")

# Create expenses table
cursor.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT,
    amount REAL,
    category TEXT,
    date TEXT
)
""")
# Create budget table
cursor.execute("""
CREATE TABLE IF NOT EXISTS budget (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    month TEXT,
    amount REAL
)
""")

conn.commit()
conn.close()

print("Users and Income and Expenses tables created successfully!")