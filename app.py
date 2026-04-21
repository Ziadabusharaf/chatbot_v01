import json
import os
import sqlite3
from datetime import datetime
from typing import Any

from flask import Flask, g, jsonify, request

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "chatbot.db")

app = Flask(__name__)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_: Any):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL,
            branch TEXT,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS builders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS plan_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            builder_id INTEGER NOT NULL,
            plan_number TEXT NOT NULL,
            community TEXT,
            house_type TEXT,
            version INTEGER DEFAULT 1,
            defaults_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(builder_id) REFERENCES builders(id)
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_number TEXT UNIQUE NOT NULL,
            builder_id INTEGER NOT NULL,
            community TEXT NOT NULL,
            address TEXT NOT NULL,
            plan_number TEXT NOT NULL,
            house_type TEXT,
            material TEXT NOT NULL,
            thickness_mm INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            override_notes TEXT,
            FOREIGN KEY(builder_id) REFERENCES builders(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS job_areas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            area_name TEXT NOT NULL,
            sink_model TEXT,
            appliance_model TEXT,
            edge_profile TEXT,
            backsplash TEXT,
            overhang_inches REAL,
            corner_details TEXT,
            support_type TEXT,
            special_notes TEXT,
            required_photos_count INTEGER DEFAULT 0,
            uploaded_photos_count INTEGER DEFAULT 0,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        );

        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            templater_id INTEGER NOT NULL,
            scheduled_start TEXT NOT NULL,
            scheduled_end TEXT NOT NULL,
            territory TEXT,
            route_group TEXT,
            dry_run_reason TEXT,
            readiness_confirmed INTEGER DEFAULT 0,
            FOREIGN KEY(job_id) REFERENCES jobs(id),
            FOREIGN KEY(templater_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS template_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            templater_id INTEGER NOT NULL,
            source TEXT DEFAULT 'manual',
            is_offline_synced INTEGER DEFAULT 0,
            has_signature INTEGER DEFAULT 0,
            notes TEXT,
            submitted_at TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(id),
            FOREIGN KEY(templater_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS ai_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            completeness_score REAL NOT NULL,
            missing_items_json TEXT NOT NULL,
            conflicts_json TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        );

        CREATE TABLE IF NOT EXISTS approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            approver_id INTEGER,
            audience TEXT NOT NULL,
            status TEXT NOT NULL,
            comments TEXT,
            version INTEGER NOT NULL,
            acted_at TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        );

        CREATE TABLE IF NOT EXISTS sps_exports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            export_status TEXT NOT NULL,
            error_message TEXT,
            pushed_by INTEGER,
            pushed_at TEXT,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id INTEGER,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            before_json TEXT,
            after_json TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    db.commit()
    db.close()


def now() -> str:
    return datetime.utcnow().isoformat()


