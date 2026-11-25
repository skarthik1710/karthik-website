import os
import re
import json
import time
import random
import requests
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree
import firebase_admin
from firebase_admin import credentials, firestore
from google import genai

from newsletter_review import REVIEWERS, review_item, decide

# --- Clients ---
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
firebase_key = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])
cred = credentials.Certificate(firebase_key)
firebase_admin.initialize_app(cred)
db = firestore.client()

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "skarthik1710@gmail.com")
SITE_URL    = os.environ.get("SITE_URL", "https://karthikeyanselvam.com")

# Human-in-the-loop (no auto-publish). Every run saves DRAFTS (pending_review) for
# one issue, has two independent search-grounded reviewers check them, and emails
# the admin a review digest. Nothing goes live on the site or to subscribers until
# the admin approves the issue at /admin/ (approveIssue Cloud Function).
RECENCY_DAYS   = 7      # only write about news from the last week
MIN_BODY_WORDS = 350    # reject anything thinner than this
NUM_ARTICLES   = 2      # fewer, deeper pieces per issue
QUICK_HITS     = 3      # "links worth your time" — headline + one-line take

WRITER_MODEL   = os.environ.get("NEWSLETTER_WRITER_MODEL", "models/gemini-2.5-flash")
REVIEW_MODELS  = {
    "fact_checker": os.environ.get("NEWSLETTER_FACTCHECK_MODEL", "models/gemini-2.5-pro"),
    "editor":       os.environ.get("NEWSLETTER_EDITOR_MODEL", "models/gemini-2.5-flash"),
}
REVIEW_EMAIL_URL = os.environ.get(
    "REVIEW_EMAIL_URL",
    "https://us-central1-karthik-website-b5801.cloudfunctions.net/sendReviewEmail")
NEWSLETTER_SECRET = os.environ.get("NEWSLETTER_SECRET", "")
FORCE_RERUN = os.environ.get("NEWSLETTER_FORCE", "").strip().lower() in ("1", "true", "yes")

# --- Real News Sources (RSS feeds, no API key needed) ---
RSS_FEEDS = [
    "https://feeds.feedburner.com/venturebeat/SZYF",       # VentureBeat AI
    "https://www.artificialintelligence-news.com/feed/",    # AI News
    "https://techcrunch.com/category/artificial-intelligence/feed/",  # TechCrunch AI
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", # The Verge AI
]

TOPICS = [
    "Microsoft Copilot and AI workplace productivity",
    "Enterprise AI adoption and digital transformation",
    "RPA and intelligent automation trends",
    "AI governance, ethics and enterprise risk",
    "Google Workspace AI and collaboration tools",
]


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


# ── DATE HELPERS ──────────────────────────────────────────────────────────────
def parse_pub_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


# ── 1. FETCH REAL NEWS FROM RSS (recent only) ─────────────────────────────────
def fetch_real_news(max_items=30):
    articles = []
    headers  = {"User-Agent": "Mozilla/5.0 (compatible; KSNewsletter/1.0)"}
    for url in RSS_FEEDS:
        try:
            resp = requests.get(url, timeout=10, headers=headers)
            root = ElementTree.fromstring(resp.content)
            items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
            for item in items[:8]:
                def t(tag):
                    return (item.findtext(tag) or "").strip()
                title   = t("title")
                link    = t("link")
                summary = t("description") or t("{http://www.w3.org/2005/Atom}summary")
                pub     = t("pubDate") or t("{http://www.w3.org/2005/Atom}updated")
                summary = re.sub(r"<[^>]+>", "", summary)[:400]  # strip html
                if title and link:
                    articles.append({
                        "title":   title,
                        "link":    link,
                        "summary": summary,
                        "source":  url.split("/")[2],
                        "pub":     pub,
                        "pub_dt":  parse_pub_date(pub),
                    })
        except Exception as e:
            print(f"RSS fetch failed for {url}: {e}")

    # deduplicate by title
    seen, unique = set(), []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)

    # recency filter: keep items from the last RECENCY_DAYS; keep undated items too
    cutoff = datetime.now(timezone.utc) - timedelta(days=RECENCY_DAYS)
    recent = [a for a in unique if (a["pub_dt"] is None or a["pub_dt"] >= cutoff)]

    # if recency leaves us too thin, fall back to the freshest items we have
    if len(recent) < 3:
        dated = sorted([a for a in unique if a["pub_dt"]], key=lambda a: a["pub_dt"], reverse=True)
        recent = (dated + [a for a in unique if not a["pub_dt"]])[:max_items]

    print(f"   {len(recent)}/{len(unique)} items within last {RECENCY_DAYS} days")
    return recent[:max_items]


