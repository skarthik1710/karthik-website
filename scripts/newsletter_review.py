"""Two independent, search-grounded reviewers for newsletter drafts.

Each reviewer is a separate Gemini call with Google Search grounding, so claims
are checked against what is CURRENT on the web — not just the RSS snippets the
writer saw. They have different jobs so they don't share one blind spot:

  * fact_checker — every concrete claim (numbers, dates, names, products, quotes,
    "X announced Y") is verified against trusted, recent sources.
  * editor       — misleading framing, stale/superseded facts, claims that
    overreach their source, unverifiable predictions stated as fact, and
    confidentiality (client names, internal detail) in public copy.

Nothing here publishes anything. Reviews are attached to drafts and summarised
in the morning review email; a human approves every issue.

This module has no import-time side effects (no clients, no env reads), so the
pure helpers can be unit-tested without credentials.
"""
import json
import re
import time

TRUSTED_SOURCES_HINT = (
    "Prefer primary and high-trust sources: the vendor's own announcement, blog, "
    "docs or SEC filing; established outlets (Reuters, AP, Bloomberg, FT, WSJ, "
    "The Verge, TechCrunch, Ars Technica, VentureBeat); official standards or "
    "government bodies. Treat SEO content farms, unsourced aggregators, forums and "
    "social posts as NOT verifying anything."
)

REVIEWERS = {
    "fact_checker": {
        "label": "Fact-checker",
        "role": (
            "You are a meticulous newsroom fact-checker. Extract EVERY concrete, "
            "checkable claim from the draft — figures, percentages, money, dates, "
            "company/product/model names and versions, quotes, and statements that "
            "something was announced, launched, acquired or reported. Search the web "
            "for each one and decide whether current, trusted sources support it. "
            "Opinions and predictions clearly framed as the author's view are NOT "
            "claims — skip them."
        ),
    },
    "editor": {
        "label": "Editor",
        "role": (
            "You are a skeptical senior editor protecting the author's credibility "
            "with an expert audience. Search the web to check whether the draft is "
            "still accurate TODAY. Flag: facts that are stale or superseded by newer "
            "news; claims that overstate or distort what the source actually said; "
            "predictions or opinions written as if they were facts; misleading "
            "framing; and anything that should not be in public copy (named "
            "clients/customers of the author, internal project or system details). "
            "Do not nitpick style or voice."
        ),
    },
}

CLAIM_VERDICTS = {"supported", "unsupported", "contradicted", "outdated", "overstated", "confidential"}
BAD_CLAIM_VERDICTS = CLAIM_VERDICTS - {"supported"}
ITEM_VERDICTS = ("pass", "revise", "fail")


def item_to_text(item):
    """Flatten a draft (article / links / hype_check) into reviewable text."""
    kind = item.get("type", "article")
    if kind == "links":
        lines = [f'- "{h.get("title", "")}" ({h.get("source", "")}): {h.get("take", "")}'
                 for h in item.get("items", [])]
        return "QUICK LINKS (headline + the author's one-line take):\n" + "\n".join(lines)
    if kind == "hype_check":
        return (f"HYPE CHECK\nClaim being debunked: {item.get('claim', '')}\n"
                f"Author's reality check: {item.get('reality', '')}\n"
                f"Source: {item.get('source', '')}")
    parts = [
        f"TITLE: {item.get('title', '')}",
        f"TAKEAWAY: {item.get('takeaway', '')}",
        f"EXCERPT: {item.get('excerpt', '')}",
        f"ACTION: {item.get('action', '')}",
        f"BODY:\n{item.get('body', '')}",
    ]
    return "\n".join(parts)


def build_review_prompt(reviewer_key, item, today):
    r = REVIEWERS[reviewer_key]
    sources = item.get("news_sources") or []
    src_block = "\n".join(f"- {s.get('title', '')} — {s.get('url', '')}" for s in sources) or "- (none recorded)"
    return f"""{r['role']}

Today is {today}. Use Google Search. {TRUSTED_SOURCES_HINT}

The writer was given these RSS items as sources (they are a starting point, not proof):
{src_block}

════════ DRAFT TO REVIEW ════════
{item_to_text(item)}
════════════════════════════════

Return ONLY a JSON object (no prose before or after), exactly this shape:
{{
  "verdict": "pass" | "revise" | "fail",
  "summary": "one or two sentences for the author",
  "claims": [
    {{
      "claim": "the exact claim, quoted or tightly paraphrased",
      "verdict": "supported" | "unsupported" | "contradicted" | "outdated" | "overstated" | "confidential",
      "evidence": "what the trusted source actually says (one sentence)",
      "source_url": "URL of the best source you found, or empty string"
    }}
  ]
}}

Verdict rules:
- "fail"   — any claim is contradicted, any material claim cannot be supported,
             or there is a confidentiality problem. Publishing would embarrass the author.
- "revise" — minor issues: a claim is overstated, slightly outdated, or needs softening.
- "pass"   — every checkable claim is supported by trusted, current sources.
List every claim you checked, including supported ones.
"""


