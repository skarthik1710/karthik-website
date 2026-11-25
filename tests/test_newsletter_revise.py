"""Run: python3 -m unittest discover -s tests   (no credentials needed)"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "functions-python"))
import newsletter_content as nc  # noqa: E402
import newsletter_revise as rv   # noqa: E402

ART = {"type": "article", "title": "T", "takeaway": "tk", "excerpt": "ex", "action": "ac",
       "body": " ".join(["word"] * 400), "news_sources": [{"title": "S", "url": "https://s", "source": "s.com"}],
       "status": "pending_review", "issue_id": "2026-11-27"}
LINKS = {"type": "links", "items": [{"title": "A", "url": "https://a", "source": "a", "take": "old"},
                                    {"title": "B", "url": "https://b", "source": "b", "take": "old2"}]}


class Selection(unittest.TestCase):
    def test_item_notes_win(self):
        self.assertEqual(rv.items_to_revise(["a", "b", "c"], {"b": "fix"}, "overall"), ["b"])

    def test_overall_only_revises_all(self):
        self.assertEqual(rv.items_to_revise(["a", "b"], {}, "tone down"), ["a", "b"])

    def test_nothing(self):
        self.assertEqual(rv.items_to_revise(["a"], {"a": "  "}, " "), [])


class ParseRevision(unittest.TestCase):
    def test_article_merge_keeps_sources(self):
        out = json.dumps({"revised": {"title": "New", "takeaway": "t2", "excerpt": "e2", "action": "a2",
                                      "body": " ".join(["new"] * 300)}, "changes": "shorter"})
        merged, changes = rv.parse_revision(out, "article", ART)
        self.assertEqual(merged["title"], "New")
        self.assertEqual(merged["news_sources"], ART["news_sources"])
        self.assertEqual(merged["status"], "pending_review")
        self.assertEqual(changes, "shorter")

    def test_emptied_field_rejected(self):
        out = json.dumps({"revised": {"title": "", "takeaway": "t", "excerpt": "e", "action": "a", "body": "b " * 300}})
        with self.assertRaises(ValueError):
            rv.parse_revision(out, "article", ART)

    def test_short_body_rejected(self):
        out = json.dumps({"revised": {"title": "x", "takeaway": "t", "excerpt": "e", "action": "a", "body": "too short"}})
        with self.assertRaises(ValueError):
            rv.parse_revision(out, "article", ART)

    def test_links_keep_titles_and_urls(self):
        out = json.dumps({"revised": {"takes": [{"title": "HACKED", "take": "new1"}, {"title": "B", "take": "new2"}]}})
        merged, _ = rv.parse_revision(out, "links", LINKS)
        self.assertEqual([h["title"] for h in merged["items"]], ["A", "B"])
        self.assertEqual([h["url"] for h in merged["items"]], ["https://a", "https://b"])
        self.assertEqual([h["take"] for h in merged["items"]], ["new1", "new2"])

    def test_links_count_change_rejected(self):
        with self.assertRaises(ValueError):
            rv.parse_revision(json.dumps({"revised": {"takes": [{"take": "x"}]}}), "links", LINKS)

    def test_garbage_rejected(self):
        for t in ["", "nope", '{"changes": "x"}']:
            with self.assertRaises(ValueError):
                rv.parse_revision(t, "article", ART)

    def test_prompt_has_notes_and_draft(self):
        p = rv.build_revision_prompt("article", ART, "cut para 3", "less hype", "Nov 27, 2026")
        for s in ["cut para 3", "less hype", "https://s", '"title": "T"']:
            self.assertIn(s, p)


class ReviewEmail(unittest.TestCase):
    def rows(self):
        rev = {"fact_checker": {"verdict": "pass", "claims": [], "model": "m"}, "editor": {"verdict": "pass", "claims": [], "model": "m"}}
        return [{"id": "A1", "kind": "article", "record": ART, "reviews": rev, "decision": "clean", "reason": "ok",
                 "note": "cut <b>", "changes": "cut it"},
                {"id": "B2", "kind": "links", "record": LINKS, "reviews": {}, "decision": "kept", "reason": ""}]

    def test_buttons_and_version(self):
        subj, html = nc.build_review_email("2026-11-27", "Nov 27, 2026", self.rows(), version=2, overall_note="less hype")
        self.assertTrue(subj.startswith("[Review v2]"))
        for intent in ["approve", "changes", "reject"]:
            self.assertIn(f"/admin/?issue=2026-11-27&intent={intent}", html)
        self.assertIn("cut &lt;b&gt;", html)          # notes are escaped
        self.assertIn("What changed:", html)
        self.assertIn("Unchanged in this version", html)

    def test_v1_subject(self):
        subj, _ = nc.build_review_email("2026-11-27", "d", self.rows()[:1])
        self.assertTrue(subj.startswith("[Review] "))


if __name__ == "__main__":
    unittest.main()
