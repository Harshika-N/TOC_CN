import os
import sqlite3
from flask import current_app, g
from .seed import DEPOTS, HANDLERS, DISTANCES

SCHEMA = """
CREATE TABLE IF NOT EXISTS depots(id INTEGER PRIMARY KEY, name TEXT UNIQUE, zone TEXT, capacity INTEGER);
CREATE TABLE IF NOT EXISTS handlers(id TEXT PRIMARY KEY, name TEXT, depot_id INTEGER REFERENCES depots(id), specialties TEXT, capacity INTEGER, available INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS route_distances(route_key TEXT, depot_id INTEGER REFERENCES depots(id), km REAL, PRIMARY KEY(route_key,depot_id));
CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, reporter TEXT NOT NULL, contact TEXT NOT NULL, bus_id TEXT NOT NULL,
 route_key TEXT NOT NULL, code TEXT NOT NULL, description TEXT NOT NULL, urgency TEXT NOT NULL, category TEXT NOT NULL,
 priority TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Pending', handler_id TEXT REFERENCES handlers(id), depot_id INTEGER REFERENCES depots(id),
 routing_note TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS reports_queue ON reports(status, priority, created_at);
"""

def get_db():
    if "db" not in g:
        path = current_app.config["DATABASE"]
        if path != ":memory:":
            path = os.path.join(current_app.root_path, "..", path) if not os.path.isabs(path) else path
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        g.db = sqlite3.connect(path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

def close_db(_=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA)
        if db.execute("SELECT COUNT(*) FROM depots").fetchone()[0] == 0:
            ids = []
            for name, zone, capacity in DEPOTS:
                cur = db.execute("INSERT INTO depots(name,zone,capacity) VALUES(?,?,?)", (name,zone,capacity))
                ids.append(cur.lastrowid)
            for hid,name,depot,specialties,capacity in HANDLERS:
                depot_id = ids[[d[0] for d in DEPOTS].index(depot)]
                db.execute("INSERT INTO handlers(id,name,depot_id,specialties,capacity) VALUES(?,?,?,?,?)", (hid,name,depot_id,specialties,capacity))
            for key, values in DISTANCES.items():
                for depot_id, km in zip(ids, values):
                    db.execute("INSERT INTO route_distances VALUES(?,?,?)", (key,depot_id,km))
        db.commit()
