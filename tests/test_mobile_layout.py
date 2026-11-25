"""Mobile layout regressions for the public pages.

Run:  python3 -m unittest tests.test_mobile_layout -v
Needs Playwright + Chromium (skips otherwise). GSAP is allowed from cdnjs so
the homepage behaves like a real phone (the Act III bug only shows when GSAP
loads but its >=900px animation is off); if cdnjs is unreachable the GSAP-
dependent assertions are skipped rather than silently passing.
"""
import functools
import http.server
import os
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

    def beats(self, pg):
        return pg.evaluate("""() => [...document.querySelectorAll('#turn-stage .beat')].map(b => {
            const r = b.getBoundingClientRect();
            return { top: r.top + scrollY, bottom: r.bottom + scrollY, pos: getComputedStyle(b).position }; })""")

    def test_act3_beats_do_not_overlap_below_900px(self):
        for width in (360, 390, 820, 899):
            with self.subTest(width=width):
                pg = self.page(width)
                if not pg.evaluate("typeof gsap !== 'undefined'"):
                    self.skipTest("GSAP (cdnjs) unreachable — cannot reproduce the real-phone state")
                bs = self.beats(pg)
                self.assertEqual(len(bs), 4)
                for a, b in zip(bs, bs[1:]):
                    self.assertLessEqual(a["bottom"], b["top"] + 0.5, "Act III beats overlap")

    def test_act3_desktop_animation_unchanged(self):
        pg = self.page(1280, 900)
        if not pg.evaluate("typeof gsap !== 'undefined'"):
            self.skipTest("GSAP (cdnjs) unreachable")
        self.assertTrue(all(b["pos"] == "absolute" for b in self.beats(pg)),
                        "desktop beats should stay absolutely positioned for the pinned animation")
        self.assertTrue(pg.evaluate("!!document.querySelector('.pin-spacer #turn-stage')"),
                        "desktop Act III should still be pinned by ScrollTrigger")

    def test_playbook_has_no_horizontal_overflow(self):
        for width in (360, 390, 768):
            with self.subTest(width=width):
                pg = self.page(width, path="/playbook.html")
                self.assertFalse(pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
                missing = pg.evaluate("""() => [...document.querySelectorAll('a.cite')]
                    .map(a => a.getAttribute('href').slice(1)).filter(id => !document.getElementById(id))""")
                self.assertEqual(missing, [], "citation links without a matching source")

    def test_nav_fits_on_one_line_on_phones(self):
        for path in ("/index.html", "/experience.html", "/newsletter.html", "/playbook.html"):
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
