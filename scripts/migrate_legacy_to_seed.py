#!/usr/bin/env python3
"""Migrate legacy server/data JSON into Tube-Next seed JSON for local/Firestore bootstrap."""
from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "server", "data")
OUT = os.path.join(ROOT, "tube_next", "assets", "seed_data.json")
TENANT = "org_waseda_london"


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def legacy_id(login_id: str, role: str, class_id: str, seat: str) -> str:
    if role == "teacher":
        return "WAL-TCH-001"
    m = re.match(r"^j(\d)([a-z])(\d+)$", login_id)
    if m:
        grade, section, num = m.groups()
        return f"WAL-J{grade}{section.upper()}-{num.zfill(2)}"
    return f"WAL-{login_id.upper()}"


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    accounts = load(os.path.join(DATA, "accounts.json"), {})
    assignments = load(os.path.join(DATA, "assignments.json"), {})
    progress_dir = os.path.join(DATA, "progress")

    users = {}
    login_map = {}
    for login_id, acct in accounts.items():
        uid = legacy_id(login_id, acct.get("role", "student"), acct.get("classId", ""), acct.get("seat", ""))
        if uid in users:
            uid = f"{uid}-{secrets.token_hex(2).upper()}"
        login_map[login_id] = uid
        grade = acct.get("level", "j2")
        users[uid] = {
            "tenant_id": TENANT,
            "role": acct.get("role", "student"),
            "grade": grade,
            "class_id": acct.get("classId", ""),
            "seat": acct.get("seat", ""),
            "assigned_grades": acct.get("classes", []) if acct.get("role") == "teacher" else [],
            "legacy_login": login_id,
            "legacy_sid": acct.get("sid"),
            "password_salt": acct.get("salt"),
            "password_hash": acct.get("hash"),
            "password_alg": acct.get("alg", "pbkdf2-600k"),
            "streak_days": 0,
            "xp": 0,
            "is_archived": False,
        }

    hw_rows = []
    for hw_id, hw in assignments.items():
        grade = hw.get("classId") or ""
        if not grade and hw.get("students"):
            sid = hw["students"][0]
            for u in users.values():
                if u.get("legacy_sid") == sid:
                    grade = u.get("class_id", "")
                    break
        hw_rows.append({
            "id": f"HW_{hw_id.upper()}",
            "tenant_id": TENANT,
            "title": hw.get("title", "Homework"),
            "source": hw.get("source", "grit2500"),
            "grade": grade.replace("a", "").replace("b", "") if grade else "j2",
            "class_id": hw.get("classId", ""),
            "word_range": [hw.get("from", 1), hw.get("to", 1)],
            "due_date": iso(hw.get("dueAt", int(datetime.now(tz=timezone.utc).timestamp() * 1000))),
            "note": hw.get("note", ""),
            "target_sids": hw.get("students") or [],
            "legacy_id": hw_id,
        })

    progress_rows = []
    sid_to_user = {u["legacy_sid"]: uid for uid, u in users.items() if u.get("legacy_sid")}
    for fname in os.listdir(progress_dir):
        if not fname.endswith(".json"):
            continue
        blob_doc = load(os.path.join(progress_dir, fname), {})
        sid = blob_doc.get("sid")
        uid = sid_to_user.get(sid)
        if not uid:
            continue
        blob = blob_doc.get("blob") or {}
        users[uid]["streak_days"] = blob.get("streak", 0)
        users[uid]["xp"] = blob.get("xp", 0)
        hw_map = blob.get("hw") or {}
        for legacy_hw, state in hw_map.items():
            aid = f"HW_{legacy_hw.upper()}"
            done = state.get("done") or {}
            total = len(done)
            progress_rows.append({
                "id": f"{uid}_{aid}",
                "tenant_id": TENANT,
                "user_id": uid,
                "assignment_id": aid,
                "status": "completed" if state.get("completedAt") else ("in_progress" if total else "not_started"),
                "score": min(100, total),
                "done_numbers": list(done.keys()),
                "updated_at": iso(state.get("completedAt") or state.get("startedAt") or blob_doc.get("savedAt", 0)),
            })

    seed = {
        "tenant_id": TENANT,
        "tenants": {
            TENANT: {
                "name": "Waseda Academy London",
                "curriculums": ["GRIT2500"],
                "branding": {
                    "primary_color": "#D97757",
                    "logo_url": "",
                    "app_title": "Tube for Schools",
                },
                "sources": [
                    {"id": "grit2500", "name": "Vocabulary GRIT 2500", "short": "GRIT", "max": 2500},
                ],
            }
        },
        "users": users,
        "assignments": {r["id"]: r for r in hw_rows},
        "progress": {r["id"]: r for r in progress_rows},
        "demo_passwords": {
            login_map.get("j2a01", "WAL-J2A-01"): "demo-j2a01",
            login_map.get("sensei", "WAL-TCH-001"): "demo-sensei",
        },
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(seed, f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUT}")
    print(f"Users: {len(users)}, Assignments: {len(hw_rows)}, Progress: {len(progress_rows)}")


if __name__ == "__main__":
    main()
