const test = require("node:test");
const assert = require("node:assert/strict");
const {
    normalizeHistory, trimToSentence, parseModelOutput, sanitizeFollowups, isBlocked, MAX_FOLLOWUPS
} = require("../lib");

test("normalizeHistory: rejects empty / non-array / assistant-last", () => {
    assert.equal(normalizeHistory(null), null);
    assert.equal(normalizeHistory([]), null);
    assert.equal(normalizeHistory([{ role: "user", content: "hi" }, { role: "assistant", content: "yo" }]), null);
    assert.equal(normalizeHistory([{ role: "user", content: "   " }]), null);
});

test("normalizeHistory: drops leading assistant turns after slicing", () => {
    const msgs = [];
    for (let i = 0; i < 7; i++) { msgs.push({ role: "user", content: "q" + i }); msgs.push({ role: "assistant", content: "a" + i }); }
    msgs.push({ role: "user", content: "last" });
    const out = normalizeHistory(msgs);
    assert.equal(out[0].role, "user");
    assert.equal(out[out.length - 1].content, "last");
    assert.ok(out.length <= 12);
});

test("normalizeHistory: merges consecutive same-role turns", () => {
    const out = normalizeHistory([{ role: "user", content: "a" }, { role: "user", content: "b" }]);
    assert.deepEqual(out, [{ role: "user", content: "a\n\nb" }]);
});

test("normalizeHistory: merge keeps the newest question intact", () => {
    const out = normalizeHistory([{ role: "user", content: "x".repeat(590) }, { role: "user", content: "What is RevokAI?" }]);
    assert.equal(out.length, 1);
    assert.ok(out[0].content.endsWith("What is RevokAI?"));
    assert.equal(out[0].content.length, 600);
});

test("normalizeHistory: role caps (user 600, assistant 1500), unknown role -> user", () => {
    const out = normalizeHistory([
        { role: "user", content: "x".repeat(900) },
        { role: "assistant", content: "y".repeat(2000) },
        { role: "system", content: "z" }
    ]);
    assert.equal(out[0].content.length, 600);
    assert.equal(out[1].content.length, 1500);
    assert.equal(out[2].role, "user");
});

test("parseModelOutput: valid JSON", () => {
    const r = parseModelOutput(JSON.stringify({ reply: " Hello. ", followups: ["What is RevokAI?"] }));
    assert.equal(r.reply, "Hello.");
    assert.deepEqual(r.followups, ["What is RevokAI?"]);
    assert.equal(r.salvaged, false);
});

test("parseModelOutput: fenced JSON", () => {
    const r = parseModelOutput('```json\n{"reply":"Hi there.","followups":[]}\n```');
    assert.equal(r.reply, "Hi there.");
});

test("parseModelOutput: truncated JSON salvages reply with escapes", () => {
    const r = parseModelOutput('{"reply": "He led \\"RevokAI\\".\\nIt saves 25 hours a week. And then he');
    assert.equal(r.salvaged, true);
    assert.ok(r.reply.startsWith('He led "RevokAI".\nIt saves'));
    assert.deepEqual(r.followups, []);
});

test("parseModelOutput: truncated mid-escape does not throw", () => {
    const r = parseModelOutput('{"reply": "Some answer text here \\');
    assert.equal(r.reply, "Some answer text here");
    const r2 = parseModelOutput('{"reply": "Café \\u00');
    assert.equal(r2.reply, "Café");
});

test("parseModelOutput: plain text passthrough; broken JSON without reply -> empty", () => {
    assert.equal(parseModelOutput("Just text.").reply, "Just text.");
    assert.equal(parseModelOutput('{"followups": ["a"').reply, "");
    assert.equal(parseModelOutput("").reply, "");
});

test("trimToSentence: cuts to last full sentence, else ellipsis", () => {
    assert.equal(trimToSentence("He built a platform on Google Cloud. It runs agents. And then the"), "He built a platform on Google Cloud. It runs agents.");
    assert.equal(trimToSentence('The platform team told everyone "it works." Then he'), 'The platform team told everyone "it works."');
    assert.equal(trimToSentence("Short and cut,"), "Short and cut…");
    assert.equal(trimToSentence(""), "");
});

test("sanitizeFollowups: cleans, caps, dedupes, drops asked + junk", () => {
    const out = sanitizeFollowups([
        "1. **What is RevokAI?**",
        "what is revokai",
        "Tell me about his AI platform",
        42,
        "short",
        "Visit https://example.com for more?",
        "x".repeat(120),
        "How does he drive Copilot adoption",
        "Which certifications does he hold?"
    ], ["Tell me about his AI platform?"]);
    assert.deepEqual(out, ["What is RevokAI?", "How does he drive Copilot adoption?", "Which certifications does he hold?"]);
    assert.ok(out.length <= MAX_FOLLOWUPS);
});

test("sanitizeFollowups: non-array -> []", () => {
    assert.deepEqual(sanitizeFollowups(undefined, []), []);
    assert.deepEqual(sanitizeFollowups("What?", []), []);
});

test("isBlocked", () => {
    assert.equal(isBlocked({ promptFeedback: { blockReason: "SAFETY" } }, {}), true);
    assert.equal(isBlocked({}, { finishReason: "SAFETY" }), true);
    assert.equal(isBlocked({}, { finishReason: "STOP" }), false);
    assert.equal(isBlocked({}, { finishReason: "MAX_TOKENS" }), false);
});
