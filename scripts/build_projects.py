#!/usr/bin/env python3
"""Build public/projects.html from content/projects/.

    python3 scripts/build_projects.py

Inputs (all in content/projects/):
  template.html          page frame with <!--PROJECT_CARDS-->, <!--PROJECT_DETAILS-->, <!--PROJECT_STATS--> and
                         <!--PROJECT_COUNT--> markers
  projects.json          "order" (rank, best first), index labels, and specs for projects rendered here
  legacy-<id>.html       hand-built sections kept verbatim (only their "NN / MM" index is renumbered)

The page is progressive: a card grid first; a card opens the project in a dialog (deep-linkable by #id) showing
role, problem/what/value and the layers at a glance; layers expand to their components, and "Go deeper" toggles
reveal the detailed diagram with its numbered flow, the controls, human in the loop and the stack. Every section,
spec or legacy, is rendered as before and then split into those parts, and the build fails if any content would
fall outside them.

Each component or control with a "pb" anchor links to that Playbook section. Anchors are checked
against public/playbook.html so a renamed heading fails the build instead of shipping a dead link.
"""
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "content", "projects")
OUT = os.path.join(ROOT, "public", "projects.html")
PLAYBOOK = os.path.join(ROOT, "public", "playbook.html")

# Short labels already used on the page, keyed by playbook anchor.
SHORT = {
    "the-reference-architecture-layers-of-an-enterprise-agent": "Reference architecture",
    "build-principles": "Build principles",
    "the-production-control-stack": "Control stack",
    "resilience": "Resilience",
    "limits-and-budgets": "Limits and budgets",
    "audit": "Audit",
    "policy": "Policy",
    "kill-switch-preflight-and-dry-run": "Kill switch and dry-run",
    "health-and-telemetry": "Health and telemetry",
    "multi-tenancy": "Multi-tenancy",
    "secrets-and-identity": "Secrets and identity",
    "pii-and-dlp": "PII and DLP",
    "integration-and-interoperability": "Integration",
    "tool-design": "Tool design",
    "mcp-what-s-current": "MCP",
    "a2a-for-agent-to-agent-delegation": "A2A delegation",
    "gateway-and-registry": "Gateway and registry",
    "multi-agent-used-deliberately": "Multi-agent",
    "quality-evals-and-observability": "Evals and observability",
    "security-for-agents": "Security for agents",
    "governance-and-the-autonomy-ladder": "Autonomy ladder",
    "the-delivery-pipeline-commit-to-production": "Delivery pipeline",
    "scaling-and-cost": "Scaling and cost",
}

E = lambda s: html.escape(str(s), quote=True)


def playbook_sections():
    """anchor -> section number (e.g. '4.3'), read from the built playbook."""
    s = open(PLAYBOOK, encoding="utf-8").read()
    out = {}
    for m in re.finditer(r'<h[23][^>]* id="([^"]+)"[^>]*>(.*?)</h[23]>', s, re.S):
        text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        num = re.match(r"(\d+(?:\.\d+)?)\.?\s", text)
        if num:
            out[m.group(1)] = num.group(1)
    return out


SECS = playbook_sections()


def pb_label(anchor):
    if anchor not in SECS:
        sys.exit(f"build_projects: playbook anchor #{anchor} not found in public/playbook.html")
    return SECS[anchor], SHORT.get(anchor, anchor.replace("-", " ").capitalize())


def pb_link(anchor):
    n, t = pb_label(anchor)
    return (f'<a class="pb-link" href="/playbook.html#{anchor}">How to build this <span aria-hidden="true">→</span>'
            f'<span class="pb-sec">Playbook §{n} · {E(t)}</span></a>')


def wrap(text, width, max_lines):
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= width:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max(0, width - 1)].rstrip() + "…"
    return lines


# ── diagram ──────────────────────────────────────────────────────────────────────────────
W, BX, BW, PAD, GAP, NH, ROWGAP, LABEL_H, BAND_GAP, PER_ROW = 1000, 18, 964, 14, 16, 100, 14, 30, 34, 4


