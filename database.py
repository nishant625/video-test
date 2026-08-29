
import sqlite3
from pathlib import Path
from datetime import datetime, timezone


DB_PATH = Path(__file__).resolve().parent / "viral_engine.db"


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():

    with connect() as db:

        db.execute("""
        CREATE TABLE IF NOT EXISTS runs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            idea TEXT NOT NULL,

            video_prompt TEXT,
            youtube_title TEXT,

            kie_task_id TEXT,
            kie_state TEXT,
            video_url TEXT,

            zernio_account_id TEXT,
            zernio_platform TEXT,
            zernio_post_id TEXT,

            status TEXT NOT NULL,

            error_message TEXT
        )
        """)

        db.execute("""
        CREATE TABLE IF NOT EXISTS run_events (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            run_id INTEGER NOT NULL,

            timestamp TEXT NOT NULL,

            stage TEXT NOT NULL,

            level TEXT NOT NULL,

            message TEXT NOT NULL,

            FOREIGN KEY(run_id)
                REFERENCES runs(id)
        )
        """)


def create_run(idea):

    timestamp = now()

    with connect() as db:

        cursor = db.execute(
            """
            INSERT INTO runs
            (
                created_at,
                updated_at,
                idea,
                status
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                timestamp,
                timestamp,
                idea,
                "CREATED",
            ),
        )

        return cursor.lastrowid


def update_run(run_id, **fields):

    if not fields:
        return

    fields["updated_at"] = now()

    assignments = ", ".join(
        f"{key} = ?"
        for key in fields
    )

    values = list(fields.values())
    values.append(run_id)

    with connect() as db:

        db.execute(
            f"""
            UPDATE runs
            SET {assignments}
            WHERE id = ?
            """,
            values,
        )


def add_event(
    run_id,
    stage,
    level,
    message,
):

    with connect() as db:

        db.execute(
            """
            INSERT INTO run_events
            (
                run_id,
                timestamp,
                stage,
                level,
                message
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                now(),
                stage,
                level,
                message,
            ),
        )
