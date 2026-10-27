"""Local BOM projects: immutable inputs, transactional checkpoints and separate human review.

Saved results are historical until controllers recheck them. This store is not an engineering authority
and is deliberately absent from the model's tool registry. A review never changes a check result.
"""
from __future__ import annotations

from contextlib import contextmanager
import csv
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from .checks.compat import POLICY
from .core.bom import import_bom_csv
from .core.model import digest, to_jsonable, utc_now
from .records import new_run_id
from .secrets import redact

SCHEMA_VERSION = 1
MAX_BOM_BYTES = 8 * 1024 * 1024


class ProfileInUse(RuntimeError):
    """The owning desktop must close normally before another writer opens the profile."""


def qualification_scope():
    policy = to_jsonable(POLICY)
    return {"policy": "reference-attributes-v1", "policy_sha256": digest(policy),
            "families": {k: {"required": [p for p, _, required in v if required],
                              "when_stated": [p for p, _, required in v if not required]}
                         for k, v in policy.items()},
            "meaning": "Verified means the evidenced reference attributes passed the current policy.",
            "application": "Circuit, footprint/pinout and operating characteristics require independent review.",
            "manufacturing_ready": False}


def decision_digest(decision):
    return digest({k: v for k, v in decision.items()
                   if k not in {"current_context", "stored_in_memory", "prior_decisions_from_memory"}})


def _json(value):
    return json.dumps(redact(to_jsonable(value)), sort_keys=True, ensure_ascii=False)


def _text(value, label, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label} must contain 1–{maximum} characters")
    return value.strip()