# ── 2. PULL RECENT ARTICLES (for de-duplication) ──────────────────────────────
def fetch_recent_history(limit=40):
    """Past titles + source URLs we've already covered, so we don't repeat ourselves."""
    titles, used_urls = [], set()
    try:
        q = (db.collection("newsletter_articles")
               .order_by("created_at", direction=firestore.Query.DESCENDING)
               .limit(limit))
        for doc in q.stream():
            d = doc.to_dict() or {}
            if d.get("title"):
                titles.append(d["title"])
            for ns in (d.get("news_sources") or []):
                if ns.get("url"):
                    used_urls.add(ns["url"])
    except Exception as e:
        print(f"   ⚠️ Could not load history (continuing without de-dup): {e}")
    return titles, used_urls


# ── 3. FILTER NEWS RELEVANT TO TOPIC (skip already-used sources) ──────────────
def filter_news_for_topic(news, topic, used_urls):
    fresh = [a for a in news if a["link"] not in used_urls]
    pool  = fresh if len(fresh) >= 3 else news  # don't starve if everything was used
    keywords = topic.lower().split()
    scored = []
    for i, a in enumerate(pool):
        text  = (a["title"] + " " + a["summary"]).lower()
        score = sum(1 for k in keywords if k in text)
        if score > 0:
            scored.append((score, i, a))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    results = [a for _, _, a in scored[:5]]
    return results if results else pool[:3]


# ── 4. BUILD STRICT, VOICE-MATCHED PROMPT ─────────────────────────────────────
def build_prompt(topic, relevant_news, recent_titles, today):
    news_block = ""
    for i, a in enumerate(relevant_news, 1):
        news_block += f"""
SOURCE {i}:
  Headline : {a["title"]}
  From     : {a["source"]}
  Published: {a["pub"]}
  Summary  : {a["summary"]}
  URL      : {a["link"]}
"""

    avoid_block = "\n".join(f"  - {t}" for t in recent_titles[:20]) or "  (none yet)"

    return f"""{STYLE_GUIDE}

Today is {today}.

Your task is to write ONE newsletter article about: "{topic}"

════════════════════════════════════════════════════
REAL NEWS SOURCES FOR THIS ARTICLE (use ONLY these):
════════════════════════════════════════════════════
{news_block}
════════════════════════════════════════════════════
ALREADY COVERED IN RECENT ISSUES — do NOT repeat these topics or angles:
{avoid_block}
════════════════════════════════════════════════════

STRICT RULES — violating ANY rule means the article is rejected:
1. ACCURACY IS ABSOLUTE. Every specific fact — every statistic, percentage, dollar
   figure, date, company quote, product name, model name, version number, or
   benchmark result — MUST appear verbatim in the SOURCE text above. If it is not
   written in a source, you may NOT write it. Do NOT recall numbers or names from
   memory. Do NOT estimate, round, or invent a plausible-sounding figure. When in
   doubt, leave it out.
   ✗ NEVER do this: name a model or benchmark ("GPT-5.4", "scored 94.7% accuracy")
     or a deal size ("a $250 million settlement") that is not quoted in a source.
   ✓ Instead, make the point qualitatively: "a major vendor settlement", "a new
     open-source model", "a notable jump in accuracy" — no invented specifics.
2. OPINION vs FACT. Your analysis, predictions, and practitioner judgment are yours —
   state them freely as opinion. But anything phrased as a fact or a number must be
   traceable to a source above. Keep that line clean.
3. RECENT: only discuss what's in these sources (all from the last few days). Do not
   reach for older background facts unless they appear in a source.
4. UNIQUE & NO OVERLAP: this issue has multiple articles. Build THIS one on DIFFERENT
   source headlines and a different angle than the others — do not re-tell the same
   news. Also do not rehash the "already covered" list. Synthesize in your own words;
   never copy phrasing from the source summaries.
5. VOICE: write as Karthikeyan Selvam per the style guide. Opinionated practitioner,
   not a neutral reporter.
6. No bullet points. Flowing paragraphs only.
7. Length: 450–550 words for BODY.

OUTPUT FORMAT (exactly):
TITLE: [A specific, compelling title that references actual news]
CATEGORY: [One of: Microsoft Copilot | AI & ML | RPA & Automation | Enterprise Tech]
CATEGORY_KEY: [One of: copilot | ai | rpa | enterprise]
TAKEAWAY: [ONE sentence — the single thing the reader should take away. Concrete, not a teaser. Start with who it's for, e.g. "If you run a Copilot rollout, ..."]
EXCERPT: [2 sentences — hook the reader, reference real news, no fluff]
ACTION: [ONE specific thing the reader could actually do THIS WEEK because of this news. A real step, not "stay informed". No fluff.]
SOURCES_USED: [Comma-separated list of source domains you drew facts from]
BODY:
[Full article here — 450-550 words, first person, practitioner tone, grounded in the sources above]
"""