def step_ids(p):
    """component id -> list of (data-step, badge label) in flow order."""
    hits = {}
    for flow in p["flows"]:
        prefix = flow.get("prefix", "")
        for i, st in enumerate(flow["steps"], 1):
            key, lab = (f"{prefix.lower()}{i}", f"{prefix}{i}")
            for nid in st.get("nodes", []):
                hits.setdefault(nid, []).append((key, lab))
    return hits


def diagram(p):
    pid, hits = p["id"], step_ids(p)
    parts, y = [], 14
    known = {c["id"] for L in p["layers"] for c in L["components"]}
    for flow in p["flows"]:
        for st in flow["steps"]:
            for nid in st.get("nodes", []):
                if nid not in known:
                    sys.exit(f"build_projects: {pid}: flow step references unknown component '{nid}'")
    for li, layer in enumerate(p["layers"], 1):
        comps = layer["components"]
        rows = [comps[i:i + PER_ROW] for i in range(0, len(comps), PER_ROW)]
        band_h = LABEL_H + len(rows) * NH + (len(rows) - 1) * ROWGAP + PAD
        parts.append(f'<rect class="dg-band" x="{BX}" y="{y}" width="{BW}" height="{band_h}" rx="12"/>')
        parts.append(f'<text class="dg-layer" x="{BX + PAD}" y="{y + 21}"><tspan class="dg-layer-n">{li:02d}</tspan>  {E(layer["name"].upper())}</text>')
        for ri, row in enumerate(rows):
            n = len(row)
            nw = (BW - 2 * PAD - (n - 1) * GAP) / n
            ny = y + LABEL_H + ri * (NH + ROWGAP)
            for ci, c in enumerate(row):
                nx = BX + PAD + ci * (nw + GAP)
                name_lines = wrap(c["name"], int((nw - 24) / 7.1), 2)
                tech_lines = wrap(c.get("tech", ""), int((nw - 24) / 5.4), 2) if c.get("tech") else []
                inner = [f'<rect x="{nx:.1f}" y="{ny:.1f}" width="{nw:.1f}" height="{NH}" rx="9"/>']
                ty = ny + 24
                for ln in name_lines:
                    inner.append(f'<text class="dg-name" x="{nx + 12:.1f}" y="{ty:.1f}">{E(ln)}</text>')
                    ty += 16
                ty += 1
                for ln in tech_lines:
                    inner.append(f'<text class="dg-tech" x="{nx + 12:.1f}" y="{ty:.1f}">{E(ln)}</text>')
                    ty += 13
                if c.get("pb"):
                    num, t = pb_label(c["pb"])
                    inner.append(f'<text class="dg-pb" x="{nx + 12:.1f}" y="{ny + NH - 12:.1f}">↗ Playbook §{num}</text>')
                    parts.append(f'<a class="dg-node pb" href="/playbook.html#{c["pb"]}" aria-label="{E(c["name"])} — how to build this: playbook section {num}, {E(t)}">'
                                 f'<title>{E(c["name"])} — how to build this (Playbook §{num} {E(t)})</title>{"".join(inner)}</a>')
                else:
                    parts.append(f'<g class="dg-node"><title>{E(c["name"])}</title>{"".join(inner)}</g>')
                badges = hits.get(c["id"], [])[:6]
                for bi, (key, lab) in enumerate(badges):   # ascending, left to right, ending at the right edge
                    cx, cy = nx + nw - 14 - (len(badges) - 1 - bi) * 23, ny
                    parts.append(f'<g class="dg-badge node" data-step="{key}"><circle cx="{cx:.1f}" cy="{cy:.1f}" r="10"/><text x="{cx:.1f}" y="{cy + 0.5:.1f}">{E(lab)}</text></g>')
        y += band_h
        if li < len(p["layers"]):
            parts.append(f'<path class="dg-edge" d="M {W / 2:.1f} {y + 3} L {W / 2:.1f} {y + BAND_GAP - 5}" marker-end="url(#{pid}-arr)"/>')
            y += BAND_GAP
    h = y + 14
    names = ", ".join(L["name"] for L in p["layers"])
    ncomp = sum(len(L["components"]) for L in p["layers"])
    svg = (f'<svg class="dg" viewBox="0 0 {W} {h}" role="group" aria-labelledby="{pid}-dg-title {pid}-dg-desc">\n'
           f'<title id="{pid}-dg-title">{E(p["name"])}: layered architecture</title>\n'
           f'<desc id="{pid}-dg-desc">Layers from top to bottom: {E(names)}. Numbered badges on each component match the steps listed below the diagram. '
           f'Components outlined in orange link to the playbook section on how that part is built.</desc>\n'
           f'<defs><marker id="{pid}-arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
           f'<path d="M0 1 L9 5 L0 9 z" class="dg-arrow"/></marker></defs>\n' + "\n".join(parts) + "\n</svg>")
    return (f'<figure class="arch">\n<div class="arch-head"><span class="arch-dot" aria-hidden="true"></span><span>Architecture — layered view</span>'
            f'<span class="arch-stack">{len(p["layers"])} layers · {ncomp} components</span><span class="arch-swipe" aria-hidden="true">swipe →</span></div>\n'
            f'<div class="dg-scroll" tabindex="0" role="region" aria-label="{E(p["name"])} architecture diagram (scrolls sideways on small screens)">\n{svg}\n</div>\n'
            f'<figcaption class="arch-legend"><span><i class="lg-badge" aria-hidden="true">1</i> numbered badge = flow step</span>'
            f'<span><i class="lg-node pb" aria-hidden="true"></i> orange outline = opens its playbook section</span></figcaption>\n</figure>')


