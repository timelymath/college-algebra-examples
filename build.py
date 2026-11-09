#!/usr/bin/env python3
"""Build the course index website from data/course.yaml.

    python3 build.py            # writes site/index.html, a page per video (site/1.1/6/) and copies files/

Nothing else to configure: edit the YAML, run this, and the page is rebuilt.

An example whose video is scheduled carries `public_at` (UTC, e.g.
"2026-11-02T15:00:00Z"). Until that time it shows "Coming Nov 2"; the first
build after it shows the Watch button.
"""
import datetime as dt
import html
import json
import pathlib
import re
import shutil
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data" / "course.yaml"
OUT = ROOT / "site"

ICONS = {
    "play": '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2.5v11l9-5.5z"/></svg>',
    "guide": '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 1.5h7l3 3v10H3z" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M5.5 7.5h5M5.5 10h5" stroke="currentColor" stroke-width="1.4"/></svg>',
    "book": '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 3c2-1 4-1 6 .5C10 2 12 2 14 3v10c-2-1-4-1-6 .5C6 12 4 12 2 13z" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M8 3.5v10" stroke="currentColor" stroke-width="1.4"/></svg>',
    "link": '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6.5 9.5l3-3M7 4.5l1.2-1.2a2.6 2.6 0 013.7 3.7L10.7 8.2M9 11.5l-1.2 1.2a2.6 2.6 0 01-3.7-3.7l1.2-1.2" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>',
}
KIND_ICON = {"guide": "guide", "worksheet": "guide", "practice": "guide",
             "slides": "guide", "video": "play", "link": "link"}

# Math for the Try It panels (KaTeX), loaded only on the pages that have one.
KATEX = "https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9"

e = html.escape


def slug(*parts):
    return "-".join(str(p).replace(".", "-") for p in parts)


def chip(res):
    icon = ICONS[KIND_ICON.get(res.get("kind", "link"), "link")]
    return (f'<a class="chip" href="{e(res["url"])}" target="_blank" rel="noopener">'
            f'{icon}<span>{e(res["label"])}</span></a>')


def chips(resources, extra=""):
    items = [chip(r) for r in (resources or [])]
    if not items and not extra:
        return ""
    return f'<div class="chips">{extra}{"".join(items)}</div>'


NOW = dt.datetime.now(dt.timezone.utc)


