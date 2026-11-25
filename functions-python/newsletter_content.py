"""Shared newsletter content: the author's style guide and the email builders.

Used by both the weekly generator (scripts/generate_newsletter.py) and the
revision Cloud Function (functions-python/main.py). No import-time side effects.
"""
import os
import re

import requests

from newsletter_review import REVIEWERS

SITE_URL = os.environ.get("SITE_URL", "https://karthikeyanselvam.com")


# ── VOICE / STYLE GUIDE — Karthikeyan Selvam ──────────────────────────────────
# Derived from his site copy (polished register) and how he talks in working
# sessions (attitude). The goal is that a reader who knows him recognizes the voice.
STYLE_GUIDE = """
WRITE AS KARTHIKEYAN SELVAM. His voice is specific — match it, don't write a generic blog post.

VOICE:
- First-person practitioner with 18 years in the field. You've actually rolled this
  out across enterprises — you write from the trenches, not from a press release.
- Short, declarative sentences. Use the em-dash for a punchy aside. Vary length but lean tight.
- Opinionated and concrete. Say what you actually think. State the uncomfortable part out loud.
- Skeptical of hype and vanity metrics. Call out vendor spin, inflated numbers, and lazy assumptions.
- Accuracy is non-negotiable. You'd be embarrassed to put a wrong number in front of experts —
  so if a fact isn't in the sources, you cut it rather than guess.
- Plain English. No buzzword salad ("leverage synergies", "in today's fast-paced world"),
  no corporate filler, no emoji, no bullet lists.

STRUCTURE:
- Open with a sharp, specific hook tied to the actual news — often a slightly contrarian take.
  Never open with throat-clearing or "In today's world".
- Middle: your read on what it really means for enterprises, grounded in the sources.
- Close with a practitioner's takeaway — what you'd do Monday morning, or what to watch for.

VOICE ANCHORS (the rhythm to echo — do NOT copy verbatim):
- "Process mining first, automation second — always."
- "Technology is only 30% of a transformation. The other 70% is people."
- "...architectures that survive a Monday morning in production."
- "Because no one cares about backup until they need it."
"""


# ── EMAILS ────────────────────────────────────────────────────────────────
def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def _safe_url(u):
    return u if re.match(r"^https?://", u or "") else "#"

TEAL = "#00C9A7"

def subscriber_item_html(kind, d):
    """One item's block for the SUBSCRIBER email. Each block is wrapped in
    <!--item:ID--> markers by the caller so approveIssue can strip any item the
    admin drops before approving."""
    parts = []
    if kind == "article":
        url = f"{SITE_URL}/newsletter.html"
        parts.append(f'<h2 style="font-size:20px;margin:24px 0 6px;">{_esc(d["title"])}</h2>')
        if d.get("takeaway"):
            parts.append(f'<p style="font-size:15px;font-weight:600;color:#111;margin:0 0 8px;border-left:3px solid {TEAL};padding-left:10px;">{_esc(d["takeaway"])}</p>')
        if d.get("excerpt"):
            parts.append(f'<p style="font-size:14px;line-height:1.6;color:#444;margin:0 0 8px;">{_esc(d["excerpt"])}</p>')
        if d.get("action"):
            parts.append(f'<p style="font-size:14px;color:#111;margin:0 0 6px;"><strong>Your move this week:</strong> {_esc(d["action"])}</p>')
        parts.append(f'<p style="margin:0 0 4px;"><a href="{url}" style="color:{TEAL};font-weight:600;text-decoration:none;">Read the full analysis →</a></p>')
    elif kind == "hype_check":
        parts.append('<div style="margin:28px 0;padding:16px;background:#faf6e8;border-radius:8px;">')
        parts.append('<p style="font-size:12px;letter-spacing:1px;text-transform:uppercase;color:#9a7d22;margin:0 0 6px;">Hype Check</p>')
        parts.append(f'<p style="font-size:14px;color:#444;margin:0 0 4px;"><em>{_esc(d["claim"])}</em></p>')
        parts.append(f'<p style="font-size:14px;color:#111;margin:0;">{_esc(d["reality"])}</p>')
        parts.append('</div>')
    elif kind == "links":
        parts.append('<h3 style="font-size:16px;margin:24px 0 8px;">Worth your time</h3>')
        for h in d.get("items", []):
            take = f' — {_esc(h["take"])}' if h.get("take") else ""
            parts.append(f'<p style="font-size:14px;line-height:1.5;margin:0 0 8px;"><a href="{_esc(_safe_url(h["url"]))}" style="color:{TEAL};text-decoration:none;font-weight:600;">{_esc(h["title"])}</a><span style="color:#444;">{take}</span></p>')
    return "".join(parts)


