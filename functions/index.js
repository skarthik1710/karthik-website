// Newsletter functions. One rule above all: subscribers are emailed ONLY from
// approveIssue, which only the signed-in admin can call. Everything automated
// (the weekly generator, the custom-newsletter workflow) can at most create an
// issue that waits for approval and email the admin a review digest.
const { onRequest, onCall, HttpsError } = require("firebase-functions/v2/https");
const { defineSecret } = require("firebase-functions/params");
const { initializeApp } = require("firebase-admin/app");
const { getFirestore, FieldValue, Timestamp } = require("firebase-admin/firestore");
const nodemailer = require("nodemailer");
const crypto = require("crypto");

initializeApp();

const GMAIL_USER = defineSecret("GMAIL_USER");
const GMAIL_PASSWORD = defineSecret("GMAIL_PASSWORD");
const NEWSLETTER_SECRET = defineSecret("NEWSLETTER_SECRET");

// Must match isAdmin() in firestore.rules.
const ADMIN_EMAIL = "skarthik1710@gmail.com";
const SITE_URL = "https://karthikeyanselvam.com";
const FUNCTIONS_BASE = "https://us-central1-karthik-website-b5801.cloudfunctions.net";
const MAIL_SECRETS = ["GMAIL_USER", "GMAIL_PASSWORD", "NEWSLETTER_SECRET"];

// Constant-time compare so the secret-gated endpoints can't be brute-forced/timed.
function authorized(req) {
    const expected = NEWSLETTER_SECRET.value();
    const provided = req.get("X-Newsletter-Secret") || "";
    if (!expected || !provided) return false;
    const a = Buffer.from(provided);
    const b = Buffer.from(expected);
    return a.length === b.length && crypto.timingSafeEqual(a, b);
}

function requireAdmin(request) {
    const t = request.auth && request.auth.token;
    if (!t || t.email_verified !== true || t.email !== ADMIN_EMAIL) {
        throw new HttpsError("permission-denied", "Admin only.");
    }
}

function transporter() {
    return nodemailer.createTransport({
        service: "gmail",
        auth: { user: GMAIL_USER.value(), pass: GMAIL_PASSWORD.value() },
    });
}

const FROM = () => `"Karthikeyan Selvam" <${GMAIL_USER.value()}>`;

// ── unsubscribe tokens: HMAC(email) so links can't be forged for other people ──
function unsubToken(email) {
    return crypto.createHmac("sha256", NEWSLETTER_SECRET.value())
        .update("unsub:" + email.toLowerCase()).digest("hex").slice(0, 32);
}
function unsubUrl(email) {
    return `${FUNCTIONS_BASE}/unsubscribe?e=${encodeURIComponent(email)}&t=${unsubToken(email)}`;
}

// Weekly issues are dark-text-on-light; legacy custom issues were written for a
// dark card. The issue doc says which.
function wrap(bodyHtml, footerHtml, theme) {
    const dark = theme === "dark";
    return `
        <div style="max-width:640px; margin:0 auto; font-family:Inter,Arial,sans-serif;
                    background:${dark ? "#060810" : "#ffffff"}; color:${dark ? "#E6EDF3" : "#1a1a1a"};
                    padding:2rem; border-radius:12px;">
            <div style="line-height:1.7;">${bodyHtml}</div>
            <hr style="border:none; border-top:1px solid ${dark ? "rgba(0,201,167,0.2)" : "#eee"}; margin:2rem 0;"/>
            <p style="font-size:0.8rem; color:#8B949E;">${footerHtml}</p>
        </div>`;
}

// Remove the blocks of items that are not approved (<!--item:ID-->…<!--/item:ID-->).
function stripUnapproved(html, approvedIds) {
    return html.replace(/<!--item:([A-Za-z0-9]+)-->([\s\S]*?)<!--\/item:\1-->/g,
        (_, id, inner) => (approvedIds.has(id) ? inner : ""));
}

const emailKey = (email) => crypto.createHash("sha256").update(email).digest("hex").slice(0, 40);

// ────────────────────────────────────────────────────────────────────────────
// sendReviewEmail — the generator's morning digest. The recipient is fixed to
// the admin; callers cannot choose who gets mail.
exports.sendReviewEmail = onRequest({ secrets: MAIL_SECRETS }, async (req, res) => {
    if (req.method !== "POST") return res.status(405).send("Method not allowed");
    if (!authorized(req)) return res.status(401).json({ error: "Unauthorized" });
    const { subject, html } = req.body || {};
    if (!subject || !html) return res.status(400).json({ error: "subject and html are required" });
    try {
        await transporter().sendMail({ from: FROM(), to: ADMIN_EMAIL, subject: String(subject).slice(0, 200), html });
        return res.json({ success: true });
    } catch (err) {
        console.error("Review email error:", err);
        // Secret-gated caller (CI): return the SMTP error class only, e.g. EAUTH.
        return res.status(500).json({ error: "send failed", code: err.code || "", response: err.responseCode || "" });
    }
});

