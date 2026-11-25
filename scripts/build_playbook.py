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
    # Reading time counts prose only: figure labels (diagram text) and HTML tags are excluded.
    prose = re.sub(r"<figure\b.*?</figure>", " ", md_text, flags=re.S)
    prose = re.sub(r"<span class=\"chip[^\"]*\">[^<]*</span>|<p class=\"(?:callout-label|chip-legend)\">.*?</p>", " ", prose)
    prose = re.sub(r"<[^>]+>", " ", prose)
    words = len(re.sub(r"## 15\. Sources.*", "", prose, flags=re.S).split())
    minutes = int(math.ceil(words / 230.0))
    n_sources = len(re.findall(r"^\d+\.\s", md_text.split("## 15. Sources")[-1], flags=re.M))

    body = markdown.markdown(md_text, extensions=["tables", "sane_lists", "md_in_html"], output_format="html5")

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

        /* ── VISUAL CUES: figures, callouts, chips ── */
        .prose .pb-fig {{ margin: 1.7em 0; }}
        .pb-fig figcaption {{ margin-top: 0.7rem; font-size: 0.8rem; line-height: 1.55; color: var(--muted); }}
        .pb-fig ol {{ list-style: none; padding-left: 0; }}
        .pb-fig ol > li {{ margin-top: 0; }}
        .pb-fig-frame {{ border: 1px solid var(--line); border-radius: 12px; background: var(--surface); padding: 1rem; }}
        .cs-grid a:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
        /* Reference architecture (same visual language as the homepage diagram) */
        .pb-arch {{ display: block; width: 100%; height: auto; }}
        .pb-arch-tall {{ display: none; max-width: 460px; margin: 0 auto; }}  /* portrait variant for phones */
        .pb-arch .arch-node rect {{ fill: var(--surface-2); stroke: var(--line-strong); stroke-width: 1.2; }}
        .pb-arch .nlabel {{ fill: var(--text); font-family: var(--font-display); font-size: 14px; font-weight: 600; }}
        .pb-arch .nsub {{ fill: var(--muted); font-size: 11px; }}
        .pb-arch .arch-num {{ fill: var(--accent); font-family: var(--font-mono); font-size: 13px; font-weight: 600; }}
        .pb-arch .arch-plane rect {{ fill: rgba(255, 107, 53, 0.045); stroke: var(--accent); stroke-width: 1.1; stroke-dasharray: 7 5; }}
        .pb-arch .arch-plane-label {{ fill: var(--accent); font-family: var(--font-mono); font-size: 11.5px; font-weight: 600;
            letter-spacing: 1px; text-transform: uppercase; }}
        .pb-arch .arch-plane-sub {{ fill: var(--muted); font-family: var(--font-mono); font-size: 10.5px; }}
        .pb-arch .arch-edge {{ stroke: var(--line-strong); stroke-width: 1.5; fill: none; stroke-dasharray: 5 4; }}
        /* Production control stack */
        .cs-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.6rem; }}
        .cs-grid a {{ display: flex; flex-direction: column; gap: 0.2rem; height: 100%; padding: 0.85rem 0.95rem;
            border: 1px solid var(--line); border-radius: 10px; background: var(--surface); text-decoration: none;
            transition: border-color 0.15s, background 0.15s; }}
        .cs-grid a:hover {{ border-color: var(--accent-dim); background: var(--surface-2); }}
        .cs-n {{ font-family: var(--font-mono); font-size: 0.7rem; color: var(--accent); letter-spacing: 0.04em; }}
        .cs-t {{ font-family: var(--font-display); font-size: 0.95rem; font-weight: 600; color: var(--text); line-height: 1.3; }}
        .cs-d {{ font-size: 0.8rem; line-height: 1.45; color: var(--muted); }}
        /* Autonomy ladder */
        .al-wrap {{ border: 1px solid var(--line); border-radius: 12px; background: var(--surface); padding: 1.2rem 1.2rem 1rem; }}
        .al {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); grid-template-rows: auto auto; gap: 0.5rem 0.55rem; }}
        .al > li {{ display: grid; grid-row: span 2; grid-template-rows: subgrid; gap: 0.5rem; }}
        .al-bar {{ align-self: end; display: flex; flex-direction: column; justify-content: flex-end; gap: 0.1rem;
            height: calc(3.4rem + var(--lvl) * 1.4rem); padding: 0.55rem 0.65rem; border-radius: 8px 8px 4px 4px;
            border: 1px solid var(--accent-dim); background: rgba(255, 107, 53, calc(0.04 + var(--lvl) * 0.045)); }}
        .al-n {{ font-family: var(--font-mono); font-size: 0.7rem; font-weight: 600; color: #FFB08F; }}
        .al-t {{ font-family: var(--font-display); font-size: 0.92rem; font-weight: 600; color: var(--text); line-height: 1.2; }}
        .al-d {{ font-size: 0.76rem; line-height: 1.45; color: var(--muted); }}
        .al-axis {{ display: flex; justify-content: space-between; gap: 1rem; margin-top: 0.9rem; padding-top: 0.55rem;
            border-top: 2px solid; border-image: linear-gradient(90deg, var(--line-strong), var(--accent)) 1;
            font-family: var(--font-mono); font-size: 0.68rem; letter-spacing: 0.04em; color: var(--muted); }}
        /* Delivery pipeline */
        .pp {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.7rem 1.4rem; }}
        .pp-step {{ position: relative; display: flex; flex-direction: column; gap: 0.15rem; padding: 0.75rem 0.85rem;
            border: 1px solid var(--line); border-radius: 10px; background: var(--surface); }}
        .pp-step:not(:nth-child(4n)):not(:last-child)::after {{ content: "→" / ""; position: absolute; right: -1.15rem; top: 50%;
            transform: translateY(-50%); color: var(--accent); font-size: 0.95rem; line-height: 1; }}
        .pp-n {{ font-family: var(--font-mono); font-size: 0.68rem; color: var(--muted); }}
        .pp-t {{ font-family: var(--font-display); font-size: 0.93rem; font-weight: 600; color: var(--text); line-height: 1.3; }}
        .pp-g {{ font-size: 0.78rem; line-height: 1.45; color: var(--muted); }}
        .pp-step.is-gate {{ border-color: var(--accent); background: var(--accent-faint); }}
        .pp-step.is-gate .pp-g {{ color: var(--text); font-weight: 600; }}
        .pp-step.is-loop {{ border-style: dashed; border-color: var(--line-strong); }}
        /* Crawl / walk / run */
        .cwr {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1.4rem; counter-reset: cwr; }}
        .cwr > li {{ position: relative; display: flex; flex-direction: column; gap: 0.4rem; padding: 1rem 1.05rem 1.1rem;
            border: 1px solid var(--line); border-top: 3px solid var(--accent-dim); border-radius: 10px; background: var(--surface);
            counter-increment: cwr; }}
        .cwr > li:last-child {{ border-top-color: var(--accent); }}
        .cwr > li:not(:last-child)::after {{ content: "→" / ""; position: absolute; right: -1.15rem; top: 1.25rem;
            color: var(--accent); font-size: 0.95rem; line-height: 1; }}
        .cwr-k {{ font-family: var(--font-mono); font-size: 0.7rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; color: var(--accent); }}
        .cwr-k::before {{ content: "0" counter(cwr) " · "; color: var(--muted); font-weight: 500; }}
        .cwr-t {{ font-family: var(--font-display); font-size: 1.02rem; font-weight: 600; color: var(--text); line-height: 1.3; }}
        .cwr-lvl {{ align-self: flex-start; font-family: var(--font-mono); font-size: 0.68rem; line-height: 1.4; color: var(--text);
            background: var(--surface-2); border: 1px solid var(--line-strong); border-radius: 6px; padding: 0.2rem 0.45rem; }}
        .cwr-d {{ list-style: none; padding-left: 0 !important; font-size: 0.8rem; line-height: 1.5; color: var(--muted); }}
        .cwr-d li {{ position: relative; padding-left: 0.9rem; }}
        .prose .cwr-d li + li {{ margin-top: 0.25rem; }}
        .cwr-d li::before {{ content: "" / ""; position: absolute; left: 0; top: 0.62em; width: 4px; height: 4px; border-radius: 50%; background: var(--accent-dim); }}
        /* Callouts */
        .callout {{ border: 1px solid var(--line); border-left: 3px solid var(--accent); border-radius: 10px;
            background: var(--surface); padding: 0.95rem 1.15rem 1rem; }}
        .callout > * + * {{ margin-top: 0.55em; }}
        .prose .callout-label {{ display: flex; align-items: center; gap: 0.45rem; font-family: var(--font-mono); font-size: 0.68rem;
            font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: var(--accent); line-height: 1.4; }}
        .callout-label::before {{ content: "★" / ""; font-size: 0.8rem; letter-spacing: 0; }}
        .callout-retire {{ border-left-color: #F2837B; }}
        .callout-retire .callout-label {{ color: #F2837B; }}
        .callout-retire .callout-label::before {{ content: "✕" / ""; }}
        .callout-instead {{ border-left-color: #6CCF9C; }}
        .callout-instead .callout-label {{ color: #6CCF9C; }}
        .callout-instead .callout-label::before {{ content: "→" / ""; }}
        .callout-pair {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 0.7rem; }}
        .callout-pair > .callout {{ margin: 0; }}
        /* Status chips (What's outdated, what's new) */
        .chip {{ display: inline-block; font-family: var(--font-mono); font-size: 0.64rem; font-weight: 600; letter-spacing: 0.08em;
            text-transform: uppercase; line-height: 1.5; padding: 0.05em 0.55em; border: 1px solid; border-radius: 999px; white-space: nowrap; }}
        .chip-retire {{ color: #F2837B; background: rgba(242, 131, 123, 0.1); border-color: rgba(242, 131, 123, 0.4); }}
        .chip-update {{ color: #EDC06D; background: rgba(237, 192, 109, 0.1); border-color: rgba(237, 192, 109, 0.4); }}
        .chip-new {{ color: #6CCF9C; background: rgba(108, 207, 156, 0.1); border-color: rgba(108, 207, 156, 0.4); }}
        .prose td .chip {{ display: block; width: max-content; margin-bottom: 0.35rem; }}
        .prose th .chip {{ margin-left: 0.4rem; vertical-align: 0.12em; }}
        .prose .chip-legend {{ display: flex; flex-wrap: wrap; gap: 0.45rem 1.2rem; font-size: 0.8rem; color: var(--muted); }}
        .chip-legend .chip {{ margin-right: 0.3rem; }}
        @media (prefers-reduced-motion: reduce) {{
            .cs-grid a {{ transition: none; }}
        }}
        @media (max-width: 760px) {{
            .cwr {{ grid-template-columns: minmax(0, 1fr); gap: 1.3rem; }}
            .cwr > li:not(:last-child)::after {{ content: "↓" / ""; right: auto; left: 1.2rem; top: auto; bottom: -1.2rem; }}
            .callout-pair {{ grid-template-columns: minmax(0, 1fr); }}
        }}
        @media (max-width: 640px) {{
            .pb-arch-wide {{ display: none; }}
            .pb-arch-tall {{ display: block; }}
            .pb-fig-frame {{ padding: 0.6rem; }}
            .cs-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .pp {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .pp .pp-step:nth-child(even)::after {{ content: none; }}  /* arrows only between the two columns */
            .al-axis {{ flex-direction: column; gap: 0.15rem; }}
            .al-wrap {{ padding: 1rem; }}
            .al {{ grid-template-columns: minmax(0, 1fr); grid-template-rows: none; gap: 0.7rem; }}
            .al > li {{ display: flex; flex-direction: column; grid-row: auto; gap: 0.25rem; }}
            .al-bar {{ align-self: flex-start; flex-direction: row; align-items: baseline; justify-content: flex-start; gap: 0.55rem; height: auto;
                width: calc(40% + var(--lvl) * 12%); border-radius: 4px 8px 8px 4px; }}
        }}
        @media (max-width: 420px) {{
            .cs-grid {{ grid-template-columns: minmax(0, 1fr); gap: 0.45rem; }}
            .cs-grid a {{ display: grid; grid-template-columns: 2.1rem minmax(0, 1fr); align-items: baseline; row-gap: 0.15rem; padding: 0.65rem 0.85rem; }}
            .cs-d {{ grid-column: 2; }}
        }}
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
