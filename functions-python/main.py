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

    try:
        _run(db, issue_ref, rev_ref, issue_id, req)
    except Exception as e:  # noqa: BLE001 — always hand the issue back to the admin
        msg = str(e)[:400]
        print(f"reviseIssue failed for {issue_id}: {msg}")
        rev_ref.update({"status": "failed", "error": msg})
        issue_ref.update({"status": "awaiting_approval"})
        try:
            send_review_email(
                f"[Review] Revision failed for newsletter {issue_id}",
                f"<p>The revision you requested could not be completed, so the issue is back to "
                f"<strong>awaiting approval</strong> with the previous version unchanged.</p>"
                f"<p>Error: {msg.replace('<', '&lt;')}</p>"
                f'<p><a href="https://karthikeyanselvam.com/admin/?issue={issue_id}">Open the review desk</a></p>',
                REVIEW_EMAIL_URL, NEWSLETTER_SECRET.value)
        except Exception as e2:  # noqa: BLE001
            print(f"could not send failure email: {e2}")


def _run(db, issue_ref, rev_ref, issue_id, req):
    issue = issue_ref.get().to_dict() or {}
    if issue.get("status") != "revising":
        raise RuntimeError(f"issue is {issue.get('status')}, not revising")

    version = int(req.get("version", 2))
    overall = req.get("overall_note", "") or ""
    notes = req.get("item_notes", {}) or {}
    item_ids = list(issue.get("item_ids", []))
    today = datetime.now(timezone.utc).strftime("%b %d, %Y")

    docs = {s.id: s for s in db.get_all([db.collection("newsletter_articles").document(i) for i in item_ids]) if s.exists}
    targets = [i for i in items_to_revise(item_ids, notes, overall)
               if i in docs and docs[i].to_dict().get("status") != "rejected"]   # admin-dropped stays dropped
    if not targets:
        raise RuntimeError("nothing to revise (no notes on items still in the issue)")

    client = genai.Client(api_key=GEMINI_API_KEY.value)
    review_client = genai.Client(api_key=GEMINI_API_KEY.value, http_options={"api_version": "v1beta"})

    rows, still_in, newly_dropped = [], [], []
    for item_id in item_ids:
        if item_id not in docs:
            continue
        rec = docs[item_id].to_dict()
        kind = rec.get("type", "article")
        if item_id not in targets:
            rows.append({"id": item_id, "kind": kind, "record": rec, "reviews": {}, "decision": "kept", "reason": ""})
            still_in.append(item_id)
            continue

        merged, changes = revise_item(client, WRITER_MODEL, kind, rec, notes.get(item_id, ""), overall, today)
        reviews = review_item(review_client, REVIEW_MODELS, merged, today)
        decision, reason = decide(reviews)
        prev_version = int(rec.get("revision_version", 1))
        update = {k: v for k, v in merged.items() if k in ("title", "takeaway", "excerpt", "action", "body",
                                                             "claim", "reality", "items")}
        update.update({
            "review": reviews, "review_decision": decision, "review_reason": reason,
            "revision_version": version, "last_changes": changes, "last_note": notes.get(item_id, "") or overall,
            "versions": firestore.ArrayUnion([snapshot(kind, rec, prev_version)]),
            "status": "rejected" if decision == "drop" else rec.get("status", "pending_review"),
        })
        docs[item_id].reference.update(update)
        rows.append({"id": item_id, "kind": kind, "record": {**rec, **merged}, "reviews": reviews,
                     "decision": decision, "reason": reason, "note": notes.get(item_id, ""), "changes": changes})
        (newly_dropped if decision == "drop" else still_in).append(item_id)

    kept_rows = [r for r in rows if r["id"] in still_in]
    issue_ref.update({
        "status": "awaiting_approval",
        "version": version,
        "item_ids": still_in,
        "dropped_ids": firestore.ArrayUnion(newly_dropped) if newly_dropped else issue.get("dropped_ids", []),
        "subject_candidates": [{"id": r["id"], "title": r["record"].get("title", "")}
                               for r in kept_rows if r["kind"] == "article"],
        "email_html": build_subscriber_email([(r["id"], r["kind"], r["record"]) for r in kept_rows],
                                             issue.get("date", issue_id)),
    })
    rev_ref.update({"status": "done", "finished_at": firestore.SERVER_TIMESTAMP,
                    "revised": targets, "dropped": newly_dropped})

    subject, html = build_review_email(issue_id, issue.get("date", issue_id), rows, version=version, overall_note=overall)
    send_review_email(subject, html, REVIEW_EMAIL_URL, NEWSLETTER_SECRET.value)