// ────────────────────────────────────────────────────────────────────────────
// sendNewsletter — kept for the custom-newsletter workflow, but it can no longer
// email subscribers. With testTo it sends a [TEST] copy to the ADMIN only;
// otherwise it creates a custom issue awaiting approval and emails the admin.
exports.sendNewsletter = onRequest({ secrets: MAIL_SECRETS }, async (req, res) => {
    if (req.method !== "POST") return res.status(405).send("Method not allowed");
    if (!authorized(req)) return res.status(401).json({ error: "Unauthorized" });
    const { subject, body, testTo } = req.body || {};
    if (!subject || !body) return res.status(400).json({ error: "subject and body are required" });

    try {
        if (testTo) {
            await transporter().sendMail({
                from: FROM(), to: ADMIN_EMAIL, subject: `[TEST] ${subject}`,
                html: wrap(body, "TEST SEND — real subscribers were not emailed.", "dark"),
            });
            return res.json({ success: true, sent: 1, test: true, to: ADMIN_EMAIL });
        }

        const issueId = "custom-" + new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-");
        await getFirestore().collection("newsletter_issues").doc(issueId).create({
            issue_id: issueId,
            kind: "custom",
            date: new Date().toISOString().slice(0, 10),
            status: "awaiting_approval",
            item_ids: [],
            subject_candidates: [],
            fallback_subject: String(subject).slice(0, 200),
            email_html: body,
            theme: "dark",
            created_at: FieldValue.serverTimestamp(),
        });
        await transporter().sendMail({
            from: FROM(), to: ADMIN_EMAIL,
            subject: `[Review] Custom newsletter: ${subject}`,
            html: wrap(
                `<p><strong>Nothing has been sent.</strong> Approve or reject this custom issue on the
                 <a href="${SITE_URL}/admin/?issue=${issueId}">review desk</a> (Google sign-in required).</p>
                 <hr/>${body}`,
                `Issue ${issueId}`, "dark"),
        });
        return res.json({ success: true, issue: issueId, status: "awaiting_approval" });
    } catch (err) {
        console.error("Newsletter error:", err);
        return res.status(500).json({ error: "request failed" });
    }
});

