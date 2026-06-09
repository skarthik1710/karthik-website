"""One-time (and ~yearly) LinkedIn OAuth bootstrap — run LOCALLY, not in CI.

Produces the LINKEDIN_REFRESH_TOKEN and LINKEDIN_PERSON_URN you store as GitHub
secrets. After that, the "Post to LinkedIn" workflow runs unattended until the
refresh token expires (~365 days), at which point you re-run this.

Prerequisites (do these once in https://developer.linkedin.com):
  1. Create an app, linked to a Company Page you administer.
  2. Add products: "Share on LinkedIn" (gives w_member_social) and
     "Sign In with LinkedIn using OpenID Connect" (gives openid/profile).
  3. Under Auth, add an Authorized redirect URL exactly matching REDIRECT_URI below.
  4. Confirm the app issues refresh tokens (Auth tab). If it does NOT, you'll get
     a 60-day access token only and will re-auth more often.

Usage:
  export LINKEDIN_CLIENT_ID=...   LINKEDIN_CLIENT_SECRET=...
  python scripts/linkedin_oauth_bootstrap.py
"""
import os
import sys
import urllib.parse

import requests

REDIRECT_URI = os.environ.get("LINKEDIN_REDIRECT_URI", "http://localhost:8000/callback")
SCOPES = "openid profile w_member_social"


def main():
    client_id = os.environ.get("LINKEDIN_CLIENT_ID") or input("Client ID: ").strip()
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET") or input("Client Secret: ").strip()

    auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
        }
    )
    print("\nStep 1 — open this URL in a browser, authorize, then copy the `code`")
    print(f"query param from the redirected URL (it'll point at {REDIRECT_URI}):\n")
    print(auth_url + "\n")

    code = input("Step 2 — paste the authorization code here: ").strip()
    if not code:
        sys.exit("No code provided.")

    resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=20,
    )
    if resp.status_code != 200:
        sys.exit(f"Token exchange failed ({resp.status_code}): {resp.text}")
    tok = resp.json()

    access_token = tok.get("access_token", "")
    refresh_token = tok.get("refresh_token")

    person_urn = ""
    if access_token:
        ui = requests.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        if ui.status_code == 200:
            person_urn = "urn:li:person:" + ui.json().get("sub", "")

    print("\n================= STORE THESE AS GITHUB SECRETS =================")
    if refresh_token:
        print(f"LINKEDIN_REFRESH_TOKEN = {refresh_token}")
    else:
        print("LINKEDIN_REFRESH_TOKEN = (none returned — refresh tokens are NOT")
        print("  enabled on this app; you'll re-auth every ~60 days using the")
        print("  access token instead. Check the app's Auth settings.)")
        print(f"LINKEDIN_ACCESS_TOKEN  = {access_token}")
    if person_urn:
        print(f"LINKEDIN_PERSON_URN    = {person_urn}")
    print("================================================================")
    print(
        f"\n(access token expires_in={tok.get('expires_in')}s, "
        f"refresh_token_expires_in={tok.get('refresh_token_expires_in')}s)"
    )
    print("\nAdd them with:  gh secret set LINKEDIN_REFRESH_TOKEN  (etc.)")


if __name__ == "__main__":
    main()
