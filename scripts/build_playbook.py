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


PB_CSS = r"""
        /* ── PROGRESSIVE DISCLOSURE ── */
        .pb-progress { position: fixed; top: 0; left: 0; right: 0; height: 2px; z-index: 120; pointer-events: none; }
        .pb-progress i { display: block; height: 100%; width: 100%; transform-origin: 0 50%; transform: scaleX(var(--p, 0));
            background: linear-gradient(90deg, rgba(255,107,53,0.35), var(--accent) 70%, #FFB08F);
            box-shadow: 0 0 10px rgba(255,107,53,0.7); }
        .pb-hero { position: relative; overflow: hidden; }
        .pb-hero .wrap { position: relative; z-index: 1; }
        .pb-hero::after { content: ""; position: absolute; inset: auto 0 0 0; height: 40%; pointer-events: none;
            background: linear-gradient(transparent, var(--bg)); z-index: 0; }

        .pb-glance { padding: 3.2rem 0 3.4rem; border-bottom: 1px solid var(--line);
            background: radial-gradient(900px 340px at 85% 0%, rgba(255,107,53,0.07), transparent 70%); }
        .pb-glance-top { display: flex; justify-content: space-between; align-items: flex-end; gap: 2rem; flex-wrap: wrap; margin-bottom: 2rem; }
        .pb-kicker { font-family: var(--font-mono); font-size: 0.72rem; letter-spacing: 0.16em; text-transform: uppercase; color: var(--accent);
            display: flex; align-items: center; gap: 0.6rem; }
        .pb-kicker::before { content: ""; width: 22px; height: 1px; background: var(--accent); }
        .pb-glance-h { font-family: var(--font-display); color: var(--text); font-size: clamp(1.45rem, 2.6vw, 2rem); letter-spacing: -0.02em;
            line-height: 1.2; margin: 0.7rem 0 0.6rem; }
        .pb-glance-p { color: var(--muted); max-width: 40em; font-size: 0.95rem; line-height: 1.7; }
        .pb-tools { display: flex; flex-direction: column; align-items: flex-end; gap: 0.7rem; }
        .pb-meter { display: flex; align-items: center; gap: 0.7rem; font-family: var(--font-mono); font-size: 0.72rem; color: var(--dim); letter-spacing: 0.04em; }
        .pb-meter b { color: var(--accent); font-weight: 600; }
        .pb-meter-bar { position: relative; width: 120px; height: 4px; border-radius: 4px; background: var(--line); overflow: hidden; }
        .pb-meter-bar i { position: absolute; inset: 0; transform-origin: 0 50%; transform: scaleX(var(--e, 0)); background: var(--accent);
            box-shadow: 0 0 8px rgba(255,107,53,0.8); transition: transform 0.5s cubic-bezier(.2,.7,.2,1); }
        .pb-seg, .pb-toc-tools { display: inline-flex; border: 1px solid var(--line-strong); border-radius: 999px; overflow: hidden; background: var(--surface); }
        .pb-seg button, .pb-toc-tools button { font: 500 0.78rem var(--font-body); color: var(--muted); background: none; border: none; cursor: pointer;
            padding: 0.5rem 0.95rem; transition: color 0.15s, background 0.15s; }
        .pb-seg button + button, .pb-toc-tools button + button { border-left: 1px solid var(--line-strong); }
        .pb-seg button:hover, .pb-toc-tools button:hover { color: var(--text); background: var(--surface-2); }
        .pb-seg button:focus-visible, .pb-toc-tools button:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
        .pb-toc-tools { margin-bottom: 1.1rem; }
        .pb-toc-tools button { font-size: 0.72rem; padding: 0.38rem 0.7rem; }

        .pb-groups { display: flex; flex-direction: column; gap: 1.1rem; }
        .pb-group { display: grid; grid-template-columns: 150px minmax(0, 1fr); gap: 1.2rem; align-items: start; }
        .pb-group-l { position: sticky; top: 90px; display: flex; flex-direction: column; gap: 0.2rem; padding-top: 0.9rem;
            border-top: 1px solid var(--accent-dim); }
        .pb-group-n { font-family: var(--font-mono); font-size: 0.68rem; color: var(--accent); letter-spacing: 0.08em; }
        .pb-group-t { font-family: var(--font-display); font-size: 0.98rem; font-weight: 600; color: var(--text); }
        .pb-cards { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.75rem; }
        /* A lone card on the last row stretches across it rather than leaving a hole */
        .pb-cards > .pb-card:last-child:nth-child(3n+1) { grid-column: 1 / -1; }
        .pb-cards > .pb-card:last-child:nth-child(3n+2) { grid-column: span 2; }
        .pb-card { display: flex; flex-direction: column; gap: 0.45rem; padding: 1rem 1.05rem 0.95rem; border-radius: 12px; text-decoration: none;
            border: 1px solid var(--line); background: linear-gradient(180deg, var(--surface-2), var(--surface));
            transition: border-color 0.25s, transform 0.25s, box-shadow 0.25s; }
        .pb-card:hover, .pb-card:focus-visible { border-color: var(--accent-dim); transform: translateY(-2px);
            box-shadow: 0 10px 30px -12px rgba(255,107,53,0.35); outline: none; }
        .pb-card-top { display: flex; justify-content: space-between; align-items: center; }
        .pb-card-n { font-family: var(--font-mono); font-size: 0.78rem; font-weight: 600; color: var(--accent); letter-spacing: 0.06em; }
        .pb-card-seen { font-family: var(--font-mono); font-size: 0.6rem; letter-spacing: 0.12em; text-transform: uppercase; color: #6CCF9C;
            opacity: 0; transition: opacity 0.3s; }
        .pb-card-seen::before { content: "● "; }
        .pb-card.is-visited .pb-card-seen { opacity: 1; }
        .pb-card-t { font-family: var(--font-display); font-size: 1rem; font-weight: 600; color: var(--text); line-height: 1.3; }
        .pb-card-b { font-size: 0.8rem; line-height: 1.5; color: var(--muted); flex: 1; }
        .pb-card-go { font-family: var(--font-mono); font-size: 0.66rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--dim);
            transition: color 0.2s, letter-spacing 0.25s; }
        .pb-card:hover .pb-card-go { color: var(--accent); letter-spacing: 0.12em; }

        /* Sections: collapsed to a summary card, full text on demand */
        .pb-intro > * + * { margin-top: 1.05em; }
        .prose .pb-sec { margin-top: 1.4rem; position: relative; border: 1px solid var(--line); border-radius: 14px; background: var(--surface);
            transition: border-color 0.3s, box-shadow 0.3s; }
        .prose .pb-intro + .pb-sec { margin-top: 2.4rem; }
        .pb-sec::before { content: ""; position: absolute; left: -1px; top: 18px; bottom: 18px; width: 2px; border-radius: 2px;
            background: var(--accent); opacity: 0; box-shadow: 0 0 12px 1px rgba(255,107,53,0.7); transition: opacity 0.3s; }
        .pb-sec.is-open { border-color: var(--line-strong); box-shadow: 0 0 0 1px rgba(255,107,53,0.08), 0 24px 60px -30px rgba(255,107,53,0.25); }
        .pb-sec.is-open::before, .pb-sec.pb-flash::before { opacity: 1; }
        .pb-sec.pb-flash, .pb-sub.pb-flash { animation: pbFlash 1.6s ease-out; }
        @keyframes pbFlash { 0% { box-shadow: 0 0 0 1px var(--accent), 0 0 40px -6px rgba(255,107,53,0.55); } 100% { box-shadow: 0 0 0 1px transparent, 0 0 0 0 transparent; } }
        .pb-head { padding: 1.4rem 1.6rem 1.3rem; cursor: pointer; }
        .pb-sec.is-open .pb-head { cursor: default; }
        .prose .pb-head h2 { margin: 0; padding: 0; border: none; font-size: 1.45rem; display: flex; gap: 0.7rem; align-items: baseline; }
        .pb-head h2 .pb-n, .pb-sub-toggle .pb-n { font-family: var(--font-mono); color: var(--accent); font-weight: 600; font-size: 0.72em;
            letter-spacing: 0.04em; flex: none; }
        .prose .pb-summary { margin-top: 0.85rem; }
        .prose .pb-summary-l { font-family: var(--font-mono); font-size: 0.66rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--dim); margin-bottom: 0.45rem; }
        .prose .pb-takeaways { list-style: none; padding-left: 0; font-size: 0.93rem; line-height: 1.6; }
        .prose .pb-takeaways li { position: relative; padding-left: 1.2rem; color: var(--text); opacity: 0.88; }
        .prose .pb-takeaways li + li { margin-top: 0.4rem; }
        .pb-takeaways li::before { content: ""; position: absolute; left: 0.1rem; top: 0.62em; width: 6px; height: 6px; border-radius: 50%;
            background: var(--accent); box-shadow: 0 0 8px rgba(255,107,53,0.8); }
        .prose .pb-lede { font-size: 0.93rem; color: var(--muted); margin: 0; }
        .pb-toggle, .pb-collapse { display: inline-flex; align-items: center; gap: 0.5rem; margin-top: 1.05rem; cursor: pointer;
            font: 600 0.82rem var(--font-body); color: var(--accent); background: var(--accent-faint); border: 1px solid var(--accent-dim);
            border-radius: 999px; padding: 0.5rem 1rem; transition: background 0.2s, box-shadow 0.2s, color 0.2s; }
        .pb-toggle:hover, .pb-collapse:hover { background: rgba(255,107,53,0.16); box-shadow: 0 0 18px -4px rgba(255,107,53,0.6); color: #FFB08F; }
        .pb-toggle:focus-visible, .pb-collapse:focus-visible, .pb-sub-toggle:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
        .pb-chev { display: inline-block; transition: transform 0.35s cubic-bezier(.2,.7,.2,1); }
        .pb-toggle[aria-expanded="true"] .pb-chev { transform: rotate(180deg); }
        .pb-toggle[aria-expanded="true"] { background: transparent; border-color: var(--line-strong); color: var(--muted); }
        .pb-body { overflow: clip; }
        .pb-sec > .pb-body > .pb-inner { padding: 0.2rem 1.6rem 1.6rem; border-top: 1px dashed var(--line); }
        .pb-sec > .pb-body > .pb-inner > :first-child { margin-top: 1.3rem; }
        .pb-inner > * + * { margin-top: 1.05em; }
        .pb-collapse { margin-top: 1.8rem; background: transparent; border-color: var(--line-strong); color: var(--muted); }
        .pb-sec.is-open > .pb-body > .pb-inner > * { animation: pbIn 0.55s cubic-bezier(.2,.7,.2,1) both; }
        .pb-sec.is-open > .pb-body > .pb-inner > :nth-child(2) { animation-delay: 0.05s; }
        .pb-sec.is-open > .pb-body > .pb-inner > :nth-child(3) { animation-delay: 0.1s; }
        .pb-sec.is-open > .pb-body > .pb-inner > :nth-child(n+4) { animation-delay: 0.15s; }
        @keyframes pbIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }

        /* Subsections: clickable rows */
        .prose .pb-sub { border: 1px solid var(--line); border-radius: 10px; background: var(--bg); transition: border-color 0.25s, box-shadow 0.25s; }
        .prose .pb-sub + .pb-sub { margin-top: 0.55rem; }
        .pb-sub:hover { border-color: var(--line-strong); }
        .pb-sub.is-open { border-color: var(--accent-dim); box-shadow: 0 0 24px -12px rgba(255,107,53,0.55); }
        .pb-sub-head { padding: 0.15rem 1rem 0.75rem; cursor: pointer; }
        .pb-sub.is-open .pb-sub-head { cursor: default; }
        .prose .pb-sub-head h3 { margin: 0; font-size: 1.02rem; }
        .pb-sub-toggle { all: unset; box-sizing: border-box; display: flex; align-items: baseline; gap: 0.6rem; width: 100%; cursor: pointer;
            padding: 0.7rem 0 0.15rem; color: var(--text); font: inherit; font-family: var(--font-display); font-weight: 600; }
        .pb-sub-t { flex: 1; }
        .pb-plus { position: relative; width: 12px; height: 12px; flex: none; align-self: center; }
        .pb-plus::before, .pb-plus::after { content: ""; position: absolute; left: 0; top: 5px; width: 12px; height: 2px; border-radius: 2px;
            background: var(--accent); transition: transform 0.3s cubic-bezier(.2,.7,.2,1); }
        .pb-plus::after { transform: rotate(90deg); }
        .pb-sub-toggle[aria-expanded="true"] .pb-plus::after { transform: rotate(0deg); }
        .prose .pb-sub-brief { margin: 0.1rem 0 0; font-size: 0.84rem; line-height: 1.5; color: var(--muted); }
        .pb-sub-body > .pb-inner { padding: 0.2rem 1rem 1.1rem; }
        .pb-sub-body > .pb-inner > :first-child { margin-top: 0.4rem; }
        .pb-toc li a.is-open::after { content: ""; display: inline-block; width: 5px; height: 5px; margin-left: 0.4rem; vertical-align: 0.15em;
            border-radius: 50%; background: var(--accent); box-shadow: 0 0 6px rgba(255,107,53,0.9); }

        @media (max-width: 1100px) and (min-width: 641px) {
            .pb-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .pb-cards > .pb-card:last-child:nth-child(3n+1), .pb-cards > .pb-card:last-child:nth-child(3n+2) { grid-column: auto; }
            .pb-cards > .pb-card:last-child:nth-child(2n+1) { grid-column: 1 / -1; }
        }
        @media (max-width: 960px) {
            .pb-group { grid-template-columns: minmax(0, 1fr); gap: 0.6rem; }
            .pb-group-l { position: static; flex-direction: row; align-items: baseline; gap: 0.6rem; padding-top: 0.7rem; }
            .pb-tools { align-items: flex-start; }
            .pb-toc-tools { margin-bottom: 0.8rem; }
        }
        @media (max-width: 640px) {
            .pb-glance { padding: 2.2rem 0 2.4rem; }
            .pb-cards { grid-template-columns: minmax(0, 1fr); gap: 0.5rem; }
            .pb-cards > .pb-card:last-child:nth-child(n) { grid-column: auto; }
            .pb-card { padding: 0.8rem 0.95rem; gap: 0.3rem; }
            .pb-card-b { font-size: 0.78rem; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
            .pb-card-go { display: none; }
            .pb-head { padding: 1.1rem 1.1rem 1.1rem; }
            .prose .pb-head h2 { font-size: 1.22rem; }
            .pb-sec > .pb-body > .pb-inner { padding: 0.2rem 1.1rem 1.3rem; }
            .pb-sub-head { padding: 0.1rem 0.85rem 0.7rem; }
            .pb-sub-body > .pb-inner { padding: 0.2rem 0.85rem 1rem; }
        }
        @media (prefers-reduced-motion: reduce) {
            .pb-card, .pb-chev, .pb-plus::before, .pb-plus::after, .pb-meter-bar i, .pb-sec, .pb-sub { transition: none; }
            .pb-card:hover { transform: none; }
            .pb-sec.is-open > .pb-body > .pb-inner > *, .pb-sec.pb-flash, .pb-sub.pb-flash { animation: none; }
        }
        @media print {
            .pb-progress, .pb-glance, .pb-toc, .pb-toggle, .pb-collapse, .pb-plus, canvas.fx-embers, #chat-launcher, #chat-pop { display: none !important; }
            .pb-body, .pb-body[hidden] { display: block !important; content-visibility: visible !important; height: auto !important; overflow: visible !important; }
            .pb-layout { display: block; }
            .prose .pb-sec, .prose .pb-sub { border: none; box-shadow: none; background: none; }
        }
"""