def public_at(ex):
    """The UTC time the video goes public, or None if there's no schedule."""
    t = ex.get("public_at")
    if not t:
        return None
    if isinstance(t, str):
        t = dt.datetime.strptime(t.replace("Z", "+0000").replace("+00:00", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
    elif isinstance(t, dt.date) and not isinstance(t, dt.datetime):
        t = dt.datetime(t.year, t.month, t.day)
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def is_posted(ex):
    t = public_at(ex)
    return bool(ex.get("video")) and (t is None or t <= NOW)


def example_row(sec, ex):
    anchor = slug("ex", sec["number"], ex["n"])
    title = e(ex["title"])
    res = "".join(chip(r) for r in ex.get("resources") or [])
    if is_posted(ex):
        page = page_path(sec, ex)
        name = f'<a class="ex-title" href="{e(page)}">{title}</a>'
        action = (f'<a class="watch" href="{e(page)}" '
                  f'aria-label="Watch Example {ex["n"]}: {title}">{ICONS["play"]}<span>Watch</span></a>')
        state = "posted"
    else:
        name = f'<span class="ex-title">{title}</span>'
        t = public_at(ex)
        when = f'{t:%b} {t.day}' if t else "soon"
        action = f'<span class="soon">Coming {when}</span>'
        state = "pending"
    return (f'<li class="ex {state}" id="{anchor}" data-search="{e(sec["number"])} example {ex["n"]} {title.lower()}">'
            f'<span class="num">{ex["n"]}</span>'
            f'<div class="ex-main">{name}{f"<div class=ex-res>{res}</div>" if res else ""}</div>'
            f'<div class="ex-act">{action}</div></li>')


def section_block(sec):
    exs = sec.get("examples") or []
    posted = sum(1 for x in exs if is_posted(x))
    book = ""
    if sec.get("playlist_url"):
        book += chip({"kind": "video", "label": "Section playlist", "url": sec["playlist_url"]})
    if sec.get("review"):
        book += chip({"kind": "video", "label": "Section review video", "url": sec["review"]})
    if sec.get("compendium"):
        # The section's compendium page (our rewrite of the section) takes the textbook link's place.
        book += (f'<a class="chip" href="{e(compendium_path(sec))}">'
                 f'{ICONS["book"]}<span>Section {e(sec["number"])} Compendium</span></a>')
    elif sec.get("textbook_url"):
        book += (f'<a class="chip quiet" href="{e(sec["textbook_url"])}" target="_blank" rel="noopener">'
                 f'{ICONS["book"]}<span>Read the section</span></a>')
    rows = "".join(example_row(sec, x) for x in exs)
    pct = round(100 * posted / len(exs)) if exs else 0
    return f'''
    <details class="section" id="{slug("sec", sec["number"])}" open>
      <summary>
        <span class="sec-num">{e(sec["number"])}</span>
        <span class="sec-title">{e(sec["title"])}</span>
        <span class="sec-eyebrow">Section {e(sec["number"])}</span>
        <span class="sec-count" title="{posted} of {len(exs)} videos posted">
          <span class="bar"><span style="width:{pct}%"></span></span>{posted}/{len(exs)}
        </span>
      </summary>
      {chips(sec.get("resources"), book)}
      <ol class="examples">{rows}</ol>
    </details>'''


def compendium_path(sec):
    """Where a section's compendium page is served, e.g. 8.1/compendium/."""
    return f'{sec["number"]}/compendium/'


def released(sec):
    """A section shows once any of its videos is posted: sections go public whole, so until then it stays hidden."""
    return any(is_posted(x) for x in sec.get("examples") or [])


def visible(chapters):
    """The chapters with their released sections only; chapters with none are left out."""
    out = []
    for ch in chapters:
        secs = [s for s in ch.get("sections") or [] if released(s)]
        if secs:
            out.append(dict(ch, sections=secs))
    return out


def chapter_block(ch):
    secs = "".join(section_block(s) for s in ch.get("sections") or [])
    return f'''
  <section class="chapter" id="{slug("ch", ch["number"])}">
    <h2><span class="ch-label">Chapter {ch["number"]}</span>{e(ch["title"])}</h2>
    {chips(ch.get("resources"))}
    {secs}
  </section>'''


def build():
    data = yaml.safe_load(DATA.read_text())
    c = data["course"]
    chapters = visible(data.get("chapters") or [])
    all_ex = [x for ch in chapters for s in ch.get("sections") or [] for x in s.get("examples") or []]
    posted = sum(1 for x in all_ex if is_posted(x))
    toc = "".join(
        f'<a href="#{slug("ch", ch["number"])}">Ch {ch["number"]} · {e(ch["title"])}</a>' for ch in chapters)
    top_links = [chip({"kind": "video", "label": "YouTube channel", "url": c["channel_url"]})] if c.get("channel_url") else []
    top_links += [chip({"kind": "link", "label": "Free textbook (OpenStax)", "url": c["textbook_url"]})]
    top_links += [chip(r) for r in c.get("resources") or []]

    page = TEMPLATE.format(
        base_css=BASE_CSS, title=e(c["title"]), tagline=e(c["tagline"]), author=e(c.get("author", "")),
        links="".join(top_links), toc=toc, posted=posted, total=len(all_ex),
        chapters="".join(chapter_block(ch) for ch in chapters),
    )
    if OUT.exists():
        shutil.rmtree(OUT)  # so a page for a removed link doesn't linger
    OUT.mkdir()
    (OUT / "index.html").write_text(page)

    # One clean page per example that has a video link (scheduled ones say "Coming Nov 2").
    order = [(s, x) for ch in chapters for s in ch.get("sections") or [] for x in s.get("examples") or []]
    pages = 0
    for i, (sec, ex) in enumerate(order):
        if not ex.get("video"):
            continue
        prev = order[i - 1] if i else None
        nxt = order[i + 1] if i + 1 < len(order) else None
        d = OUT / page_path(sec, ex)
        d.mkdir(parents=True)
        (d / "index.html").write_text(video_page(sec, ex, prev, nxt))
        pages += 1
    # Compendium pages are finished HTML (built outside this repo); copy each released one into place.
    for ch in chapters:
        for sec in ch.get("sections") or []:
            if sec.get("compendium"):
                d = OUT / compendium_path(sec)
                d.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / sec["compendium"], d / "index.html")
    files = ROOT / "files"
    if files.exists():
        shutil.copytree(files, OUT / "files", dirs_exist_ok=True)
    (OUT / ".nojekyll").write_text("")
    print(f"Built site/index.html: {len(chapters)} chapter(s), {len(all_ex)} examples, {posted} videos posted, {pages} video pages")


BASE_CSS = """/* Clean Teal, matched to the videos: flat white cards on a cool gray page,
   bold teal titles, muted letter-spaced eyebrows, outlined teal part circles. */
:root {
  --bg:#F3F5F8; --card:#FFFFFF; --text:#1F2633; --muted:#8A93A3; --line:#E6EAF0;
  --teal:#1F7A8C; --teal-ink:#FFFFFF; --coral:#D9573B; --pending:#C3CAD5;
}
@media (prefers-color-scheme: dark) {
  :root { --bg:#141A21; --card:#1D252F; --text:#E7EBF1; --muted:#8A93A3; --line:#2A333F;
          --teal:#4DB3C6; --teal-ink:#0E1A20; --coral:#EC7A5F; --pending:#4A5463; }
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font:16px/1.5 Arial, "Helvetica Neue", Helvetica, sans-serif; }
a { color:var(--teal); }"""


VIDEO_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Section {sec} Example {n}</title>
<meta name="description" content="Video walkthrough of Example {n} in Section {sec} of OpenStax College Algebra 2e: {title}.">
<style>
{base_css}
.wrap {{ max-width:960px; margin:0 auto; padding:28px 16px 48px; }}
.eyebrow {{ font-size:13px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); font-weight:700; }}
h1 {{ font-size:clamp(22px,4vw,30px); line-height:1.2; margin:6px 0 18px; color:var(--teal); }}
.player {{ position:relative; aspect-ratio:16/9; border-radius:10px; overflow:hidden; background:#000;
  box-shadow:0 1px 3px rgba(31,38,51,.12); }}
