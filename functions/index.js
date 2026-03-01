const { onRequest } = require("firebase-functions/v2/https");
const { defineSecret } = require("firebase-functions/params");
const admin = require("firebase-admin");
const nodemailer = require("nodemailer");

admin.initializeApp();

const GMAIL_USER = defineSecret("GMAIL_USER");
const GMAIL_PASSWORD = defineSecret("GMAIL_PASSWORD");

exports.sendNewsletter = onRequest(
    { secrets: ["GMAIL_USER", "GMAIL_PASSWORD"] },
    async (req, res) => {

        if (req.method !== "POST") return res.status(405).send("Method not allowed");

        const { subject, body } = req.body;
        if (!subject || !body) {
            return res.status(400).json({ error: "subject and body are required" });
        }

        const transporter = nodemailer.createTransport({
            service: "gmail",
            auth: {
                user: GMAIL_USER.value(),
                pass: GMAIL_PASSWORD.value()
            }
        });

        try {
            const db = admin.firestore();
            const snapshot = await db.collection("customers")
                .where("active", "==", true)
                .get();

            const subscribers = [];
            snapshot.forEach(doc => subscribers.push(doc.data().email));

            if (subscribers.length === 0) {
                return res.json({ success: true, sent: 0, message: "No subscribers found" });
            }

            let sent = 0;
            for (const email of subscribers) {
                await transporter.sendMail({
                    from: `"Karthikeyan Selvam" <${GMAIL_USER.value()}>`,
                    to: email,
                    subject: subject,
                    html: `
                        <div style="max-width:600px; margin:0 auto; font-family:Inter,sans-serif;
                                    background:#060810; color:#E6EDF3; padding:2rem; border-radius:12px;">
                            <h2 style="color:#00C9A7; margin-bottom:1rem;">KS | AI Insights</h2>
                            <div style="line-height:1.8; color:#c9d1d9;">${body}</div>
                            <hr style="border-color:rgba(0,201,167,0.2); margin:2rem 0;"/>
                            <p style="font-size:0.8rem; color:#8B949E;">
                                You received this because you subscribed at karthikeyanselvam.com
                            </p>
                        </div>
                    `
                });
                sent++;
            }

            res.json({ success: true, sent });

        } catch(err) {
            console.error("Newsletter error:", err);
            res.status(500).json({ error: err.message });
        }
    }
);