PB_JS = r"""
(function () {
    var doc = document, root = doc.documentElement;
    var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var bodies = [].slice.call(doc.querySelectorAll('.pb-body'));
    var secs = [].slice.call(doc.querySelectorAll('.pb-sec'));
    var visited = {};

    function host(body) { return body.parentElement; }  // .pb-sec or .pb-sub
    function isOpen(body) { return !body.hasAttribute('hidden'); }

    function sync(body) {
        var open = isOpen(body), h = host(body);
        doc.querySelectorAll('[aria-controls="' + body.id + '"]').forEach(function (b) {
            b.setAttribute('aria-expanded', open ? 'true' : 'false');
            var l = b.querySelector('.pb-tl');
            if (l && b.dataset.open) l.textContent = open ? b.dataset.close : b.dataset.open;
        });
        h.classList.toggle('is-open', open);
        if (h.classList.contains('pb-sec')) {
            var sid = h.getAttribute('data-sec');
            var t = doc.querySelector('.pb-toc a[href="#' + sid + '"]');
            if (t) t.classList.toggle('is-open', open);
            if (open && !visited[sid]) {
                visited[sid] = true;
                var c = doc.querySelector('.pb-card[data-card="' + sid + '"]');
                if (c) c.classList.add('is-visited');
            }
            meter();
        }
    }

    function meter() {
        var n = Object.keys(visited).length, total = secs.length;
        doc.querySelectorAll('[data-pb-count]').forEach(function (el) { el.textContent = n; });
        doc.querySelectorAll('[data-pb-bar]').forEach(function (el) { el.style.setProperty('--e', total ? n / total : 0); });
    }

    function afterTransition(el, fn) {
        var done = false;
        function f(e) {
            if (e && e.target !== el) return;
            if (done) return;
            done = true;
            el.removeEventListener('transitionend', f);
            fn();
        }
        el.addEventListener('transitionend', f);
        setTimeout(f, 700);
    }

    function open(body, animate) {
        if (isOpen(body)) { sync(body); return; }
        body.removeAttribute('hidden');
        sync(body);
        if (animate && !reduce) {
            var h = body.scrollHeight;
            body.style.height = '0px';
            void body.offsetHeight;
            body.style.transition = 'height .5s cubic-bezier(.2,.7,.2,1)';
            body.style.height = h + 'px';
            afterTransition(body, function () { body.style.height = ''; body.style.transition = ''; });
        }
    }

    function close(body, animate) {
        if (!isOpen(body)) { sync(body); return; }
        function fin() {
            body.setAttribute('hidden', 'until-found');
            body.style.height = ''; body.style.transition = '';
            sync(body);
        }
        if (animate && !reduce) {
            body.style.height = body.scrollHeight + 'px';
            void body.offsetHeight;
            body.style.transition = 'height .38s cubic-bezier(.4,0,.2,1)';
            body.style.height = '0px';
            host(body).classList.remove('is-open');
            afterTransition(body, fin);
        } else fin();
    }

    function toggle(body) { if (isOpen(body)) close(body, true); else open(body, true); }

    function flash(el) {
        if (!el) return;
        el.classList.remove('pb-flash'); void el.offsetWidth; el.classList.add('pb-flash');
        setTimeout(function () { el.classList.remove('pb-flash'); }, 1700);
    }

    // Open whatever contains the element with this id (plus the section/subsection it heads), then scroll to it.
    function reveal(id, scroll, smooth) {
        var el = id && doc.getElementById(id);
        if (!el) return false;
        var own = null;
        if (/^H[23]$/.test(el.tagName)) {
            var h = el.closest('.pb-sec, .pb-sub');
            if (h && (h.querySelector(':scope > .pb-head > h2') === el || h.querySelector(':scope > .pb-sub-head > h3') === el)) {
                own = h.querySelector(':scope > .pb-body');
            }
        }
        var chain = [], p = el.parentElement && el.parentElement.closest('.pb-body');
        while (p) { chain.unshift(p); p = p.parentElement && p.parentElement.closest('.pb-body'); }
        if (own) chain.push(own);
        chain.forEach(function (b) { open(b, false); });
        if (scroll) {
            requestAnimationFrame(function () {
                el.scrollIntoView({ block: 'start', behavior: smooth && !reduce ? 'smooth' : 'instant' });
                flash(el.closest('.pb-sub') || el.closest('.pb-sec'));
            });
        }
        return true;
    }

    // Toggle buttons, collapsible heads, collapse-at-end, expand/collapse all
    doc.addEventListener('click', function (e) {
        var t = e.target;
        var btn = t.closest('.pb-toggle, .pb-sub-toggle');
        if (btn) { toggle(doc.getElementById(btn.getAttribute('aria-controls'))); return; }
        var c = t.closest('.pb-collapse');
        if (c) {
            var b = doc.getElementById(c.getAttribute('data-collapse'));
            var head = host(b).querySelector('h2');
            close(b, false);
            head.scrollIntoView({ block: 'start', behavior: 'instant' });
            return;
        }
        var all = t.closest('[data-pb-all]');
        if (all) {
            var anchorTop = all.getBoundingClientRect().top;
            var want = all.getAttribute('data-pb-all') === 'open';
            bodies.forEach(function (b) { want ? open(b, false) : close(b, false); });
            var shift = all.getBoundingClientRect().top - anchorTop;
            if (shift) window.scrollBy(0, shift);
            return;
        }
        // Clicking a collapsed head (not a link) opens it
        var hd = t.closest('.pb-head, .pb-sub-head');
        if (hd && !t.closest('a, button')) {
            var hb = host(hd).querySelector(':scope > .pb-body');
            if (hb && !isOpen(hb)) { open(hb, true); return; }
        }
        // In-page links (cards, contents, figure tiles, citations): open the target first
        var a = t.closest('a[href^="#"]');
        if (a && e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) {
            var id = decodeURIComponent(a.getAttribute('href').slice(1));
            if (id && doc.getElementById(id)) {
                e.preventDefault();
                if (location.hash !== '#' + id) history.pushState(null, '', '#' + id);
                reveal(id, true, true);
            }
        }
    });

    window.addEventListener('hashchange', function () { reveal(decodeURIComponent(location.hash.slice(1)), true, true); });
    // Find-in-page opens hidden="until-found" content itself; keep buttons and state in step.
    doc.addEventListener('beforematch', function (e) {
        var b = e.target.closest && e.target.closest('.pb-body');
        if (b) setTimeout(function () { sync(b); }, 0);
    }, true);
    window.addEventListener('beforeprint', function () { bodies.forEach(function (b) { open(b, false); }); });

    // Deep link on load (e.g. /playbook.html#secrets-and-identity from the Projects page)
    if (location.hash) {
        var hid = decodeURIComponent(location.hash.slice(1));
        if (reveal(hid, false)) {
            var flashed = false;
            var go = function () {
                var el = doc.getElementById(hid);
                if (!el) return;
                el.scrollIntoView({ block: 'start', behavior: 'instant' });
                if (!flashed) { flashed = true; flash(el.closest('.pb-sub') || el.closest('.pb-sec')); }
            };
            requestAnimationFrame(go);
            // Re-pin after web fonts and late layout settle (only if the reader hasn't scrolled away).
            window.addEventListener('load', function () {
                var el = doc.getElementById(hid);
                if (el && Math.abs(el.getBoundingClientRect().top - 84) < 400) go();
            });
        }
    }
    bodies.forEach(sync);

    // Reading progress bar
    var bar = doc.querySelector('.pb-progress');
    var ticking = false;
    function progress() {
        ticking = false;
        var max = root.scrollHeight - window.innerHeight;
        bar.style.setProperty('--p', max > 0 ? Math.min(1, window.scrollY / max) : 0);
    }
    window.addEventListener('scroll', function () { if (!ticking) { ticking = true; requestAnimationFrame(progress); } }, { passive: true });
    window.addEventListener('resize', progress);
    progress();

    // Contents: collapsed by default on small screens; highlight the section in view on wide ones.
    var toc = doc.querySelector('.pb-toc details');
    if (toc && window.matchMedia('(max-width: 960px)').matches) toc.removeAttribute('open');
    var links = doc.querySelectorAll('.pb-toc li a');
    if (!('IntersectionObserver' in window) || !links.length) return;
    var map = {};
    links.forEach(function (a) { map[a.getAttribute('href').slice(1)] = a; });
    var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
            var sid = en.target.getAttribute('data-sec');
            if (en.isIntersecting && map[sid]) {
                links.forEach(function (a) { a.classList.remove('on'); });
                map[sid].classList.add('on');
            }
        });
    }, { rootMargin: '-80px 0px -70% 0px' });
    secs.forEach(function (s) { io.observe(s); });
})();
"""


