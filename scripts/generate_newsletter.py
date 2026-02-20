import os
import re
import random
import time
from datetime import datetime
from bs4 import BeautifulSoup
from google import genai
import firebase_admin
from firebase_admin import credentials, firestore

# --- Gemini Config ---
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# --- Firebase Config ---
import json
firebase_key = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])
cred = credentials.Certificate(firebase_key)
firebase_admin.initialize_app(cred)
db = firestore.client()

TOPICS = [
    "Microsoft Copilot and AI workplace productivity",
    "Enterprise AI adoption and digital transformation",
    "RPA and intelligent automation trends",
    "AI governance, ethics and enterprise risk",
    "Google Workspace AI and collaboration tools",
]

EMOJIS = ["🤖", "🧠", "⚙️", "🏢", "🚀"]
GRADIENTS = [
    "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    "linear-gradient(135deg, #764ba2 0%, #667eea 100%)",
    "linear-gradient(135deg, #e94560 0%, #764ba2 100%)",
]

def generate_article(topic):
    today = datetime.now().strftime("%B %d, %Y")
    prompt = f"""
You are Karthikeyan Selvam, a Digital Workplace & AI Consultant with 18+ years of experience
in Microsoft Copilot, RPA, AI Ops, and Enterprise IT. Azure and Google Cloud certified.

Today is {today}. Write a 400-word original newsletter article about: "{topic}"

Structure exactly as:
TITLE: [Compelling article title]
CATEGORY: [One of: Microsoft Copilot / AI & ML / RPA & Automation / Enterprise Tech]
CATEGORY_KEY: [One of: copilot / ai / rpa / enterprise]
EXCERPT: [A 2-sentence teaser only]
BODY: [Full article in flowing paragraphs covering:
  1. What is happening in this space right now
  2. The Opportunity for digital workplaces
  3. The Challenge organizations must navigate
  4. Your Take - first person insight from consulting experience]

No bullet points. Warm, expert, analytical tone. No URLs.
"""
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
                print(f"⏳ Rate limit. Waiting {wait}s...")
                time.sleep(wait)
            else:
                raise e
    return None

def parse_article(raw_text):
    title = re.search(r'TITLE:\s*(.+)', raw_text)
    category = re.search(r'CATEGORY:\s*(.+)', raw_text)
    category_key = re.search(r'CATEGORY_KEY:\s*(.+)', raw_text)
    excerpt = re.search(r'EXCERPT:\s*(.+)', raw_text)
    body = re.search(r'BODY:\s*([\s\S]+)', raw_text)
    return {
        "title": title.group(1).strip() if title else "AI Insights",
        "category": category.group(1).strip() if category else "AI & ML",
        "category_key": category_key.group(1).strip().lower() if category_key else "ai",
        "excerpt": excerpt.group(1).strip() if excerpt else "",
        "body": body.group(1).strip() if body else ""
    }

def save_to_firestore(parsed, date_str):
    doc_ref = db.collection("newsletter_articles").document()
    doc_ref.set({
        "title": parsed["title"],
        "category": parsed["category"],
        "category_key": parsed["category_key"],
        "excerpt": parsed["excerpt"],
        "body": parsed["body"],
        "date": date_str,
        "created_at": firestore.SERVER_TIMESTAMP
    })
    return doc_ref.id

def build_article_card(parsed, date_str, index, doc_id):
    emoji = EMOJIS[index % len(EMOJIS)]
    gradient = GRADIENTS[index % len(GRADIENTS)]
    return f"""
            <article class="article-card" data-category="{parsed['category_key']}">
                <div class="article-image" style="background: {gradient}; display: flex; align-items: center; justify-content: center; font-size: 4rem;">
                    {emoji}
                </div>
                <div class="article-content">
                    <div class="article-meta">
                        <span class="article-category">{parsed['category']}</span>
                        <span class="article-date">{date_str}</span>
                    </div>
                    <h3 class="article-title">{parsed['title']}</h3>
                    <p class="article-excerpt">{parsed['excerpt']}</p>
                    <p class="article-source">Analysis by Karthikeyan Selvam | karthikeyanselvam.com</p>
                    <a class="read-more" onclick="openArticle('{doc_id}')" style="cursor:pointer;">Read Full Analysis →</a>
                </div>
            </article>"""

def update_newsletter_html(new_cards_html):
    html_path = "public/newsletter.html"
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    container = soup.find("div", id="newsletter-articles") or \
                soup.find("div", class_="articles-grid")
    if container:
        container.insert(0, BeautifulSoup(new_cards_html, "html.parser"))
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(str(soup))
    print("✅ newsletter.html updated")

if __name__ == "__main__":
    date_str = datetime.now().strftime("%b %d, %Y")
    todays_topics = random.sample(TOPICS, 3)
    all_cards = ""

    for i, topic in enumerate(todays_topics):
        print(f"✍️  Writing: {topic}")
        raw = generate_article(topic)
        if raw:
            parsed = parse_article(raw)
            doc_id = save_to_firestore(parsed, date_str)
            all_cards += build_article_card(parsed, date_str, i, doc_id)
            print(f"✅ Saved to Firestore: {parsed['title']}")

    if all_cards:
        update_newsletter_html(all_cards)
        print("🚀 Done!")