.player iframe {{ position:absolute; inset:0; width:100%; height:100%; border:0; }}
.player.soon {{ background:var(--card); display:grid; place-items:center; color:var(--muted); font-size:18px; }}
nav.steps {{ display:flex; justify-content:space-between; gap:16px; margin-top:20px; }}
.step {{ display:flex; align-items:center; gap:14px; flex:0 1 48%; min-width:0; text-decoration:none; background:var(--card);
  border:1.5px solid var(--line); border-radius:10px; padding:14px 16px; box-shadow:0 1px 2px rgba(31,38,51,.06);
  transition:border-color .15s, box-shadow .15s, transform .15s; }}
.step:hover {{ border-color:var(--teal); box-shadow:0 3px 10px rgba(31,38,51,.12); transform:translateY(-1px); }}
.step:focus-visible {{ outline:2px solid var(--teal); outline-offset:2px; }}
.step .arrow {{ flex:none; width:40px; height:40px; border-radius:50%; display:grid; place-items:center; background:var(--teal); color:#fff; }}
.step .arrow svg {{ width:18px; height:18px; }}
.step .txt {{ min-width:0; }}
.step .k {{ display:block; font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); font-weight:700; }}
.step .t {{ display:block; color:var(--teal); font-weight:700; margin-top:2px; }}
.step.next {{ flex-direction:row-reverse; text-align:right; margin-left:auto; }}
.quiet {{ margin-top:22px; font-size:14px; color:var(--muted); }}
.quiet a {{ color:var(--muted); }}
@media (max-width:560px) {{ nav.steps {{ flex-direction:column; }} .step {{ flex-basis:auto; }} }}
.res {{ margin-top:36px; padding-top:22px; border-top:1px solid var(--line); scroll-margin-top:16px; }}
.res-head {{ display:flex; align-items:baseline; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:12px; }}
.res h2 {{ font-size:20px; margin:0; color:var(--teal); }}
.res .chips {{ display:flex; flex-wrap:wrap; gap:6px 20px; }}
</style>{head_extra}
</head>
<body>
<div class="wrap">
  <div class="eyebrow">Section {sec} · Example {n}</div>
  <h1>{title}</h1>
  {player}
  <nav class="steps">{prev}{next}</nav>{tryit}
  {resources}
  <p class="quiet"><a href="{home}#{anchor}">All examples</a>{yt}</p>
</div>{scripts}
</body>
</html>
"""





def resources_block(sec, ex):
    # Video pages sit two folders down (8.1/6/), so links into files/ need ../../ in front.
    res = [dict(r, url="../../" + r["url"]) if str(r.get("url", "")).startswith("files/") else r
           for r in ex.get("resources") or []]
    extra = chips(res)
    if not extra:
        return ""
    return f'<section class="res"><div class=res-head><h2>Resources</h2></div>{extra}</section>'


def try_it_block(sec, ex):
    """The textbook's Try It for this example: the problem, then a hint and the answer behind reveals.
    prompt, hint and answer may hold simple HTML and $math$ (rendered by KaTeX)."""
    t = ex.get("try_it")
    if not t:
        return ""
    book = e(sec.get("textbook_url") or "https://openstax.org/details/books/college-algebra-2e")
    return f'''
  <section class="tryit" id="try-it" aria-labelledby="try-it-h">
    <div class="ti-head"><h2 id="try-it-h">Try It #{t["n"]}</h2><span class="ti-sub">Your turn: a problem like the one in the video</span></div>
    <div class="ti-prompt">{t["prompt"]}</div>
    <details class="ti-reveal"><summary>Show a hint</summary><div class="ti-body">{t["hint"]}</div></details>
    <details class="ti-reveal"><summary>Show the answer</summary><div class="ti-body">{t["answer"]}</div></details>
    <p class="ti-credit">Try It #{t["n"]} is from <a href="{book}" target="_blank" rel="noopener">College Algebra 2e, Section {e(sec["number"])}</a> (OpenStax, CC BY 4.0). The hint is ours.</p>
  </section>'''


EXTRAS_CSS = """
<style>
.tryit {{ margin-top:28px; background:var(--card); border-radius:10px; padding:20px 22px; box-shadow:0 1px 2px rgba(31,38,51,.06); }}
.tryit {{ border-left:4px solid var(--coral); }}
.ti-head {{ display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; margin-bottom:10px; }}
.tryit h2 {{ font-size:20px; margin:0; color:var(--teal); }}
.ti-sub {{ font-size:13px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); font-weight:700; }}
.ti-prompt {{ font-size:17px; }}
.ti-prompt p, .ti-body p {{ margin:0 0 8px; }}
.ti-prompt ol, .ti-body ol, .ti-body ul {{ margin:6px 0 8px; padding-left:24px; }}
.ti-prompt li, .ti-body li {{ margin:4px 0; }}
.ti-reveal {{ margin-top:12px; border:1.5px solid var(--line); border-radius:8px; }}
.ti-reveal summary {{ cursor:pointer; padding:10px 14px; font-weight:700; color:var(--teal); list-style:none; display:flex; align-items:center; gap:10px; }}
.ti-reveal summary::-webkit-details-marker {{ display:none; }}
.ti-reveal summary::before {{ content:""; width:7px; height:7px; border-right:2px solid currentColor; border-bottom:2px solid currentColor;
  transform:rotate(-45deg); transition:transform .15s; flex:none; }}