# ── section ──────────────────────────────────────────────────────────────────────────────
def section(p):
    pid = p["id"]
    chips = "".join(f'\n<span class="proj-chip">{E(c)}</span>' for c in p.get("chips", []))
    out = [f'<section class="proj" id="{pid}" aria-labelledby="{pid}-title">',
           f'<div class="proj-head">\n<div class="proj-meta"><span class="sec-idx">00 / 00</span>{chips}\n</div>',
           f'<h2 class="proj-title" id="{pid}-title">{E(p["name"])}</h2>',
           f'<p class="proj-tagline">{E(p["tagline"])}</p></div>']
    rel = p.get("related")
    rel_html = f'<p>{E(rel["text"])} <a class="inline-link" href="{E(rel["href"])}">{E(rel["label"])} →</a></p>' if rel else ""
    out.append(f'<div class="built-on"><h3>My role</h3><p>{E(p["role"])}</p>{rel_html}</div>')
    out.append('<div class="pwv">'
               f'\n<div class="pwv-card problem"><h3>Problem</h3><p>{E(p["problem"])}</p></div>'
               f'\n<div class="pwv-card what-it-does"><h3>What it does</h3><p>{E(p["what"])}</p></div>'
               f'\n<div class="pwv-card value"><h3>Value</h3><p>{E(p["value"])}</p></div>\n</div>')
    out.append(diagram(p))
    for flow in p["flows"]:
        prefix = flow.get("prefix", "")
        lis = []
        for i, st in enumerate(flow["steps"], 1):
            key, lab = f"{prefix.lower()}{i}", f"{prefix}{i}"
            lis.append(f'<li class="flow-step" data-step="{key}" tabindex="0"><span class="flow-n" aria-hidden="true">{E(lab)}</span>'
                       f'<span class="flow-txt"><span class="sr-only">Step {E(lab)}: </span>{E(st["text"])}</span></li>')
        out.append(f'<div class="block"><h3 class="block-title"><span class="bt-k">Flow</span>{E(flow["title"])}</h3>\n'
                   f'<ol class="flow" data-proj="{pid}">\n' + "\n".join(lis) + "\n</ol></div>")
    comp = ['<div class="block"><h3 class="block-title"><span class="bt-k">Components</span>What each part does</h3>']
    for li, layer in enumerate(p["layers"], 1):
        cards = []
        for c in layer["components"]:
            cls = "comp-card pb" if c.get("pb") else "comp-card"
            tech = f'<div class="comp-tech">{E(c["tech"])}</div>' if c.get("tech") else ""
            link = pb_link(c["pb"]) if c.get("pb") else ""
            cards.append(f'<div class="{cls}"><h4>{E(c["name"])}</h4><p>{E(c["role"])}</p>{tech}{link}</div>')
        comp.append(f'<div class="comp-layer"><div class="comp-layer-name"><span class="cl-n">{li:02d}</span> {E(layer["name"])}</div>'
                    f'<div class="comp-grid">\n' + "\n".join(cards) + "\n</div></div>")
    comp.append("</div>")
    out.append("\n".join(comp))
    rows = [f'<div class="scope-row"><div class="scope-key">{E(c["name"])}</div><div class="scope-val">{E(c["how"])}'
            f'{pb_link(c["pb"]) if c.get("pb") else ""}</div></div>' for c in p["controls"]]
    out.append('<div class="block"><h3 class="block-title"><span class="bt-k">Controls</span>Guardrails built in</h3><div class="scope controls">\n'
               + "\n".join(rows) + "\n</div></div>")
    out.append('<div class="hitl"><div class="hitl-k"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="3.6"/>'
               '<path d="M4.5 20c.8-4 3.8-6 7.5-6s6.7 2 7.5 6"/></svg>Human in the loop</div>'
               f'<p>{E(p["hitl"])}</p></div>')
    anchors = []
    for L in p["layers"]:
        for c in L["components"]:
            if c.get("pb") and c["pb"] not in anchors:
                anchors.append(c["pb"])
    for c in p["controls"]:
        if c.get("pb") and c["pb"] not in anchors:
            anchors.append(c["pb"])
    anchors.sort(key=lambda a: [int(x) for x in pb_label(a)[0].split(".")])
    tags = "".join(f'<span class="timeline-tag">{E(t)}</span>' for t in p["stack"])
    pbchips = "".join(f'<a class="pb-chip" href="/playbook.html#{a}"><b>§{pb_label(a)[0]}</b> {E(pb_label(a)[1])}</a>' for a in anchors)
    out.append(f'<div class="foot-grid"><div><div class="mini-k">Stack</div><div class="timeline-tags">{tags}</div></div>\n'
               f'<div><div class="mini-k">Playbook sections this build uses</div><div class="pb-chips">{pbchips}</div></div></div>')
    out.append('<a class="to-index" href="#project-index">↑ Back to project index</a>\n</section>')
    return "\n".join(out)


