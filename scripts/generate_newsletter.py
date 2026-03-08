import os
import re
import json
import time
import requests
from datetime import datetime, timezone
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

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
ADMIN_EMAIL      = os.environ.get("ADMIN_EMAIL", "skarthik1710@gmail.com")
SITE_URL         = os.environ.get("SITE_URL", "https://karthikeyanselvam.com")

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

CATEGORY_MAP = {
    "Microsoft Copilot": ("copilot", "Microsoft Copilot"),
    "AI & ML":           ("ai",      "AI & ML"),
    "RPA & Automation":  ("rpa",     "RPA & Automation"),
    "Enterprise Tech":   ("enterprise", "Enterprise Tech"),
}


# ── 1. FETCH REAL NEWS FROM RSS ───────────────────────────────────────────────
def fetch_real_news(max_items=15):
    articles = []
    headers  = {"User-Agent": "Mozilla/5.0 (compatible; KSNewsletter/1.0)"}
    for url in RSS_FEEDS:
        try:
            resp = requests.get(url, timeout=10, headers=headers)
            root = ElementTree.fromstring(resp.content)
            ns   = ""
            items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
            for item in items[:5]:
                def t(tag):
                    return (item.findtext(tag) or "").strip()
                title   = t("title")
                link    = t("link")
                summary = t("description") or t("{http://www.w3.org/2005/Atom}summary")
                pub     = t("pubDate") or t("{http://www.w3.org/2005/Atom}updated")
                # strip html tags from summary
                summary = re.sub(r"<[^>]+>", "", summary)[:400]
                if title and link:
                    articles.append({
                        "title":   title,
                        "link":    link,
                        "summary": summary,
                        "source":  url.split("/")[2],
                        "pub":     pub,
                    })
        except Exception as e:
            print(f"RSS fetch failed for {url}: {e}")
    # deduplicate by title
    seen, unique = set(), []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)
    return unique[:max_items]


# ── 2. FILTER NEWS RELEVANT TO TOPIC ─────────────────────────────────────────
def filter_news_for_topic(news, topic):
    keywords = topic.lower().split()
    scored   = []
    for i, a in enumerate(news):
        text  = (a["title"] + " " + a["summary"]).lower()
        score = sum(1 for k in keywords if k in text)
        if score > 0:
            scored.append((score, i, a))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    results = [a for _, _, a in scored[:5]]
    return results if results else news[:3]


# ── 3. BUILD STRICT GROUNDED PROMPT ──────────────────────────────────────────
def build_prompt(topic, relevant_news, today):
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

    return f"""You are Karthikeyan Selvam — a Digital Workplace & AI Consultant with 18 years of hands-on enterprise experience in Microsoft Copilot, RPA, AI Ops, and Enterprise IT. You are Azure- and Google Cloud-certified.

Today is {today}.

Your task is to write ONE newsletter article about: "{topic}"

════════════════════════════════════════════════════
REAL NEWS SOURCES FOR THIS ARTICLE (use ONLY these):
════════════════════════════════════════════════════
{news_block}
════════════════════════════════════════════════════

STRICT RULES — violating any rule means the article is rejected:
1. Every factual claim MUST come from the sources above. No invented statistics, no hallucinated product names, no made-up quotes.
2. If you are unsure of a fact, omit it entirely.
3. Write in first person as Karthikeyan Selvam — practitioner voice, not a generic blog post.
4. Be specific and opinionated. Say what you actually think about this news, not generic observations.
5. No bullet points. Flowing paragraphs only.
6. Length: 450–550 words for BODY.
7. Do NOT invent URLs or sources not listed above.

OUTPUT FORMAT (exactly):
TITLE: [A specific, compelling title that references actual news]
CATEGORY: [One of: Microsoft Copilot | AI & ML | RPA & Automation | Enterprise Tech]
CATEGORY_KEY: [One of: copilot | ai | rpa | enterprise]
EXCERPT: [2 sentences — hook the reader, reference real news, no fluff]
SOURCES_USED: [Comma-separated list of source domains you drew facts from]
BODY:
[Full article here — 450-550 words, first person, practitioner tone, grounded in the sources above]
"""


# ── 4. GENERATE ARTICLE VIA GEMINI ───────────────────────────────────────────
def generate_article(topic, relevant_news, today):
    prompt = build_prompt(topic, relevant_news, today)
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="models/gemini-2.5-flash",
                contents=prompt
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


# ── 5. PARSE GEMINI RESPONSE ──────────────────────────────────────────────────
def parse_article(raw):
    def extract(pattern, text, default=""):
        m = re.search(pattern, text, re.DOTALL)
        return m.group(1).strip() if m else default

    title        = extract(r"TITLE:\s*(.+)", raw)
    category     = extract(r"CATEGORY:\s*(.+)", raw)
    category_key = extract(r"CATEGORY_KEY:\s*(.+)", raw).lower()
    excerpt      = extract(r"EXCERPT:\s*(.+?)(?=SOURCES_USED:|BODY:)", raw)
    sources_used = extract(r"SOURCES_USED:\s*(.+)", raw)
    body         = extract(r"BODY:\n(.+)", raw)

    return {
        "title":        title or "AI Insights",
        "category":     category or "AI & ML",
        "category_key": category_key or "ai",
        "excerpt":      excerpt,
        "sources_used": sources_used,
        "body":         body,
    }


