"""reviseIssue: rewrites newsletter drafts from the admin's notes, re-reviews them,
and emails the admin the next version.

Trigger: the admin submits "Request changes" on /admin/ → the Node callable
requestRevision (admin-only) creates newsletter_issues/{issueId}/revisions/{n}.
This function picks that up. It never publishes or emails subscribers: the issue
goes back to awaiting_approval and the admin decides again.
"""
from datetime import datetime, timezone

from firebase_admin import firestore, initialize_app
from firebase_functions import firestore_fn, options
from firebase_functions.params import SecretParam
from google import genai

from newsletter_content import build_subscriber_email, build_review_email, send_review_email
from newsletter_review import decide, review_item
from newsletter_revise import items_to_revise, revise_item, snapshot

GEMINI_API_KEY = SecretParam("GEMINI_API_KEY")
NEWSLETTER_SECRET = SecretParam("NEWSLETTER_SECRET")

# Keep in sync with the weekly workflow's models (repo variables).
WRITER_MODEL = "models/gemini-2.5-flash"
REVIEW_MODELS = {"fact_checker": "models/gemini-2.5-flash", "editor": "models/gemini-2.5-flash"}
REVIEW_EMAIL_URL = "https://us-central1-karthik-website-b5801.cloudfunctions.net/sendReviewEmail"

initialize_app()


@firestore_fn.on_document_created(
    document="newsletter_issues/{issueId}/revisions/{revId}",
    region="us-central1",
    secrets=[GEMINI_API_KEY, NEWSLETTER_SECRET],
    timeout_sec=540,
    memory=options.MemoryOption.MB_512,
    max_instances=1,
)
def reviseIssue(event: firestore_fn.Event[firestore_fn.DocumentSnapshot | None]) -> None:
    db = firestore.client()
    issue_id = event.params["issueId"]
    rev_ref = db.collection("newsletter_issues").document(issue_id).collection("revisions").document(event.params["revId"])
    issue_ref = db.collection("newsletter_issues").document(issue_id)

    # Events are delivered at-least-once: claim the request so it runs once.
    @firestore.transactional
    def claim(tx):
        snap = rev_ref.get(transaction=tx)
        if not snap.exists or snap.to_dict().get("status") != "queued":
            return None
        tx.update(rev_ref, {"status": "running", "started_at": firestore.SERVER_TIMESTAMP})
        return snap.to_dict()

    req = claim(db.transaction())
    if req is None:
        return
    rev_id = event.params["revId"]

    @firestore.transactional
    def hand_back(tx):
        # Only reopen the issue if THIS revision still owns it (it may have been
        # rejected, approved, or superseded by a newer request meanwhile).
        snap = issue_ref.get(transaction=tx)
        d = snap.to_dict() or {}
        if d.get("status") == "revising" and d.get("current_revision") == rev_id:
            tx.update(issue_ref, {"status": "awaiting_approval"})
            return True
        return False

    try:
        result = _compute(db, issue_ref, issue_id, req)
    except Exception as e:  # noqa: BLE001 — nothing has been written; hand back unchanged
        msg = str(e)[:400]
        print(f"reviseIssue failed for {issue_id}: {msg}")
        rev_ref.update({"status": "failed", "error": msg})
        if hand_back(db.transaction()):
            _notify(f"[Review] Revision failed for newsletter {issue_id}",
                    f"<p>The revision you requested could not be completed. Nothing was changed: "
                    f"the issue is back to <strong>awaiting approval</strong> exactly as before.</p>"
                    f"<p>Error: {msg.replace('<', '&lt;')}</p>"
                    f'<p><a href="https://karthikeyanselvam.com/admin/?issue={issue_id}">Open the review desk</a></p>')
        return

    # Phase 2: all-or-nothing commit, only if this revision still owns the issue.
    @firestore.transactional
    def commit(tx):
        snap = issue_ref.get(transaction=tx)
        d = snap.to_dict() or {}
        if d.get("status") != "revising" or d.get("current_revision") != rev_id:
            return False
        for ref, update in result["article_updates"]:
            tx.update(ref, update)
        tx.update(issue_ref, result["issue_update"])
        tx.update(rev_ref, {"status": "done", "finished_at": firestore.SERVER_TIMESTAMP,
                            "revised": result["targets"], "dropped": result["dropped"]})
        return True

    if not commit(db.transaction()):
        rev_ref.update({"status": "superseded"})
        print(f"reviseIssue {issue_id}/{rev_id}: issue moved on before commit; discarded")
        return

    # Phase 3: email. A failure here must not roll anything back — the desk
    # already shows the new version.
    try:
        send_review_email(result["subject"], result["html"], REVIEW_EMAIL_URL, NEWSLETTER_SECRET.value)
    except Exception as e:  # noqa: BLE001
        print(f"reviseIssue: committed v{req.get('version')} but review email failed: {e}")
        rev_ref.update({"email_error": str(e)[:300]})


