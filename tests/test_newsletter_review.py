"""Run: python3 -m unittest discover -s tests   (no credentials needed)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import newsletter_review as nr  # noqa: E402


class ParseReviewJson(unittest.TestCase):
    def test_fenced_json(self):
        r = nr.parse_review_json('Here you go:\n```json\n{"verdict":"pass","summary":"ok","claims":[]}\n```')
        self.assertEqual(r["verdict"], "pass")
        self.assertEqual(r["error"], "")

    def test_bare_json_with_prose(self):
        r = nr.parse_review_json('Sure. {"verdict":"revise","claims":[]} Thanks')
        self.assertEqual(r["verdict"], "revise")

    def test_garbage_is_error_not_pass(self):
        for text in ["", "no json here", "{not json}", "[1,2]"]:
            self.assertEqual(nr.parse_review_json(text)["verdict"], "error", text)

    def test_pass_with_bad_claim_is_downgraded(self):
        r = nr.parse_review_json('{"verdict":"pass","claims":[{"claim":"x","verdict":"unsupported"}]}')
        self.assertEqual(r["verdict"], "revise")

    def test_contradicted_or_confidential_forces_fail(self):
        for v in ["contradicted", "confidential"]:
            r = nr.parse_review_json('{"verdict":"pass","claims":[{"claim":"x","verdict":"%s"}]}' % v)
            self.assertEqual(r["verdict"], "fail", v)

    def test_unknown_claim_verdict_becomes_unsupported(self):
        r = nr.parse_review_json('{"verdict":"revise","claims":[{"claim":"x","verdict":"probably"}]}')
        self.assertEqual(r["claims"][0]["verdict"], "unsupported")

    def test_non_http_source_url_is_dropped(self):
        r = nr.parse_review_json(
            '{"verdict":"pass","claims":[{"claim":"x","verdict":"supported","source_url":"javascript:alert(1)"}]}')
        self.assertEqual(r["claims"][0]["source_url"], "")

    def test_missing_verdict_inferred(self):
        self.assertEqual(nr.parse_review_json('{"claims":[]}')["verdict"], "pass")
        self.assertEqual(nr.parse_review_json('{"claims":[{"claim":"x","verdict":"outdated"}]}')["verdict"], "revise")


class Decide(unittest.TestCase):
    def rv(self, fc, ed):
        return {"fact_checker": {"verdict": fc}, "editor": {"verdict": ed}}

    def test_both_fail_drops(self):
        self.assertEqual(nr.decide(self.rv("fail", "fail"))[0], "drop")

    def test_one_fail_flags_not_drops(self):
        self.assertEqual(nr.decide(self.rv("fail", "pass"))[0], "flag")

    def test_error_never_counts_as_pass(self):
        self.assertEqual(nr.decide(self.rv("pass", "error"))[0], "flag")
        self.assertEqual(nr.decide(self.rv("error", "error"))[0], "flag")

    def test_both_pass_clean(self):
        self.assertEqual(nr.decide(self.rv("pass", "pass"))[0], "clean")

    def test_revise_flags(self):
        self.assertEqual(nr.decide(self.rv("pass", "revise"))[0], "flag")


class Prompt(unittest.TestCase):
    def test_prompt_contains_draft_and_sources(self):
        item = {"type": "article", "title": "T", "body": "B body", "news_sources": [{"title": "S", "url": "https://x"}]}
        for key in nr.REVIEWERS:
            p = nr.build_review_prompt(key, item, "Nov 27, 2026")
            self.assertIn("B body", p)
            self.assertIn("https://x", p)
            self.assertIn("Nov 27, 2026", p)

    def test_extras_flatten(self):
        self.assertIn("take1", nr.item_to_text({"type": "links", "items": [{"title": "a", "source": "s", "take": "take1"}]}))
        self.assertIn("big claim", nr.item_to_text({"type": "hype_check", "claim": "big claim", "reality": "r"}))


if __name__ == "__main__":
    unittest.main()