.ti-reveal[open] summary::before {{ transform:rotate(45deg); }}
.ti-reveal summary:focus-visible {{ outline:2px solid var(--teal); outline-offset:2px; border-radius:6px; }}
.ti-body {{ padding:2px 16px 14px; }}
.ti-why {{ color:var(--muted); }}
.ti-credit {{ margin:14px 0 0; font-size:13px; color:var(--muted); }}
.ti-credit a {{ color:var(--muted); }}
.katex {{ font-size:1.08em; }}
.ti-prompt .katex-display {{ margin:10px 0 4px; }}
@media (max-width:560px) {{
  .tryit {{ padding:16px 14px; }}
}}
</style>"""


def page_assets(ex):
    """The extra <head> and closing scripts a page with a Try It needs, or empty strings for a plain page."""
    if not ex.get("try_it"):
        return "", ""
    head = (EXTRAS_CSS.replace("{{", "{").replace("}}", "}") +
            f'\n<link rel="stylesheet" href="{KATEX}/katex.min.css">')
    scripts = f'''
<script defer src="{KATEX}/katex.min.js"></script>
<script defer src="{KATEX}/contrib/auto-render.min.js"
  onload="renderMathInElement(document.querySelector('.tryit'), {{delimiters:[{{left:'$$',right:'$$',display:true}},{{left:'$',right:'$',display:false}}], throwOnError:false}})"></script>'''
    return head, scripts


def video_id(url):
    m = re.search(r"(?:v=|youtu\.be/|embed/)([\w-]{11})", url or "")
    return m.group(1) if m else None


def page_path(sec, ex):
    """Where an example's video page lives, relative to the site root."""
    return f'{sec["number"]}/{ex["n"]}/'


