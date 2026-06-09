"""Generate a grounded LinkedIn post DRAFT (generate-then-approve).

Reuses the newsletter pipeline's news fetch, voice guide, and hallucination
gate, so a scheduled LinkedIn draft is held to the same accuracy bar as the
newsletter. Writes the draft to linkedin_post.txt for review — the separate
"Post to LinkedIn" workflow publishes it only after you approve. Also records a
pending_review doc in Firestore for cross-channel de-duplication.

Env (CI secrets): GEMINI_API_KEY, FIREBASE_SERVICE_ACCOUNT
"""
import os
import random
from datetime import datetime, timezone

from firebase_admin import firestore

# Importing the newsletter module reuses its initialized Gemini + Firestore
# clients and helpers (it runs module-level init, which needs the two secrets).
from generate_newsletter import (
    client,
    db,
    STYLE_GUIDE,
    TOPICS,
    fetch_real_news,
    fetch_recent_history,
    filter_news_for_topic,
    check_grounding,
)

POST_FILE = os.environ.get("LINKEDIN_POST_FILE", "linkedin_post.txt")
MODEL = "models/gemini-2.5-flash"
MIN_WORDS = 40


def build_prompt(topic, news, recent_titles, today):
    news_block = ""
    for i, a in enumerate(news, 1):
        news_block += f'\nSOURCE {i}: "{a["title"]}" ({a["source"]}) — {a["summary"]} [{a["link"]}]\n'
    avoid = "\n".join(f"  - {t}" for t in recent_titles[:15]) or "  (none yet)"
    return f"""{STYLE_GUIDE}

Today is {today}. Write ONE LinkedIn post in Karthik's voice about: "{topic}".

REAL NEWS SOURCES (use ONLY these — every fact, number, name must appear here):
{news_block}

RECENTLY COVERED — choose a different angle, don't repeat these:
{avoid}

RULES:
- 120-200 words. First-person practitioner, opinionated, skeptical of hype.
- ACCURACY ABSOLUTE: no statistic, %, $ figure, date, product/model name, or
  version that isn't written verbatim in a source above. If it's not there, leave
  it out. Never recall numbers or names from memory.
- Plain English. No emoji, no corporate filler, no bullet lists.
- Sharp hook, your read on what it means, a practitioner takeaway to close.
- Last line: 2-3 relevant hashtags.

OUTPUT: the post text only. No preamble, no labels, no surrounding quotes.
"""


def generate(topic, news, recent_titles, today):
    prompt = build_prompt(topic, news, recent_titles, today)
    resp = client.models.generate_content(model=MODEL, contents=prompt)
    return (resp.text or "").strip()


def set_output(key, value):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def main():
    today = datetime.now(timezone.utc).strftime("%b %d, %Y")
    print("Fetching news...")
    news = fetch_real_news(max_items=30)
    recent_titles, used_urls = fetch_recent_history(limit=40)

    produced = None
    for topic in random.sample(TOPICS, len(TOPICS)):
        relevant = filter_news_for_topic(news, topic, used_urls)
        if not relevant:
            continue
        print(f"Trying topic: {topic} ({len(relevant)} sources)")
        for _ in range(2):
            text = generate(topic, relevant, recent_titles, today)
            if not text or len(text.split()) < MIN_WORDS:
                print("  too short — retrying")
                continue
            ok, reason = check_grounding(text, relevant)
            if ok:
                produced = (topic, text, relevant)
                break
            print(f"  rejected ({reason}) — retrying")
        if produced:
            break

    if not produced:
        print("No grounded LinkedIn post could be generated this run — skipping.")
        set_output("generated", "false")
        return

    topic, text, relevant = produced
    with open(POST_FILE, "w", encoding="utf-8") as f:
        f.write(text + "\n")

    db.collection("newsletter_articles").document().set(
        {
            "type": "linkedin_post",
            "body": text,
            "topic": topic,
            "status": "pending_review",
            "news_sources": [
                {"title": n["title"], "url": n["link"], "source": n["source"]}
                for n in relevant
            ],
            "date": today,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )

    print("\n=== LinkedIn draft (pending review) ===\n")
    print(text)
    set_output("generated", "true")


if __name__ == "__main__":
    main()