// ────────────────────────────────────────────────────────────────────────────
// approveIssue — the ONLY path that emails subscribers. Admin-only callable.
// Idempotent: a transaction claims the issue, and each delivery is recorded so a
// retry (status send_incomplete) never emails anyone twice.
exports.approveIssue = onCall({ secrets: MAIL_SECRETS, timeoutSeconds: 540 }, async (request) => {
    requireAdmin(request);
    const issueId = String((request.data || {}).issueId || "");
    if (!/^[A-Za-z0-9-]{4,40}$/.test(issueId)) throw new HttpsError("invalid-argument", "Bad issue id.");

    const db = getFirestore();
    const issueRef = db.collection("newsletter_issues").doc(issueId);

    // 1. Claim the issue (awaiting_approval | send_incomplete → publishing).
    const issue = await db.runTransaction(async (tx) => {
        const snap = await tx.get(issueRef);
        if (!snap.exists) throw new HttpsError("not-found", "No such issue.");
        const d = snap.data();
        const leaseExpired = d.status === "publishing" &&
            (!d.publishing_lease_until || d.publishing_lease_until.toMillis() < Date.now());
        if (!["awaiting_approval", "send_incomplete"].includes(d.status) && !leaseExpired) {
            throw new HttpsError("failed-precondition",
                d.status === "publishing" ? "Already publishing — try again in a few minutes if it seems stuck."
                                          : `Issue is already ${d.status}.`);
        }
        tx.update(issueRef, {
            status: "publishing",
            // If this run dies (timeout/crash) the lease lapses and approving again resumes.
            publishing_lease_until: Timestamp.fromMillis(Date.now() + 10 * 60 * 1000),
            approved_at: d.approved_at || FieldValue.serverTimestamp(),
            approved_by: request.auth.token.email,
        });
        return d;
    });

    try {
        // 2. Publish: still-pending items go live; items the admin dropped stay rejected.
        const approvedIds = new Set();
        const articleRefs = (issue.item_ids || []).map((id) => db.collection("newsletter_articles").doc(id));
        if (articleRefs.length) {
            const snaps = await db.getAll(...articleRefs);
            const batch = db.batch();
            for (const s of snaps) {
                if (!s.exists) continue;
                const st = s.data().status;
                if (st === "pending_review") {
                    batch.update(s.ref, { status: "approved", published_at: FieldValue.serverTimestamp() });
                    approvedIds.add(s.id);
                } else if (st === "approved") {
                    approvedIds.add(s.id);
                }
            }
            await batch.commit();
        }

        const isCustom = issue.kind === "custom";
        if (!isCustom && approvedIds.size === 0) {
            await issueRef.update({ status: "rejected", note: "every item was dropped before approval",
                publishing_lease_until: FieldValue.delete() });
            return { status: "rejected", sent: 0, message: "Every item was dropped, so nothing was sent." };
        }

        const lead = (issue.subject_candidates || []).find((c) => approvedIds.has(c.id));
        const subject = lead ? lead.title : issue.fallback_subject;
        const body = isCustom ? issue.email_html : stripUnapproved(issue.email_html, approvedIds);

        // 3. Send once per unique active subscriber, recording each delivery.
        const subsSnap = await db.collection("customers").where("active", "==", true).get();
        const emails = [...new Set(subsSnap.docs
            .map((d) => String(d.data().email || "").trim().toLowerCase())
            .filter((e) => e.includes("@")))];

        const deliveries = issueRef.collection("deliveries");
        const mailer = transporter();
        let sent = 0, skipped = 0, failed = 0;
        for (const email of emails) {
            const dref = deliveries.doc(emailKey(email));
            // Claim BEFORE sending: at-most-once. A crash after the claim may skip
            // one person, but nobody is ever emailed twice.
            try {
                await dref.create({ state: "sending", at: FieldValue.serverTimestamp() });
            } catch (e) {
                if (e.code === 6 /* ALREADY_EXISTS */) { skipped++; continue; }
                throw e;
            }
            const unsub = unsubUrl(email);
            try {
                await mailer.sendMail({
                    from: FROM(), to: email, subject,
                    html: wrap(body,
                        `You received this because you subscribed at karthikeyanselvam.com.
                         <a href="${unsub}" style="color:#8B949E;">Unsubscribe</a>`,
                        issue.theme || "light"),
                    headers: { "List-Unsubscribe": `<${unsub}>` },
                });
            } catch (e) {
                // SMTP refused it: release the claim so a resume retries this person.
                console.error("Delivery failed for one recipient:", e.message);
                await dref.delete().catch(() => {});
                failed++;
                continue;
            }
            sent++;
            await dref.update({ state: "sent" }).catch((e) => console.error("delivery record:", e.message));
        }

        const status = failed ? "send_incomplete" : "sent";
        await issueRef.update({
            status, subject,
            publishing_lease_until: FieldValue.delete(),
            approved_item_ids: [...approvedIds],
            sent_count: FieldValue.increment(sent),
            failed_count: failed,
            sent_at: FieldValue.serverTimestamp(),
        });
        return { status, sent, skipped, failed, subscribers: emails.length };
    } catch (err) {
        // Anything unexpected: leave it retryable rather than stuck in "publishing".
        console.error("approveIssue error:", err);
        await issueRef.update({ status: "send_incomplete", publishing_lease_until: FieldValue.delete(), error: String(err.message || err).slice(0, 300) });
        throw new HttpsError("internal", "Publishing failed part-way; it is safe to approve again to resume.");
    }
});

// ────────────────────────────────────────────────────────────────────────────
// requestRevision — admin-only. Queues a rewrite of the issue from the admin's
// notes; the Python function reviseIssue does the work and emails version n+1.
// Nothing is published: the issue sits in "revising", then back to awaiting_approval.
const MAX_NOTE = 2000;
exports.requestRevision = onCall(async (request) => {
    requireAdmin(request);
    const data = request.data || {};
    const issueId = String(data.issueId || "");
    if (!/^[A-Za-z0-9-]{4,40}$/.test(issueId)) throw new HttpsError("invalid-argument", "Bad issue id.");
    const overall = String(data.overallNote || "").trim().slice(0, MAX_NOTE);
    const itemNotes = {};
    for (const [id, note] of Object.entries(data.itemNotes || {}).slice(0, 30)) {
        const n = String(note || "").trim().slice(0, MAX_NOTE);
        if (/^[A-Za-z0-9]{10,40}$/.test(id) && n) itemNotes[id] = n;
    }
    if (!overall && Object.keys(itemNotes).length === 0) {
        throw new HttpsError("invalid-argument", "Write at least one note.");
    }

    const db = getFirestore();
    const issueRef = db.collection("newsletter_issues").doc(issueId);
    return db.runTransaction(async (tx) => {
        const snap = await tx.get(issueRef);
        if (!snap.exists) throw new HttpsError("not-found", "No such issue.");
        const d = snap.data();
        if (d.kind === "custom") throw new HttpsError("failed-precondition", "Custom issues can't be auto-revised.");
        // A revision stuck for 15+ minutes (function crashed) may be re-requested.
        const stuck = d.status === "revising" && d.revision_requested_at &&
            d.revision_requested_at.toMillis() < Date.now() - 15 * 60 * 1000;
        if (d.status !== "awaiting_approval" && !stuck) {
            throw new HttpsError("failed-precondition", `Issue is ${d.status}.`);
        }
        for (const id of Object.keys(itemNotes)) {
            if (!(d.item_ids || []).includes(id)) delete itemNotes[id];
        }
        const version = (d.version || 1) + 1;
        // Unique, never-reused id per request: a create always fires the trigger,
        // and a late result from an older request can't commit (it no longer owns
        // current_revision).
        const seq = (d.revision_seq || 0) + 1;
        const revId = `r${seq}`;
        tx.update(issueRef, { status: "revising", revision_seq: seq, current_revision: revId,
                              revision_requested_at: FieldValue.serverTimestamp() });
        tx.create(issueRef.collection("revisions").doc(revId), {
            version, overall_note: overall, item_notes: itemNotes, status: "queued",
            requested_by: request.auth.token.email, requested_at: FieldValue.serverTimestamp(),
        });
        return { status: "revising", version };
    });
});