# ── progressive disclosure: parse each rendered section into parts ──────────────────────
def balanced_end(s, start, tag):
    """s[start:] opens <tag ...>; return the index just past its matching </tag>."""
    depth = 0
    for m in re.finditer(rf"<{tag}\b|</{tag}>", s[start:]):
        depth += -1 if m.group(0).startswith("</") else 1
        if depth == 0:
            return start + m.end()
    raise ValueError(f"unbalanced <{tag}> at {start}")


class Parts:
    def __init__(self, sec, pid):
        self.pid, self.rest = pid, sec
        self.head = self.pull(r'<div class="proj-head">', "div")
        self.role = self.pull(r'<div class="built-on">', "div", required=False)
        self.pwv = self.pull(r'<div class="pwv">', "div")
        self.arch = self.pull(r'<figure class="arch">', "figure")
        self.flows, self.components, self.controls = [], None, None
        while True:
            b = self.pull(r'<div class="block">', "div", required=False)
            if b is None:
                break
            kind = re.search(r'<span class="bt-k">([^<]+)</span>', b).group(1)
            if kind == "Flow":
                self.flows.append(b)
            elif kind == "Components":
                self.components = b
            elif kind == "Controls":
                self.controls = b
            else:
                sys.exit(f"build_projects: {pid}: unknown block kind {kind!r}")
        self.hitl = self.pull(r'<div class="hitl">', "div", required=False)
        self.foot = self.pull(r'<div class="foot-grid">', "div", required=False)
        self.pull(r'<a class="to-index"', "a", required=False)   # navigation only; the dialog has its own
        left = re.sub(r"<section[^>]*>|</section>", "", self.rest)
        if re.sub(r"<[^>]+>", "", left).strip():
            sys.exit(f"build_projects: {pid}: content outside the known parts would be lost: {left.strip()[:200]!r}")
        if not (self.flows and self.components and self.controls):
            sys.exit(f"build_projects: {pid}: missing flow, components or controls block")
        # head fields
        self.idx = re.search(r'<span class="sec-idx">([^<]+)</span>', self.head).group(1)
        meta = re.search(r'<div class="proj-meta">(.*?)</div>', self.head, re.S).group(1)
        self.chips = re.sub(r'<span class="sec-idx">[^<]*</span>', "", meta).strip()
        self.title = re.search(r'<h2 class="proj-title"[^>]*>(.*?)</h2>', self.head, re.S).group(1).strip()
        self.tagline = re.search(r'<p class="proj-tagline">(.*?)</p>', self.head, re.S).group(1).strip()
        # layers from the components block
        self.layers = []
        comp = self.components
        for m in re.finditer(r'<div class="comp-layer">', comp):
            layer = comp[m.start():balanced_end(comp, m.start(), "div")]
            nm = re.search(r'<div class="comp-layer-name">', layer)
            name_html = layer[nm.end():balanced_end(layer, nm.start(), "div") - len("</div>")]
            name_html = re.sub(r'<span class="cl-n">[^<]*</span>\s*', "", name_html).strip()
            short = re.sub(r"<[^>]+>", "", re.sub(r'<span class="cl-sub">.*?</span>', "", name_html, flags=re.S)).strip()
            cards = []
            for cm in re.finditer(r'<div class="comp-card', layer):
                if cards and cm.start() < cards[-1][1]:
                    continue
                cards.append((cm.start(), balanced_end(layer, cm.start(), "div")))
            cards = [layer[a:b] for a, b in cards]
            names = [re.sub(r"<[^>]+>", "", re.search(r"<h4>(.*?)</h4>", c, re.S).group(1)).strip() for c in cards]
            self.layers.append({"name_html": name_html, "short": short, "cards": cards, "names": names})
        if not self.layers:
            sys.exit(f"build_projects: {pid}: no component layers found")

    def pull(self, opener, tag, required=True):
        m = re.search(opener, self.rest)
        if not m:
            if required:
                sys.exit(f"build_projects: {self.pid}: missing {opener}")
            return None
        e = balanced_end(self.rest, m.start(), tag)
        frag = self.rest[m.start():e]
        self.rest = self.rest[:m.start()] + self.rest[e:]
        return frag

    @property
    def ncomp(self):
        return sum(len(L["cards"]) for L in self.layers)