# "At a glance" grouping of the H2 sections, by section number.
GROUPS = [
    ("Foundations", 1, 3),
    ("Build it safely", 4, 7),
    ("Run it at scale", 8, 10),
    ("Get started", 11, 13),
    ("Reference", 14, 15),
]
HR_TAIL = r"\s*<hr\s*/?>\s*$"


def split_num(text):
    m = re.match(r"\s*(\d+(?:\.\d+)?)\.?\s+(.*)", text, re.S)
    return (m.group(1), m.group(2).strip()) if m else ("", text.strip())


def inline(text):
    return html.escape(text, quote=False)


def wrap_sub(chunk, briefs):
    """One ### subsection -> a collapsed row (title + one-line brief) with its body behind a toggle."""
    m = re.match(r'<h3 id="([^"]+)">(.*?)</h3>', chunk, re.S)
    hid, inner = m.group(1), m.group(2)
    rest = re.sub(HR_TAIL, "", chunk[m.end():])
    num, title = split_num(inner)
    b = briefs.get(hid)
    brief = f'\n<p class="pb-sub-brief">{inline(b)}</p>' if b else ""
    return f'''<div class="pb-sub" data-sub="{hid}">
<div class="pb-sub-head">
<h3 id="{hid}"><button type="button" class="pb-sub-toggle" aria-expanded="false" aria-controls="pb-b-{hid}"><span class="pb-n">{num}</span> <span class="pb-sub-t">{title}</span><span class="pb-plus" aria-hidden="true"></span></button></h3>{brief}
</div>
<div class="pb-body pb-sub-body" id="pb-b-{hid}" hidden="until-found"><div class="pb-inner">
{rest}
</div></div>
</div>
'''