def log_action(actor_user_id: int | None, entity_type: str, entity_id: int, action: str, before=None, after=None):
    db = get_db()
    db.execute(
        """
        INSERT INTO audit_logs (actor_user_id, entity_type, entity_id, action, before_json, after_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            actor_user_id,
            entity_type,
            entity_id,
            action,
            json.dumps(before) if before is not None else None,
            json.dumps(after) if after is not None else None,
            now(),
        ),
    )


def validate_job_payload(payload: dict[str, Any]) -> list[str]:
    required = ["job_number", "builder", "community", "address", "plan_number", "material", "thickness_mm", "areas"]
    missing = [f for f in required if not payload.get(f)]
    areas = payload.get("areas")
    if not isinstance(areas, list) or not areas:
        missing.append("areas")
        return missing

    for idx, area in enumerate(areas):
        for k in ["area_name", "sink_model", "appliance_model", "edge_profile", "backsplash"]:
            if not area.get(k):
                missing.append(f"areas[{idx}].{k}")
    return missing


def get_or_create_builder(name: str) -> int:
    db = get_db()
    row = db.execute("SELECT id FROM builders WHERE name=?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = db.execute("INSERT INTO builders (name) VALUES (?)", (name,))
    return cur.lastrowid


def get_or_create_user(email: str, name: str, role: str) -> int:
    db = get_db()
    row = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if row:
        return row["id"]
    cur = db.execute("INSERT INTO users (name, email, role) VALUES (?, ?, ?)", (name, email, role))
    return cur.lastrowid


def run_ai_review(job_id: int) -> dict[str, Any]:
    db = get_db()
    areas = db.execute("SELECT * FROM job_areas WHERE job_id=?", (job_id,)).fetchall()
    sub = db.execute(
        "SELECT * FROM template_submissions WHERE job_id=? ORDER BY submitted_at DESC LIMIT 1", (job_id,)
    ).fetchone()

    job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    prior = db.execute(
        """
        SELECT * FROM jobs
        WHERE builder_id=? AND plan_number=? AND id != ?
        ORDER BY created_at DESC LIMIT 1
        """,
        (job["builder_id"], job["plan_number"], job_id),
    ).fetchone()

    score = 100.0
    missing, conflicts = [], []
    if not areas:
        missing.append("No job areas found")
        score -= 35

    for area in areas:
        if not area["sink_model"]:
            missing.append(f"{area['area_name']}: missing sink model")
            score -= 8
        if not area["appliance_model"]:
            missing.append(f"{area['area_name']}: missing appliance model")
            score -= 8
        if area["overhang_inches"] is None:
            missing.append(f"{area['area_name']}: missing overhang")
            score -= 8
        elif area["overhang_inches"] > 15:
            conflicts.append(f"{area['area_name']}: abnormal overhang {area['overhang_inches']}")
            score -= 5
        if area["required_photos_count"] > area["uploaded_photos_count"]:
            missing.append(f"{area['area_name']}: missing required photos")
            score -= 6

    if not sub or not sub["has_signature"]:
        missing.append("Missing customer/builder signature")
        score -= 12

    if prior:
        prior_count = db.execute("SELECT COUNT(*) c FROM job_areas WHERE job_id=?", (prior["id"],)).fetchone()["c"]
        if prior_count != len(areas):
            conflicts.append("Area count differs from prior plan instance")
            score -= 5

    score = max(0, round(score, 1))
    if score >= 85 and not missing:
        reco = "ready_for_review"
    elif score >= 65:
        reco = "needs_correction"
    else:
        reco = "block"

    return {
        "completeness_score": score,
        "missing_items": missing,
        "conflicts": conflicts,
        "recommendation": reco,
    }


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "stone-workflow-platform"})


@app.post("/api/jobs")
def create_job():
    payload = request.get_json(force=True)
    missing = validate_job_payload(payload)
    if missing:
        return jsonify({"status": "invalid", "missing": missing}), 422

    db = get_db()
    builder_id = get_or_create_builder(payload["builder"])
    creator_id = get_or_create_user(
        payload.get("created_by_email", "system@local"), payload.get("created_by_name", "System"), "order_entry"
    )

    ts = now()
    cur = db.execute(
        """
        INSERT INTO jobs
        (job_number, builder_id, community, address, plan_number, house_type, material, thickness_mm, status, created_by, created_at, updated_at, override_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["job_number"],
            builder_id,
            payload["community"],
            payload["address"],
            payload["plan_number"],
            payload.get("house_type"),
            payload["material"],
            int(payload["thickness_mm"]),
            "ready_to_schedule",
            creator_id,
            ts,
            ts,
            payload.get("override_notes"),
        ),
    )
    job_id = cur.lastrowid

    for area in payload["areas"]:
        db.execute(
            """
            INSERT INTO job_areas
            (job_id, area_name, sink_model, appliance_model, edge_profile, backsplash, overhang_inches, corner_details, support_type, special_notes, required_photos_count, uploaded_photos_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                area["area_name"],
                area.get("sink_model"),
                area.get("appliance_model"),
                area.get("edge_profile"),
                area.get("backsplash"),
                area.get("overhang_inches"),
                area.get("corner_details"),
                area.get("support_type"),
                area.get("special_notes"),
                area.get("required_photos_count", 0),
                area.get("uploaded_photos_count", 0),
            ),
        )

    log_action(creator_id, "job", job_id, "create", None, payload)
    db.commit()
    return jsonify({"job_id": job_id, "status": "ready_to_schedule"}), 201


@app.get("/api/jobs/<int:job_id>/repeat-plan-suggestions")
def repeat_plan_suggestions(job_id: int):
    db = get_db()
    job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        return jsonify({"error": "job not found"}), 404

    history = db.execute(
        """
        SELECT id FROM jobs
        WHERE builder_id=? AND plan_number=? AND id != ?
        ORDER BY created_at DESC LIMIT 5
        """,
        (job["builder_id"], job["plan_number"], job_id),
    ).fetchall()

    if not history:
        return jsonify({"suggestions": {}, "notes": ["No historical plan data found"]})

    sink_counts, edge_counts = {}, {}
    for h in history:
        areas = db.execute("SELECT sink_model, edge_profile FROM job_areas WHERE job_id=?", (h["id"],)).fetchall()
        for a in areas:
            if a["sink_model"]:
                sink_counts[a["sink_model"]] = sink_counts.get(a["sink_model"], 0) + 1
            if a["edge_profile"]:
                edge_counts[a["edge_profile"]] = edge_counts.get(a["edge_profile"], 0) + 1

    return jsonify(
        {
            "suggestions": {
                "most_common_sink": max(sink_counts, key=sink_counts.get) if sink_counts else None,
                "most_common_edge": max(edge_counts, key=edge_counts.get) if edge_counts else None,
                "historical_jobs_checked": len(history),
            }
        }
    )


@app.post("/api/jobs/<int:job_id>/schedule")
def schedule(job_id: int):
    payload = request.get_json(force=True)
    if not payload.get("templater_email"):
        return jsonify({"error": "templater_email required"}), 400

    db = get_db()
    job = db.execute("SELECT id FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        return jsonify({"error": "job not found"}), 404

    templater_id = get_or_create_user(
        payload["templater_email"], payload.get("templater_name", "Templater"), payload.get("templater_role", "templater_in_house")
    )

    cur = db.execute(
        """
        INSERT INTO schedules
        (job_id, templater_id, scheduled_start, scheduled_end, territory, route_group, readiness_confirmed)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            templater_id,
            payload["scheduled_start"],
            payload["scheduled_end"],
            payload.get("territory"),
            payload.get("route_group"),
            int(bool(payload.get("readiness_confirmed", False))),
        ),
    )
    db.execute("UPDATE jobs SET status=?, updated_at=? WHERE id=?", ("scheduled", now(), job_id))
    log_action(templater_id, "job", job_id, "schedule", None, payload)
    db.commit()
    return jsonify({"status": "scheduled", "schedule_id": cur.lastrowid})


