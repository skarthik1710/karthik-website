"""Diagnostic: run the public newsletter query server-side.

Admin SDK ignores security rules but still needs the same composite index a
client needs. So:
  - success  -> the composite index exists; a client error is a RULES problem
  - FAILED_PRECONDITION -> the composite index is missing (fix: create it)
"""
import json
import os

import firebase_admin
from firebase_admin import credentials, firestore

firebase_admin.initialize_app(
    credentials.Certificate(json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"]))
)
db = firestore.client()

try:
    q = (
        db.collection("newsletter_articles")
        .where("status", "==", "approved")
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(12)
    )
    docs = list(q.stream())
    print(f"QUERY OK — composite index exists. Returned {len(docs)} approved doc(s):")
    for s in docs:
        d = s.to_dict()
        print(f"   • [{d.get('type','article')}] {d.get('title','')[:70]}  status={d.get('status')}")
    print("\n=> Index is fine. A client 'Error loading' is therefore a RULES/permissions issue.")
except Exception as e:
    print(f"QUERY FAILED: {type(e).__name__}")
    print(str(e))
    print("\n=> If this says the query requires an index, that's the client error too.")
