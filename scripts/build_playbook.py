#!/usr/bin/env python3
"""Build public/playbook.html from content/playbook.md.

The page reuses experience.html's design tokens, nav, Skipper chat markup and
footer so it stays visually consistent. Re-run after editing the Markdown:

    pip install --target /tmp/pylib markdown      # once
    PYTHONPATH=/tmp/pylib python3 scripts/build_playbook.py

Citations written as [12] become links to the numbered source list, tables are
wrapped for horizontal scrolling on phones, and an auto-generated table of
contents is built from the H2 headings.
"""
import html
import math
import os
import re
import sys

import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "content", "playbook.md")
TEMPLATE = os.path.join(ROOT, "public", "experience.html")
OUT = os.path.join(ROOT, "public", "playbook.html")

TITLE = "Building Enterprise Agents That Survive Production"
SHORT_TITLE = "Enterprise Agent Playbook"
DESCRIPTION = ("A vendor-neutral playbook for building and scaling enterprise AI agents: a layered reference "
               "architecture, the production controls that matter, evals, security, governance, delivery and cost, "
               "plus what to retire from first-generation agent patterns.")
URL = "https://karthikeyanselvam.com/playbook.html"
ASSET_VERSION = "20261125"


def between(s, start, end, include=True):
    i = s.index(start)
    j = s.index(end, i) + (len(end) if include else 0)
    return s[i:j]


