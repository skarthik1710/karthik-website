import feedparser
import google.generativeai as genai
import os
import re
from datetime import datetime
from bs4 import BeautifulSoup

# --- Config ---
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")  # Free tier

RSS_FEEDS = [
    "https://feeds.feedburner.com/TechCrunch/",
    "https://www.technologyreview.com/feed/",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
]

KEYWORDS = ["AI", "artificial intelligence", "copilot", "digital workplace",
            "automation", "Microsoft", "generative AI", "enterprise"]

def fetch_articles():
    articles = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            link = entry.get("link", "")
            if any(kw.lower() in (title + summary).lower() for kw in KEYWORDS):
                articles.append({"title": title, "summary": summary, "link": link,
                                  "source": feed.feed.get("title", "Tech News")})
    return articles[:3]  # Top 3 relevant articles

def generate_analysis(article):
    prompt = f"""
You are Karthikeyan Selvam, a Digital Workplace & AI Consultant with 18+ years of experience 
in Microsoft Copilot, RPA, AI Ops, and Enterprise IT. 

Analyze this news article and write a 200-word newsletter piece for professionals. 
Structure it as:
1. What happened (1-2 sentences)
2. The Opportunity: Why this is exciting for digital workplaces
3. The Challenge: Key risks or hurdles organizations must watch
4. Your Take: A brief personal insight in first-person

Write in a warm, expert, and analytical tone. No bullet points — flowing paragraphs only.

Article Title: {article['title']}
Article Summary: {article['summary']}
"""
    response = model.generate_content(prompt)
    return response.text

def build_article_card(article, analysis, date_str):
    excerpt = analysis[:180].rsplit(' ', 1)[0] + "..."
    card = f"""
                <article class="newsletter-card">
                    <div class="newsletter-card-header">
                        <span class="newsletter-badge">AI & Digital Workplace</span>
                        <span class="newsletter-date">{date_str}</span>
                    </div>
                    <h3>{article['title']}</h3>
                    <p>{excerpt}</p>
                    <div class="newsletter-meta">
                        <span>Source: {article['source']} | Analysis by Karthikeyan Selvam</span>
                        <a href="{article['link']}" target="_blank" class="read-more">Read Full Analysis →</a>
                    </div>
                </article>"""
    return card

def update_newsletter_html(new_cards_html):
    with open("public/newsletter.html", "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    # Find the articles container — targets existing card section
    container = soup.find("section", {"id": "newsletter-articles"}) or \
                soup.find("div", class_=re.compile("newsletter|articles|feed"))

    if container:
        # Prepend new articles at the top
        container.insert(0, BeautifulSoup(new_cards_html, "html.parser"))
    
    with open("public/newsletter.html", "w", encoding="utf-8") as f:
        f.write(str(soup))
    print("✅ newsletter.html updated successfully.")

if __name__ == "__main__":
    articles = fetch_articles()
    if not articles:
        print("No new relevant articles found today.")
        exit(0)

    date_str = datetime.now().strftime("%B %d, %Y")
    all_cards = ""
    for article in articles:
        print(f"Generating analysis for: {article['title']}")
        analysis = generate_analysis(article)
        all_cards += build_article_card(article, analysis, date_str)
    
    update_newsletter_html(all_cards)
