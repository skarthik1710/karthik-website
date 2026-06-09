"""Publish a text post to LinkedIn (personal profile) via the Posts API.

Run by the "Post to LinkedIn" GitHub workflow. Each run mints a fresh access
token from the long-lived refresh token, so there's nothing to rotate between
runs — the only manual upkeep is re-running the OAuth bootstrap once a year when
the refresh token itself expires (~365 days).

Required env (GitHub secrets):
  LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, LINKEDIN_REFRESH_TOKEN
Optional:
  LINKEDIN_PERSON_URN   (urn:li:person:xxxx; auto-derived via /userinfo if unset)
  LINKEDIN_VERSION      (YYYYMM, defaults below; bump periodically)
  LINKEDIN_POST_FILE    (defaults to linkedin_post.txt)
"""
import json
import os
import sys

import requests

CLIENT_ID = os.environ["LINKEDIN_CLIENT_ID"]
CLIENT_SECRET = os.environ["LINKEDIN_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["LINKEDIN_REFRESH_TOKEN"]
PERSON_URN = os.environ.get("LINKEDIN_PERSON_URN", "").strip()
LINKEDIN_VERSION = os.environ.get("LINKEDIN_VERSION", "202605")
POST_FILE = os.environ.get("LINKEDIN_POST_FILE", "linkedin_post.txt")

MAX_CHARS = 3000  # LinkedIn commentary hard limit

# Posts API "little text format" treats these as control characters; escape them
# so the post renders verbatim and doesn't 422. '#' is intentionally left alone
# so hashtags stay clickable.
_RESERVED = set("\\<>{}[]()@|*~_")


def escape_commentary(text):
    return "".join("\\" + ch if ch in _RESERVED else ch for ch in text)


def get_access_token():
    resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "refresh_token",
            "refresh_token": REFRESH_TOKEN,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=20,
    )
    if resp.status_code != 200:
        sys.exit(
            f"Token refresh failed ({resp.status_code}): {resp.text}\n"
            "If this is an auth error, the refresh token likely expired "
            "(~365 days) — re-run scripts/linkedin_oauth_bootstrap.py and update "
            "the LINKEDIN_REFRESH_TOKEN secret."
        )
    return resp.json()["access_token"]


def resolve_person_urn(access_token):
    if PERSON_URN:
        return PERSON_URN
    resp = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=20,
    )
    if resp.status_code != 200:
        sys.exit(
            f"Could not derive person URN from /userinfo ({resp.status_code}): "
            f"{resp.text}\nSet the LINKEDIN_PERSON_URN secret explicitly."
        )
    return f"urn:li:person:{resp.json()['sub']}"


def main():
    try:
        with open(POST_FILE, encoding="utf-8") as f:
            raw = f.read().strip()
    except FileNotFoundError:
        sys.exit(f"Post file '{POST_FILE}' not found.")
    if not raw:
        sys.exit(f"Post file '{POST_FILE}' is empty — nothing to post.")
    if len(raw) > MAX_CHARS:
        sys.exit(f"Post is {len(raw)} chars; LinkedIn limit is {MAX_CHARS}.")

    access_token = get_access_token()
    author = resolve_person_urn(access_token)

    payload = {
        "author": author,
        "commentary": escape_commentary(raw),
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    resp = requests.post(
        "https://api.linkedin.com/rest/posts",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": LINKEDIN_VERSION,
        },
        data=json.dumps(payload),
        timeout=30,
    )
    if resp.status_code != 201:
        sys.exit(f"Post failed ({resp.status_code}): {resp.text}")

    post_urn = resp.headers.get("x-restli-id", "(id not returned)")
    print(f"Posted successfully: {post_urn}")
    print(f"View: https://www.linkedin.com/feed/update/{post_urn}/")


if __name__ == "__main__":
    main()
