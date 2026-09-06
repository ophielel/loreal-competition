import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / 'data/workspace.sqlite'


@contextmanager
def connect():
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, session TEXT, cursor INTEGER, title TEXT, note TEXT, status TEXT, created TEXT, UNIQUE(session,cursor,title))')
    try:
        with con:
            yield con
    finally:
        con.close()


def list_tasks():
    with connect() as con:
        return [dict(r) for r in con.execute('SELECT * FROM tasks ORDER BY id DESC')]


def create_task(sid, cursor, title, note):
    with connect() as con:
        con.execute('INSERT OR IGNORE INTO tasks(session,cursor,title,note,status,created) VALUES(?,?,?,?,?,?)',
                    (sid, cursor, title, note, '待处理', datetime.now().isoformat(timespec='seconds')))
        return dict(con.execute('SELECT * FROM tasks WHERE session=? AND cursor=? AND title=?', (sid, cursor, title)).fetchone())


def complete_task(task_id):
    with connect() as con:
        con.execute('UPDATE tasks SET status=? WHERE id=?', ('已完成', task_id))
        row = con.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        return dict(row) if row else None