def slug(text):
    t = re.sub(r"<[^>]+>", "", text)
    t = re.sub(r"^\d+(\.\d+)*\.?\s*", "", html.unescape(t))
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def main():
    md_text = open(SRC, encoding="utf-8").read()
    tpl = open(TEMPLATE, encoding="utf-8").read()

    # Title + italic byline live in the page hero, not the article body.
    md_text = re.sub(r"\A#\s+[^\n]+\n+\*[^\n]+\*\n+", "", md_text)
    words = len(re.sub(r"## 15\. Sources.*", "", md_text, flags=re.S).split())
    minutes = int(math.ceil(words / 230.0))
    n_sources = len(re.findall(r"^\d+\.\s", md_text.split("## 15. Sources")[-1], flags=re.M))

    body = markdown.markdown(md_text, extensions=["tables", "sane_lists"], output_format="html5")

    # H2 ids + TOC
    toc = []

    def h2(m):
        inner = m.group(1)
        sid = slug(inner)
        toc.append((sid, re.sub(r"<[^>]+>", "", inner)))
        return f'<h2 id="{sid}">{inner}</h2>'
    body = re.sub(r"<h2>(.*?)</h2>", h2, body)

    def h3(m):
        return f'<h3 id="{slug(m.group(1))}">{m.group(1)}</h3>'
    body = re.sub(r"<h3>(.*?)</h3>", h3, body)

    # Numbered source list: give each <li> an anchor
    src_h2 = re.search(r'<h2 id="sources">', body)
    if src_h2:
        head, tail = body[:src_h2.start()], body[src_h2.start():]
        m = re.search(r"<ol(?: start=\"(\d+)\")?>(.*?)</ol>", tail, flags=re.S)
        if m:
            start = int(m.group(1) or 1)
            counter = [start - 1]

            def li(_m):
                counter[0] += 1
                return f'<li id="src-{counter[0]}">'
            ol = '<ol class="sources">' + re.sub(r"<li>", li, m.group(2)) + "</ol>"
            tail = tail[:m.start()] + ol + tail[m.end():]
        body = head + tail

    # Inline citations [n] -> links (not markdown links, which are already <a>)
    body = re.sub(r"\[(\d{1,3})\](?!\()", r'<a class="cite" href="#src-\1" aria-label="Source \1">[\1]</a>', body)
    # External links open in a new tab
    body = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" target="_blank" rel="noopener"', body)
    # Bare URLs inside the source list become links
    body = re.sub(r'(?<!href=")(?<!">)(https?://[^\s<]+[^\s<.,;)])',
                  r'<a href="\1" target="_blank" rel="noopener">\1</a>', body)
    # Scrollable tables
    body = body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")

    style = between(tpl, "<style>", "</style>")
    nav = between(tpl, '<nav class="nav">', "</nav>")
    nav = nav.replace(' class="active"', "").replace(
        '<a href="/playbook.html">Playbook</a>', '<a href="/playbook.html" class="active">Playbook</a>')
    chat = between(tpl, "<!-- ── CHAT LAUNCHER + POPOVER ── -->", "<!-- ── FOOTER ── -->", include=False)
    footer = between(tpl, "<!-- ── FOOTER ── -->", "</footer>")
    head_links = between(tpl, '<link rel="icon"', "</style>", include=False)  # favicon + fonts
    head_links = head_links[:head_links.index("<style>")] if "<style>" in head_links else head_links

    toc_html = "\n".join(f'<li><a href="#{sid}">{html.escape(t)}</a></li>' for sid, t in toc)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>{SHORT_TITLE} — Karthikeyan Selvam</title>
    <meta name="description" content="{html.escape(DESCRIPTION)}"/>
    <link rel="canonical" href="{URL}"/>
    <meta property="og:title" content="{TITLE} — a 2026 playbook"/>
    <meta property="og:description" content="{html.escape(DESCRIPTION)}"/>
    <meta property="og:image" content="https://karthikeyanselvam.com/og-image.png"/>
    <meta property="og:url" content="{URL}"/>
    <meta property="og:type" content="article"/>
    <meta name="twitter:card" content="summary_large_image"/>
    {head_links.strip()}
    {style}
    <style>
        /* ── PLAYBOOK (long-form article) ── */
        .pb-meta {{ display: flex; flex-wrap: wrap; gap: 0.5rem 1.4rem; margin-top: 1.4rem;
            font-family: var(--font-mono); font-size: 0.74rem; color: var(--dim); letter-spacing: 0.03em; }}
        .pb-meta b {{ color: var(--muted); font-weight: 500; }}
        .pb-layout {{ max-width: var(--w); margin: 0 auto; padding: 3rem 2rem 5rem;
            display: grid; grid-template-columns: 250px minmax(0, 1fr); gap: 3.5rem; align-items: start; }}
        .pb-layout > * {{ min-width: 0; }}
        .pb-toc {{ position: sticky; top: 84px; max-height: calc(100vh - 110px); overflow-y: auto;
            border-left: 1px solid var(--line); padding-left: 1.1rem; }}
        .pb-toc h2 {{ font-family: var(--font-mono); font-size: 0.68rem; letter-spacing: 0.12em; text-transform: uppercase;
            color: var(--dim); margin-bottom: 0.8rem; font-weight: 500; }}
        .pb-toc ol {{ list-style: none; }}
        .pb-toc li a {{ display: block; padding: 0.3rem 0; font-size: 0.82rem; line-height: 1.4; color: var(--muted);
            text-decoration: none; transition: color 0.15s; }}
        .pb-toc li a:hover, .pb-toc li a.on {{ color: var(--accent); }}
        .prose {{ max-width: 760px; color: var(--muted); font-size: 1rem; line-height: 1.8; }}
        .prose > * + * {{ margin-top: 1.05em; }}
        .prose h2 {{ font-family: var(--font-display); color: var(--text); font-size: 1.65rem; line-height: 1.25;
            letter-spacing: -0.02em; margin-top: 2.6em; padding-top: 1.4em; border-top: 1px solid var(--line); scroll-margin-top: 84px; }}
        .prose h3 {{ font-family: var(--font-display); color: var(--text); font-size: 1.15rem; margin-top: 1.9em; scroll-margin-top: 84px; }}
        .prose strong {{ color: var(--text); font-weight: 600; }}
        .prose a {{ color: var(--accent); text-underline-offset: 2px; overflow-wrap: anywhere; }}
        .prose a.cite {{ font-family: var(--font-mono); font-size: 0.72em; text-decoration: none; vertical-align: 0.15em;
            color: var(--accent); opacity: 0.85; margin-left: 0.05em; }}
        .prose a.cite:hover {{ opacity: 1; text-decoration: underline; }}
        .prose ul, .prose ol {{ padding-left: 1.3em; }}
        .prose li + li {{ margin-top: 0.4em; }}
        .prose hr {{ border: none; border-top: 1px solid var(--line); margin: 2.4em 0; }}
        .prose hr + h2 {{ border-top: none; padding-top: 0; margin-top: 0; }}
        .prose code {{ font-family: var(--font-mono); font-size: 0.86em; background: var(--surface-2);
            border: 1px solid var(--line); border-radius: 4px; padding: 0.05em 0.35em; }}
        .prose blockquote {{ border-left: 2px solid var(--accent); padding-left: 1rem; color: var(--text); }}
        .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); }}
        .prose table {{ width: 100%; border-collapse: collapse; font-size: 0.86rem; line-height: 1.55; }}
        .prose th, .prose td {{ text-align: left; vertical-align: top; padding: 0.7rem 0.9rem; border-bottom: 1px solid var(--line); }}
        .prose th {{ color: var(--text); font-family: var(--font-display); font-weight: 600; background: var(--surface-2); }}
        .prose tr:last-child td {{ border-bottom: none; }}
        .prose ol.sources {{ font-size: 0.82rem; line-height: 1.6; }}
        .prose ol.sources li {{ scroll-margin-top: 90px; }}
        .prose ol.sources li:target {{ background: var(--accent-faint); outline: 1px solid var(--accent-dim); border-radius: 4px; }}
        .pb-cta {{ margin-top: 3rem; padding: 1.6rem 1.8rem; border: 1px solid var(--line); border-radius: 12px; background: var(--surface); }}
        .pb-cta h2 {{ border: none; padding: 0; margin: 0 0 0.5rem; font-size: 1.2rem; }}
        @media (max-width: 960px) {{
            .pb-layout {{ grid-template-columns: minmax(0, 1fr); gap: 1.6rem; padding: 2rem 1.25rem 4rem; }}
            .pb-toc {{ position: static; max-height: none; border-left: none; padding-left: 0;
                border: 1px solid var(--line); border-radius: 10px; padding: 1rem 1.1rem; background: var(--surface); }}
            .pb-toc details summary {{ cursor: pointer; font-family: var(--font-mono); font-size: 0.72rem;
                letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); }}
            .pb-toc details[open] summary {{ margin-bottom: 0.6rem; }}
            .prose {{ font-size: 0.97rem; }}
            .prose table {{ min-width: 560px; }}  /* readable columns; the frame scrolls sideways */
            .prose h2 {{ font-size: 1.4rem; }}
        }}
    </style>
    <link rel="stylesheet" href="/chat.css?v={ASSET_VERSION}"/>
    <script type="application/ld+json">
    {{"@context": "https://schema.org", "@type": "TechArticle", "headline": "{TITLE}",
      "description": "{DESCRIPTION}", "author": {{"@type": "Person", "name": "Karthikeyan Selvam",
      "url": "https://karthikeyanselvam.com/"}}, "datePublished": "2026-11-25", "url": "{URL}"}}
    </script>