# ── 5. GENERATE ARTICLE VIA GEMINI ────────────────────────────────────────────
def generate_article(topic, relevant_news, recent_titles, today):
    prompt = build_prompt(topic, relevant_news, recent_titles, today)
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=WRITER_MODEL,
                contents=prompt,
            )
            return response.text
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait = 60 * (attempt + 1)
                print(f"Rate limit. Waiting {wait}s...")
                time.sleep(wait)
            else:
                raise e
    return None


# ── 6. PARSE GEMINI RESPONSE ──────────────────────────────────────────────────
def parse_article(raw):
    def extract(pattern, text, default=""):
        m = re.search(pattern, text, re.DOTALL)
        return m.group(1).strip() if m else default

    return {
        "title":        extract(r"TITLE:\s*([^\n]+)", raw) or "AI Insights",
        "category":     extract(r"CATEGORY:\s*([^\n]+)", raw) or "AI & ML",
        "category_key": (extract(r"CATEGORY_KEY:\s*([^\n]+)", raw) or "ai").lower(),
        "takeaway":     extract(r"TAKEAWAY:\s*(.+?)(?=EXCERPT:|ACTION:|SOURCES_USED:|BODY:)", raw),
        "excerpt":      extract(r"EXCERPT:\s*(.+?)(?=ACTION:|SOURCES_USED:|BODY:)", raw),
        "action":       extract(r"ACTION:\s*(.+?)(?=SOURCES_USED:|BODY:)", raw),
        "sources_used": extract(r"SOURCES_USED:\s*([^\n]+)", raw),
        "body":         extract(r"BODY:\n(.+)", raw),
    }


# ── 7. VALIDATE (structural gate before review) ───────────────────────────
def validate_article(p):
    body  = (p.get("body") or "").strip()
    words = len(body.split())
    if words < MIN_BODY_WORDS:
        return False, f"too short ({words} words)"
    if not p.get("title"):
        return False, "missing title"
    if not (p.get("sources_used") or "").strip():
        return False, "no sources cited"
    low = body.lower()
    for bad in ["lorem ipsum", "as an ai", "i cannot", "[insert", "todo:", "xxxx", "as a language model"]:
        if bad in low:
            return False, f"contains placeholder/refusal marker: '{bad}'"
    return True, "ok"


# ── 7b. GROUNDING GATE — reject fabricated specifics (accuracy first) ──────────
# The model is shown ONLY each source's title + summary, so every concrete figure
# or model/version name it writes must trace back to that text. Anything that
# doesn't is treated as a hallucination and the article is rejected. We deliberately
# err toward rejecting borderline cases — a dropped article beats a wrong one.
ALLOWED_NUMBERS = {"18", "30", "70"}   # his stock voice anchors (e.g. "30% tech / 70% people")
MODEL_PATTERN   = re.compile(
    r"\b(gpt|claude|gemini|llama|mistral|grok|harness|phi|qwen|copilot)[-\s]?\d+(?:\.\d+)?\b",
    re.I,
)

def _squash(s):
    return re.sub(r"[\s\-]", "", s).lower()