@app.post("/api/jobs/<int:job_id>/field-submission")
def field_submission(job_id: int):
    payload = request.get_json(force=True)
    db = get_db()
    templater = db.execute("SELECT id FROM users WHERE email=?", (payload.get("templater_email"),)).fetchone()
    if not templater:
        return jsonify({"error": "templater_email not found"}), 404

    cur = db.execute(
        """
        INSERT INTO template_submissions
        (job_id, templater_id, source, is_offline_synced, has_signature, notes, submitted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            templater["id"],
            payload.get("source", "manual"),
            int(bool(payload.get("is_offline_synced", False))),
            int(bool(payload.get("has_signature", False))),
            payload.get("notes"),
            now(),
        ),
    )
    db.execute("UPDATE jobs SET status=?, updated_at=? WHERE id=?", ("field_submitted", now(), job_id))
    log_action(templater["id"], "template_submission", job_id, "submit", None, payload)
    db.commit()
    return jsonify({"status": "field_submitted", "submission_id": cur.lastrowid})


@app.post("/api/jobs/<int:job_id>/ai-review")
def ai_review(job_id: int):
    db = get_db()
    job = db.execute("SELECT id FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        return jsonify({"error": "job not found"}), 404

    report = run_ai_review(job_id)
    cur = db.execute(
        """
        INSERT INTO ai_reviews
        (job_id, completeness_score, missing_items_json, conflicts_json, recommendation, reviewed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (job_id, report["completeness_score"], json.dumps(report["missing_items"]), json.dumps(report["conflicts"]), report["recommendation"], now()),
    )

    next_status = {
        "ready_for_review": "qa_review",
        "needs_correction": "needs_correction",
        "block": "blocked",
    }[report["recommendation"]]
    db.execute("UPDATE jobs SET status=?, updated_at=? WHERE id=?", (next_status, now(), job_id))
    log_action(None, "ai_review", job_id, "run", None, report)
    db.commit()
    return jsonify({"job_status": next_status, "ai_review_id": cur.lastrowid, "ai_review": report})


@app.post("/api/jobs/<int:job_id>/approve")
def approve(job_id: int):
    payload = request.get_json(force=True)
    db = get_db()
    status = payload.get("status", "pending")
    cur = db.execute(
        """
        INSERT INTO approvals (job_id, audience, status, comments, version, acted_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (job_id, payload.get("audience", "internal"), status, payload.get("comments"), payload.get("version", 1), now()),
    )

    if status == "approved":
        new_status = "ready_for_production"
    elif status in {"rejected", "revise"}:
        new_status = "needs_correction"
    else:
        new_status = "ready_for_approval"

    db.execute("UPDATE jobs SET status=?, updated_at=? WHERE id=?", (new_status, now(), job_id))
    log_action(None, "approval", job_id, status, None, payload)
    db.commit()
    return jsonify({"job_status": new_status, "approval_id": cur.lastrowid})


@app.post("/api/jobs/<int:job_id>/sps-stage")
def sps_stage(job_id: int):
    db = get_db()
    job = db.execute(
        """
        SELECT j.*, b.name AS builder_name
        FROM jobs j JOIN builders b ON b.id=j.builder_id
        WHERE j.id=?
        """,
        (job_id,),
    ).fetchone()
    if not job:
        return jsonify({"error": "job not found"}), 404
    areas = db.execute("SELECT * FROM job_areas WHERE job_id=?", (job_id,)).fetchall()

    payload = {
        "JobNumber": job["job_number"],
        "Builder": job["builder_name"],
        "Address": job["address"],
        "Plan": job["plan_number"],
        "Material": job["material"],
        "ThicknessMM": job["thickness_mm"],
        "Areas": [
            {
                "Name": a["area_name"],
                "Sink": a["sink_model"],
                "Appliance": a["appliance_model"],
                "Edge": a["edge_profile"],
                "Splash": a["backsplash"],
                "Overhang": a["overhang_inches"],
                "Support": a["support_type"],
            }
            for a in areas
        ],
        "ApprovalStatus": job["status"],
    }

    cur = db.execute(
        "INSERT INTO sps_exports (job_id, payload_json, export_status) VALUES (?, ?, ?)",
        (job_id, json.dumps(payload), "staged"),
    )
    log_action(None, "sps_export", job_id, "stage", None, payload)
    db.commit()
    return jsonify({"export_id": cur.lastrowid, "export_status": "staged", "payload": payload})


@app.get("/api/dashboard/kpis")
def kpis():
    db = get_db()
    jobs_entered = db.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
    jobs_scheduled = db.execute("SELECT COUNT(*) c FROM jobs WHERE status='scheduled'").fetchone()["c"]
    jobs_templated = db.execute("SELECT COUNT(*) c FROM jobs WHERE status='field_submitted'").fetchone()["c"]
    dry_runs = db.execute("SELECT COUNT(*) c FROM schedules WHERE dry_run_reason IS NOT NULL").fetchone()["c"]
    ai_blocked = db.execute("SELECT COUNT(*) c FROM jobs WHERE status='blocked'").fetchone()["c"]
    review_rows = db.execute("SELECT completeness_score FROM ai_reviews ORDER BY reviewed_at DESC LIMIT 200").fetchall()
    avg_score = round(sum(r["completeness_score"] for r in review_rows) / len(review_rows), 2) if review_rows else None

    return jsonify(
        {
            "jobs_entered": jobs_entered,
            "jobs_scheduled": jobs_scheduled,
            "jobs_templated": jobs_templated,
            "dry_runs": dry_runs,
            "ai_blocked_jobs": ai_blocked,
            "avg_ai_completeness_score": avg_score,
        }
    )


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