def card(p):
    mx = max(len(L["cards"]) for L in p.layers)
    bands = "".join(f'<span style="--w:{30 + round(70 * len(L["cards"]) / mx)}%"><i></i><em>{L["short"]}</em></span>'
                    for L in p.layers)
    n = p.idx.split("/")[0].strip()
    # The whole card is a link, so chip links (kept in the detail view) render as plain chips here.
    chips = re.sub(r'<a class="proj-chip[^"]*"[^>]*>(.*?)</a>', r'<span class="proj-chip">\1</span>', p.chips, flags=re.S)
    return (f'<li><a class="pcard fx-spot" data-reveal href="#{p.pid}" aria-haspopup="dialog" aria-controls="proj-dialog">'
            f'<span class="pc-top"><span class="pc-n">{n}</span><span class="pc-chips">{chips}</span></span>'
            f'<h3 class="pc-name">{p.title}</h3><span class="pc-tag">{p.tagline}</span>'
            f'<span class="pc-glyph" aria-hidden="true">{bands}</span>'
            f'<span class="pc-foot"><span>{len(p.layers)} layers · {p.ncomp} components</span>'
            f'<span class="pc-go">Explore <span aria-hidden="true">→</span></span></span></a></li>')


def detail(p):
    pid = p.pid
    bands = []
    for i, L in enumerate(p.layers):
        names = " · ".join(E(x) for x in L["names"])
        bands.append(
            f'<li class="band" style="--i:{i}"><button type="button" class="band-btn" aria-expanded="true" aria-controls="{pid}-L{i + 1}">'
            f'<span class="band-n">{i + 1:02d}</span><span class="band-name">{L["name_html"]}</span>'
            f'<span class="band-comps">{names}</span>'
            f'<span class="band-count" aria-label="{len(L["cards"])} components">{len(L["cards"])}</span>'
            f'<span class="band-chev" aria-hidden="true"></span></button>'
            f'<div class="band-body" id="{pid}-L{i + 1}"><div class="comp-grid">\n' + "\n".join(L["cards"]) + "\n</div></div></li>")
    hl = (f'<section class="hl-arch" aria-label="{E(re.sub(r"<[^>]+>", "", p.title))}: architecture at a glance">'
          f'<div class="hl-head"><span class="arch-dot" aria-hidden="true"></span><span>Architecture at a glance</span>'
          f'<span class="hl-stack">{len(p.layers)} layers · {p.ncomp} components</span>'
          f'<button type="button" class="hl-all" aria-pressed="false">Expand all layers</button></div>'
          f'<p class="hl-hint">Top to bottom, from the person using it down to data and delivery. Open a layer to see its components.</p>'
          f'<ol class="bands">\n' + "\n".join(bands) + "\n</ol></section>")
    panels = [("flow", "Request flow", p.arch + "\n" + "\n".join(p.flows)),
              ("controls", "Controls", p.controls)]
    if p.hitl:
        panels.append(("hitl", "Human in the loop", p.hitl))
    if p.foot:
        panels.append(("stack", "Stack", p.foot))
    btns = "".join(f'<button type="button" class="dx-btn" aria-expanded="true" aria-controls="{pid}-p-{k}">{lab}</button>'
                   for k, lab, _ in panels)
    bodies = "\n".join(f'<div class="dx-panel" id="{pid}-p-{k}" role="region" aria-label="{lab}">\n{body}\n</div>'
                       for k, lab, body in panels)
    return "\n".join([
        f'<article class="proj" id="{pid}" aria-labelledby="{pid}-title">',
        p.head, p.role or "", p.pwv, hl,
        f'<div class="dx"><div class="dx-k">Go deeper</div><div class="dx-btns">{btns}</div></div>',
        bodies, "</article>"])


