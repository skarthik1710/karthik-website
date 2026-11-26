#!/usr/bin/env python3
"""Build the resume (Word + PDF) from content/resume.json.

    python3 scripts/build_resume.py                       # public: public/resume/*.docx|pdf
    RESUME_PHONE="+1 ..." python3 scripts/build_resume.py --private ~/resume-private
                                                          # private copy with phone, outside the repo

The public site download carries email, website and LinkedIn. The phone number is
never stored in the repo: it is passed via RESUME_PHONE only for the private build.

Screener (ATS) friendly by construction: no tables, text boxes or headers/footers;
contact details are plain body text; standard section names; logos are a decorative
image with all certifications also listed as text.

The PDF is rendered from an HTML twin of the same content with headless Chromium
(Playwright), using Carlito (metric-compatible with Calibri, the Word font) and
Word-like line spacing, so the two lay out closely. Only the PDF page count is
checked automatically; open the .docx once to confirm 2 pages. --no-pdf skips the PDF.
"""
import base64
import datetime
import html
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile

from docx import Document
from docx.enum.text import WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "content" / "resume.json"
OUT = ROOT / "public" / "resume"
BASENAME = "Karthikeyan-Selvam-Resume"

ACCENT = RGBColor(0xB4, 0x3A, 0x0E)   # print-safe version of the site orange
INK = RGBColor(0x1F, 0x1B, 0x18)
MUTED = RGBColor(0x5A, 0x52, 0x4C)
MARGIN_IN = 0.55
PAGE_W_IN = 8.5
BODY_PT = 10

# Certification groups (label, issuer prefix) and brand marks, mirroring the
# "Certified across" block on the home page: real Microsoft / Google marks, coloured
# monograms for the rest. Counts are derived from the certification list.
MS_SVG = ('<svg viewBox="0 0 21 21"><rect x="0" y="0" width="10" height="10" fill="#F25022"/>'
          '<rect x="11" y="0" width="10" height="10" fill="#7FBA00"/><rect x="0" y="11" width="10" height="10" fill="#00A4EF"/>'
          '<rect x="11" y="11" width="10" height="10" fill="#FFB900"/></svg>')
G_SVG = ('<svg viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>'
         '<path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>'
         '<path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>'
         '<path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>')
BRANDS = [  # (label, issuer prefix used to count, mark html)
    ("Microsoft", "Microsoft", MS_SVG),
    ("Google Cloud", "Google", G_SVG),
    ("UiPath", "UiPath", '<span class="mm" style="background:#FA4616">Ui</span>'),
    ("PRINCE2", "Axelos", '<span class="mm" style="background:#82154D">P2</span>'),
    ("Scrum.org", "Scrum.org", '<span class="mm" style="background:#1F6F43">SM</span>'),
    ("Atos Lean", "Atos", '<span class="mm" style="background:#0073C6">At</span>'),
]
CERT_GROUPS = [("Google Cloud", "Google Cloud"), ("Microsoft", "Microsoft"), ("UiPath", "UiPath"),
               ("Delivery and methodology", "")]  # "" = everything else
BRAND_CSS = """
.brands { display: inline-flex; align-items: center; gap: 11pt; white-space: nowrap; }
.brands .bl { font-size: 7.5pt; font-weight: 700; letter-spacing: 0.08em; color: #B43A0E; }
.brands .bi { display: inline-flex; align-items: center; gap: 3.5pt; font-size: 9pt; color: #1F1B18; line-height: 1; }
.brands svg, .brands .mm { width: 11pt; height: 11pt; flex-shrink: 0; display: block; }
.brands .mm { border-radius: 2pt; color: #fff; font-size: 6pt; font-weight: 700; display: flex; align-items: center; justify-content: center; }
.brands .bi b { color: #5A524C; font-weight: 400; font-size: 8pt; margin-left: 1pt; }
"""
FONT_LINK = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Carlito:ital,wght@0,400;0,700;1,400&display=block">'


def contacts(d, phone=None):
    """Two rows of (text, url); url None = plain text. Row 1: location, email, phone
    (phone only in the private build). Row 2: website and LinkedIn."""
    row1 = [(d["location"], None)] if d.get("location") else []
    row1.append((d["email"], "mailto:" + d["email"]))
    if phone:
        row1.append((phone, "tel:" + re.sub(r"[^+\d]", "", phone)))
    row2 = [(c["text"], c["url"]) for c in d.get("links", [])]
    return [r for r in (row1, row2) if r]