def build_subscriber_email(items, date_str):
    """items: list of (doc_id, kind, record) in display order (articles, hype, links)."""
    parts = ['<div style="font-family:Inter,Arial,sans-serif;color:#1a1a1a;max-width:640px;margin:0 auto;">']
    parts.append(f'<p style="color:#666;font-size:13px;letter-spacing:1px;text-transform:uppercase;">AI &amp; Digital Workplace Insights — {_esc(date_str)}</p>')
    for doc_id, kind, rec in items:
        parts.append(f"<!--item:{doc_id}-->{subscriber_item_html(kind, rec)}<!--/item:{doc_id}-->")
    parts.append('<hr style="border:none;border-top:1px solid #eee;margin:28px 0;">')
    parts.append(f'<p style="font-size:13px;color:#888;">Written by Karthikeyan Selvam — Digital Workplace &amp; AI Consultant — <a href="{SITE_URL}" style="color:{TEAL};">karthikeyanselvam.com</a></p>')
    parts.append('</div>')
    return "".join(parts)


VERDICT_COLOURS = {"pass": "#1f8a4c", "revise": "#b7791f", "fail": "#c53030", "error": "#718096"}
CLAIM_COLOURS = {"supported": "#1f8a4c", "outdated": "#b7791f", "overstated": "#b7791f",
                 "unsupported": "#c53030", "contradicted": "#c53030", "confidential": "#c53030"}
DECISION_LABEL = {"clean": ("✅ Both reviewers passed", "#1f8a4c"),
                  "flag":  ("⚠️ Needs your attention", "#b7791f"),
                  "drop":  ("⛔ Dropped automatically", "#c53030")}

def item_title(kind, rec):
    if kind == "article":
        return rec.get("title", "Untitled")
    if kind == "hype_check":
        return "Hype check: " + (rec.get("claim", "")[:90])
    return "Worth your time (quick links)"


def _button(href, label, bg, fg):
    return (f'<a href="{href}" style="display:inline-block;background:{bg};color:{fg};font-weight:700;'
            f'padding:11px 18px;border-radius:7px;text-decoration:none;margin:0 8px 8px 0;">{label}</a>')