def check_grounding(text, news_sources):
    src = " ".join((n.get("title", "") + " " + n.get("summary", "")) for n in news_sources)
    src_squash = _squash(src)
    year = str(datetime.now(timezone.utc).year)

    ungrounded = []

    # dollar amounts ($250 million, $13 billion) and percentages (94.7%, 43 percent)
    money_pct = re.findall(r"\$\s?\d[\d,.]*\s?(?:billion|million|trillion|bn|m|k)?", text, re.I)
    money_pct += re.findall(r"\d+(?:\.\d+)?\s?(?:%|percent)", text, re.I)
    for tok in money_pct:
        digits = re.findall(r"\d[\d,.]*", tok)
        core = digits[0].replace(",", "") if digits else ""
        if not core or core in ALLOWED_NUMBERS or core.startswith(year):
            continue
        if core not in _squash(src):
            ungrounded.append(tok.strip())

    # AI model + version names (GPT-5.4, Harness-1, Claude 3.5) not in the sources
    for m in MODEL_PATTERN.finditer(text):
        if _squash(m.group(0)) not in src_squash:
            ungrounded.append(m.group(0).strip())

    if ungrounded:
        seen, uniq = set(), []
        for u in ungrounded:
            if u.lower() not in seen:
                seen.add(u.lower()); uniq.append(u)
        return False, "ungrounded specifics not in sources: " + ", ".join(uniq[:6])
    return True, "ok"


# ── 8. DRAFT RECORDS (saved after review — never auto-published) ─────────────
def article_record(parsed, date_str, issue_id, news_sources):
    return {
        "type":         "article",
        "title":        parsed["title"],
        "category":     parsed["category"],
        "category_key": parsed["category_key"],
        "takeaway":     parsed.get("takeaway", ""),
        "excerpt":      parsed["excerpt"],
        "action":       parsed.get("action", ""),
        "body":         parsed["body"],
        "sources_used": parsed["sources_used"],
        "news_sources": [{"title": n["title"], "url": n["link"], "source": n["source"]} for n in news_sources],
        "date":         date_str,
        "issue_id":     issue_id,
    }


# ── 9. QUICK HITS — "links worth your time" (headline + one-line take) ─────────
def generate_quick_hits(news_items, today):
    """One short, opinionated sentence per link, in Karthik's voice. Grounded:
    any take that smuggles in a figure/model not in its source is dropped."""
    if not news_items:
        return []
    src_block = ""
    for i, a in enumerate(news_items, 1):
        src_block += f'{i}. "{a["title"]}" ({a["source"]}) — {a["summary"]}\n'

    prompt = f"""{STYLE_GUIDE}

Today is {today}. Below are {len(news_items)} recent news items. For EACH, write ONE
sentence in Karthik's voice — your sharp practitioner take on why it matters (or why it
doesn't). No invented numbers, names, or figures beyond what's in the item. No hype.

{src_block}

OUTPUT: one line per item, numbered to match, format exactly:
1. [your one-sentence take]
2. [your one-sentence take]
(continue for all items)
"""
    try:
        resp = client.models.generate_content(model=WRITER_MODEL, contents=prompt)
        text = resp.text or ""
    except Exception as e:
        print(f"   ⚠️ Quick-hits generation failed: {e}")
        return []

    takes = {}
    for line in text.splitlines():
        m = re.match(r"\s*(\d+)[.)]\s*(.+)", line)
        if m:
            takes[int(m.group(1))] = m.group(2).strip()

    hits = []
    for i, a in enumerate(news_items, 1):
        take = takes.get(i, "").strip()
        if not take:
            continue
        ok, _ = check_grounding(take, [a])   # the take must not invent specifics
        if not ok:
            take = ""                         # keep the link, drop the ungrounded take
        hits.append({"title": a["title"], "url": a["link"], "source": a["source"], "take": take})
    return hits


# ── 10. HYPE CHECK — call out one overblown claim of the week ──────────────────
def generate_hype_check(news_items, today):
    if not news_items:
        return None
    src_block = ""
    for i, a in enumerate(news_items, 1):
        src_block += f'{i}. "{a["title"]}" ({a["source"]}) — {a["summary"]}\n'

    prompt = f"""{STYLE_GUIDE}

Today is {today}. From the news items below, pick the ONE claim, headline, or vendor
promise that is most overhyped or oversold, and cut it down to size in Karthik's voice.
Quote ONLY what's in the items — invent no numbers or names.

{src_block}

OUTPUT format exactly:
CLAIM: [the overblown claim, paraphrased from one item]
REALITY: [your one or two sentence skeptical take — what's actually true / what to watch]
SOURCE: [the source domain of the item you picked]
"""
    try:
        resp = client.models.generate_content(model=WRITER_MODEL, contents=prompt)
        raw = resp.text or ""
    except Exception as e:
        print(f"   ⚠️ Hype-check generation failed: {e}")
        return None

    def ex(p):
        m = re.search(p, raw, re.DOTALL)
        return m.group(1).strip() if m else ""
    claim   = ex(r"CLAIM:\s*(.+?)(?=REALITY:|SOURCE:|$)")
    reality = ex(r"REALITY:\s*(.+?)(?=SOURCE:|$)")
    source  = ex(r"SOURCE:\s*(.+)")
    if not (claim and reality):
        return None
    ok, reason = check_grounding(claim + " " + reality, news_items)
    if not ok:
        print(f"   ⚠️ Hype-check dropped (ungrounded: {reason})")
        return None
    return {"claim": claim, "reality": reality, "source": source}