def cert_groups(d):
    """[(label, [item text])] — every certification exactly once, as plain text."""
    rest = list(d["certifications"])
    groups = []
    for label, prefix in CERT_GROUPS:
        take = [c for c in rest if (c["issuer"].startswith(prefix) if prefix else True)]
        rest = [c for c in rest if c not in take]
        items = []
        for c in take:
            extra = c["issuer"][len(prefix):].strip(" ()") if prefix else c["issuer"]
            meta = ", ".join(x for x in (extra, c.get("year", "")) if x)
            name = c["name"]
            if meta and name.endswith(")"):  # "Azure Fundamentals (AZ-900)" -> "(AZ-900, 2025)"
                items.append(f"{name[:-1]}, {meta})")
            else:
                items.append(name + (f" ({meta})" if meta else ""))
        if items:
            groups.append((label, items))
    return groups


def brand_html(d):
    items = []
    for label, prefix, mark in BRANDS:
        n = sum(1 for c in d["certifications"] if c["issuer"].startswith(prefix))
        if n:
            count = f"<b>×{n}</b>" if n > 1 else ""
            items.append(f'<span class="bi">{mark}<span>{label}{count}</span></span>')
    return f'<div class="brands"><span class="bl">CERTIFIED ACROSS</span>{"".join(items)}</div>'


def brand_png(d, path):
    """Rasterise the brand strip (4x) for the Word file, which can't embed SVG. Returns width in inches."""
    from playwright.sync_api import sync_playwright
    page = (f'<!doctype html><html><head><meta charset="utf-8">{FONT_LINK}<style>body{{margin:0;'
            f'font-family:Carlito,Calibri,sans-serif;background:#fff}}{BRAND_CSS}</style></head>'
            f'<body>{brand_html(d)}</body></html>')
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(device_scale_factor=4)
        pg.set_content(page, wait_until="networkidle")
        pg.evaluate("document.fonts.ready")
        el = pg.locator(".brands")
        width_px = el.bounding_box()["width"]
        el.screenshot(path=str(path))
        b.close()
    return width_px / 96.0


# ── Word ──────────────────────────────────────────────────────────────
def _spacing(p, before=0, after=0, line=1.0):
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = line


def _run(p, text, bold=False, italic=False, size=None, color=None):
    r = p.add_run(text)
    r.bold, r.italic = bold, italic
    if size:
        r.font.size = Pt(size)
    if color is not None:
        r.font.color.rgb = color
    return r


def _bottom_border(p, color="B43A0E", sz=6):
    pPr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", str(sz)), ("w:space", "1"), ("w:color", color)):
        b.set(qn(k), v)
    bdr.append(b)
    pPr.append(bdr)


def _hyperlink(p, url, text, color="B43A0E"):
    rid = p.part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    h = OxmlElement("w:hyperlink")
    h.set(qn("r:id"), rid)
    r = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    c = OxmlElement("w:color")
    c.set(qn("w:val"), color)
    rpr.append(c)
    r.append(rpr)
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    r.append(t)
    h.append(r)
    p._p.append(h)


def _heading(doc, text):
    p = doc.add_paragraph()
    _spacing(p, before=7, after=3)
    _run(p, text.upper(), bold=True, size=10.5, color=ACCENT)
    _bottom_border(p)
    p.paragraph_format.keep_with_next = True
    return p


def _bullet(doc, text, label=None):
    p = doc.add_paragraph(style="List Bullet")
    _spacing(p, after=1, line=1.0)
    p.paragraph_format.left_indent = Inches(0.18)
    p.paragraph_format.first_line_indent = Inches(-0.14)
    if label:
        _run(p, label, bold=True)
        _run(p, " — " + text)
    else:
        _run(p, text)
    return p


def _labelled(doc, label, text, size=None):
    p = doc.add_paragraph()
    _spacing(p, after=1, line=1.0)
    _run(p, label + ": ", bold=True, size=size)
    _run(p, text, size=size)
    return p