def step_link(kind, item, here):
    """A Previous or Next link: to the neighbor's video page if it has one, else to its row on the index."""
    if not item:
        return ""
    sec, ex = item
    href = here + (page_path(sec, ex) if ex.get("video") else f'#{slug("ex", sec["number"], ex["n"])}')
    label = "Previous example" if kind == "prev" else "Next example"
    arrow = ('<svg viewBox="0 0 16 16" aria-hidden="true"><path d="' + ("M10 3L5 8l5 5" if kind == "prev" else "M6 3l5 5-5 5")
             + '" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    return (f'<a class="step {kind}" href="{e(href)}" aria-label="{label}: {e(sec["number"])} Example {ex["n"]}, {e(ex["title"])}">'
            f'<span class="arrow">{arrow}</span>'
            f'<span class="txt"><span class="k">{label} · {e(sec["number"])} Example {ex["n"]}</span>'
            f'<span class="t">{e(ex["title"])}</span></span></a>')


def video_page(sec, ex, prev, nxt):
    home = "../../"
    vid = video_id(ex.get("video"))
    title = e(ex["title"])
    if is_posted(ex) and vid:
        player = (f'<div class="player"><iframe src="https://www.youtube-nocookie.com/embed/{vid}?rel=0" '
                  f'title="{title}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; '
                  f'picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe></div>')
        yt = f' · <a href="https://www.youtube.com/watch?v={vid}" target="_blank" rel="noopener">Watch on YouTube</a>'
    else:
        t = public_at(ex)
        player = f'<div class="player soon">Coming {f"{t:%b} {t.day}" if t else "soon"}</div>'
        yt = ""
    resources = resources_block(sec, ex)
    head_extra, scripts = page_assets(ex)
    return VIDEO_TEMPLATE.format(
        base_css=BASE_CSS, title=title, sec=e(sec["number"]), n=ex["n"], player=player, home=home,
        anchor=slug("ex", sec["number"], ex["n"]), yt=yt, resources=resources,
        tryit=try_it_block(sec, ex), head_extra=head_extra, scripts=scripts,
        prev=step_link("prev", prev, home), next=step_link("next", nxt, home))


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{tagline}">
<style>
{base_css}
html {{ scroll-behavior:smooth; }}
.wrap {{ max-width:880px; margin:0 auto; padding:0 16px 64px; }}
header {{ padding:44px 0 18px; }}
.eyebrow, .ch-label, .sec-eyebrow {{ font-size:13px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); font-weight:700; }}
h1 {{ font-size:clamp(28px,5.2vw,40px); line-height:1.15; margin:8px 0 10px; color:var(--teal); font-weight:700; }}
.tagline {{ margin:0 0 14px; max-width:62ch; font-size:17px; }}
.stat {{ font-size:14px; color:var(--muted); margin-top:12px; }}
.stat b {{ color:var(--teal); }}
.toolbar {{ position:sticky; top:0; z-index:5; background:var(--bg); padding:12px 0 10px; }}
.search {{ width:100%; padding:11px 14px; font:inherit; border:0; border-radius:8px; background:var(--card); color:var(--text);
  box-shadow:0 1px 2px rgba(31,38,51,.06); }}
