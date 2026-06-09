"""Delete stale pending_review newsletter drafts, keeping a few by title.

Destructive (uses the Admin SDK, which bypasses Firestore rules), so it runs in
DRY_RUN mode by default — it only prints what it *would* delete. Set
DRY_RUN=false to actually delete.

Env:
  FIREBASE_SERVICE_ACCOUNT  service-account JSON (same secret as the generator)
  KEEP_TITLES               '||'-separated article titles to KEEP
  DRY_RUN                   'false' to actually delete (default: dry run)
"""
import json
import os

import firebase_admin
from firebase_admin import credentials, firestore

firebase_admin.initialize_app(
    credentials.Certificate(json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"]))
)
db = firestore.client()

DRY_RUN = os.environ.get("DRY_RUN", "true").strip().lower() != "false"
KEEP = {t.strip() for t in os.environ.get("KEEP_TITLES", "").split("||") if t.strip()}


def main():
    print(f"Mode: {'DRY RUN (no deletes)' if DRY_RUN else 'LIVE DELETE'}")
    print(f"Keeping {len(KEEP)} title(s):")
    for t in KEEP:
        print(f"   • {t}")
    print()

    docs = list(db.collection("newsletter_articles").where("status", "==", "pending_review").stream())
    keep, delete = [], []
    for snap in docs:
        d = snap.to_dict()
        title = (d.get("title") or "").strip()
        kind = d.get("type", "article")
        if kind == "article" and title in KEEP:
            keep.append((snap.id, kind, title))
        else:
            delete.append((snap.reference, snap.id, kind, title or f"<{kind}>"))

    print(f"Total pending_review: {len(docs)}  |  keep: {len(keep)}  |  delete: {len(delete)}\n")
    print("KEEP:")
    for _id, kind, title in keep:
        print(f"   ✅ [{kind}] {title}  ({_id})")
    print("\nDELETE:")
    for _ref, _id, kind, title in delete:
        print(f"   🗑️  [{kind}] {title}  ({_id})")

    if DRY_RUN:
        print("\nDRY RUN — nothing deleted. Re-run with DRY_RUN=false to apply.")
        return

    n = 0
    for ref, _id, _kind, _title in delete:
        ref.delete()
        n += 1
    print(f"\nDeleted {n} draft(s).")


if __name__ == "__main__":
    main()