def build_docx(d, path, phone=None, brand_img=None):
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(PAGE_W_IN), Inches(11)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Inches(MARGIN_IN))
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    normal.font.size = Pt(BODY_PT)
    normal.font.color.rgb = INK
    core = doc.core_properties
    core.author = core.last_modified_by = d["name"]
    core.title = f'{d["name"]} — Resume'
    core.comments = ""
    core.created = core.modified = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    core.revision = 1

    p = doc.add_paragraph()
    _spacing(p, after=0)
    _run(p, d["name"], bold=True, size=20, color=INK)
    p = doc.add_paragraph()
    _spacing(p, after=1)
    _run(p, d["headline"], bold=True, size=11, color=ACCENT)
    rows = contacts(d, phone)
    for ri, row in enumerate(rows):
        p = doc.add_paragraph()
        _spacing(p, after=2 if ri == len(rows) - 1 else 0)
        for i, (text, url) in enumerate(row):
            if i:
                _run(p, "  ·  ", color=MUTED)
            if url:
                _hyperlink(p, url, text)
            else:
                _run(p, text, color=INK)
    if brand_img:
        img, width_in = brand_img
        p = doc.add_paragraph()
        _spacing(p, before=1, after=0)
        p.add_run().add_picture(str(img), width=Inches(width_in))

    _heading(doc, "Summary")
    p = doc.add_paragraph()
    _spacing(p, after=1, line=1.0)
    _run(p, d["summary"])

    if d.get("scope"):
        _heading(doc, "Scope of leadership")
        for s in d["scope"]:
            _labelled(doc, s["group"], s["items"])

    _heading(doc, "Skills")
    for s in d["skills"]:
        _labelled(doc, s["group"], s["items"])

    _heading(doc, "Experience")
    text_w = Inches(PAGE_W_IN - 2 * MARGIN_IN)
    for i, e in enumerate(d["experience"]):
        p = doc.add_paragraph()
        _spacing(p, before=4 if i else 1, after=0)
        p.paragraph_format.tab_stops.add_tab_stop(text_w, WD_TAB_ALIGNMENT.RIGHT)
        p.paragraph_format.keep_with_next = True
        _run(p, e["title"], bold=True)
        _run(p, "\t" + e["period"], color=MUTED, size=9.5)
        p = doc.add_paragraph()
        _spacing(p, after=1)
        p.paragraph_format.keep_with_next = True
        _run(p, e["org"], italic=True, color=MUTED)
        for b in e["bullets"]:
            _bullet(doc, b)

    if d.get("projects"):
        _heading(doc, "Projects")
        for pr in d["projects"]:
            _bullet(doc, pr["line"], label=pr["name"])

    _heading(doc, "Certifications")
    for label, items in cert_groups(d):
        _labelled(doc, label, " · ".join(items))

    if d.get("awards"):
        _heading(doc, "Awards and recognition")
        for a in d["awards"]:
            _bullet(doc, a)

    _heading(doc, "Education")
    p = doc.add_paragraph()
    _spacing(p, after=0)
    _run(p, d["education"])

    doc.save(path)


# ── HTML twin → PDF ───────────────────────────────────────────────────
def _e(s):
    return html.escape(s, quote=True)