def parse_review_json(text):
    """Pull the JSON object out of a model reply and normalise it.

    Grounded (search-tool) calls can't use JSON response mode, so the model may
    wrap the object in prose or a ``` fence. Anything unparseable becomes an
    'error' review — never a silent pass.
    """
    if not text:
        return error_review("empty response")
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return error_review("no JSON object in response")
        candidate = text[start:end + 1]
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as e:
        return error_review(f"invalid JSON: {e}")
    if not isinstance(data, dict):
        return error_review("JSON was not an object")

    verdict = str(data.get("verdict", "")).strip().lower()
    claims = []
    for c in data.get("claims") or []:
        if not isinstance(c, dict):
            continue
        cv = str(c.get("verdict", "")).strip().lower()
        if cv not in CLAIM_VERDICTS:
            cv = "unsupported"
        url = str(c.get("source_url", "") or "").strip()
        if not re.match(r"^https?://", url):
            url = ""
        claims.append({
            "claim": str(c.get("claim", "")).strip()[:500],
            "verdict": cv,
            "evidence": str(c.get("evidence", "")).strip()[:600],
            "source_url": url,
        })

    # Never trust a "pass" that contradicts its own claim list.
    bad = [c for c in claims if c["verdict"] in BAD_CLAIM_VERDICTS]
    if verdict not in ITEM_VERDICTS:
        verdict = "revise" if bad else "pass"
    if verdict == "pass" and bad:
        verdict = "revise"
    if any(c["verdict"] in ("contradicted", "confidential") for c in claims):
        verdict = "fail"

    return {
        "verdict": verdict,
        "summary": str(data.get("summary", "")).strip()[:800],
        "claims": claims,
        "error": "",
    }


def error_review(reason):
    return {"verdict": "error", "summary": "", "claims": [], "error": reason}


def grounding_sources(response, limit=8):
    """Web sources Google Search actually returned for this call."""
    out, seen = [], set()
    try:
        meta = response.candidates[0].grounding_metadata
        for ch in (meta.grounding_chunks or []):
            web = getattr(ch, "web", None)
            uri = getattr(web, "uri", "") if web else ""
            if uri and uri not in seen:
                seen.add(uri)
                out.append({"title": getattr(web, "title", "") or "", "url": uri})
            if len(out) >= limit:
                break
    except (AttributeError, IndexError, TypeError):
        pass
    return out


def run_reviewer(client, model, reviewer_key, item, today, retries=3):
    """One grounded review. Returns a normalised review dict (never raises)."""
    from google.genai import types  # local import keeps this module import-safe

    prompt = build_review_prompt(reviewer_key, item, today)
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.1,
    )
    last_err = ""
    for attempt in range(retries):
        try:
            resp = client.models.generate_content(model=model, contents=prompt, config=config)
            review = parse_review_json(resp.text or "")
            review["searched"] = grounding_sources(resp)
            review["model"] = model
            review["reviewer"] = reviewer_key
            return review
        except Exception as e:  # network / quota / model errors
            last_err = str(e)
            if "429" in last_err or "RESOURCE_EXHAUSTED" in last_err:
                time.sleep(30 * (attempt + 1))
                continue
            break
    review = error_review(last_err[:300] or "unknown error")
    review.update({"searched": [], "model": model, "reviewer": reviewer_key})
    return review


def review_item(client, models, item, today):
    """Run both reviewers on one draft. `models` maps reviewer_key -> model id."""
    return {key: run_reviewer(client, models[key], key, item, today) for key in REVIEWERS}


def decide(reviews):
    """Combine two reviews into an action for the draft.

    Returns (decision, reason):
      'drop'  — BOTH reviewers failed it: excluded from the issue automatically.
      'flag'  — at least one reviewer failed/revised it, or a reviewer errored:
                kept, but called out prominently in the review email.
      'clean' — both reviewers passed.
    A reviewer error is never treated as a pass.
    """
    verdicts = {k: r.get("verdict") for k, r in reviews.items()}
    vals = list(verdicts.values())
    if vals and all(v == "fail" for v in vals):
        return "drop", "both reviewers failed it"
    if "error" in vals:
        missing = [REVIEWERS[k]["label"] for k, v in verdicts.items() if v == "error"]
        return "flag", "not fully reviewed (" + ", ".join(missing) + " errored)"
    if any(v in ("fail", "revise") for v in vals):
        return "flag", "; ".join(f"{REVIEWERS[k]['label']}: {v}" for k, v in verdicts.items())
    return "clean", "both reviewers passed"