# ── 6. SAVE TO FIRESTORE AS PENDING ──────────────────────────────────────────
def save_to_firestore(parsed, date_str, news_sources):
    doc_ref = db.collection("newsletter_articles").document()
    doc_ref.set({
        "title":        parsed["title"],
        "category":     parsed["category"],
        "category_key": parsed["category_key"],
        "excerpt":      parsed["excerpt"],
        "body":         parsed["body"],
        "sources_used": parsed["sources_used"],
        "news_sources": [{"title": n["title"], "url": n["link"], "source": n["source"]} for n in news_sources],
        "date":         date_str,
        "status":       "pending_review",   # ← APPROVAL GATE
        "created_at":   firestore.SERVER_TIMESTAMP,
    })
    return doc_ref.id


# ── 7. SEND APPROVAL EMAIL VIA SENDGRID ──────────────────────────────────────
def send_approval_email(articles_info):
    if not SENDGRID_API_KEY:
        print("No SENDGRID_API_KEY set — skipping email.")
        return

    rows = ""
    for a in articles_info:
        approve_url = f"{SITE_URL}/admin/review.html?id={a['doc_id']}&action=approve"
        reject_url  = f"{SITE_URL}/admin/review.html?id={a['doc_id']}&action=reject"
        rows += f"""
        <tr>
          <td style="padding:12px; border-bottom:1px solid #eee;">
            <strong>{a["title"]}</strong><br/>
            <small style="color:#888">{a["category"]} &mdash; {a["excerpt"][:100]}...</small><br/><br/>
            <a href="{approve_url}" style="background:#00C9A7;color:#fff;padding:8px 18px;border-radius:6px;text-decoration:none;margin-right:8px;">✅ Approve</a>
            <a href="{reject_url}" style="background:#e94560;color:#fff;padding:8px 18px;border-radius:6px;text-decoration:none;">❌ Reject</a>
          </td>
        </tr>"""

    html = f"""
    <html><body style="font-family:Inter,sans-serif;background:#060810;color:#E6EDF3;padding:2rem;">
      <h2 style="color:#00C9A7;">📬 New Articles Ready for Review</h2>
      <p style="color:#8B949E;">{len(articles_info)} article(s) generated and waiting for your approval before going live.</p>
      <table style="width:100%;border-collapse:collapse;">{rows}</table>
      <p style="color:#8B949E;margin-top:2rem;font-size:0.85rem;">
        Or review all drafts at: <a href="{SITE_URL}/admin/review.html" style="color:#00C9A7;">{SITE_URL}/admin/review.html</a>
      </p>
    </body></html>"""

    payload = {
        "personalizations": [{"to": [{"email": ADMIN_EMAIL}]}],
        "from":    {"email": "newsletter@karthikeyanselvam.com", "name": "KS Newsletter Bot"},
        "subject": f"✍️ {len(articles_info)} New Article(s) Awaiting Your Approval",
        "content": [{"type": "text/html", "value": html}],
    }

    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    if resp.status_code == 202:
        print("✅ Approval email sent!")
    else:
        print(f"⚠️ Email failed: {resp.status_code} {resp.text}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    today    = datetime.now(timezone.utc).strftime("%b %d, %Y")
    date_str = today

    print("📰 Fetching real news...")
    all_news = fetch_real_news(max_items=20)
    print(f"   Found {len(all_news)} articles from RSS feeds")

    import random
    selected_topics = random.sample(TOPICS, 3)
    articles_info   = []

    for topic in selected_topics:
        print(f"\n✍️  Writing: {topic}")
        relevant = filter_news_for_topic(all_news, topic)
        print(f"   Using {len(relevant)} relevant news sources")

        raw = generate_article(topic, relevant, today)
        if not raw:
            print("   ⚠️ Generation failed, skipping.")
            continue

        parsed = parse_article(raw)
        doc_id = save_to_firestore(parsed, date_str, relevant)
        print(f"   ✅ Saved as PENDING: {parsed['title']}")
        print(f"   📌 Sources used: {parsed['sources_used']}")

        articles_info.append({
            "doc_id":   doc_id,
            "title":    parsed["title"],
            "category": parsed["category"],
            "excerpt":  parsed["excerpt"],
        })

    print(f"\n📧 Sending approval email for {len(articles_info)} article(s)...")
    send_approval_email(articles_info)
    print("\n🎉 Done! Articles are PENDING your approval — nothing published yet.")