def build_html(d, phone=None, brand=None):
    def labelled(rows):
        return "".join(f'<p class="sk"><b>{_e(a)}:</b> {_e(b)}</p>' for a, b in rows)
    scope = labelled((s["group"], s["items"]) for s in d.get("scope", []))
    skills = labelled((s["group"], s["items"]) for s in d["skills"])
    certs = labelled((label, " · ".join(items)) for label, items in cert_groups(d))
    contact = "<br>".join('<span class="sep">·</span>'.join(
        f'<a href="{_e(u)}">{_e(t)}</a>' if u else f'<span class="loc">{_e(t)}</span>' for t, u in row)
        for row in contacts(d, phone))
    exp = "".join(
        f'<div class="job"><div class="jh"><b>{_e(e["title"])}</b><span>{_e(e["period"])}</span></div>'
        f'<div class="org">{_e(e["org"])}</div><ul>{"".join(f"<li>{_e(b)}</li>" for b in e["bullets"])}</ul></div>'
        for e in d["experience"])
    proj = "".join(f'<li><b>{_e(p["name"])}</b> — {_e(p["line"])}</li>' for p in d.get("projects", []))
    awards = "".join(f"<li>{_e(a)}</li>" for a in d.get("awards", []))
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{_e(d['name'])} — Resume</title>
{FONT_LINK}
<style>
@page {{ size: Letter; margin: {MARGIN_IN}in; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: Carlito, Calibri, sans-serif; font-size: {BODY_PT}pt; color: #1F1B18; line-height: 1.22; }}
h1 {{ font-size: 20pt; margin: 0; line-height: 1.15; }}
.hl {{ color: #B43A0E; font-weight: 700; font-size: 11pt; margin: 0 0 1pt; }}
.ct a {{ color: #B43A0E; text-decoration: none; }}
.ct .sep {{ color: #5A524C; padding: 0 6pt; }}
.ct .loc {{ color: #1F1B18; }}
.ct {{ margin: 0 0 3pt; }}
h2 {{ color: #B43A0E; font-size: 10.5pt; text-transform: uppercase; margin: 7pt 0 3pt; padding-bottom: 1pt; border-bottom: 0.75pt solid #B43A0E; break-after: avoid; }}
p {{ margin: 0 0 1pt; line-height: 1.22; }}
ul {{ margin: 0; padding-left: 0.18in; }}
li {{ margin: 0 0 1pt; line-height: 1.22; }}
.job {{ margin-top: 4pt; }}
.job:first-of-type {{ margin-top: 1pt; }}
.jh {{ display: flex; justify-content: space-between; break-after: avoid; }}
.jh span, .org {{ color: #5A524C; }}
.jh span {{ font-size: 9.5pt; }}
.org {{ font-style: italic; margin-bottom: 1pt; break-after: avoid; }}
{BRAND_CSS}
</style></head><body>
<h1>{_e(d['name'])}</h1><p class="hl">{_e(d['headline'])}</p>
<p class="ct">{contact}</p>
{_brand_block(d, brand)}
<h2>Summary</h2><p>{_e(d['summary'])}</p>
{f'<h2>Scope of leadership</h2>{scope}' if scope else ''}
<h2>Skills</h2>{skills}
<h2>Experience</h2>{exp}
{f'<h2>Projects</h2><ul>{proj}</ul>' if proj else ''}
<h2>Certifications</h2>{certs}
{f'<h2>Awards and recognition</h2><ul>{awards}</ul>' if awards else ''}
<h2>Education</h2><p>{_e(d['education'])}</p>
</body></html>"""


def _brand_block(d, brand):
    """Same rasterised strip as the Word file, so logos stay out of the PDF text layer."""
    if not brand:
        return brand_html(d)
    img, width_in = brand
    data = base64.b64encode(pathlib.Path(img).read_bytes()).decode()
    return f'<img alt="" src="data:image/png;base64,{data}" style="width:{width_in:.3f}in;display:block;margin-top:1pt">'


def build_pdf(d, path, phone=None, brand=None):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.set_content(build_html(d, phone, brand), wait_until="networkidle")
        pg.evaluate("document.fonts.ready")
        pg.pdf(path=str(path), format="Letter", print_background=True, prefer_css_page_size=True)
        b.close()
    return len(re.findall(rb"/Type\s*/Page[^s]", path.read_bytes()))


def main():
    src = SRC
    if "--src" in sys.argv:  # render a candidate JSON (e.g. for layout experiments)
        src = pathlib.Path(sys.argv[sys.argv.index("--src") + 1]).expanduser()
    d = json.loads(src.read_text())
    out, phone = OUT, None
    if "--private" in sys.argv:
        i = sys.argv.index("--private")
        if i + 1 >= len(sys.argv):
            sys.exit("--private needs an output directory outside the repo")
        out = pathlib.Path(sys.argv[i + 1]).expanduser().resolve()
        if ROOT in out.parents or out == ROOT:
            sys.exit("refusing to write the private resume inside the repo")
        phone = os.environ.get("RESUME_PHONE", "").strip()
        if not phone:
            sys.exit("set RESUME_PHONE for the private build")
    out.mkdir(parents=True, exist_ok=True)
    show = (lambda p: p.relative_to(ROOT)) if ROOT in out.parents else (lambda p: p)

    docx_path = out / f"{BASENAME}.docx"
    with tempfile.TemporaryDirectory() as td:
        brand = None
        try:
            img = pathlib.Path(td) / "brands.png"
            brand = (img, brand_png(d, img))
        except Exception as exc:  # Playwright missing: build the Word file without logos
            print(f"warning: certification logos skipped ({exc})")
        build_docx(d, docx_path, phone, brand)
        print(f"wrote {show(docx_path)}")
        if "--no-pdf" in sys.argv:
            return
        pdf_path = out / f"{BASENAME}.pdf"
        tmp = pathlib.Path(td) / "resume.pdf"
        pages = build_pdf(d, tmp, phone, brand)
        if pages != 2:
            sys.exit(f"expected 2 pages, got {pages}; {pdf_path.name} left unchanged")
        if b"Carlito" not in tmp.read_bytes():
            sys.exit(f"Carlito font did not load (offline?); {pdf_path.name} left unchanged")
        shutil.move(str(tmp), pdf_path)
        print(f"wrote {show(pdf_path)} ({pages} pages)")


if __name__ == "__main__":
    main()