def disclose(body, toc, briefs, takeaways):
    """Wrap each H2 section (and each H3 subsection) so it starts collapsed to its summary.

    Collapsed bodies use hidden="until-found": the browser's find-in-page still searches them and
    opens the match. Heading ids and their "N. Title" text are unchanged, because
    build_projects.py reads them to validate its playbook links.
    """
    parts = re.split(r'(?=<h2 id=")', body)
    intro, secs = re.sub(HR_TAIL, "", parts[0]), parts[1:]
    out = [f'<div class="pb-intro">\n{intro}\n</div>']
    for chunk in secs:
        chunk = re.sub(HR_TAIL, "", chunk)
        m = re.match(r'<h2 id="([^"]+)">(.*?)</h2>', chunk, re.S)
        sid, inner = m.group(1), m.group(2)
        rest = chunk[m.end():]
        num, title = split_num(inner)
        if '<h3 id="' in rest:
            sp = re.split(r'(?=<h3 id=")', rest)
            rest = sp[0] + "".join(wrap_sub(s, briefs) for s in sp[1:])
        tk = takeaways.get(sid)
        if tk:
            summary = ('<div class="pb-summary"><p class="pb-summary-l">Key takeaways</p><ul class="pb-takeaways">'
                       + "".join(f"<li>{inline(t)}</li>" for t in tk) + "</ul></div>")
        else:
            summary = f'<div class="pb-summary"><p class="pb-lede">{inline(briefs.get(sid, ""))}</p></div>'
        out.append(f'''<section class="pb-sec" data-sec="{sid}">
<div class="pb-head">
<h2 id="{sid}"><span class="pb-n">{num}.</span> {title}</h2>
{summary}
<button type="button" class="pb-toggle" aria-expanded="false" aria-controls="pb-b-{sid}" data-open="Read the full section" data-close="Collapse section"><span class="pb-tl">Read the full section</span><span class="pb-chev" aria-hidden="true">↓</span></button>
</div>
<div class="pb-body" id="pb-b-{sid}" hidden="until-found"><div class="pb-inner">
{rest}
<button type="button" class="pb-collapse" data-collapse="pb-b-{sid}">Collapse section <span aria-hidden="true">↑</span></button>
</div></div>
</section>
''')

    # At-a-glance cards, grouped
    nums = {}
    for sid, t in toc:
        n, title = split_num(t)
        nums[int(n)] = (sid, title)
    groups = []
    for name, lo, hi in GROUPS:
        cards = []
        for n in range(lo, hi + 1):
            if n not in nums:
                continue
            sid, title = nums[n]
            cards.append(f'''<a class="pb-card fx-spot" data-reveal href="#{sid}" data-card="{sid}">
<span class="pb-card-top"><span class="pb-card-n">{n:02d}</span><span class="pb-card-seen" aria-hidden="true">explored</span></span>
<span class="pb-card-t">{html.escape(title)}</span>
<span class="pb-card-b">{inline(briefs.get(sid, ""))}</span>
<span class="pb-card-go" aria-hidden="true">Open section →</span>
</a>''')
        groups.append(f'''<div class="pb-group">
<div class="pb-group-l"><span class="pb-group-n">{lo:02d}–{hi:02d}</span><span class="pb-group-t">{name}</span></div>
<div class="pb-cards" data-reveal-stagger="0.06">
{"".join(cards)}
</div>
</div>''')
    glance = "\n".join(groups)
    return "\n".join(out), glance