# ── 11. PER-ISSUE EXTRAS (links / hype_check) live in newsletter_articles ────
# Same collection (a `type` field tells them apart) so the existing public read
# rule (approved only) and the site's queries cover them.
def extra_record(doc_type, payload, date_str, issue_id):
    return {"type": doc_type, "date": date_str, "issue_id": issue_id, **payload}


# ── 12. EMAILS ────────────────────────────────────────────────────────────────
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

def _item_title(kind, rec):
    if kind == "article":
        return rec.get("title", "Untitled")
    if kind == "hype_check":
        return "Hype check: " + (rec.get("claim", "")[:90])
    return "Worth your time (quick links)"


def build_review_email(issue_id, date_str, reviewed):
    """Digest for the ADMIN only. reviewed: list of dicts
    {id, kind, record, reviews, decision, reason}."""
    approve_url = f"{SITE_URL}/admin/?issue={issue_id}"
    kept = [r for r in reviewed if r["decision"] != "drop"]
    flagged = [r for r in reviewed if r["decision"] == "flag"]
    dropped = [r for r in reviewed if r["decision"] == "drop"]

    p = ['<div style="font-family:Inter,Arial,sans-serif;color:#1a1a1a;max-width:680px;margin:0 auto;">']
    p.append(f'<p style="color:#666;font-size:13px;letter-spacing:1px;text-transform:uppercase;margin:0 0 6px;">Newsletter review — issue {issue_id}</p>')
    p.append(f'<h1 style="font-size:22px;margin:0 0 10px;">{len(kept)} item(s) ready · {len(flagged)} flagged · {len(dropped)} dropped</h1>')
    p.append('<p style="font-size:14px;color:#444;margin:0 0 16px;">Nothing has been published or sent. '
             'Two independent reviewers checked every claim against current web sources. '
             'Read below, then approve or reject on the review desk (Google sign-in required).</p>')
    p.append(f'<p style="margin:0 0 28px;"><a href="{approve_url}" style="display:inline-block;background:#FF6B35;color:#210D02;'
             f'font-weight:700;padding:12px 22px;border-radius:7px;text-decoration:none;">Review &amp; approve on the desk →</a></p>')

    for r in reviewed:
        label, colour = DECISION_LABEL[r["decision"]]
        p.append(f'<div style="border:1px solid #e2e2e2;border-left:4px solid {colour};border-radius:8px;padding:16px 18px;margin:0 0 22px;">')
        p.append(f'<p style="font-size:12px;font-weight:700;color:{colour};margin:0 0 4px;">{label} — {_esc(r["reason"])}</p>')
        p.append(f'<h2 style="font-size:18px;margin:0 0 10px;">{_esc(_item_title(r["kind"], r["record"]))}</h2>')

        for key, rev in r["reviews"].items():
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
                src = (f' <a href="{_esc(c["source_url"])}" style="color:{TEAL};">source</a>' if c.get("source_url") else "")
                p.append(f'<p style="font-size:13px;margin:0 0 6px;padding-left:10px;border-left:2px solid {CLAIM_COLOURS[c["verdict"]]};">'
                         f'<strong style="color:{CLAIM_COLOURS[c["verdict"]]};">{c["verdict"]}</strong>: “{_esc(c["claim"])}”'
                         f'<br><span style="color:#555;">{_esc(c["evidence"])}</span>{src}</p>')
            if ok_count:
                p.append(f'<p style="font-size:12px;color:#1f8a4c;margin:0 0 4px;">{ok_count} claim(s) verified as supported.</p>')

        rec = r["record"]
        if r["kind"] == "article":
            p.append('<details><summary style="font-size:13px;color:#555;cursor:pointer;margin-top:10px;">Full draft</summary>')
            p.append(f'<p style="font-size:14px;font-weight:600;margin:10px 0 6px;">{_esc(rec.get("takeaway", ""))}</p>')
            body_html = "".join(f'<p style="font-size:14px;line-height:1.6;color:#333;margin:0 0 10px;">{_esc(para)}</p>'
                                for para in (rec.get("body") or "").split("\n") if para.strip())
            p.append(body_html)
            p.append('</details>')
        else:
            p.append(subscriber_item_html(r["kind"], rec))
        p.append('</div>')

    p.append(f'<p style="font-size:12px;color:#888;">If you do nothing, nothing publishes. Issue id: {issue_id}</p>')
    p.append('</div>')
    subject = f"[Review] Newsletter {issue_id}: {len(kept)} ready, {len(flagged)} flagged, {len(dropped)} dropped"
    return subject, "".join(p)