class ProjectStore:
    """One desktop writer per profile; each connection has a bounded SQLite transaction."""
    def __init__(self, state):
        self.root = Path(state).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "projects.sqlite3"
        self._lease = (self.root / "projects.lock").open("a+b")
        try:
            self._lease.seek(0)
            if os.name == "nt":
                import msvcrt
                # The byte need not exist for Windows locking, but provision it for other runtimes.
                if not self._lease.read(1):
                    self._lease.write(b"\0"); self._lease.flush()
                self._lease.seek(0)
                msvcrt.locking(self._lease.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.close()
            raise ProfileInUse("This PartLens profile is already open. Close its other window before reopening.") from exc
        try:
            with self._db() as db:
                version = db.execute("PRAGMA user_version").fetchone()[0]
                if version not in (0, SCHEMA_VERSION):
                    raise ValueError("Project database requires a compatible PartLens version; it was preserved")
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS projects (
                      id TEXT PRIMARY KEY, title TEXT NOT NULL, created TEXT NOT NULL, active_revision TEXT);
                    CREATE TABLE IF NOT EXISTS revisions (
                      id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                      number INTEGER NOT NULL, created TEXT NOT NULL, filename TEXT NOT NULL,
                      sha256 TEXT NOT NULL, original BLOB NOT NULL, UNIQUE(project_id, number));
                    CREATE TABLE IF NOT EXISTS jobs (
                      id TEXT PRIMARY KEY, revision_id TEXT NOT NULL REFERENCES revisions(id),
                      run_id TEXT NOT NULL, status TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS job_events (
                      seq INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
                      at TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS checkpoints (
                      seq INTEGER PRIMARY KEY, revision_id TEXT NOT NULL REFERENCES revisions(id),
                      job_id TEXT NOT NULL REFERENCES jobs(id), run_id TEXT NOT NULL, at TEXT NOT NULL,
                      context TEXT NOT NULL, report TEXT NOT NULL, sha256 TEXT NOT NULL,
                      record_path TEXT NOT NULL, record_bytes INTEGER NOT NULL, record_sha256 TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS reviews (
                      seq INTEGER PRIMARY KEY, revision_id TEXT NOT NULL REFERENCES revisions(id),
                      run_id TEXT NOT NULL, at TEXT NOT NULL, decision_id TEXT NOT NULL, line TEXT NOT NULL,
                      decision_sha256 TEXT NOT NULL, context TEXT NOT NULL,
                      action TEXT NOT NULL, reviewer TEXT NOT NULL, reason TEXT NOT NULL, scope TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    PRAGMA user_version=1;
                """)
                # The exclusive profile lease proves the prior desktop writer is gone.
                for row in db.execute("SELECT id FROM jobs WHERE status IN ('running','waiting')").fetchall():
                    self._transition(db, row['id'], 'interrupted', 'Previous process ended; explicit recheck required')
        except Exception:
            self.close()
            raise

    def close(self):
        if self._lease is not None:
            self._lease.close()
            self._lease = None

    @contextmanager
    def _db(self):
        if self._lease is None:
            raise RuntimeError('Project store is closed')
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, title):
        title = _text(title, "Project title", 120)
        project = new_run_id()
        with self._db() as db:
            db.execute("INSERT INTO projects VALUES (?,?,?,NULL)", (project, title, utc_now()))
            db.execute("INSERT OR REPLACE INTO preferences VALUES ('last_project',?)", (project,))
        return project

    def list(self):
        with self._db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM projects ORDER BY created DESC, id DESC")]

    def last_project(self):
        with self._db() as db:
            row = db.execute("SELECT value FROM preferences WHERE key='last_project'").fetchone()
            return row[0] if row else None

    def select(self, project, revision=None):
        with self._db() as db:
            p = db.execute("SELECT * FROM projects WHERE id=?", (project,)).fetchone()
            if not p:
                raise ValueError("Project not found")
            revision = revision or p['active_revision']
            if revision and not db.execute("SELECT 1 FROM revisions WHERE id=? AND project_id=?", (revision, project)).fetchone():
                raise ValueError("Revision does not belong to this project")
            db.execute("UPDATE projects SET active_revision=? WHERE id=?", (revision, project))
            db.execute("INSERT OR REPLACE INTO preferences VALUES ('last_project',?)", (project,))
        return revision

    def revisions(self, project):
        with self._db() as db:
            return [dict(r) for r in db.execute(
                "SELECT id,project_id,number,created,filename,sha256 FROM revisions WHERE project_id=? ORDER BY number DESC", (project,))]

    def add_revision(self, project, path):
        path = Path(path).resolve()
        if any('experiments' in p.casefold() or 'benchmark' in p.casefold() or 'badge' in p.casefold() for p in path.parts):
            raise ValueError("Excluded private material cannot be imported")
        if path.suffix.casefold() != '.csv':
            raise ValueError("Select a CSV BOM")
        with path.open('rb') as source:
            raw = source.read(MAX_BOM_BYTES + 1)
        if len(raw) > MAX_BOM_BYTES:
            raise ValueError("BOM exceeds the 8 MiB project import limit")
        bom = import_bom_csv(text=raw.decode('utf-8-sig'))
        if not bom.lines or len(bom.lines) > 10000:
            raise ValueError("A project BOM must contain 1–10,000 component lines")
        revision = new_run_id()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM projects WHERE id=?", (project,)).fetchone():
                raise ValueError("Project not found")
            number = db.execute("SELECT COALESCE(MAX(number),0)+1 FROM revisions WHERE project_id=?", (project,)).fetchone()[0]
            db.execute("INSERT INTO revisions VALUES (?,?,?,?,?,?,?)",
                       (revision, project, number, utc_now(), path.name, hashlib.sha256(raw).hexdigest(), raw))
            db.execute("UPDATE projects SET active_revision=? WHERE id=?", (revision, project))
        return revision

    def input_path(self, revision):
        with self._db() as db:
            row = db.execute("SELECT project_id,sha256,original FROM revisions WHERE id=?", (revision,)).fetchone()
        if not row:
            raise ValueError("Revision not found")
        raw = bytes(row['original'])
        if hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError("Saved BOM integrity check failed; original data preserved")
        folder = self.root / 'projects' / row['project_id'] / revision
        if not folder.resolve().is_relative_to(self.root):
            raise ValueError('Project input folder is outside this profile')
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'bom.csv'
        if not path.exists():
            with path.open('xb') as target:
                target.write(raw)
        if path.is_symlink() or not path.resolve().is_relative_to(self.root) or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError("Project input copy changed; recheck blocked to preserve evidence")
        return path

    def _transition(self, db, job, status, detail=''):
        now = utc_now()
        db.execute("UPDATE jobs SET status=?,updated=? WHERE id=?", (status, now, job))
        db.execute("INSERT INTO job_events(job_id,at,status,detail) VALUES (?,?,?,?)", (job, now, status, detail))

    def start_job(self, revision, run_id):
        job = new_run_id(); now = utc_now()
        with self._db() as db:
            db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?)", (job, revision, run_id, 'running', now, now))
            self._transition(db, job, 'running')
        return job

    def finish_job(self, job, status, detail=''):
        if status not in {'running', 'waiting', 'completed', 'failed', 'cancelled'}:
            raise ValueError('Invalid job transition')
        with self._db() as db:
            self._transition(db, job, status, detail)

    def checkpoint(self, revision, job, session, report):
        record = session.recorder.path.resolve()
        if not record.is_relative_to(self.root) or record.is_symlink():
            raise ValueError('Checkpoint record is outside this profile')
        raw = record.read_bytes()
        saved = {k: v for k, v in report.items() if k != 'Run record'}
        payload = _json(saved)
        with self._db() as db:
            db.execute("INSERT INTO checkpoints(revision_id,job_id,run_id,at,context,report,sha256,record_path,record_bytes,record_sha256) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (revision, job, session.recorder.run_id, utc_now(), session.context_digest(), payload,
                        hashlib.sha256(payload.encode()).hexdigest(), str(record.relative_to(self.root)), len(raw), hashlib.sha256(raw).hexdigest()))

    def latest(self, revision):
        with self._db() as db:
            row = db.execute("SELECT c.*,j.status AS job_status FROM checkpoints c JOIN jobs j ON c.job_id=j.id WHERE c.revision_id=? ORDER BY c.seq DESC LIMIT 1", (revision,)).fetchone()
        if not row:
            return None
        row = dict(row)
        if hashlib.sha256(row['report'].encode()).hexdigest() != row['sha256']:
            raise ValueError('Saved report integrity check failed')
        path = (self.root / row['record_path']).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise ValueError('Saved run record is missing or outside the profile')
        # Appended operations do not invalidate earlier, immutable record prefixes.
        with path.open('rb') as f:
            raw = f.read(row['record_bytes'])
        if len(raw) != row['record_bytes'] or hashlib.sha256(raw).hexdigest() != row['record_sha256']:
            raise ValueError('Saved run record changed; recovery and review blocked')
        row['report'] = json.loads(row['report']); row['record_path'] = str(path)
        return row

    def jobs(self, revision):
        with self._db() as db:
            return [dict(r) for r in db.execute('SELECT * FROM jobs WHERE revision_id=? ORDER BY created DESC,id DESC', (revision,))]

    def quantity_record(self, revision):
        """Locate the original user's run within this revision, never manufacture a new confirmation."""
        checkpoint = self.latest(revision)
        if not checkpoint:
            return None
        requirements = checkpoint['report'].get('Requirements', {}).get('requirements', [])
        quantity = next((r for r in requirements if r.get('id') == 'design.board_quantity' and r.get('binding')), None)
        if not quantity or not quantity.get('source', '').startswith('user:'):
            return None
        run = quantity['source'].split('#')[0][5:]
        with self._db() as db:
            row = db.execute('SELECT record_path,record_bytes,record_sha256 FROM checkpoints WHERE revision_id=? AND run_id=? ORDER BY seq DESC LIMIT 1', (revision, run)).fetchone()
        if not row:
            raise ValueError('Original quantity record is not bound to this BOM revision')
        path = (self.root / row['record_path']).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('Original quantity record is outside this profile')
        with path.open('rb') as f:
            raw = f.read(row['record_bytes'])
        if hashlib.sha256(raw).hexdigest() != row['record_sha256']:
            raise ValueError('Original quantity record changed')
        return path

    def reviews(self, revision):
        with self._db() as db:
            return [dict(r) for r in db.execute('SELECT * FROM reviews WHERE revision_id=? ORDER BY seq DESC', (revision,))]

    def review(self, revision, run_id, decision_id, action, reviewer, reason, *, acknowledge=False):
        reviewer = _text(reviewer, 'Reviewer name', 120); reason = _text(reason, 'Review rationale', 2000)
        if action not in {'accept', 'reject', 'needs_evidence'}:
            raise ValueError('Unknown review action')
        checkpoint = self.latest(revision)
        if not checkpoint or checkpoint['run_id'] != run_id or checkpoint['job_status'] != 'completed':
            raise ValueError('Complete a fresh recheck before reviewing this revision')
        matches = [d for d in checkpoint['report'].get('Qualifications', []) if d.get('decision_id') == decision_id]
        if not matches or matches[-1].get('current_context') is not True:
            raise ValueError('Decision is missing or historical; recheck first')
        decision = matches[-1]
        if action == 'accept' and (decision.get('status') != 'verified' or acknowledge is not True):
            raise ValueError('Only verified reference attributes can be accepted, with explicit application-scope acknowledgement')
        scope = 'checked reference attributes only; application and manufacturing release NOT approved'
        with self._db() as db:
            db.execute('INSERT INTO reviews(revision_id,run_id,at,decision_id,line,decision_sha256,context,action,reviewer,reason,scope) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                       (revision, run_id, utc_now(), decision_id, decision['line'], decision_digest(decision), checkpoint['context'], action, reviewer, reason, scope))
        return self.reviews(revision)[0]

    def export(self, revision, run_id):
        """Export an auditable proposal; never mutate the imported BOM or call it a released design."""
        checkpoint = self.latest(revision)
        if not checkpoint or checkpoint['run_id'] != run_id or checkpoint['job_status'] != 'completed':
            raise ValueError('Complete a fresh recheck before exporting a proposal')
        report = checkpoint['report']
        decisions = {d['decision_id']: d for d in report.get('Qualifications', []) if d.get('current_context') is True}
        latest_reviews = {}
        for review in self.reviews(revision):
            latest_reviews.setdefault(review['decision_id'], review)
        accepted = {}
        for key, review in latest_reviews.items():
            decision = decisions.get(key)
            if (review['action'] != 'accept' or review['run_id'] != run_id or review['context'] != checkpoint['context']
                    or not decision or decision['status'] != 'verified' or review['decision_sha256'] != decision_digest(decision)):
                continue
            if decision['line'] in accepted:
                raise ValueError('Multiple accepted candidates for one line; reject the unwanted proposal before export')
            accepted[decision['line']] = decision
        if not accepted:
            raise ValueError('Accept at least one freshly checked proposal before exporting')
        bom = import_bom_csv(self.input_path(revision))
        folder = self.root / 'exports' / new_run_id()
        folder.mkdir(parents=True, exist_ok=False)
        rows = []
        changes = []
        for line in bom.lines:
            decision = accepted.get(line.id)
            part = decision['comparison']['candidate'] if decision else {}
            rows.append([line.id, ','.join(line.refs), line.qty_per_board, line.value, line.footprint,
                         part.get('mpn', line.mpn), part.get('manufacturer', line.manufacturer),
                         part['key'].split(':',1)[-1] if decision else line.supplier_pn,
                         part.get('key'), line.dnp, 'reviewed proposal' if decision else 'original input'])
            if decision:
                changes.append([line.id, decision['original'], decision['candidate'], decision['decision_id'],
                                decision['status'], decision.get('application', {}).get('status', 'unverified')])
        _write_csv(folder/'reviewed-proposal.csv', ['Line','Refs','Qty','Value','Footprint','MPN','Manufacturer','SupplierPart','SupplierKey','DNP','ReviewScope'], rows)
        _write_csv(folder/'changes.csv', ['Line','Original','Candidate','Decision','ReferenceAttributes','Application'], changes)
        packet = {'format_version': 1, 'created': utc_now(), 'revision': revision, 'run_id': run_id,
                  'manufacturing_ready': False, 'identity_assurance': 'reviewer-entered name; no authenticated accounts',
                  'scope': qualification_scope(), 'report': report, 'reviews': list(latest_reviews.values()),
                  'accepted_decisions': accepted, 'record': {k: checkpoint[k] for k in ('record_path','record_bytes','record_sha256')},
                  'warning': 'Reviewed proposal only. Application qualification, original BOM issues, commercial terms and assembly fees may remain unresolved. Costs describe the recorded scenarios, not a quote for this manually selected proposal.'}
        (folder/'review.json').write_text(_json(packet), encoding='utf-8')
        (folder/'original.csv').write_bytes(self.input_path(revision).read_bytes())
        with Path(checkpoint['record_path']).open('rb') as source:
            (folder/'run-record.jsonl').write_bytes(source.read(checkpoint['record_bytes']))
        quantity_record = self.quantity_record(revision)
        if quantity_record and quantity_record != Path(checkpoint['record_path']):
            (folder/'original-quantity-record.jsonl').write_bytes(quantity_record.read_bytes())
        (folder/'README.txt').write_text(
            'REVIEWED PROPOSAL ONLY. Application qualification and manufacturing release are incomplete.\n'
            'Derived CSVs escape spreadsheet formulas. original.csv is the exact unescaped input for provenance.\n'
            'Supplier evidence and personal review information are internal. Check permissions before sharing.\n'
            'Hashes detect accidental changes; they are not signatures or authenticated approvals.\n'
            'Costs describe recorded scenarios; they are not a quotation for this manually selected proposal.\n', encoding='utf-8')
        manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}
        (folder/'manifest.json').write_text(_json({'sha256': manifest, 'manufacturing_ready': False}), encoding='utf-8')
        return {'path': str(folder), 'accepted_lines': len(accepted), 'manufacturing_ready': False}


def _write_csv(path, headers, rows):
    def safe(value):
        value = '' if value is None else str(value)
        return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')) else value
    with path.open('x', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f); writer.writerow(headers)
        writer.writerows([[safe(v) for v in row] for row in rows])