def main():
    spec = json.load(open(os.path.join(SRC, "projects.json"), encoding="utf-8"))
    new = {p["id"]: p for p in spec["projects"]}
    order = spec["order"]
    sections = []
    for pid in order:
        if pid in new:
            sections.append(section(new[pid]))
        else:
            path = os.path.join(SRC, f"legacy-{pid}.html")
            if not os.path.exists(path):
                sys.exit(f"build_projects: no spec or legacy section for '{pid}'")
            sections.append(open(path, encoding="utf-8").read())
    total = len(sections)
    sections = [re.sub(r'<span class="sec-idx">\d+ / \d+</span>', f'<span class="sec-idx">{i:02d} / {total:02d}</span>', s, count=1)
                for i, s in enumerate(sections, 1)]
    parts = [Parts(s, pid) for s, pid in zip(sections, order)]
    cards = '<ol class="pgrid">\n' + "\n".join(card(p) for p in parts) + "\n</ol>"
    details = "\n".join(detail(p) for p in parts)
    stats = (f'<div class="ph-stat"><b>{total}</b><span>projects</span></div>'
             f'<div class="ph-stat"><b>{sum(len(p.layers) for p in parts)}</b><span>architecture layers</span></div>'
             f'<div class="ph-stat"><b>{sum(p.ncomp for p in parts)}</b><span>components mapped</span></div>')
    tpl = open(os.path.join(SRC, "template.html"), encoding="utf-8").read()
    for marker in ("<!--PROJECT_CARDS-->", "<!--PROJECT_DETAILS-->", "<!--PROJECT_STATS-->", "<!--PROJECT_COUNT-->"):
        if marker not in tpl:
            sys.exit(f"build_projects: template is missing {marker}")
    page = (tpl.replace("<!--PROJECT_CARDS-->", cards).replace("<!--PROJECT_DETAILS-->", details)
            .replace("<!--PROJECT_STATS-->", stats).replace("<!--PROJECT_COUNT-->", str(total)))
    ids = re.findall(r'\sid="([^"]+)"', page)
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        sys.exit(f"build_projects: duplicate ids {dupes[:10]}")
    open(OUT, "w", encoding="utf-8").write(page)
    print(f"wrote {os.path.relpath(OUT, ROOT)}: {total} projects ({len(new)} from spec, {total - len(new)} legacy)")


if __name__ == "__main__":
    main()