.search::placeholder {{ color:var(--muted); }}
.search:focus {{ outline:2px solid var(--teal); outline-offset:0; }}
.toc {{ display:flex; gap:18px; flex-wrap:wrap; margin-top:10px; font-size:14px; }}
.toc a {{ text-decoration:none; color:var(--teal); font-weight:700; }}
.toc a:hover {{ text-decoration:underline; }}
.chapter {{ margin-top:34px; scroll-margin-top:110px; }}
h2 {{ font-size:26px; margin:0 0 6px; display:flex; flex-direction:column; color:var(--teal); line-height:1.2; }}
.ch-label {{ margin-bottom:4px; }}
.chips {{ display:flex; flex-wrap:wrap; gap:6px 20px; margin:6px 0 12px; }}
.chip {{ display:inline-flex; align-items:center; gap:6px; font-size:15px; text-decoration:none; color:var(--teal); font-weight:700; }}
.chip.quiet {{ color:var(--muted); font-weight:700; }}
.chip:hover span {{ text-decoration:underline; }}
.chip svg, .watch svg {{ width:15px; height:15px; fill:currentColor; flex:none; }}
.section {{ background:var(--card); border-radius:10px; margin:14px 0; scroll-margin-top:110px; overflow:hidden;
  box-shadow:0 1px 2px rgba(31,38,51,.05); }}
.section > .chips {{ padding:0 22px; margin:0 0 10px; }}
summary {{ list-style:none; cursor:pointer; display:grid; grid-template-columns:1fr auto auto; grid-template-areas:"eye count chev" "title count chev";
  column-gap:14px; align-items:center; padding:16px 22px 10px; }}
summary::-webkit-details-marker {{ display:none; }}
summary::after {{ grid-area:chev; content:""; width:8px; height:8px; border-right:2px solid var(--muted); border-bottom:2px solid var(--muted);
  transform:rotate(45deg); transition:transform .15s; }}
details[open] > summary::after {{ transform:rotate(225deg); }}
.sec-num {{ display:none; }}
.sec-eyebrow {{ grid-area:eye; }}
.sec-title {{ grid-area:title; font-weight:700; font-size:20px; color:var(--teal); line-height:1.25; }}
.sec-count {{ grid-area:count; display:flex; align-items:center; gap:8px; font-size:13px; color:var(--muted); font-variant-numeric:tabular-nums; }}
.bar {{ width:56px; height:5px; border-radius:3px; background:var(--line); overflow:hidden; }}
.bar span {{ display:block; height:100%; background:var(--teal); }}
.examples {{ list-style:none; margin:0; padding:0 0 8px; }}
.ex {{ display:flex; align-items:center; gap:14px; padding:10px 22px; border-top:1px solid var(--line); scroll-margin-top:110px;
  border-left:3px solid transparent; }}
