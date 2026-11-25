/* ────────────────────────────────────────────────────────────────────────────
   Pure helpers for askKarthik — no Firebase / network dependencies, so they
   can be unit-tested with `node --test` (see functions-chat/test/).
──────────────────────────────────────────────────────────────────────────── */

const MAX_USER_CHARS = 600;
const MAX_ASSISTANT_CHARS = 1500;
const MAX_TURNS = 12;
const MAX_FOLLOWUPS = 3;
const MAX_FOLLOWUP_CHARS = 90;

// Shown when the model returns no usable follow-ups, or the request was
// blocked by a safety filter. Must stay answerable from the system-prompt facts.
const STARTER_FOLLOWUPS = [
    "Tell me about his AI platform",
    "How does he approach AI governance?",
    "Why hire him as an AI leader?"
];

// Gemini structured-output schema. propertyOrdering puts `reply` first so a
// MAX_TOKENS cut-off still leaves a salvageable reply string.
const RESPONSE_SCHEMA = {
    type: "OBJECT",
    properties: {
        reply: { type: "STRING" },
        followups: { type: "ARRAY", items: { type: "STRING" } }
    },
    required: ["reply", "followups"],
    propertyOrdering: ["reply", "followups"]
};

/**
 * Validate + normalise the client-supplied history into a Gemini-safe shape:
 * last MAX_TURNS turns, per-role length caps, no leading assistant turn,
 * consecutive same-role turns merged (Gemini expects alternation), and the
 * final turn must be from the user. Returns null if unusable.
 */
function normalizeHistory(messages) {
    if (!Array.isArray(messages) || messages.length === 0) return null;
    const turns = [];
    for (const m of messages.slice(-MAX_TURNS)) {
        const role = m && m.role === "assistant" ? "assistant" : "user";
        const cap = role === "assistant" ? MAX_ASSISTANT_CHARS : MAX_USER_CHARS;
        const content = String((m && m.content) || "").slice(0, cap).trim();
        if (!content) continue;
        const prev = turns[turns.length - 1];
        if (prev && prev.role === role) {
            // Keep the TAIL: the newest text (usually the live question) must never be cut.
            prev.content = (prev.content + "\n\n" + content).slice(-cap);
        } else {
            turns.push({ role, content });
        }
    }
    while (turns.length && turns[0].role !== "user") turns.shift();
    if (turns.length === 0 || turns[turns.length - 1].role !== "user") return null;
    return turns;
}

/** Trim text that hit the token cap back to its last complete sentence. */
function trimToSentence(text) {
    const s = String(text || "").trim();
    const re = /[.!?]["')\]]?(?=\s|$)/g;
    let cut = -1, m;
    while ((m = re.exec(s)) !== null) cut = m.index + m[0].length;
    if (cut > 40) return s.slice(0, cut);
    return s ? s.replace(/[\s,;:–—-]+$/, "") + "…" : s;
}

/**
 * Parse the model's structured output. Falls back gracefully:
 *  1. valid JSON {reply, followups}
 *  2. truncated JSON → salvage the (complete or partial) "reply" string
 *  3. plain text (model ignored JSON mode) → whole text is the reply
 */
function parseModelOutput(raw) {
    const text = String(raw || "").trim();
    if (!text) return { reply: "", followups: [], salvaged: false };
    const unfenced = text.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
    try {
        const obj = JSON.parse(unfenced);
        if (obj && typeof obj === "object" && typeof obj.reply === "string") {
            return {
                reply: obj.reply.trim(),
                followups: Array.isArray(obj.followups) ? obj.followups : [],
                salvaged: false
            };
        }
    } catch (_) { /* fall through to salvage */ }
    const m = unfenced.match(/"reply"\s*:\s*"((?:[^"\\]|\\.)*)/);
    if (m) {
        let body = m[1];
        // Drop a dangling escape left by truncation before decoding.
        body = body.replace(/\\u[0-9a-fA-F]{0,3}$/, "").replace(/\\$/, "");
        let reply;
        try { reply = JSON.parse('"' + body + '"'); }
        catch (_) { reply = body.replace(/\\n/g, "\n").replace(/\\"/g, '"'); }
        return { reply: reply.trim(), followups: [], salvaged: true };
    }
    if (/^\s*[{[]/.test(unfenced)) return { reply: "", followups: [], salvaged: true };
    return { reply: text, followups: [], salvaged: false };
}

function normQ(s) {
    return String(s || "").toLowerCase().replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();
}

/**
 * Clean model-proposed follow-up questions: strings only, markdown/numbering
 * stripped, length-capped, ends with "?", de-duplicated, and never repeating a
 * question the visitor already asked. At most MAX_FOLLOWUPS.
 */
function sanitizeFollowups(list, askedQuestions) {
    const asked = new Set((askedQuestions || []).map(normQ));
    const seen = new Set();
    const out = [];
    for (const item of Array.isArray(list) ? list : []) {
        if (typeof item !== "string") continue;
        let q = item
            .replace(/[*_`#>]/g, "")
            .replace(/^\s*(?:[-•]|\d+[.)])\s*/, "")
            .replace(/\s+/g, " ")
            .trim()
            .replace(/^["'“”]+|["'“”]+$/g, "")
            .trim();
        if (q.length < 8 || q.length > MAX_FOLLOWUP_CHARS) continue;
        if (/https?:\/\/|@/.test(q)) continue;
        if (!/[?]$/.test(q)) q = q.replace(/[.!]+$/, "") + "?";
        const key = normQ(q);
        if (!key || seen.has(key) || asked.has(key)) continue;
        seen.add(key);
        out.push(q);
        if (out.length >= MAX_FOLLOWUPS) break;
    }
    return out;
}

/** True when Gemini refused the prompt or output on safety/recitation grounds. */
function isBlocked(data, cand) {
    if (data && data.promptFeedback && data.promptFeedback.blockReason) return true;
    const fr = cand && cand.finishReason;
    return fr === "SAFETY" || fr === "RECITATION" || fr === "BLOCKLIST" || fr === "PROHIBITED_CONTENT" || fr === "SPII";
}

module.exports = {
    MAX_FOLLOWUPS,
    STARTER_FOLLOWUPS,
    RESPONSE_SCHEMA,
    normalizeHistory,
    trimToSentence,
    parseModelOutput,
    sanitizeFollowups,
    isBlocked
};
