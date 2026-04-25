import sqlite3
import json
from datetime import datetime

DB_PATH = "research_history.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            task_id TEXT PRIMARY KEY,
            topic TEXT,
            status TEXT,
            created_at TEXT,
            started_at TEXT,
            completed_at TEXT,
            final_answer TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            turn INTEGER,
            action TEXT,
            content TEXT,
            timestamp TEXT,
            FOREIGN KEY(task_id) REFERENCES sessions(task_id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()

def save_session(session_data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO sessions (task_id, topic, status, created_at, started_at, completed_at, final_answer)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        session_data['task_id'], session_data['topic'], session_data['status'],
        session_data['created_at'], session_data.get('started_at'),
        session_data.get('completed_at'), session_data.get('final_answer')
    ))
    conn.commit()
    conn.close()

def save_history_entry(task_id, entry):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO history_entries (task_id, turn, action, content, timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', (task_id, entry['turn'], entry['action'], entry['content'], entry['timestamp']))
    conn.commit()
    conn.close()

def get_all_sessions(query=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if query:
        cursor.execute('SELECT * FROM sessions WHERE topic LIKE ? ORDER BY created_at DESC', (f'%{query}%',))
    else:
        cursor.execute('SELECT * FROM sessions ORDER BY created_at DESC')
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_session_details(task_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sessions WHERE task_id = ?', (task_id,))
    session = cursor.fetchone()
    cursor.execute('SELECT turn, action, content, timestamp FROM history_entries WHERE task_id = ? ORDER BY turn', (task_id,))
    history = cursor.fetchall()
    conn.close()
    return session, history

def delete_session(task_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM sessions WHERE task_id = ?', (task_id,))
    conn.commit()
    conn.close()

init_db()