def build_review_email(issue_id, date_str, reviewed, version=1, overall_note=""):
    """Digest for the ADMIN only.

    reviewed: list of dicts {id, kind, record, reviews, decision, reason} plus,
    for revisions, optional "note" (the admin's request) and "changes" (what the
    writer says it changed). Items without new reviews (untouched in a revision)
    may set reviews={} and decision="kept".

    The buttons open the review desk with the action pre-selected; the desk
    requires Google sign-in and a confirm tap, so neither a forwarded email nor
    a link-prefetching mail scanner can approve anything.
    """
    desk = f"{SITE_URL}/admin/?issue={issue_id}"
    reviewed_now = [r for r in reviewed if r["decision"] != "kept"]
    kept = [r for r in reviewed if r["decision"] != "drop"]
    flagged = [r for r in reviewed if r["decision"] == "flag"]
    dropped = [r for r in reviewed if r["decision"] == "drop"]
    vtag = f" v{version}" if version > 1 else ""

    p = ['<div style="font-family:Inter,Arial,sans-serif;color:#1a1a1a;max-width:680px;margin:0 auto;">']
    p.append(f'<p style="color:#666;font-size:13px;letter-spacing:1px;text-transform:uppercase;margin:0 0 6px;">'
             f'Newsletter review{vtag} — issue {issue_id}</p>')
    p.append(f'<h1 style="font-size:22px;margin:0 0 10px;">{len(kept)} item(s) ready · {len(flagged)} flagged · {len(dropped)} dropped</h1>')
    if version > 1:
        p.append(f'<p style="font-size:14px;color:#444;margin:0 0 12px;">Revised per your notes; '
                 f'{len(reviewed_now)} item(s) rewritten and re-checked by both reviewers.</p>')
        if overall_note:
            p.append(f'<p style="font-size:13px;color:#555;margin:0 0 16px;padding:10px 12px;background:#f6f6f6;border-radius:6px;">'
                     f'<strong>Your note:</strong> {_esc(overall_note)}</p>')
    else:
        p.append('<p style="font-size:14px;color:#444;margin:0 0 16px;">Nothing has been published or sent. '
                 'Two independent reviewers checked every claim against current web sources.</p>')
    p.append('<p style="margin:0 0 6px;">'
             + _button(f"{desk}&intent=approve", "✅ Approve &amp; send", "#1f8a4c", "#ffffff")
             + _button(f"{desk}&intent=changes", "✏️ Request changes", "#FF6B35", "#210D02")
             + _button(f"{desk}&intent=reject", "❌ Reject", "#ffffff;border:1px solid #c53030", "#c53030")
             + '</p>')
    p.append('<p style="font-size:12px;color:#888;margin:0 0 26px;">Each button opens your review desk '
             '(Google sign-in) and asks you to confirm — the email alone can\'t publish anything.</p>')

    for r in reviewed:
        if r["decision"] == "kept":
            label, colour = ("Unchanged in this version", "#888888")
        else:
            label, colour = DECISION_LABEL[r["decision"]]
        p.append(f'<div style="border:1px solid #e2e2e2;border-left:4px solid {colour};border-radius:8px;padding:16px 18px;margin:0 0 22px;">')
        reason = f' — {_esc(r["reason"])}' if r.get("reason") else ""
        p.append(f'<p style="font-size:12px;font-weight:700;color:{colour};margin:0 0 4px;">{label}{reason}</p>')
        p.append(f'<h2 style="font-size:18px;margin:0 0 10px;">{_esc(item_title(r["kind"], r["record"]))}</h2>')
        if r.get("note"):
            p.append(f'<p style="font-size:13px;color:#555;margin:0 0 6px;"><strong>Your note:</strong> {_esc(r["note"])}</p>')
        if r.get("changes"):
            p.append(f'<p style="font-size:13px;color:#1a1a1a;margin:0 0 8px;"><strong>What changed:</strong> {_esc(r["changes"])}</p>')

        for key, rev in (r.get("reviews") or {}).items():
            v = rev.get("verdict", "error")
            p.append(f'<p style="font-size:13px;margin:10px 0 4px;"><strong>{REVIEWERS[key]["label"]}</strong> '
                     f'<span style="color:{VERDICT_COLOURS.get(v, "#718096")};font-weight:700;text-transform:uppercase;">{v}</span>'
                     f'<span style="color:#888;"> · {_esc(rev.get("model", "").replace("models/", ""))}</span></p>')
            if rev.get("error"):
                p.append(f'<p style="font-size:13px;color:#718096;margin:0 0 4px;">Reviewer error: {_esc(rev["error"])}</p>')
            if rev.get("summary"):
                p.append(f'<p style="font-size:13px;color:#444;margin:0 0 6px;">{_esc(rev["summary"])}</p>')
            issues = [c for c in rev.get("claims", []) if c["verdict"] != "supported"]
            ok_count = len(rev.get("claims", [])) - len(issues)
            for c in issues:
                src = (f' <a href="{_esc(_safe_url(c["source_url"]))}" style="color:{TEAL};">source</a>' if c.get("source_url") else "")
                p.append(f'<p style="font-size:13px;margin:0 0 6px;padding-left:10px;border-left:2px solid {CLAIM_COLOURS[c["verdict"]]};">'
                         f'<strong style="color:{CLAIM_COLOURS[c["verdict"]]};">{c["verdict"]}</strong>: “{_esc(c["claim"])}”'
                         f'<br><span style="color:#555;">{_esc(c["evidence"])}</span>{src}</p>')
            if ok_count:
                p.append(f'<p style="font-size:12px;color:#1f8a4c;margin:0 0 4px;">{ok_count} claim(s) verified as supported.</p>')

        rec = r["record"]
        if r["kind"] == "article":
            p.append('<details><summary style="font-size:13px;color:#555;cursor:pointer;margin-top:10px;">Full draft</summary>')
            p.append(f'<p style="font-size:14px;font-weight:600;margin:10px 0 6px;">{_esc(rec.get("takeaway", ""))}</p>')
            p.append("".join(f'<p style="font-size:14px;line-height:1.6;color:#333;margin:0 0 10px;">{_esc(para)}</p>'
                             for para in (rec.get("body") or "").split("\n") if para.strip()))
            p.append('</details>')
        else:
            p.append(subscriber_item_html(r["kind"], rec))
        p.append('</div>')

    p.append(f'<p style="font-size:12px;color:#888;">If you do nothing, nothing publishes. Issue {issue_id}{vtag}.</p>')
    p.append('</div>')
    subject = (f"[Review{vtag}] Newsletter {issue_id}: {len(kept)} ready, "
               f"{len(flagged)} flagged, {len(dropped)} dropped")
    return subject, "".join(p)


def send_review_email(subject, html, url, secret):
    """Admin-only digest via the sendReviewEmail function (recipient is fixed
    server-side to the admin — this call cannot email anyone else)."""
    if not secret:
        raise RuntimeError("NEWSLETTER_SECRET not set — cannot send the review email")
    resp = requests.post(url, json={"subject": subject, "html": html},
                         headers={"X-Newsletter-Secret": secret}, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"review email failed: HTTP {resp.status_code} {resp.text[:200]}")
