import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.assets = self.directory / "assets"
        self.assets.mkdir(exist_ok=True)
        self.database = self.directory / "studio.sqlite3"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, revision INTEGER NOT NULL, body TEXT NOT NULL, updated REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, kind TEXT NOT NULL,
                    filename TEXT NOT NULL, original_name TEXT NOT NULL, metadata TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, scene_id TEXT, kind TEXT NOT NULL,
                    state TEXT NOT NULL, body TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS quotes (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    body TEXT NOT NULL, expires REAL NOT NULL, job_id TEXT
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def list_projects(self):
        with self.connect() as db:
            return [json.loads(row["body"]) for row in db.execute("SELECT body FROM projects ORDER BY updated DESC")]

    def project(self, project_id):
        with self.connect() as db:
            row = db.execute("SELECT body FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            raise KeyError("Project not found")
        return json.loads(row["body"])

    def save_project(self, project, create=False):
        body = project.model_dump() if hasattr(project, "model_dump") else dict(project)
        with self.connect() as db:
            if create:
                if db.execute("SELECT id FROM projects WHERE id=?", (body["id"],)).fetchone():
                    raise Conflict("Project ID already exists")
                body["revision"] = 1
                db.execute("INSERT INTO projects VALUES (?,?,?,?)", (body["id"], 1, json.dumps(body), time.time()))
            else:
                old_revision = body["revision"]
                body["revision"] += 1
                result = db.execute(
                    "UPDATE projects SET revision=?,body=?,updated=? WHERE id=? AND revision=?",
                    (body["revision"], json.dumps(body), time.time(), body["id"], old_revision),
                )
                if not result.rowcount:
                    raise Conflict("Project changed. Reload it before saving.")
        return body

    def add_asset(self, project_id, kind, path, original_name, metadata=None):
        asset_id = path.stem
        record = dict(id=asset_id, project_id=project_id, kind=kind, filename=path.name,
                      original_name=original_name, metadata=metadata or {})
        with self.connect() as db:
            db.execute("INSERT INTO assets VALUES (?,?,?,?,?,?)", (
                asset_id, project_id, kind, path.name, original_name, json.dumps(record["metadata"]),
            ))
        return record

    def asset(self, asset_id, project_id=None, kind=None):
        with self.connect() as db:
            row = db.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
        if row is None or (project_id and row["project_id"] != project_id) or (kind and row["kind"] != kind):
            raise KeyError("Asset not found in this project")
        record = dict(row)
        record["metadata"] = json.loads(record["metadata"])
        return record

    def path(self, asset_id, project_id=None, kind=None):
        record = self.asset(asset_id, project_id, kind)
        path = (self.assets / record["filename"]).resolve()
        if path.parent != self.assets or not path.is_file():
            raise KeyError("Asset file is missing")
        return path

    def list_assets(self, project_id):
        with self.connect() as db:
            return [self.asset(row["id"]) for row in db.execute("SELECT id FROM assets WHERE project_id=?", (project_id,))]

    def quote(self, project, payload):
        quote_id = uuid.uuid4().hex
        body = dict(payload, id=quote_id, project_id=project["id"], revision=project["revision"], expires=time.time() + 600)
        with self.connect() as db:
            db.execute("INSERT INTO quotes VALUES (?,?,?,?,?,NULL)",
                       (quote_id, project["id"], project["revision"], json.dumps(body), body["expires"]))
        return body

    def accept_quote(self, quote_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM quotes WHERE id=?", (quote_id,)).fetchone()
            if row is None:
                raise KeyError("Quote not found")
            if row["job_id"]:
                return self.job(row["job_id"]), False
            current = db.execute("SELECT revision FROM projects WHERE id=?", (row["project_id"],)).fetchone()
            if row["expires"] < time.time() or not current or current["revision"] != row["revision"]:
                raise Conflict("Quote expired or project changed. Estimate again.")
            payload = json.loads(row["body"])
            job_id = uuid.uuid4().hex
            now = time.time()
            job = dict(id=job_id, project_id=row["project_id"], scene_id=payload.get("scene_id"),
                       kind=payload["kind"], state="queued", payload=payload, progress=0, error=None,
                       output_asset_id=None, prompt_id=None, elapsed_seconds=None, created=now, updated=now)
            db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)", (
                job_id, row["project_id"], job["scene_id"], job["kind"], "queued", json.dumps(job), now, now,
            ))
            db.execute("UPDATE quotes SET job_id=? WHERE id=?", (job_id, quote_id))
        return job, True

    def job(self, job_id):
        with self.connect() as db:
            row = db.execute("SELECT body FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError("Job not found")
        return json.loads(row["body"])

    def jobs(self, project_id=None):
        with self.connect() as db:
            query = "SELECT body FROM jobs"
            args = ()
            if project_id:
                query += " WHERE project_id=?"
                args = (project_id,)
            return [json.loads(row["body"]) for row in db.execute(query + " ORDER BY created DESC LIMIT 200", args)]

    def update_job(self, job_id, **changes):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM jobs WHERE id=?", (job_id,)).fetchone()
            job = json.loads(row["body"])
            job.update(changes, updated=time.time())
            db.execute("UPDATE jobs SET state=?,body=?,updated=? WHERE id=?",
                       (job["state"], json.dumps(job), job["updated"], job_id))
        return job

    def transition_job(self, job_id, expected_state, **changes):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError("Job not found")
            job = json.loads(row["body"])
            if job["state"] != expected_state:
                raise Conflict("The job state changed. Refresh the queue.")
            job.update(changes, updated=time.time())
            db.execute("UPDATE jobs SET state=?,body=?,updated=? WHERE id=?",
                       (job["state"], json.dumps(job), job["updated"], job_id))
        return job

    def recover_jobs(self):
        for job in self.jobs():
            if job["state"] in ("running", "queued"):
                self.update_job(job["id"], state="interrupted", error="Studio restarted. Check ComfyUI history before starting another generation.")