.ex:target {{ border-left-color:var(--coral); }}
.ex:target .ex-title {{ color:var(--coral); }}
.num {{ flex:none; width:30px; height:30px; border-radius:50%; display:grid; place-items:center; font-size:14px; font-weight:700;
  border:1.5px solid var(--teal); color:var(--teal); background:var(--card); }}
.pending .num {{ border-color:var(--pending); color:var(--muted); }}
.ex-main {{ flex:1; min-width:0; }}
.ex-title {{ text-decoration:none; color:var(--text); font-size:16px; }}
a.ex-title:hover {{ color:var(--teal); text-decoration:underline; }}
.pending .ex-title {{ color:var(--muted); }}
.ex-res .chips {{ margin:2px 0 0; }}
.ex-res .chip {{ font-size:13px; }}
.ex-act {{ flex:none; }}
.watch {{ display:inline-flex; align-items:center; gap:6px; background:var(--teal); color:var(--teal-ink); text-decoration:none;
  font-weight:700; font-size:14px; padding:7px 14px; border-radius:6px; }}
.watch:hover {{ filter:brightness(1.08); }}
.soon {{ font-size:13px; color:var(--muted); }}
.empty {{ display:none; color:var(--muted); padding:24px 0; }}
footer {{ margin-top:44px; font-size:12px; color:var(--muted); }}
@media (max-width:560px) {{
  .ex {{ gap:10px; padding:10px 14px; align-items:flex-start; }}
  summary {{ padding:14px 14px 8px; }}
  .section > .chips {{ padding:0 14px; }}
  .sec-count .bar {{ display:none; }}
  .watch span {{ display:none; }}
  .watch {{ padding:8px 10px; }}
}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="eyebrow">OpenStax College Algebra 2e</div>
    <h1>{title}</h1>
    <p class="tagline">{tagline}</p>
    <div class="chips">{links}</div>
    <div class="stat"><b>{posted}</b> of <b>{total}</b> videos posted so far</div>
  </header>
  <div class="toolbar">
    <input class="search" type="search" placeholder="Search examples or a section number" aria-label="Search examples">
    <nav class="toc">{toc}</nav>
  </div>
  <main>{chapters}
    <p class="empty">No examples match that search.</p>
  </main>
  <footer>
    Examples are adapted from <a href="https://openstax.org/details/books/college-algebra-2e">College Algebra 2e</a>
    by Jay Abramson, OpenStax, under a CC BY 4.0 license. These videos are not affiliated with or endorsed by OpenStax.
    Made by {author}.
  </footer>
</div>
<script>
(function () {{
  var box = document.querySelector('.search');
  var rows = Array.prototype.slice.call(document.querySelectorAll('.ex'));
  var sections = document.querySelectorAll('.section');
  var chapters = document.querySelectorAll('.chapter');
  var empty = document.querySelector('.empty');
  box.addEventListener('input', function () {{
    var q = box.value.trim().toLowerCase();
    var any = false;
    rows.forEach(function (r) {{
      var hit = !q || r.getAttribute('data-search').indexOf(q) !== -1;
      r.style.display = hit ? '' : 'none';
      if (hit) any = true;
    }});
    sections.forEach(function (s) {{
      var vis = s.querySelectorAll('.ex:not([style*="none"])').length;
      s.style.display = vis || !q ? '' : 'none';
      if (q && vis) s.open = true;
    }});
    chapters.forEach(function (c) {{
      c.style.display = c.querySelectorAll('.section:not([style*="none"])').length ? '' : 'none';
    }});
    empty.style.display = any ? 'none' : 'block';
  }});
}})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    try:
        build()
    except Exception as exc:  # keep errors readable for non-programmers
        sys.exit(f"Build failed: {exc}")