def main():
    md_text = open(SRC, encoding="utf-8").read()
    tpl = open(TEMPLATE, encoding="utf-8").read()

    # Title + italic byline live in the page hero, not the article body.
    md_text = re.sub(r"\A#\s+[^\n]+\n+\*[^\n]+\*\n+", "", md_text)
    # Per-section summaries: <!-- brief: ... --> and <!-- takeaways: a | b | c --> right under a ## or ### heading.
    # They drive the "at a glance" cards and the collapsed view, and never render raw.
    briefs, takeaways = {}, {}
    current = None
    kept = []
    for line in md_text.split("\n"):
        hm = re.match(r"#{2,3}\s+(.+)$", line)
        if hm:
            current = slug(hm.group(1))
        cm = re.match(r"\s*<!--\s*(brief|takeaways):\s*(.*?)\s*-->\s*$", line)
        if cm and current:
            if cm.group(1) == "brief":
                briefs[current] = cm.group(2)
            else:
                takeaways[current] = [t.strip() for t in cm.group(2).split("|") if t.strip()]
            continue
        kept.append(line)
    md_text = "\n".join(kept)
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

    body, glance_html = disclose(body, toc, briefs, takeaways)
    brief_words = sum(len(b.split()) for b in briefs.values()) + sum(len(t.split()) for v in takeaways.values() for t in v)
    brief_minutes = max(1, int(math.ceil(brief_words / 230.0)))

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
<html lang="en" data-season="monsoon">
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
    <style>
{PB_CSS}
    </style>
    <link rel="stylesheet" href="/chat.css?v={ASSET_VERSION}"/>
    <link rel="stylesheet" href="/fx.css"/>
    <link rel="stylesheet" href="/seasons.css?v=20261126s"/>
    <script src="/seasons.js?v=20261126s" defer></script>
    <noscript><style>.pb-body[hidden] {{ display: block !important; content-visibility: visible !important; }}
        .pb-toggle, .pb-collapse, .pb-tools, .pb-toc-tools, .pb-plus {{ display: none !important; }}</style></noscript>
    <script type="application/ld+json">
    {{"@context": "https://schema.org", "@type": "TechArticle", "headline": "{TITLE}",
      "description": "{DESCRIPTION}", "author": {{"@type": "Person", "name": "Karthikeyan Selvam",
      "url": "https://karthikeyanselvam.com/"}}, "datePublished": "2026-11-25", "url": "{URL}"}}
    </script>