def _notify(subject, html):
    try:
        send_review_email(subject, html, REVIEW_EMAIL_URL, NEWSLETTER_SECRET.value)
    except Exception as e:  # noqa: BLE001
        print(f"could not send notification email: {e}")


def _compute(db, issue_ref, issue_id, req):
    """Phase 1: every Gemini call, NO writes. Returns what to commit."""
    issue = issue_ref.get().to_dict() or {}
    if issue.get("status") != "revising":
        raise RuntimeError(f"issue is {issue.get('status')}, not revising")

    version = int(req.get("version", 2))
    overall = req.get("overall_note", "") or ""
    notes = req.get("item_notes", {}) or {}
    item_ids = list(issue.get("item_ids", []))
    today = datetime.now(timezone.utc).strftime("%b %d, %Y")

    docs = {s.id: s for s in db.get_all([db.collection("newsletter_articles").document(i) for i in item_ids]) if s.exists}
    admin_dropped = {i for i, s in docs.items() if s.to_dict().get("status") == "rejected"}
    targets = [i for i in items_to_revise(item_ids, notes, overall) if i in docs and i not in admin_dropped]
    if not targets:
        raise RuntimeError("nothing to revise (no notes on items still in the issue)")

    client = genai.Client(api_key=GEMINI_API_KEY.value)
    review_client = genai.Client(api_key=GEMINI_API_KEY.value, http_options={"api_version": "v1beta"})

    rows, still_in, newly_dropped, article_updates = [], [], [], []
    for item_id in item_ids:
        if item_id not in docs:
            continue
        rec = docs[item_id].to_dict()
        kind = rec.get("type", "article")
        if item_id in admin_dropped:          # stays in the issue (restorable), not shown/counted
            still_in.append(item_id)
            continue
        if item_id not in targets:
            rows.append({"id": item_id, "kind": kind, "record": rec, "reviews": {}, "decision": "kept", "reason": ""})
            still_in.append(item_id)
            continue

        merged, changes = revise_item(client, WRITER_MODEL, kind, rec, notes.get(item_id, ""), overall, today)
        reviews = review_item(review_client, REVIEW_MODELS, merged, today)
        decision, reason = decide(reviews)
        update = {k: v for k, v in merged.items()
                  if k in ("title", "takeaway", "excerpt", "action", "body", "claim", "reality", "items")}
        update.update({
            "review": reviews, "review_decision": decision, "review_reason": reason,
            "revision_version": version, "last_changes": changes, "last_note": notes.get(item_id, "") or overall,
            "versions": firestore.ArrayUnion([snapshot(kind, rec, int(rec.get("revision_version", 1)))]),
            "status": "rejected" if decision == "drop" else rec.get("status", "pending_review"),
        })
        article_updates.append((docs[item_id].reference, update))
        rows.append({"id": item_id, "kind": kind, "record": {**rec, **merged}, "reviews": reviews,
                     "decision": decision, "reason": reason, "note": notes.get(item_id, ""), "changes": changes})
        (newly_dropped if decision == "drop" else still_in).append(item_id)

    # Email blocks for every item still in the issue (admin-dropped included, so a
    # restore still works; approveIssue strips non-approved blocks by marker).
    block_rows = [r for r in rows if r["id"] in still_in] + [
        {"id": i, "kind": docs[i].to_dict().get("type", "article"), "record": docs[i].to_dict()}
        for i in still_in if i in admin_dropped]
    order = {i: n for n, i in enumerate(item_ids)}
    block_rows.sort(key=lambda r: order.get(r["id"], 0))
    issue_update = {
        "status": "awaiting_approval",
        "version": version,
        "item_ids": still_in,
        "subject_candidates": [{"id": r["id"], "title": r["record"].get("title", "")}
                               for r in block_rows if r["kind"] == "article" and r["id"] not in admin_dropped],
        "email_html": build_subscriber_email([(r["id"], r["kind"], r["record"]) for r in block_rows],
                                             issue.get("date", issue_id)),
    }
    if newly_dropped:
        issue_update["dropped_ids"] = firestore.ArrayUnion(newly_dropped)
    subject, html = build_review_email(issue_id, issue.get("date", issue_id), rows, version=version, overall_note=overall)
    return {"article_updates": article_updates, "issue_update": issue_update, "targets": targets,
            "dropped": newly_dropped, "subject": subject, "html": html}
