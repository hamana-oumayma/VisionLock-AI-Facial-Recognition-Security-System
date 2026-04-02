import sqlite3

def connect():
    return sqlite3.connect("db.sqlite3")

def init_db():
    conn = connect()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY,
        user TEXT,
        status TEXT,
        watermark TEXT
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS blacklist (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE,
        reason TEXT,
        added_at TEXT
    )''')
    conn.commit()
    conn.close()