// ────────────────────────────────────────────────────────────────────────────
// rejectIssue — admin-only. Nothing is published or sent; drafts are buried.
exports.rejectIssue = onCall(async (request) => {
    requireAdmin(request);
    const issueId = String((request.data || {}).issueId || "");
    if (!/^[A-Za-z0-9-]{4,40}$/.test(issueId)) throw new HttpsError("invalid-argument", "Bad issue id.");
    const db = getFirestore();
    const issueRef = db.collection("newsletter_issues").doc(issueId);
    const issue = await db.runTransaction(async (tx) => {
        const snap = await tx.get(issueRef);
        if (!snap.exists) throw new HttpsError("not-found", "No such issue.");
        if (!["awaiting_approval", "revising"].includes(snap.data().status)) {
            throw new HttpsError("failed-precondition", `Issue is already ${snap.data().status}.`);
        }
        tx.update(issueRef, { status: "rejected", rejected_at: FieldValue.serverTimestamp() });
        return snap.data();
    });
    const refs = (issue.item_ids || []).map((id) => db.collection("newsletter_articles").doc(id));
    if (refs.length) {
        const batch = db.batch();
        for (const s of await db.getAll(...refs)) {
            if (s.exists && s.data().status === "pending_review") batch.update(s.ref, { status: "rejected" });
        }
        await batch.commit();
    }
    return { status: "rejected" };
});

// ────────────────────────────────────────────────────────────────────────────
// unsubscribe — GET shows a confirm button (so email link scanners that
// prefetch URLs can't unsubscribe people); POST performs it.
exports.unsubscribe = onRequest({ secrets: ["NEWSLETTER_SECRET"] }, async (req, res) => {
    const email = String(req.query.e || req.body?.e || "").trim().toLowerCase();
    const token = String(req.query.t || req.body?.t || "");
    const page = (msg, form = "") => res.set("Content-Type", "text/html").send(
        `<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">
         <meta name="robots" content="noindex">
         <body style="font-family:Inter,Arial,sans-serif;max-width:520px;margin:4rem auto;padding:0 1rem;color:#1a1a1a">
         <h2>Newsletter</h2><p>${msg}</p>${form}</body>`);

    const expected = email ? unsubToken(email) : "";
    const tb = Buffer.from(token), eb = Buffer.from(expected);
    const ok = email && tb.length === eb.length && crypto.timingSafeEqual(tb, eb);
    if (!ok) {
        res.status(400);
        return page("This unsubscribe link is invalid or incomplete.");
    }

    if (req.method === "POST") {
        // Emails are stored as typed (mixed case), so match on the normalised form.
        const snap = await getFirestore().collection("customers").where("active", "==", true).get();
        const matches = snap.docs.filter((d) => String(d.data().email || "").trim().toLowerCase() === email);
        if (matches.length) {
            const batch = getFirestore().batch();
            matches.forEach((d) => batch.update(d.ref, { active: false, unsubscribed_at: FieldValue.serverTimestamp() }));
            await batch.commit();
        }
        return page(matches.length ? "You're unsubscribed. You won't receive any more issues."
                                   : "This address has no active subscription — you won't receive any issues.");
    }
    const safe = email.replace(/[<>&"]/g, "");
    return page(`Unsubscribe <strong>${safe}</strong> from the newsletter?`,
        `<form method="POST"><input type="hidden" name="e" value="${safe}"><input type="hidden" name="t" value="${token}">
         <button style="padding:.6rem 1.2rem;font-size:1rem;cursor:pointer">Unsubscribe</button></form>`);
});
