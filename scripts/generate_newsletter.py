import os
import re
from datetime import datetime
from bs4 import BeautifulSoup
from google import genai

# --- Config ---
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

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

def generate_article(topic, index):
    today = datetime.now().strftime("%B %d, %Y")
    prompt = f"""
You are Karthikeyan Selvam, a Digital Workplace & AI Consultant with 18+ years of experience
in Microsoft Copilot, RPA, AI Ops, and Enterprise IT solutions. Azure and Google Cloud certified.

Today is {today}. Write a 250-word original newsletter article about this topic:
"{topic}"

Structure it exactly as:
TITLE: [A compelling, specific article title]
CATEGORY: [One of: Microsoft Copilot / AI & ML / RPA & Automation / Enterprise Tech]
CATEGORY_KEY: [One of: copilot / ai / rpa / enterprise]
BODY: [The full article in flowing paragraphs - no bullet points]

The article MUST include:
1. A current trend or development in this space (use your knowledge up to early 2026)
2. The Opportunity: Why this excites digital workplace professionals
3. The Challenge: A real risk or hurdle organizations face
4. Your Take: A brief first-person insight from your consulting experience

Write in a warm, expert, analytical tone. Make it feel human and insightful.
Do NOT include any URLs or external links.
"""
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini 2.5 Flash",
                contents=prompt
            )
            return response.text
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                import time
                wait = 60 * (attempt + 1)
                print(f"⏳ Rate limit hit. Waiting {wait}s...")
                time.sleep(wait)
            else:
                raise e
    return None

def parse_article(raw_text):
    title = re.search(r'TITLE:\s*(.+)', raw_text)
    category = re.search(r'CATEGORY:\s*(.+)', raw_text)
    category_key = re.search(r'CATEGORY_KEY:\s*(.+)', raw_text)
    body = re.search(r'BODY:\s*([\s\S]+)', raw_text)

    return {
        "title": title.group(1).strip() if title else "AI & Workplace Insights",
        "category": category.group(1).strip() if category else "AI & ML",
        "category_key": category_key.group(1).strip().lower() if category_key else "ai",
        "body": body.group(1).strip()[:300] + "..." if body else ""
    }

def build_article_card(parsed, date_str, index):
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
                    <p class="article-excerpt">{parsed['body']}</p>
                    <p class="article-source">Analysis by Karthikeyan Selvam | karthikeyanselvam.com</p>
                    <span class="read-more">✦ AI & Digital Workplace Insights</span>
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
        print("✅ Articles injected into newsletter.html")
    else:
        print("❌ Could not find articles container")
        return

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(str(soup))

if __name__ == "__main__":
    import random
    date_str = datetime.now().strftime("%b %d, %Y")

    # Pick 3 random topics each day for variety
    todays_topics = random.sample(TOPICS, 3)
    all_cards = ""

    for i, topic in enumerate(todays_topics):
        print(f"✍️  Writing article {i+1}: {topic}")
        raw = generate_article(topic, i)
        if raw:
            parsed = parse_article(raw)
            all_cards += build_article_card(parsed, date_str, i)
            print(f"✅ Done: {parsed['title']}")

    if all_cards:
        update_newsletter_html(all_cards)
        print("🚀 Newsletter update complete!")
    else:
        print("⚠️ No articles generated today.")