</head>
<body>

<!-- ── NAV ── -->
{nav}

<!-- ── PAGE HERO ── -->
<header class="page-hero">
    <div class="wrap">
        <div class="kicker">Playbook · November 2026</div>
        <h1>Building enterprise agents that <span class="accent">survive production</span></h1>
        <p>A vendor-neutral guide for leaders and architects: a layered reference architecture, the production
        controls that matter, a crawl-walk-run path to scale, and a plain list of first-generation patterns to retire.</p>
        <div class="pb-meta"><span>By <b>Karthikeyan Selvam</b></span><span><b>~{minutes} min</b> read</span><span><b>{n_sources}</b> cited sources</span></div>
    </div>
</header>

<!-- ── ARTICLE ── -->
<div class="pb-layout">
    <nav class="pb-toc" aria-label="Contents">
        <details open>
            <summary>Contents</summary>
            <ol>
{toc_html}
            </ol>
        </details>
    </nav>
    <article class="prose" id="playbook">
{body}
        <aside class="pb-cta">
            <h2>Building agents in your organisation?</h2>
            <p>I'm happy to compare notes on architecture, governance or getting a first agent to production —
            <a href="mailto:skarthik1710@gmail.com">email me</a> or connect on
            <a href="https://www.linkedin.com/in/karthikeyan-selvam-567b52157/" target="_blank" rel="noopener">LinkedIn</a>.
            Or ask Skipper, my AI assistant, in the corner of this page.</p>
        </aside>
    </article>
</div>

{chat}
{footer}

<script>
    // Collapse the contents list by default on small screens; highlight the current section on wide ones.
    (function () {{
        var toc = document.querySelector('.pb-toc details');
        if (toc && window.matchMedia('(max-width: 960px)').matches) toc.removeAttribute('open');
        var links = document.querySelectorAll('.pb-toc a');
        if (!('IntersectionObserver' in window) || !links.length) return;
        var map = {{}};
        links.forEach(function (a) {{ map[a.getAttribute('href').slice(1)] = a; }});
        var io = new IntersectionObserver(function (entries) {{
            entries.forEach(function (e) {{
                if (e.isIntersecting && map[e.target.id]) {{
                    links.forEach(function (a) {{ a.classList.remove('on'); }});
                    map[e.target.id].classList.add('on');
                }}
            }});
        }}, {{ rootMargin: '-80px 0px -70% 0px' }});
        document.querySelectorAll('.prose h2[id]').forEach(function (h) {{ io.observe(h); }});
    }})();
</script>
<script src="/chat.js?v={ASSET_VERSION}"></script>
</body>
</html>
"""
    open(OUT, "w", encoding="utf-8").write(page)
    print(f"wrote {os.path.relpath(OUT, ROOT)}: {words} words, ~{minutes} min, {n_sources} sources, {len(toc)} sections")


if __name__ == "__main__":
    sys.exit(main())
