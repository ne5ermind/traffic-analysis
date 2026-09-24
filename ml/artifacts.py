"""Disk-backed observations and compact trajectories. No full-video RAM buffer."""

import json
import sqlite3


class TrackStore:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS tracks (
          id INTEGER PRIMARY KEY, class_name TEXT, confidence REAL, first_seen REAL,
          last_seen REAL, trajectory TEXT, samples INTEGER, movement_id TEXT DEFAULT 'unknown',
          entry_zone TEXT, exit_zone TEXT, counted_at REAL, reliability REAL DEFAULT 0,
          countable INTEGER DEFAULT 1, fragments INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS observations (
          t REAL, track_id INTEGER, bbox TEXT, point TEXT, confidence REAL);
        CREATE INDEX IF NOT EXISTS observation_time ON observations(t);
        CREATE INDEX IF NOT EXISTS track_movement ON tracks(movement_id);
        """)

    def save_track(self, t):
        votes = t["votes"]
        cls = max(votes, key=votes.get)
        self.db.execute(
            "INSERT OR REPLACE INTO tracks(id,class_name,confidence,first_seen,last_seen,trajectory,samples,counted_at,countable,fragments) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                t["id"],
                cls,
                t["confidence_sum"] / t["samples"],
                t["first_seen"],
                t["last_seen"],
                json.dumps(t["trajectory"]),
                t["samples"],
                t["last_seen"],
                int(t["samples"] >= 3),
                t.get("fragments", 0),
            ),
        )

    def observation(self, t, track_id, bbox, point, confidence):
        self.db.execute("INSERT INTO observations VALUES (?,?,?,?,?)", (t, track_id, json.dumps(bbox), json.dumps(point), confidence))

    def tracks(self):
        for row in self.db.execute("SELECT * FROM tracks ORDER BY id"):
            t = dict(row)
            t["trajectory"] = json.loads(t["trajectory"])
            yield t

    def close(self):
        self.db.commit()
        self.db.close()
