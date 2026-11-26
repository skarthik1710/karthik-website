# Karthik Website - Professional Portfolio

Personal portfolio website for Karthikeyan Selvam - AI & Automation Practice Leader

🌐 **Live Site**: [https://karthikeyanselvam.com](https://karthikeyanselvam.com)

---

## 👨‍💻 About

Professional portfolio showcasing:
- 19+ years of experience in Digital Workplace Solutions
- Microsoft Copilot & Azure AI expertise
- 50+ RPA automations delivered by his team
- Product management and technical leadership
- Microsoft Azure & Google Cloud certifications

---

## 🛠️ Tech Stack

- **Frontend**: HTML5, CSS3, JavaScript
- **Hosting**: Firebase Hosting
- **Domain**: Cloudflare DNS
- **Version Control**: Git & GitHub

---

## 📁 Project Structure

```
karthik-website/
├── public/                 # Website files
│   ├── index.html         # Main homepage
│   ├── experience.html    # Detailed work experience
│   ├── Profile.jpg        # Profile photo
│   └── 404.html          # Custom error page
├── firebase.json          # Firebase configuration
├── .firebaserc           # Firebase project settings
├── .gitignore            # Git ignore rules
└── README.md             # This file
```

---

## 🚀 Deployment

This site is deployed on Firebase Hosting with custom domain configuration.

### Deploy Command:
```bash
firebase deploy --only hosting
```

### Local Testing:
```bash
firebase serve
```

---

## 📝 Sections

### Homepage (index.html)
- Hero section with professional introduction
- About summary
- Certifications showcase
- Contact information

### Experience Page (experience.html)
- Detailed work history timeline
- Project descriptions (client names anonymized)
- Skills and technologies
- Complete certifications list

---

## 🎓 Certifications

- Google Gen AI Leader
- Microsoft AI Transformation Leader
- Microsoft Azure AI Fundamentals (AI-900)
- Microsoft Azure Fundamentals (AZ-900)
- Microsoft PowerUp Program – Pathfinder (Copilot Studio)
- Microsoft Power Platform – Pathfinder
- UiPath RPA Developer Foundation
- UiPath RPA Developer – SAP Automation
- UiPath Business Analyst
- PRINCE2 – Project Management
- Professional Scrum Master (Scrum.org)
- Introduction to Atos Lean

---

## 📧 Contact

- **LinkedIn**: [Karthikeyan Selvam](https://www.linkedin.com/in/karthikeyan-selvam-567b52157/)
- **Email**: skarthik1710@gmail.com
- **Location**: Middletown, DE, USA

---

## 📄 License

© 2026 Karthikeyan Selvam. All rights reserved.

---

## 🔄 Update History

- **2026-02**: Initial website launch with Firebase Hosting
- **2026-02**: Added detailed work experience page
- **2026-02**: Integrated certification verification links

---

## 🛠️ Maintenance

### To Update Website:
1. Edit files in `public/` folder
2. Test locally: `firebase serve`
3. Commit changes: `git add . && git commit -m "Description"`
4. Push to GitHub: `git push`
5. Deploy to Firebase: `firebase deploy --only hosting`

---

**Built with ❤️ using modern web technologies**


---

## 🗞️ Newsletter pipeline (human-approved)

Nothing publishes or emails subscribers without the owner's approval.

1. **Friday 10:00 UTC** — `.github/workflows/newsletter.yml` runs `scripts/generate_newsletter.py`:
   drafts 2 articles + a hype check + quick links from recent RSS news, all saved as
   `pending_review` under one issue (`newsletter_issues/{YYYY-MM-DD}`).
2. **Two independent reviewers** (`scripts/newsletter_review.py`) — a Gemini fact-checker and a
   Gemini editor, each with Google Search grounding — check every claim against current trusted
   sources. An item both reviewers fail is dropped automatically; anything flagged or not fully
   reviewed is called out.
3. **Review email** to the admin (`sendReviewEmail` function — recipient fixed server-side).
4. **Approve on `/admin/?issue=…`** (Google sign-in). Drop any item, then *Approve & send* calls the
   `approveIssue` callable: publishes the remaining items and emails each subscriber exactly once
   (deliveries are recorded; a partial failure can be resumed without duplicates). Every email has
   a signed unsubscribe link (`unsubscribe` function).

Reviewer/writer models can be overridden with repo variables `NEWSLETTER_WRITER_MODEL`,
`NEWSLETTER_FACTCHECK_MODEL`, `NEWSLETTER_EDITOR_MODEL`. Tests: `python3 -m unittest discover -s tests`.