def send_review_email(subject, html):
    """Admin-only digest via the sendReviewEmail function (recipient is fixed
    server-side to the admin — this call cannot email anyone else)."""
    if not NEWSLETTER_SECRET:
        raise RuntimeError("NEWSLETTER_SECRET not set — cannot send the review email")
    resp = requests.post(REVIEW_EMAIL_URL, json={"subject": subject, "html": html},
                         headers={"X-Newsletter-Secret": NEWSLETTER_SECRET}, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"review email failed: HTTP {resp.status_code} {resp.text[:200]}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    now      = datetime.now(timezone.utc)
    today    = now.strftime("%b %d, %Y")
    date_str = today
    issue_id = now.strftime("%Y-%m-%d")
    issue_ref = db.collection("newsletter_issues").document(issue_id)

    # Idempotency: a re-run (or a manual dispatch on the same day) must not create
    # a second batch of drafts or a second review email for an issue that exists.
    existing = issue_ref.get()
    if existing.exists and not FORCE_RERUN:
        print(f"Issue {issue_id} already exists (status: {existing.to_dict().get('status')}). "
              f"Nothing to do. Set NEWSLETTER_FORCE=true to regenerate a non-approved issue.")
        raise SystemExit(0)
    if existing.exists and existing.to_dict().get("status") not in ("awaiting_approval", "rejected"):
        print(f"Issue {issue_id} is {existing.to_dict().get('status')} — refusing to regenerate it.")
        raise SystemExit(1)
    if existing.exists:
        # Forced regeneration: retire the previous drafts so the desk shows one batch.
        old = db.collection("newsletter_articles").where("issue_id", "==", issue_id).stream()
        retire = db.batch()
        for d in old:
            if (d.to_dict() or {}).get("status") == "pending_review":
                retire.update(d.reference, {"status": "rejected", "review_reason": "superseded by a forced re-run"})
        retire.commit()

    print("📰 Fetching real news...")
    all_news = fetch_real_news(max_items=30)
    print(f"   Found {len(all_news)} usable articles from RSS feeds")

    print("🗂️  Loading recent history for de-duplication...")
    recent_titles, used_urls = fetch_recent_history(limit=40)
    print(f"   {len(recent_titles)} past titles, {len(used_urls)} source URLs already used")

    selected_topics = random.sample(TOPICS, len(TOPICS))   # shuffle; take the first that produce valid articles
    drafts = []   # (kind, record) in display order — first article = lead

    for topic in selected_topics:
        if sum(1 for k, _ in drafts if k == "article") >= NUM_ARTICLES:
            break
        print(f"\n✍️  Writing: {topic}")
        relevant = filter_news_for_topic(all_news, topic, used_urls)
        print(f"   Using {len(relevant)} relevant (unused) news sources")
        if not relevant:
            print("   ⚠️ No fresh sources for this topic, skipping.")
            continue

        ok = False
        for attempt in range(2):  # generate, validate, one retry
            raw = generate_article(topic, relevant, recent_titles, today)
            if not raw:
                print("   ⚠️ Generation failed.")
                continue
            parsed = parse_article(raw)
            ok, reason = validate_article(parsed)
            if ok:
                grounded_text = " ".join([parsed.get("title", ""), parsed.get("takeaway", ""),
                                          parsed.get("excerpt", ""), parsed.get("action", ""), parsed.get("body", "")])
                ok, reason = check_grounding(grounded_text, relevant)
            if ok:
                break
            print(f"   ↻ Rejected ({reason}) — retrying...")

        if not ok:
            print("   ⚠️ Could not produce a valid article, skipping.")
            continue

        drafts.append(("article", article_record(parsed, date_str, issue_id, relevant)))
        recent_titles.append(parsed["title"])  # avoid repeating within this same run
        for n in relevant:
            used_urls.add(n["link"])
        print(f"   ✍️  Drafted: {parsed['title']}")

    print("\n🧯 Building hype check...")
    hype = generate_hype_check(all_news[:12], today)
    if hype:
        drafts.append(("hype_check", extra_record("hype_check", hype, date_str, issue_id)))

    leftover = [a for a in all_news if a["link"] not in used_urls][:QUICK_HITS]
    if leftover:
        print(f"\n🔗 Building {len(leftover)} quick hits...")
        quick_hits = generate_quick_hits(leftover, today)
        if quick_hits:
            drafts.append(("links", extra_record("links", {"items": quick_hits, "title": "Worth your time"},
                                                 date_str, issue_id)))

    if not drafts:
        print("\nNo drafts produced — no issue created, no email sent.")
        raise SystemExit(0)

    # ── Two independent, search-grounded reviews per draft ─────────────────────
    print(f"\n🔎 Reviewing {len(drafts)} draft(s) with {', '.join(REVIEW_MODELS.values())}...")
    reviewed = []
    for kind, rec in drafts:
        reviews = review_item(client, REVIEW_MODELS, rec, today)
        decision, reason = decide(reviews)
        ref = db.collection("newsletter_articles").document()
        reviewed.append({"id": ref.id, "ref": ref, "kind": kind, "record": rec,
                         "reviews": reviews, "decision": decision, "reason": reason})
        print(f"   {decision.upper():5} {_item_title(kind, rec)[:70]} — {reason}")
        for key, rev in reviews.items():
            if rev.get("error"):
                print(f"         {key} error: {rev['error'][:240]}")

    # ── Persist drafts (pending_review, or rejected if both reviewers failed) ──
    existed_at_start = existing.exists

    @firestore.transactional
    def commit_issue(tx, writes):
        # Re-check: the issue may have been created/approved while we were drafting.
        snap = issue_ref.get(transaction=tx)
        if snap.exists and (not existed_at_start or snap.to_dict().get("status") not in ("awaiting_approval", "rejected")):
            raise RuntimeError(f"Issue {issue_id} changed during generation "
                               f"(now {snap.to_dict().get('status')}) — not overwriting it.")
        for ref, data in writes:
            tx.set(ref, data)

    writes = []
    for r in reviewed:
        writes.append((r["ref"], {
            **r["record"],
            "status":        "rejected" if r["decision"] == "drop" else "pending_review",
            "review":        r["reviews"],
            "review_decision": r["decision"],
            "review_reason": r["reason"],
            "created_at":    firestore.SERVER_TIMESTAMP,
        }))
    kept = [r for r in reviewed if r["decision"] != "drop"]
    subscriber_html = build_subscriber_email([(r["id"], r["kind"], r["record"]) for r in kept], date_str)
    writes.append((issue_ref, {
        "issue_id":   issue_id,
        "date":       date_str,
        "status":     "awaiting_approval" if kept else "rejected",
        "item_ids":   [r["id"] for r in kept],
        "dropped_ids": [r["id"] for r in reviewed if r["decision"] == "drop"],
        # Subject = first APPROVED article's title at send time (lead may be dropped).
        "subject_candidates": [{"id": r["id"], "title": r["record"]["title"]}
                               for r in kept if r["kind"] == "article"],
        "fallback_subject": f"AI Insights — {date_str}",
        "email_html": subscriber_html,
        "review_models": REVIEW_MODELS,
        "created_at": firestore.SERVER_TIMESTAMP,
    }))
    commit_issue(db.transaction(), writes)
    print(f"\n🗃️  Issue {issue_id} saved: {len(kept)} kept, {len(reviewed) - len(kept)} dropped")

    subject, html = build_review_email(issue_id, date_str, reviewed)
    send_review_email(subject, html)
    print(f"✉️  Review email sent to the admin: {subject}")
    print(f"   Approve at {SITE_URL}/admin/?issue={issue_id} — nothing is live until then.")
