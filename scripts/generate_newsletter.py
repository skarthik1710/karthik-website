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

# --- Clients ---
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
firebase_key = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])
cred = credentials.Certificate(firebase_key)
firebase_admin.initialize_app(cred)
db = firestore.client()

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "skarthik1710@gmail.com")
SITE_URL    = os.environ.get("SITE_URL", "https://karthikeyanselvam.com")

# Auto-publish (Option B): generated articles go live immediately. The only
# safeguards before subscribers see them are the grounded prompt + validate_article().
# REVIEW_MODE flips a run to save drafts (pending_review) instead — for test runs you
# eyeball in admin/review.html before anything is public.
REVIEW_MODE    = os.environ.get("NEWSLETTER_REVIEW_MODE", "").strip().lower() in ("1", "true", "yes")
RECENCY_DAYS   = 7      # only write about news from the last week
MIN_BODY_WORDS = 350    # reject anything thinner than this

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
EXCERPT: [2 sentences — hook the reader, reference real news, no fluff]
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
                model="models/gemini-2.5-flash",
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
        "title":        extract(r"TITLE:\s*(.+)", raw) or "AI Insights",
        "category":     extract(r"CATEGORY:\s*(.+)", raw) or "AI & ML",
        "category_key": (extract(r"CATEGORY_KEY:\s*(.+)", raw) or "ai").lower(),
        "excerpt":      extract(r"EXCERPT:\s*(.+?)(?=SOURCES_USED:|BODY:)", raw),
        "sources_used": extract(r"SOURCES_USED:\s*(.+)", raw),
        "body":         extract(r"BODY:\n(.+)", raw),
    }


# ── 7. VALIDATE (the only gate before auto-publish) ───────────────────────────
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


# ── 8. SAVE TO FIRESTORE AS APPROVED (auto-publish) ───────────────────────────
def save_to_firestore(parsed, date_str, news_sources):
    status = "pending_review" if REVIEW_MODE else "approved"   # ← Option B default: auto-publish
    doc_ref = db.collection("newsletter_articles").document()
    record = {
        "title":        parsed["title"],
        "category":     parsed["category"],
        "category_key": parsed["category_key"],
        "excerpt":      parsed["excerpt"],
        "body":         parsed["body"],
        "sources_used": parsed["sources_used"],
        "news_sources": [{"title": n["title"], "url": n["link"], "source": n["source"]} for n in news_sources],
        "date":         date_str,
        "status":       status,
        "auto_published": not REVIEW_MODE,
        "created_at":   firestore.SERVER_TIMESTAMP,
    }
    if not REVIEW_MODE:
        record["published_at"] = firestore.SERVER_TIMESTAMP
    doc_ref.set(record)
    return doc_ref.id


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    today    = datetime.now(timezone.utc).strftime("%b %d, %Y")
    date_str = today

    print("📰 Fetching real news...")
    all_news = fetch_real_news(max_items=20)
    print(f"   Found {len(all_news)} usable articles from RSS feeds")

    print("🗂️  Loading recent history for de-duplication...")
    recent_titles, used_urls = fetch_recent_history(limit=40)
    print(f"   {len(recent_titles)} past titles, {len(used_urls)} source URLs already used")

    selected_topics = random.sample(TOPICS, 3)
    published = []

    for topic in selected_topics:
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
                grounded_text = " ".join([parsed.get("title", ""), parsed.get("excerpt", ""), parsed.get("body", "")])
                ok, reason = check_grounding(grounded_text, relevant)
            if ok:
                break
            print(f"   ↻ Rejected ({reason}) — retrying...")

        if not ok:
            print("   ⚠️ Could not produce a valid article, skipping (nothing published).")
            continue

        doc_id = save_to_firestore(parsed, date_str, relevant)
        recent_titles.append(parsed["title"])  # avoid repeating within this same run
        for n in relevant:
            used_urls.add(n["link"])
        published.append(parsed["title"])
        verb = "SAVED AS DRAFT" if REVIEW_MODE else "PUBLISHED"
        print(f"   ✅ {verb}: {parsed['title']}")
        print(f"   📌 Sources: {parsed['sources_used']}")

    if REVIEW_MODE:
        print(f"\n🧐 Done. {len(published)} draft(s) saved for review at {SITE_URL}/admin/review.html:")
    else:
        print(f"\n🎉 Done. {len(published)} article(s) auto-published and live:")
    for t in published:
        print(f"   • {t}")
