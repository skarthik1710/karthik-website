"""Read-only: print pending-review newsletter drafts to stdout.

Used to review drafts from CI when the admin page is unavailable. Makes no
writes. Reads FIREBASE_SERVICE_ACCOUNT (same secret the generator uses).
"""
import json
import os

import firebase_admin
from firebase_admin import credentials, firestore

firebase_key = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])
firebase_admin.initialize_app(credentials.Certificate(firebase_key))
db = firestore.client()

STATUS = os.environ.get("DUMP_STATUS", "pending_review")
RULE = "=" * 78


def show(d):
    t = d.get("type", "article")
    print(RULE)
    print(f"[{t.upper()}]  status={d.get('status')}  date={d.get('date','')}")
    if t == "article":
        print(f"TITLE:    {d.get('title','')}")
        print(f"CATEGORY: {d.get('category','')}  ({d.get('category_key','')})")
        if d.get("takeaway"):
            print(f"TAKEAWAY: {d['takeaway']}")
        if d.get("excerpt"):
            print(f"EXCERPT:  {d['excerpt']}")
        if d.get("action"):
            print(f"ACTION:   {d['action']}")
        print(f"SOURCES:  {d.get('sources_used','')}")
        print("BODY:")
        print(d.get("body", ""))
    elif t == "links":
        print(f"TITLE: {d.get('title','Worth your time')}")
        for h in d.get("items", []):
            take = f" — {h['take']}" if h.get("take") else ""
            print(f"  • {h.get('title','')} ({h.get('source','')}){take}")
            print(f"    {h.get('url','')}")
    elif t == "hype_check":
        print(f"CLAIM:   {d.get('claim','')}")
        print(f"REALITY: {d.get('reality','')}")
        print(f"SOURCE:  {d.get('source','')}")
    else:
        print(json.dumps(d, default=str, indent=2))


def main():
    q = db.collection("newsletter_articles").where("status", "==", STATUS)
    rows = []
    for snap in q.stream():
        d = snap.to_dict()
        d["_id"] = snap.id
        rows.append(d)
    rows.sort(key=lambda d: str(d.get("created_at", "")), reverse=True)
    print(f"Found {len(rows)} doc(s) with status='{STATUS}'\n")
    for d in rows:
        show(d)
    print(RULE)


if __name__ == "__main__":
    main()
