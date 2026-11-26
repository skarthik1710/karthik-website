"""Mobile layout regressions for the public pages.

Run:  python3 -m unittest tests.test_mobile_layout -v
Needs Playwright + Chromium (skips otherwise). Only same-origin requests and
cdnjs are allowed, so pages are tested without third-party fonts or analytics.
"""
import functools
import http.server
import os
import re
import threading
import unittest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

PUBLIC = os.path.join(os.path.dirname(__file__), "..", "public")


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@unittest.skipIf(sync_playwright is None, "playwright not installed")
class MobileLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(_Quiet, directory=os.path.abspath(PUBLIC)))
        cls.base = "http://127.0.0.1:%d" % cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch()
        except Exception as e:  # pragma: no cover
            cls.pw.stop(); cls.httpd.shutdown()
            raise unittest.SkipTest("chromium not installed: %s" % e)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.httpd.shutdown()

    def page(self, width, height=844, path="/index.html"):
        pg = self.browser.new_page(viewport={"width": width, "height": height})
        self.addCleanup(pg.close)
        base = self.base
        pg.route("**/*", lambda r: r.continue_()
                 if (r.request.url.startswith(base) or "cdnjs.cloudflare.com" in r.request.url) else r.abort())
        pg.goto(self.base + path)
        pg.wait_for_timeout(500)
        return pg

    def test_home_has_no_horizontal_overflow(self):
        for width in (360, 390, 820, 1280):
            with self.subTest(width=width):
                pg = self.page(width)
                over = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                self.assertLessEqual(over, 0, "homepage scrolls sideways at %dpx" % width)

    def test_home_chapter_rail_switches_panels(self):
        for width in (390, 1280):
            with self.subTest(width=width):
                pg = self.page(width, 900)
                visible = lambda: pg.evaluate("[...document.querySelectorAll('.chapter')].filter(c => !c.hidden).map(c => c.id)")
                self.assertEqual(visible(), ["p-2007"])
                pg.click("#t-2024")
                self.assertEqual(visible(), ["p-2024"])
                self.assertEqual(pg.get_attribute("#t-2024", "aria-selected"), "true")
                pg.keyboard.press("ArrowRight")
                self.assertEqual(visible(), ["p-2025"])
                pg.keyboard.press("End")
                self.assertEqual(visible(), ["p-now"])

    def test_home_tiles_expand_and_video_modal_opens(self):
        pg = self.page(1280, 900)
        head = pg.locator(".tile-head").first
        self.assertEqual(head.get_attribute("aria-expanded"), "false")
        head.click()
        self.assertEqual(head.get_attribute("aria-expanded"), "true")
        pg.wait_for_timeout(600)
        self.assertGreater(pg.locator("#lead-1").bounding_box()["height"], 40, "tile body should open")
        pg.click(".btn-play")
        self.assertTrue(pg.evaluate("document.querySelector('.fx-modal').classList.contains('fx-open')"))
        self.assertEqual(pg.get_attribute(".fx-modal video", "src"), "/media/story.mp4")
        pg.keyboard.press("Escape")
        self.assertFalse(pg.evaluate("document.querySelector('.fx-modal').classList.contains('fx-open')"))

    def test_playbook_has_no_horizontal_overflow(self):
        for width in (360, 390, 768):
            with self.subTest(width=width):
                pg = self.page(width, path="/playbook.html")
                self.assertFalse(pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
                missing = pg.evaluate("""() => [...document.querySelectorAll('a.cite')]
                    .map(a => a.getAttribute('href').slice(1)).filter(id => !document.getElementById(id))""")
                self.assertEqual(missing, [], "citation links without a matching source")

    def test_projects_has_no_horizontal_overflow_and_playbook_links_resolve(self):
        with open(os.path.join(PUBLIC, "playbook.html"), encoding="utf-8") as f:
            playbook_ids = set(re.findall(r'id="([^"]+)"', f.read()))
        for width in (360, 390, 768):
            with self.subTest(width=width):
                pg = self.page(width, path="/projects.html")
                self.assertFalse(pg.evaluate("document.documentElement.scrollWidth > innerWidth"),
                                 "projects.html scrolls sideways (wide diagrams must scroll inside their own frame)")
                anchors = pg.evaluate("""() => [...document.querySelectorAll('a[href^="/playbook.html#"]')]
                    .map(a => a.getAttribute('href').split('#')[1])""")
                self.assertGreater(len(anchors), 0, "no 'How this is built' links to the playbook")
                missing = sorted({a for a in anchors if a not in playbook_ids})
                self.assertEqual(missing, [], "playbook links without a matching id in playbook.html")
                local = pg.evaluate("""() => [...document.querySelectorAll('a[href^="#"]')]
                    .map(a => a.getAttribute('href').slice(1)).filter(id => id && !document.getElementById(id))""")
                self.assertEqual(local, [], "in-page links without a matching section")

    def test_nav_fits_on_one_line_on_phones(self):
        for path in ("/index.html", "/experience.html", "/newsletter.html", "/playbook.html", "/projects.html"):
            for width in (360, 390):
                with self.subTest(path=path, width=width):
                    pg = self.page(width, path=path)
                    m = pg.evaluate("""() => { const h = e => Math.round(e.getBoundingClientRect().height);
                        const brand = document.querySelector('.brand'), cta = document.querySelector('.nav-cta');
                        const lh = parseFloat(getComputedStyle(brand).lineHeight) || 30;
                        return { brand: h(brand), brandLine: lh, ctaRight: cta.getBoundingClientRect().right,
                                 ctaH: h(cta), overflow: document.documentElement.scrollWidth > innerWidth }; }""")
                    self.assertLess(m["brand"], m["brandLine"] * 1.5, "brand name wraps")
                    self.assertLess(m["ctaH"], 45, "'Get in touch' wraps")
                    self.assertLessEqual(m["ctaRight"], width, "CTA off-screen")
                    self.assertFalse(m["overflow"], "horizontal overflow")


if __name__ == "__main__":
    unittest.main()