</head>
<body>

<div class="pb-progress" aria-hidden="true"><i></i></div>

<!-- ── NAV ── -->
{nav}

<!-- ── PAGE HERO ── -->
<header class="page-hero pb-hero">
    <canvas class="fx-embers" aria-hidden="true"></canvas>
    <div class="wrap">
        <div class="kicker">Playbook · November 2026</div>
        <h1>Building enterprise agents that <span class="accent">survive production</span></h1>
        <p>A vendor-neutral guide for leaders and architects: a layered reference architecture, the production
        controls that matter, a crawl-walk-run path to scale, and a plain list of first-generation patterns to retire.</p>
        <div class="pb-meta"><span>By <b>Karthikeyan Selvam</b></span><span><b>~{minutes} min</b> full read</span><span><b>~{brief_minutes} min</b> in brief</span><span><b>{n_sources}</b> cited sources</span></div>
    </div>
</header>

<!-- ── AT A GLANCE ── -->
<section class="pb-glance" aria-label="Playbook at a glance">
    <div class="wrap">
        <div class="pb-glance-top">
            <div>
                <div class="pb-kicker">Playbook at a glance</div>
                <h2 class="pb-glance-h">{len(toc)} sections. Start with the one you need.</h2>
                <p class="pb-glance-p">Each card opens its section. Every section starts as a short summary, so you can skim the whole
                playbook in a few minutes and read the full text only where you want depth.</p>
            </div>
            <div class="pb-tools" role="group" aria-label="Reading controls">
                <div class="pb-meter"><span><b data-pb-count>0</b> / {len(toc)} explored</span><span class="pb-meter-bar"><i data-pb-bar></i></span></div>
                <div class="pb-seg"><button type="button" data-pb-all="open">Expand all</button><button type="button" data-pb-all="close">Collapse all</button></div>
            </div>
        </div>
        <div class="pb-groups">
{glance_html}
        </div>
    </div>
</section>

<!-- ── ARTICLE ── -->
<div class="pb-layout">
    <nav class="pb-toc" aria-label="Contents">
        <div class="pb-toc-tools" role="group" aria-label="Expand or collapse every section">
            <button type="button" data-pb-all="open">Expand all</button><button type="button" data-pb-all="close">Collapse all</button>
        </div>
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
            <a href="https://www.linkedin.com/in/skarthik1710/" target="_blank" rel="noopener">LinkedIn</a>.
            Or ask Skipper, my AI assistant, in the corner of this page.</p>
        </aside>
    </article>
</div>

{chat}
{footer}

<script>
{PB_JS}
</script>
<script src="/fx.js" defer></script>
<script src="/chat.js?v={ASSET_VERSION}"></script>
</body>
</html>
"""
    open(OUT, "w", encoding="utf-8").write(page)
    print(f"wrote {os.path.relpath(OUT, ROOT)}: {words} words, ~{minutes} min, {n_sources} sources, {len(toc)} sections")


if __name__ == "__main__":
    sys.exit(main())
