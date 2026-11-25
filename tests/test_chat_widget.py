"""Browser tests for the shared Skipper chat widget (public/chat.js + chat.css).

Run:  python3 -m unittest tests.test_chat_widget -v
Needs: pip install playwright && python3 -m playwright install chromium
       (skips cleanly if Playwright / Chromium are not installed).

The askKarthik endpoint is mocked with page.route(), and every other external
request (CDNs, Firebase, fonts) is blocked, so the tests are hermetic and free.
"""
import functools
import http.server
import json
import os
import threading
import unittest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

PUBLIC = os.path.join(os.path.dirname(__file__), "..", "public")
ENDPOINT = "https://us-central1-karthik-website-b5801.cloudfunctions.net/askKarthik"

LONG_REPLY = (
    "Karthikeyan founded and leads an enterprise multi-agent AI platform on Google Cloud, "
    "powered by Vertex AI and Gemini. He took it from concept to production and owns the "
    "roadmap, delivery and adoption across a portfolio of specialised agents.\n\n"
    "The platform encodes consulting methodologies into skill-based agents that produce "
    "version-tagged, audit-traceable deliverables, compressing multi-day consulting work "
    "into on-demand output. He also built its governance: authentication and role-based "
    "access on every endpoint, an automated model-lifecycle steward that migrates agents "
    "off retired models, and accuracy guardrails that block unsafe recommendations when "
    "data is insufficient.\n\n"
    "- Regional-only data residency\n- Scale-to-zero cost engineering\n- Token budgeting\n\n"
    "It runs under a strict regional-only data-residency policy and is cost-engineered end "
    "to end. Reach him at skarthik1710@gmail.com or https://www.linkedin.com/in/karthikeyan-selvam-567b52157/."
)
FOLLOWUPS = ["What is RevokAI?", "How does he drive Copilot adoption?", "Which certifications does he hold?"]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@unittest.skipIf(sync_playwright is None, "playwright not installed")
class ChatWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = functools.partial(_QuietHandler, directory=os.path.abspath(PUBLIC))
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.base = "http://127.0.0.1:%d" % cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch()
        except Exception as e:  # pragma: no cover
            cls.pw.stop()
            cls.httpd.shutdown()
            raise unittest.SkipTest("chromium not installed: %s" % e)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.httpd.shutdown()

    # ── helpers ──
    def new_page(self, responses, viewport=None, reduced_motion=True):
        """responses: list of (status, body_dict) served in order; the last repeats."""
        ctx = self.browser.new_context(
            viewport=viewport or {"width": 1280, "height": 860},
            reduced_motion="reduce" if reduced_motion else "no-preference",
        )
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        self.requests, self.js_errors = [], []
        page.on("pageerror", lambda e: self.js_errors.append(str(e)))
        queue = list(responses)

        def handle(route):
            req = route.request
            if req.url.startswith(ENDPOINT):
                if req.method == "OPTIONS":
                    return route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "Content-Type"})
                self.requests.append(json.loads(req.post_data or "{}"))
                status, body = queue.pop(0) if len(queue) > 1 else queue[0]
                return route.fulfill(status=status, content_type="application/json",
                                     headers={"Access-Control-Allow-Origin": "*"}, body=json.dumps(body))
            if req.url.startswith(self.base):
                return route.continue_()
            return route.abort()

        page.route("**/*", handle)
        return page

    def open_chat(self, page, path="/index.html"):
        page.goto(self.base + path)
        page.click("#chat-fab")
        page.wait_for_selector("#chat-pop.open")

    def ask_chip(self, page, idx=0):
        page.locator("#chat-chips .chat-chip").nth(idx).click()
        page.wait_for_function("!document.querySelector('#chat-log[aria-busy]') && !document.querySelector('.chat-typing')")

    def chat_errors(self):
        return [e for e in self.js_errors if "chat" in e.lower() or "skipper" in e.lower()]

    # ── tests ──
    def test_answer_revealed_from_top_not_bottom(self):
        page = self.new_page([(200, {"reply": LONG_REPLY, "followups": FOLLOWUPS})])
        self.open_chat(page)
        self.ask_chip(page)
        m = page.evaluate("""() => {
            const log = document.getElementById('chat-log');
            const bot = log.querySelector('.chat-msg.bot:last-of-type');
            const user = [...log.querySelectorAll('.chat-msg.user')].pop();
            const lr = log.getBoundingClientRect();
            return { overflow: log.scrollHeight > log.clientHeight + 5,
                     atBottom: Math.abs(log.scrollHeight - log.clientHeight - log.scrollTop) < 4,
                     userTop: user.getBoundingClientRect().top - lr.top,
                     botTop: bot.getBoundingClientRect().top - lr.top };
        }""")
        self.assertTrue(m["overflow"], "fixture reply should overflow the log")
        self.assertFalse(m["atBottom"], "log must not be pinned to the bottom of the answer")
        self.assertGreaterEqual(m["userTop"], 0)
        self.assertLess(m["userTop"], 40, "question should sit at the top of the log")
        self.assertLess(m["botTop"], 200, "start of the answer must be visible")
        self.assertEqual(self.chat_errors(), [])

    def test_followups_rendered_after_each_answer(self):
        page = self.new_page([(200, {"reply": "Short answer one.", "followups": FOLLOWUPS}),
                              (200, {"reply": "Short answer two.", "followups": []})])
        self.open_chat(page)
        self.ask_chip(page)
        chips = page.locator("#chat-chips .chat-chip").all_inner_texts()
        self.assertEqual(chips, FOLLOWUPS)
        self.assertEqual(page.inner_text(".chat-chips-label"), "ASK NEXT")
        self.assertTrue(page.is_visible("#chat-chips"))
        # second answer has no server followups → curated pool top-up, minus asked
        self.ask_chip(page, 0)
        chips2 = page.locator("#chat-chips .chat-chip").all_inner_texts()
        self.assertGreaterEqual(len(chips2), 2)
        self.assertNotIn("What is RevokAI?", chips2, "already-asked question must not be re-suggested")
        asked = [m["content"] for m in self.requests[-1]["messages"] if m["role"] == "user"]
        for c in chips2:
            self.assertNotIn(c, asked)

    def test_tab_fills_and_cycles_suggestions_then_releases_focus(self):
        page = self.new_page([(200, {"reply": "Short answer.", "followups": FOLLOWUPS})])
        self.open_chat(page)
        self.ask_chip(page)
        page.focus("#chat-input")
        self.assertEqual(page.get_attribute("#chat-input", "placeholder"), FOLLOWUPS[0])
        self.assertIn("Tab", page.inner_text("#chat-hint"))
        for expected in FOLLOWUPS:
            page.keyboard.press("Tab")
            self.assertEqual(page.input_value("#chat-input"), expected)
            self.assertEqual(page.evaluate("document.activeElement.id"), "chat-input")
            self.assertEqual(page.locator("#chat-chips .chat-chip.active").inner_text(), expected)
        page.keyboard.press("Tab")  # past the last suggestion: normal Tab (no keyboard trap)
        self.assertEqual(page.evaluate("document.activeElement.id"), "chat-send")
        # Shift+Tab is never intercepted
        page.focus("#chat-input")
        page.fill("#chat-input", "")
        page.keyboard.press("Shift+Tab")
        self.assertNotEqual(page.evaluate("document.activeElement.id"), "chat-input")
        self.assertEqual(page.input_value("#chat-input"), "")
        # own text: Tab is not intercepted
        page.fill("#chat-input", "my own question")
        page.focus("#chat-input")
        page.keyboard.press("Tab")
        self.assertEqual(page.input_value("#chat-input"), "my own question")
        self.assertEqual(page.evaluate("document.activeElement.id"), "chat-send")

    def test_arrow_keys_browse_and_enter_sends_suggestion(self):
        page = self.new_page([(200, {"reply": "Short answer.", "followups": FOLLOWUPS})])
        self.open_chat(page)
        self.ask_chip(page)
        page.focus("#chat-input")
        page.keyboard.press("ArrowDown")
        self.assertEqual(page.input_value("#chat-input"), FOLLOWUPS[0])
        page.keyboard.press("ArrowUp")
        self.assertEqual(page.input_value("#chat-input"), FOLLOWUPS[2], "ArrowUp wraps")
        page.keyboard.press("Enter")
        page.wait_for_function("document.querySelectorAll('.chat-msg.user').length === 2 && !document.querySelector('.chat-typing')")
        roles = [m["role"] for m in self.requests[-1]["messages"]]
        self.assertEqual(roles, ["user", "assistant", "user"])
        self.assertEqual(self.requests[-1]["messages"][-1]["content"], FOLLOWUPS[2])

    def test_error_offers_retry_and_keeps_history_clean(self):
        page = self.new_page([(502, {"error": "The assistant is temporarily unavailable."}),
                              (200, {"reply": "Recovered answer.", "followups": FOLLOWUPS})])
        self.open_chat(page)
        self.ask_chip(page)
        self.assertTrue(page.is_visible(".chat-msg.error .chat-retry"))
        self.assertIn("skarthik1710@gmail.com", page.inner_text(".chat-msg.error"))
        self.assertTrue(page.locator("#chat-chips .chat-chip").count() > 0, "chips must stay available after an error")
        page.click(".chat-retry")
        page.wait_for_selector("text=Recovered answer.")
        self.assertEqual(page.locator(".chat-msg.error").count(), 0)
        self.assertEqual(page.locator(".chat-msg.user").count(), 1, "retry must not duplicate the question")
        self.assertEqual([m["role"] for m in self.requests[-1]["messages"]], ["user"])

    def test_rate_limit_has_no_retry_and_restores_question(self):
        page = self.new_page([(429, {"error": "You've reached today's chat limit. Email skarthik1710@gmail.com to continue the conversation."})])
        self.open_chat(page)
        page.fill("#chat-input", "Tell me about RevokAI")
        page.press("#chat-input", "Enter")
        page.wait_for_selector(".chat-msg.error")
        self.assertEqual(page.locator(".chat-retry").count(), 0)
        self.assertEqual(page.input_value("#chat-input"), "Tell me about RevokAI")

    def test_rich_rendering_is_safe_and_links_work(self):
        evil = "**Bold** <img src=x onerror=\"window.__pwned=1\"> see javascript:alert(1) and https://example.com/path)."
        page = self.new_page([(200, {"reply": evil + "\n\n" + LONG_REPLY, "followups": []})])
        self.open_chat(page)
        self.ask_chip(page)
        bot = page.locator(".chat-msg.bot.rich").last
        self.assertEqual(bot.locator("img").count(), 0)
        self.assertIsNone(page.evaluate("window.__pwned"))
        self.assertEqual(bot.locator("strong").first.inner_text(), "Bold")
        hrefs = bot.locator("a").evaluate_all("as => as.map(a => a.getAttribute('href'))")
        self.assertIn("https://example.com/path", hrefs, "trailing ')' / '.' trimmed from URLs")
        self.assertIn("mailto:skarthik1710@gmail.com", hrefs)
        self.assertTrue(all(h.startswith(("https://", "http://", "mailto:")) for h in hrefs))
        self.assertEqual(bot.locator("ul li").count(), 3)

    def test_persists_across_pages_and_reset(self):
        page = self.new_page([(200, {"reply": "Short answer.", "followups": FOLLOWUPS})])
        self.open_chat(page)
        self.ask_chip(page)
        page.goto(self.base + "/experience.html")
        page.click("#chat-fab")
        self.assertEqual(page.locator(".chat-msg.user").count(), 1)
        self.assertEqual(page.locator("#chat-chips .chat-chip").all_inner_texts(), FOLLOWUPS)
        self.assertTrue(page.is_visible(".chat-reset"))
        page.click(".chat-reset")
        self.assertEqual(page.locator(".chat-msg.user").count(), 0)
        self.assertFalse(page.is_visible(".chat-reset"))
        self.assertEqual(page.inner_text(".chat-chips-label"), "TRY ASKING")
        self.assertIsNone(page.evaluate("sessionStorage.getItem('skipperChat.v1')"))

    def test_tampered_session_storage_does_not_break_widget(self):
        page = self.new_page([(200, {"reply": "ok.", "followups": []})])
        page.goto(self.base + "/index.html")
        page.evaluate("""sessionStorage.setItem('skipperChat.v1', JSON.stringify({history:[{role:'user',content:'<img src=x onerror=window.__pwned=1>'},{role:'evil',content:5},null], suggestions:[1,{},'Real question?']}))""")
        page.reload()
        page.click("#chat-fab")
        self.assertIsNone(page.evaluate("window.__pwned"))
        self.assertEqual(page.locator(".chat-msg.user").count(), 1)
        self.assertEqual(self.chat_errors(), [])

    def test_mobile_fullscreen_launcher_does_not_cover_send(self):
        page = self.new_page([(200, {"reply": "Short answer.", "followups": FOLLOWUPS})],
                             viewport={"width": 390, "height": 844})
        self.open_chat(page)
        self.assertFalse(page.is_visible("#chat-launcher"), "launcher must hide while full-screen chat is open")
        hit = page.evaluate("""() => { const r = document.getElementById('chat-send').getBoundingClientRect();
            const el = document.elementFromPoint(r.left + r.width/2, r.top + r.height/2); return el && el.id; }""")
        self.assertEqual(hit, "chat-send")
        box = page.locator("#chat-pop .chat-panel").bounding_box()
        self.assertAlmostEqual(box["height"], 844, delta=2)
        self.assertEqual(page.evaluate("getComputedStyle(document.getElementById('chat-input')).fontSize"), "16px")
        self.ask_chip(page)
        self.assertNotEqual(page.evaluate("document.activeElement.id"), "chat-input",
                            "must not auto-focus input on mobile (keyboard would cover the answer)")
        page.click(".chat-pop-close")
        self.assertTrue(page.is_visible("#chat-launcher"))

    def test_mobile_header_controls_fit(self):
        page = self.new_page([(200, {"reply": "Short answer.", "followups": FOLLOWUPS})],
                             viewport={"width": 360, "height": 740})
        self.open_chat(page)
        self.ask_chip(page)
        for sel in [".chat-pop-close", ".chat-reset", "#chat-send"]:
            b = page.locator(sel).bounding_box()
            self.assertLessEqual(b["x"] + b["width"], 360.5, sel + " off-screen")
        n = page.locator("#chat-chips .chat-chip").count()
        for i in range(n):
            b = page.locator("#chat-chips .chat-chip").nth(i).bounding_box()
            self.assertLessEqual(b["y"] + b["height"], page.locator(".chat-input-row").bounding_box()["y"] + 0.5)

    def test_escape_respects_story_overlay(self):
        page = self.new_page([(200, {"reply": "ok.", "followups": []})])
        self.open_chat(page)
        page.evaluate("document.getElementById('story-overlay').classList.add('open')")
        page.keyboard.press("Escape")
        self.assertTrue(page.is_visible("#chat-pop.open"))
        page.evaluate("document.getElementById('story-overlay').classList.remove('open')")
        page.keyboard.press("Escape")
        self.assertFalse(page.is_visible("#chat-pop"))
        self.assertEqual(page.evaluate("document.activeElement.id"), "chat-fab", "focus returns to the launcher")

    def test_desktop_popover_fits_short_viewport(self):
        page = self.new_page([(200, {"reply": LONG_REPLY, "followups": FOLLOWUPS})],
                             viewport={"width": 1280, "height": 600})
        self.open_chat(page)
        self.ask_chip(page)
        for sel in [".chat-head", "#chat-send"]:
            b = page.locator(sel).bounding_box()
            self.assertGreaterEqual(b["y"], 0, sel + " off top")
            self.assertLessEqual(b["y"] + b["height"], 600, sel + " off bottom")

    def test_restored_conversation_opens_at_latest_exchange(self):
        page = self.new_page([(200, {"reply": LONG_REPLY, "followups": FOLLOWUPS})])
        self.open_chat(page)
        for i in range(3):
            self.ask_chip(page, 0)
        page.goto(self.base + "/experience.html")
        page.click("#chat-fab")
        m = page.evaluate("""() => { const log = document.getElementById('chat-log');
            const u = [...log.querySelectorAll('.chat-msg.user')].pop();
            return { scrollTop: log.scrollTop, userTop: u.getBoundingClientRect().top - log.getBoundingClientRect().top }; }""")
        self.assertGreater(m["scrollTop"], 0)
        self.assertGreaterEqual(m["userTop"], 0)
        self.assertLess(m["userTop"], 40, "latest question should be at the top on reopen")

    def test_blocked_reply_is_shown_but_not_kept_in_history(self):
        page = self.new_page([(200, {"reply": "I can only help with questions about Karthikeyan's work.", "followups": FOLLOWUPS, "blocked": True}),
                              (200, {"reply": "Normal answer.", "followups": FOLLOWUPS})])
        self.open_chat(page)
        page.fill("#chat-input", "something off-topic")
        page.press("#chat-input", "Enter")
        page.wait_for_selector("text=I can only help")
        self.assertEqual(page.locator("#chat-chips .chat-chip").all_inner_texts(), FOLLOWUPS)
        self.ask_chip(page, 0)
        sent = [m["content"] for m in self.requests[-1]["messages"]]
        self.assertEqual(sent, [FOLLOWUPS[0]], "blocked turn must not be resent")

    def test_numbered_lists_keep_their_numbers(self):
        reply = "Here is how:\n1. Build\n2. Action\n\n3. Sustain\n\n- one\n\n- two"
        page = self.new_page([(200, {"reply": reply, "followups": []})])
        self.open_chat(page)
        self.ask_chip(page)
        bot = page.locator(".chat-msg.bot.rich").last
        self.assertEqual(bot.locator("p").first.inner_text(), "Here is how:")
        self.assertEqual(bot.locator("ol").count(), 1, "blank-line separated items continue one list")
        self.assertEqual(bot.locator("ol li").count(), 3)
        self.assertEqual(bot.locator("ul li").count(), 2)

    def test_landscape_phone_keeps_input_visible(self):
        page = self.new_page([(200, {"reply": LONG_REPLY, "followups": FOLLOWUPS})],
                             viewport={"width": 844, "height": 390})
        self.open_chat(page)
        self.ask_chip(page)
        self.assertIn("chat-compact", page.get_attribute("#chat-pop", "class"))
        panel = page.locator("#chat-pop .chat-panel").bounding_box()
        for sel in [".chat-head", "#chat-send", "#chat-input"]:
            b = page.locator(sel).bounding_box()
            self.assertGreaterEqual(b["y"], 0, sel)
            self.assertLessEqual(b["y"] + b["height"], min(390, panel["y"] + panel["height"]) + 0.5, sel + " clipped")

    def test_focus_returns_to_launcher_after_nudge_open(self):
        page = self.new_page([(200, {"reply": "ok.", "followups": []})])
        page.goto(self.base + "/index.html")
        page.evaluate("const n = document.getElementById('fab-nudge'); n.style.display = 'block'; n.focus();")
        page.evaluate("window.Skipper.open()")
        page.keyboard.press("Escape")
        self.assertEqual(page.evaluate("document.activeElement.id"), "chat-fab")

    def test_all_three_pages_load_widget(self):
        for path in ["/index.html", "/experience.html", "/newsletter.html", "/playbook.html", "/projects.html"]:
            with self.subTest(path=path):
                page = self.new_page([(200, {"reply": "Answer for " + path + ".", "followups": FOLLOWUPS})])
                self.open_chat(page, path)
                self.ask_chip(page)
                self.assertTrue(page.is_visible("text=Answer for " + path + "."))
                self.assertEqual(page.locator("#chat-chips .chat-chip").all_inner_texts(), FOLLOWUPS)
                self.assertEqual(page.get_attribute("#chat-log", "role"), "log")
                for sel in [".chat-pop-close", ".chat-reset"]:  # header controls stay inside the popover
                    b, pb = page.locator(sel).bounding_box(), page.locator("#chat-pop").bounding_box()
                    self.assertLessEqual(b["x"] + b["width"], pb["x"] + pb["width"] + 0.5, sel + " overflows header")
                self.assertEqual(self.chat_errors(), [])


if __name__ == "__main__":
    unittest.main()
