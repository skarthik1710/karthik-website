"""Revise newsletter drafts from the admin's notes. Pure helpers + one Gemini call.

The revision function (main.py) uses these to rewrite ONLY the items the admin
commented on, then sends them back through both reviewers. No import-time side
effects, so everything except revise_item() is unit-testable offline.
"""
import json
import re
import time

from newsletter_content import STYLE_GUIDE

MAX_NOTE_CHARS = 2000

# Fields the writer may change, per item type. Everything else (sources, URLs,
# dates, ids, status) is preserved from the original.
EDITABLE = {
    "article":    ["title", "takeaway", "excerpt", "action", "body"],
    "hype_check": ["claim", "reality"],
    "links":      ["takes"],          # one take per link; titles/URLs are fixed
}


def items_to_revise(item_ids, item_notes, overall_note):
    """Which items get rewritten.

    - Items with their own note are always revised.
    - An overall note with no per-item notes applies to every item.
    - An overall note alongside per-item notes is extra context for those items only.
    """
    noted = [i for i in item_ids if (item_notes.get(i) or "").strip()]
    if noted:
        return noted
    return list(item_ids) if (overall_note or "").strip() else []


def editable_view(kind, rec):
    if kind == "links":
        return {"takes": [{"title": h.get("title", ""), "take": h.get("take", "")} for h in rec.get("items", [])]}
    return {k: rec.get(k, "") for k in EDITABLE.get(kind, [])}


def build_revision_prompt(kind, rec, note, overall_note, today):
    sources = rec.get("news_sources") or []
    src_block = "\n".join(f"- {s.get('title', '')} ({s.get('source', '')}) {s.get('url', '')}" for s in sources) or "- (see the item)"
    instructions = []
    if (overall_note or "").strip():
        instructions.append(f"Editor's note for the whole issue: {overall_note.strip()[:MAX_NOTE_CHARS]}")
    if (note or "").strip():
        instructions.append(f"Editor's note for THIS item: {note.strip()[:MAX_NOTE_CHARS]}")
    shape = json.dumps(editable_view(kind, rec), ensure_ascii=False, indent=2)
    return f"""{STYLE_GUIDE}

Today is {today}. You are revising a newsletter draft you wrote, following the
editor's notes below. The editor is the author — treat the notes as instructions.

{chr(10).join(instructions)}

Sources this item was built on:
{src_block}

RULES:
- Change what the notes ask for; keep everything else as close to the original as possible.
- ACCURACY IS ABSOLUTE: do not add any figure, date, name, product, model, version or
  quote that is not in the original draft or its sources. If a note asks for a fact you
  cannot support, make the point qualitatively instead and say so in "changes".
- Never add client names or internal company details.
- Keep the same JSON keys and structure. For "takes", keep the same number of entries
  in the same order and do not change any "title".

CURRENT DRAFT (JSON):
{shape}

Return ONLY a JSON object with exactly two keys:
{{"revised": <the draft JSON with your edits>, "changes": "one or two sentences: what you changed and why"}}
"""


def parse_revision(text, kind, original):
    """Validate the writer's JSON and merge it onto the original record.

    Returns (merged_record, changes) or raises ValueError — a bad revision must
    never silently replace a reviewed draft.
    """
    if not text:
        raise ValueError("empty response")
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in response")
    data = json.loads(m.group(0))
    revised = data.get("revised")
    if not isinstance(revised, dict):
        raise ValueError("missing 'revised' object")
    changes = str(data.get("changes", "")).strip()[:600]

    merged = dict(original)
    if kind == "links":
        takes = revised.get("takes")
        items = list(original.get("items", []))
        if not isinstance(takes, list) or len(takes) != len(items):
            raise ValueError("links revision changed the number of entries")
        new_items = []
        for orig, t in zip(items, takes):
            if not isinstance(t, dict):
                raise ValueError("bad link entry")
            new_items.append({**orig, "take": str(t.get("take", orig.get("take", ""))).strip()})
        merged["items"] = new_items
        return merged, changes

    for key in EDITABLE.get(kind, []):
        val = revised.get(key)
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"revision dropped or emptied '{key}'")
        merged[key] = val.strip()
    if kind == "article" and len(merged["body"].split()) < 250:
        raise ValueError("revised body is too short")
    return merged, changes


def snapshot(kind, rec, version):
    """What we keep of the previous version for history on the article doc."""
    view = {k: rec.get(k) for k in EDITABLE.get(kind, []) if k != "takes"}
    if kind == "links":
        view["items"] = rec.get("items", [])
    return {"version": version, **view,
            "review_decision": rec.get("review_decision", ""), "review_reason": rec.get("review_reason", "")}


def revise_item(client, model, kind, rec, note, overall_note, today, retries=3):
    """One Gemini rewrite. Returns (merged_record, changes); raises on failure."""
    prompt = build_revision_prompt(kind, rec, note, overall_note, today)
    last = None
    for attempt in range(retries):
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt,
                config={"response_mime_type": "application/json", "temperature": 0.4})
            return parse_revision(resp.text or "", kind, rec)
        except ValueError as e:      # bad output: try again with a fresh sample
            last = e
        except Exception as e:       # quota / transient API errors
            last = e
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                time.sleep(20 * (attempt + 1))
            else:
                break
    raise RuntimeError(f"revision failed: {str(last)[:300]}")
