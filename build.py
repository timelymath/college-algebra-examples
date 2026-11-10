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


def seconds(ex):
    """An example's video length in seconds, from `duration: "3:50"`, or None if it has none."""
    m = re.fullmatch(r"(?:(\d+):)?(\d{1,2}):(\d{2})", str(ex.get("duration") or ""))
    if not m:
        return None
    return int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3))


def thumb_url(ex):
    """The video's own thumbnail, straight from YouTube, so a new section needs no image files."""
    vid = video_id(ex.get("video"))
    return f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg" if vid else ""


def thumb(ex, play=False):
    dur = f'<span class="dur">{e(str(ex["duration"]))}</span>' if seconds(ex) else ""
    btn = f'<span class="play" aria-hidden="true">{ICONS["play"]}</span>' if play else ""
    return f'<img src="{thumb_url(ex)}" alt="" width="320" height="180" loading="lazy">{btn}{dur}'


def example_row(sec, ex):
    anchor = slug("ex", sec["number"], ex["n"])
    title = e(ex["title"])
    n = ex["n"]
    attrs = (f'id="{anchor}" data-n="{n}" data-sec="{e(sec["number"])}" '
             f'data-search="{e(sec["number"])} example {n} {title.lower()}"')
    meta = [f"<span>Example {n}</span>"]
    if is_posted(ex):
        page = e(page_path(sec, ex))
        if ex.get("try_it"):
            meta.append(f'<a href="{page}#try-it">Try It #{ex["try_it"]["n"]}</a>')
        meta += [chip(r) for r in ex.get("resources") or []]
        return (f'<li class="ex posted" {attrs}>'
                f'<button class="num" type="button" aria-pressed="false" aria-label="Mark Example {n} as watched">{n}</button>'
                f'<a class="thumb" href="{page}" tabindex="-1" aria-hidden="true">{thumb(ex)}</a>'
                f'<div class="ex-main"><a class="ex-title" href="{page}">{title}</a><div class="ex-meta">{"".join(meta)}</div></div>'
                f'<a class="watch" href="{page}" aria-label="Watch Example {n}: {title}">{ICONS["play"]}<span>Watch</span></a></li>')
    t = public_at(ex)
    when = f'{t:%b} {t.day}' if t else "soon"
    return (f'<li class="ex pending" {attrs}>'
            f'<span class="num">{n}</span><span class="thumb" aria-hidden="true"></span>'
            f'<div class="ex-main"><span class="ex-title">{title}</span><div class="ex-meta">{"".join(meta)}</div></div>'
            f'<span class="soon">Coming {when}</span></li>')


RES_TAG = {"guide": "Guide", "worksheet": "Worksheet", "practice": "Practice",
           "slides": "Slides", "video": "Video", "link": "Link"}


def tile(icon, tag, title, sub, href, main=False, new_tab=True, extra=""):
    """One of a section's link cards: a small label, a title, and an optional line under it."""
    target = ' target="_blank" rel="noopener"' if new_tab else ""
    small = f"<small>{e(sub)}</small>" if sub else ""
    return (f'<a class="tile{" main" if main else ""}" href="{e(href)}"{target}>'
            f'<span class="kind">{ICONS[icon]}{e(tag)}</span><b>{e(title)}</b>{small}{extra}</a>')


def section_tiles(sec):
    """The section's link cards: Compendium first (or the textbook section), then review, playlist and resources."""
    out = []
    if sec.get("compendium"):
        tries = sum(1 for x in sec.get("examples") or [] if x.get("try_it"))
        # Filled in by the page from the progress the compendium saves in the same browser.
        pill = (f'<span class="pill" data-try-key="oca-{e(sec["number"])}-progress" data-try-total="{tries}" hidden></span>'
                if tries else "")
        out.append(tile("book", "Study the section", f'Section {sec["number"]} Compendium',
                        "The whole section on one page: worked examples, Try Its with hints, formulas, and a practice set.",
                        compendium_path(sec), main=True, new_tab=False, extra=pill))
    elif sec.get("textbook_url"):
        out.append(tile("book", "Textbook", "Read the section", "The original section at OpenStax.", sec["textbook_url"]))
    if sec.get("review"):
        out.append(tile("play", "Review", "Section review", sec.get("review_note") or "Every example in one video.", sec["review"]))
    if sec.get("playlist_url"):
        out.append(tile("play", "Playlist", "Watch straight through", "The section playlist on YouTube.", sec["playlist_url"]))
    for r in sec.get("resources") or []:
        kind = r.get("kind", "link")
        out.append(tile(KIND_ICON.get(kind, "link"), r.get("tag") or RES_TAG.get(kind, "Link"),
                        r["label"], r.get("note", ""), r["url"]))
    return f'<div class="tiles">{"".join(out)}</div>' if out else ""


def section_block(sec):
    exs = sec.get("examples") or []
    posted = [x for x in exs if is_posted(x)]
    meta = f'{len(posted)} video{"" if len(posted) == 1 else "s"}'
    lengths = [seconds(x) for x in posted]
    if posted and all(lengths):
        meta += f' · {max(1, round(sum(lengths) / 60))} minutes'
    if len(posted) < len(exs):
        meta += f' · {len(exs) - len(posted)} coming soon'
    # Rows grouped by skill (the same skills as the compendium's path); anything not listed follows, ungrouped.
    by_n = {x["n"]: x for x in exs}
    groups, used = "", set()
    for i, sk in enumerate(sec.get("skills") or []):
        rows = [by_n[n] for n in sk.get("examples") or [] if n in by_n]
        used.update(x["n"] for x in rows)
        if rows:
            groups += (f'<div class="group"><h4><b>{chr(65 + i)}</b>{e(sk["name"])}</h4>'
                       f'<ol class="examples">{"".join(example_row(sec, x) for x in rows)}</ol></div>')
    rest = [x for x in exs if x["n"] not in used]
    if rest:
        groups += f'<div class="group"><ol class="examples">{"".join(example_row(sec, x) for x in rest)}</ol></div>'
    return f'''
    <details class="section" id="{slug("sec", sec["number"])}" open>
      <summary>
        <span><span class="eyebrow">Section {e(sec["number"])}</span><span class="sec-title">{e(sec["title"])}</span><span class="sec-meta">{meta}</span></span>
        <span class="sec-count"><span class="cnt"></span><span class="bar" aria-hidden="true"><span></span></span></span>
      </summary>
      <div class="sec-body">{section_tiles(sec)}{groups}</div>
    </details>'''


def resume_card(chapters):
    """The "Start here" card. It ships pointing at the first posted example; the page then moves it to the
    first example this visitor hasn't watched, or to the newest compendium's practice set once all are watched."""
    order = [(s, x) for ch in chapters for s in ch.get("sections") or [] for x in s.get("examples") or [] if is_posted(x)]
    if not order:
        return ""
    sec, ex = order[0]
    done = ""
    with_comp = [s for ch in chapters for s in ch.get("sections") or [] if s.get("compendium")]
    if with_comp:
        last = with_comp[-1]
        done = (f' data-done-href="{e(compendium_path(last))}#practice"'
                f' data-done-text="Try the practice set in the Section {e(last["number"])} Compendium"')
    return f'''<aside class="resume" id="resume" aria-label="Where to go next"{done}>
      <p class="k">Start here</p>
      <a class="resume-link" href="{e(page_path(sec, ex))}">
        <span class="thumb">{thumb(ex, play=True)}</span>
        <span><span class="where">Section {e(sec["number"])} · Example {ex["n"]}</span><span class="t">{e(ex["title"])}</span></span>
      </a>
      <p class="resume-meta">{len(order)} example{"" if len(order) == 1 else "s"} posted</p>
    </aside>'''


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
    <h2><span class="eyebrow">Chapter {ch["number"]}</span>{e(ch["title"])}</h2>
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

    title = e(c["title"])
    head, _, tail = title.partition(", ")
    headline = f"{head}, <span>{tail}</span>" if tail else title  # the second half of the title in teal
    page = fill(
        TEMPLATE, base_css=BASE_CSS, index_css=INDEX_CSS, index_js=INDEX_JS, font_link=FONT_LINK,
        theme_head=THEME_HEAD, theme_btn=THEME_BTN, theme_js=THEME_JS,
        title=title, headline=headline, tagline=e(c["tagline"]), author=e(c.get("author", "")),
        links="".join(top_links), toc=toc, resume=resume_card(chapters),
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


FONT_LINK = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
             '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
             '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@100..125,500..800'
             '&family=Source+Serif+4:ital,opsz,wght@0,8..60,400..700;1,8..60,400..700&display=swap">')

BASE_CSS = """/* Clean Teal, matched to the videos and the compendium pages: flat cards, bold teal titles,
   muted letter-spaced eyebrows, outlined teal part circles. Same palette and typefaces as the compendium.
   Every page is dark by default. Light applies only when the reader picks it with the
   Light mode button (saved as tm-theme, shared by every page on the site). */
:root {
  --bg:#12161C; --card:#1A2029; --text:#E7ECF2; --muted:#9AA5B4; --line:#2D3643; --soft:#242C37;
  --teal:#56B8C9; --teal-ink:#0E1A20; --tint:#173238; --coral:#F28D70; --pending:#4A5463;
  --ok:#6CCB8E; --ok-ink:#0E1A20;
  --f-display:"Archivo","Arial Narrow",Arial,sans-serif;
  --f-body:"Source Serif 4",Georgia,"Times New Roman",serif;
  --f-ui:"Archivo",Arial,"Helvetica Neue",Helvetica,sans-serif;
  color-scheme:dark;
}
:root[data-theme="light"] {
  --bg:#F3F5F8; --card:#FFFFFF; --text:#1F2633; --muted:#5B6576; --line:#D8DEE7; --soft:#E9EDF3;
  --teal:#1F7A8C; --teal-ink:#FFFFFF; --tint:#E2F0F2; --coral:#D9573B; --pending:#C3CAD5;
  --ok:#22764A; --ok-ink:#FFFFFF;
  color-scheme:light;
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font:500 16px/1.5 var(--f-ui); -webkit-font-smoothing:antialiased; }
a { color:var(--teal); }
.topline { display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; }
.theme-btn { font:700 13px var(--f-ui); color:var(--muted); background:none;
  border:1.5px solid var(--line); border-radius:999px; padding:5px 12px; cursor:pointer; }
.theme-btn:hover { color:var(--teal); border-color:var(--teal); }
.theme-btn:focus-visible { outline:2px solid var(--teal); outline-offset:2px; }"""

# Dark is the default. A saved Light choice is applied before the page paints, so it never flashes dark first.
THEME_HEAD = ("<script>try{if(localStorage.getItem('tm-theme')==='light')"
              "document.documentElement.setAttribute('data-theme','light')}catch(e){}</script>")
THEME_BTN = '<button class="theme-btn" id="themeBtn" type="button">Light mode</button>'
THEME_JS = """<script>
(function () {
  var b = document.getElementById('themeBtn'), root = document.documentElement;
  if (!b) return;
  function light() { return root.getAttribute('data-theme') === 'light'; }
  function label() { b.textContent = light() ? 'Dark mode' : 'Light mode'; }
  b.addEventListener('click', function () {
    var next = light() ? 'dark' : 'light';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('tm-theme', next); } catch (e) {}
    label();
  });
  label();
})();
</script>"""


VIDEO_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Section {sec} Example {n}</title>
<meta name="description" content="Video walkthrough of Example {n} in Section {sec} of OpenStax College Algebra 2e: {title}.">
{font_link}
{theme_head}
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
.step .arrow {{ flex:none; width:40px; height:40px; border-radius:50%; display:grid; place-items:center; background:var(--teal); color:var(--teal-ink); }}
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
  <div class="topline"><div class="eyebrow">Section {sec} · Example {n}</div>{theme_btn}</div>
  <h1>{title}</h1>
  {player}
  <nav class="steps">{prev}{next}</nav>{tryit}
  {resources}
  <p class="quiet"><a href="{home}#{anchor}">All examples</a>{yt}</p>
</div>{scripts}{mark_js}
{theme_js}
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
    # Opening a posted video's page counts as watching it: the home page reads this to show checkmarks and "Up next".
    mark_js = ""
    if is_posted(ex) and vid:
        key = slug("ex", sec["number"], ex["n"])
        mark_js = ("\n<script>try{var s=JSON.parse(localStorage.getItem('tm-watched')||'{}')||{};"
                   f"s['{key}']=true;localStorage.setItem('tm-watched',JSON.stringify(s))}}catch(e){{}}</script>")
    return VIDEO_TEMPLATE.format(
        base_css=BASE_CSS, font_link=FONT_LINK, theme_head=THEME_HEAD, theme_btn=THEME_BTN, theme_js=THEME_JS, mark_js=mark_js,
        title=title, sec=e(sec["number"]), n=ex["n"], player=player, home=home,
        anchor=slug("ex", sec["number"], ex["n"]), yt=yt, resources=resources,
        tryit=try_it_block(sec, ex), head_extra=head_extra, scripts=scripts,
        prev=step_link("prev", prev, home), next=step_link("next", nxt, home))


def fill(template, **parts):
    """Put each part where its %%NAME%% marker sits (the index template holds raw CSS and JS, so no str.format)."""
    for k, v in parts.items():
        template = template.replace(f"%%{k.upper()}%%", v)
    assert "%%" not in template, "unfilled marker in the index template"
    return template


INDEX_CSS = """
/* Home page. One 940px column: the course intro beside a "start here" card, then one card per section
   (title and the visitor's progress, link cards, examples grouped by skill). */
html { scroll-behavior:smooth; }
@media (prefers-reduced-motion:reduce) { html { scroll-behavior:auto; } }
h1, h2, h3, h4, p { margin:0; }
h1, h2, h3, h4 { font-family:var(--f-display); text-wrap:balance; }
a:focus-visible, button:focus-visible, summary:focus-visible, input:focus-visible { outline:3px solid var(--teal); outline-offset:2px; border-radius:6px; }
[hidden] { display:none !important; }
.wrap { max-width:940px; margin:0 auto; padding:0 16px 64px; }
.eyebrow { font:600 12.5px var(--f-display); letter-spacing:.14em; text-transform:uppercase; color:var(--muted); }

.top { display:grid; grid-template-columns:minmax(0,1.25fr) minmax(0,1fr); gap:24px 40px; align-items:center; padding:30px 0 22px; }
h1 { font-weight:800; font-stretch:112%; font-size:clamp(30px,4.4vw,42px); line-height:1.05; letter-spacing:-.012em; margin:10px 0 14px; }
h1 span { color:var(--teal); display:block; }
.lead { font:400 18px/1.55 var(--f-body); max-width:32em; }
.chips { display:flex; flex-wrap:wrap; gap:8px 22px; margin-top:16px; }
.chip { display:inline-flex; align-items:center; gap:7px; font-weight:700; font-size:15px; text-decoration:none; color:var(--teal); }
.chip:hover span { text-decoration:underline; }
.chip svg, .watch svg, .kind svg, .play svg { width:15px; height:15px; fill:currentColor; flex:none; }

.resume { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px; }
.resume .k { font:800 12px var(--f-display); letter-spacing:.12em; text-transform:uppercase; color:var(--teal); margin-bottom:10px; }
.resume-link { display:grid; grid-template-columns:minmax(0,148px) minmax(0,1fr); gap:14px; align-items:center; text-decoration:none; color:var(--text); }
.resume-link .where { display:block; font-size:13px; font-weight:700; color:var(--muted); }
.resume-link .t { display:block; font:700 16px/1.25 var(--f-display); margin-top:3px; }
a.resume-link:hover .t { color:var(--teal); }
.resume-meta { margin-top:12px; padding-top:10px; border-top:1px solid var(--line); font-size:13px; color:var(--muted); font-variant-numeric:tabular-nums; }
.resume.complete .resume-link { grid-template-columns:1fr; }
.resume.complete .thumb { display:none; }
.resume.complete .k { color:var(--ok); }

.thumb { position:relative; display:block; aspect-ratio:16/9; max-width:100%; border-radius:8px; overflow:hidden; border:1px solid var(--line); background:var(--soft); }
.thumb img { display:block; width:100%; height:100%; object-fit:cover; }
.thumb .dur { position:absolute; right:4px; bottom:4px; background:rgba(15,20,28,.85); color:#fff; font:700 11px var(--f-ui); padding:1px 5px; border-radius:4px; font-variant-numeric:tabular-nums; }
.thumb .play { position:absolute; left:50%; top:50%; width:36px; height:36px; margin:-18px 0 0 -18px; border-radius:50%; background:var(--teal); color:var(--teal-ink); display:grid; place-items:center; }
.thumb .play svg { margin-left:2px; }

.how { list-style:none; margin:0; padding:0; display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; counter-reset:how; }
.how li { counter-increment:how; position:relative; padding:12px 14px 12px 50px; border:1px solid var(--line); border-radius:12px; font-size:14px; color:var(--muted); line-height:1.4; }
.how li::before { content:counter(how); position:absolute; left:14px; top:13px; width:26px; height:26px; border-radius:50%; border:1.5px solid var(--teal); color:var(--teal); font:800 14px/23px var(--f-display); text-align:center; }
.how b { display:block; color:var(--text); font:700 15.5px var(--f-display); }

.toolbar { position:sticky; top:0; z-index:20; background:var(--bg); padding:12px 0 10px; margin-top:22px; display:flex; gap:10px 18px; align-items:center; flex-wrap:wrap; border-bottom:1px solid var(--line); }
.search { flex:1 1 260px; min-width:0; padding:10px 14px; font:500 15px var(--f-ui); border:1px solid var(--line); border-radius:10px; background:var(--card); color:var(--text); }
.search::placeholder { color:var(--muted); }
.toc { display:flex; gap:6px 16px; flex-wrap:wrap; font-size:14px; }
.toc a { text-decoration:none; font-weight:700; }
.toc a:hover { text-decoration:underline; }

.chapter { margin-top:30px; scroll-margin-top:90px; }
.chapter > h2 { font-size:27px; font-weight:750; font-stretch:108%; line-height:1.15; display:flex; flex-direction:column; gap:4px; }
.section { background:var(--card); border:1px solid var(--line); border-radius:14px; margin-top:14px; scroll-margin-top:90px; overflow:hidden; }
.section > summary { list-style:none; cursor:pointer; display:grid; grid-template-columns:minmax(0,1fr) auto auto; column-gap:16px; align-items:center; padding:16px 20px 14px; }
.section > summary::-webkit-details-marker { display:none; }
.section > summary::after { content:""; width:8px; height:8px; border-right:2px solid var(--muted); border-bottom:2px solid var(--muted); transform:rotate(45deg); transition:transform .15s; }
.section[open] > summary::after { transform:rotate(225deg); }
.sec-title { display:block; font:750 22px/1.2 var(--f-display); color:var(--teal); margin-top:2px; }
.sec-meta { display:block; font-size:13.5px; color:var(--muted); margin-top:3px; font-variant-numeric:tabular-nums; }
.sec-count { display:flex; flex-direction:column; align-items:flex-end; gap:6px; font-size:13px; font-weight:700; color:var(--muted); font-variant-numeric:tabular-nums; }
.sec-count.all { color:var(--ok); }
.bar { width:96px; height:6px; border-radius:3px; background:var(--soft); overflow:hidden; }
.bar span { display:block; height:100%; width:0; background:var(--teal); transition:width .2s; }
.sec-count.all .bar span { background:var(--ok); }
.sec-body { padding:0 20px 8px; }

.tiles { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:10px; }
.tile { display:flex; flex-direction:column; gap:3px; min-width:0; text-decoration:none; color:var(--text); border:1px solid var(--line); border-radius:12px; padding:12px 14px; background:var(--bg); }
.tile:hover { border-color:var(--teal); }
.tile .kind { display:flex; align-items:center; gap:7px; font:800 11px var(--f-display); letter-spacing:.1em; text-transform:uppercase; color:var(--teal); }
.tile b { font:700 15.5px/1.25 var(--f-display); }
.tile small { font-size:13px; color:var(--muted); line-height:1.35; }
.tile.main { grid-column:span 2; background:var(--tint); border-color:transparent; }
.tile.main:hover { border-color:var(--teal); }
.tile.main b { font-size:17px; }
.tile .pill { align-self:flex-start; margin-top:6px; font:700 12px var(--f-ui); color:var(--teal-ink); background:var(--teal); border-radius:999px; padding:2px 10px; font-variant-numeric:tabular-nums; }

.group { margin-top:18px; }
.group h4 { display:flex; align-items:center; gap:9px; font:700 13px var(--f-display); letter-spacing:.08em; text-transform:uppercase; color:var(--muted); padding-bottom:8px; }
.group h4 b { font:800 12.5px/1 var(--f-display); letter-spacing:0; color:var(--teal-ink); background:var(--teal); border-radius:5px; padding:4px 6px; }
.examples { list-style:none; margin:0; padding:0; }
.ex { display:grid; grid-template-columns:32px 112px minmax(0,1fr) auto; gap:14px; align-items:center; padding:10px 0; border-top:1px solid var(--line); scroll-margin-top:90px; }
.num { width:32px; height:32px; border-radius:50%; display:grid; place-items:center; font:700 14.5px var(--f-display); border:1.5px solid var(--teal); color:var(--teal); background:transparent; padding:0; }
button.num { cursor:pointer; }
button.num:hover { background:var(--tint); }
.ex.watched .num { background:var(--ok); border-color:var(--ok); color:var(--ok-ink); }
.pending .num { border-color:var(--pending); color:var(--muted); }
.ex-title { display:block; text-decoration:none; color:var(--text); font:600 16px/1.3 var(--f-ui); }
a.ex-title:hover { color:var(--teal); }
.pending .ex-title { color:var(--muted); }
.ex:target .ex-title { color:var(--coral); }
.ex:target .num { border-color:var(--coral); color:var(--coral); }
.ex-meta { display:flex; gap:6px 14px; flex-wrap:wrap; margin-top:3px; font-size:13px; color:var(--muted); }
.ex-meta a { font-weight:700; text-decoration:none; font-size:13px; }
.ex-meta a:hover { text-decoration:underline; }
.watch { display:inline-flex; align-items:center; gap:6px; background:var(--teal); color:var(--teal-ink); text-decoration:none; font:700 14px var(--f-ui); padding:8px 14px; border-radius:8px; }
.watch svg { width:13px; height:13px; }
.watch:hover { filter:brightness(1.08); }
.ex.watched .watch { background:transparent; color:var(--teal); box-shadow:inset 0 0 0 1.5px var(--teal); }
.soon { font-size:13px; color:var(--muted); }
.empty { display:none; color:var(--muted); padding:24px 0; }
footer { margin-top:44px; padding-top:16px; border-top:1px solid var(--line); font-size:13px; color:var(--muted); display:grid; gap:6px; max-width:62em; }
.linkbtn { font:inherit; color:var(--teal); background:none; border:0; padding:0; cursor:pointer; text-decoration:underline; }

@media (max-width:820px) {
  .top { grid-template-columns:1fr; padding-top:22px; }
  .how { grid-template-columns:1fr; }
  .tiles { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .tile.main { grid-column:1/-1; }
}
@media (max-width:560px) {
  .section > summary { padding:14px 14px 12px; column-gap:10px; }
  .sec-body { padding:0 14px 6px; }
  .bar { width:64px; }
  .tiles { grid-template-columns:1fr; }
  .ex { grid-template-columns:30px 92px minmax(0,1fr); gap:10px; }
  .num { width:30px; height:30px; }
  .watch, .ex .soon { display:none; }
  .resume-link { grid-template-columns:minmax(0,120px) minmax(0,1fr); }
}
"""

INDEX_JS = """
(function () {
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  /* Watched examples, saved in this browser only. A video page adds itself when it is opened;
     the number circles here let a visitor mark or unmark one by hand. */
  var KEY = 'tm-watched', seen = {};
  function load() { try { seen = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { seen = {}; } }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(seen)); } catch (e) {} }
  var rows = $$('.ex.posted'), card = $('#resume'), link = card && $('.resume-link', card);

  function paint() {
    rows.forEach(function (r) {
      var on = !!seen[r.id], b = $('.num', r);
      r.classList.toggle('watched', on);
      b.setAttribute('aria-pressed', on);
      b.textContent = on ? '\\u2713' : r.getAttribute('data-n');
      b.setAttribute('aria-label', (on ? 'Unmark' : 'Mark') + ' Example ' + r.getAttribute('data-n') + ' as watched');
      $('.watch span', r).textContent = on ? 'Watch again' : 'Watch';
    });
    $$('.section').forEach(function (s) {
      var rs = $$('.ex.posted', s), c = $('.sec-count', s);
      if (!rs.length) { c.hidden = true; return; }
      var d = rs.filter(function (r) { return seen[r.id]; }).length, all = d === rs.length;
      $('.cnt', c).textContent = all ? '\\u2713 All ' + d + ' watched' : d + ' of ' + rs.length + ' watched';
      $('.bar span', c).style.width = (100 * d / rs.length) + '%';
      c.classList.toggle('all', all);
    });
    $$('.pill[data-try-key]').forEach(function (p) {
      var done = 0, total = +p.getAttribute('data-try-total');
      try {
        var t = (JSON.parse(localStorage.getItem(p.getAttribute('data-try-key')) || '{}') || {}).t || {};
        for (var k in t) if (t[k]) done++;
      } catch (e) {}
      p.textContent = 'Try Its ' + Math.min(done, total) + '/' + total;
      p.hidden = false;
    });
    if (!card) return;
    var done = rows.filter(function (r) { return seen[r.id]; }).length;
    var next = rows.filter(function (r) { return !seen[r.id]; })[0];
    card.classList.toggle('complete', !next);
    if (next) {
      $('.k', card).textContent = done ? 'Up next' : 'Start here';
      link.setAttribute('href', $('.ex-title', next).getAttribute('href'));
      $('img', link).src = $('.thumb img', next).src;
      var from = $('.thumb .dur', next), to = $('.dur', link);
      if (to) { to.textContent = from ? from.textContent : ''; to.hidden = !from; }
      $('.where', link).textContent = 'Section ' + next.getAttribute('data-sec') + ' \\u00b7 Example ' + next.getAttribute('data-n');
      $('.t', link).textContent = $('.ex-title', next).textContent;
    } else {
      $('.k', card).textContent = '\\u2713 All caught up';
      var href = card.getAttribute('data-done-href');
      if (href) {
        link.setAttribute('href', href);
        $('.where', link).textContent = 'Next step';
        $('.t', link).textContent = card.getAttribute('data-done-text');
      } else {
        link.removeAttribute('href');
        $('.where', link).textContent = '';
        $('.t', link).textContent = 'You have watched every example posted so far.';
      }
    }
    $('.resume-meta', card).textContent = done + ' of ' + rows.length + ' examples watched';
  }
  rows.forEach(function (r) {
    $('.num', r).addEventListener('click', function () { seen[r.id] = !seen[r.id]; save(); paint(); });
  });
  var reset = $('#resetSeen');
  if (reset) reset.addEventListener('click', function () { seen = {}; save(); paint(); });
  /* Coming back from a video page (also with the Back button) picks up the new checkmark. */
  window.addEventListener('pageshow', function () { load(); paint(); });
  load(); paint();

  /* Search */
  var box = $('.search'), all = $$('.ex'), empty = $('.empty');
  box.addEventListener('input', function () {
    var q = box.value.trim().toLowerCase(), any = false;
    all.forEach(function (r) {
      var hit = !q || r.getAttribute('data-search').indexOf(q) !== -1;
      r.hidden = !hit;
      if (hit) any = true;
    });
    $$('.group').forEach(function (g) { g.hidden = !$$('.ex', g).some(function (r) { return !r.hidden; }); });
    $$('.section').forEach(function (s) {
      var vis = $$('.ex', s).some(function (r) { return !r.hidden; });
      s.hidden = !vis;
      if (q && vis) s.open = true;
    });
    $$('.chapter').forEach(function (c) { c.hidden = !$$('.section', c).some(function (s) { return !s.hidden; }); });
    empty.style.display = any ? 'none' : 'block';
  });
})();
"""

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%%TITLE%%</title>
<meta name="description" content="%%TAGLINE%%">
%%FONT_LINK%%
%%THEME_HEAD%%
<style>
%%BASE_CSS%%
%%INDEX_CSS%%
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div>
      <div class="topline"><div class="eyebrow">OpenStax College Algebra 2e</div>%%THEME_BTN%%</div>
      <h1>%%HEADLINE%%</h1>
      <p class="lead">%%TAGLINE%%</p>
      <div class="chips">%%LINKS%%</div>
    </div>
    %%RESUME%%
  </header>
  <ol class="how">
    <li><b>Watch the example</b>A few minutes each, in textbook order.</li>
    <li><b>Do its Try It</b>A matching problem under every video, with a hint and the answer.</li>
    <li><b>Check the whole section</b>A finished section has a Compendium: every example, the formulas, and a practice set.</li>
  </ol>
  <div class="toolbar">
    <input class="search" type="search" placeholder="Search examples or a section number" aria-label="Search examples">
    <nav class="toc" aria-label="Chapters">%%TOC%%</nav>
  </div>
  <main>%%CHAPTERS%%
    <p class="empty">No examples match that search.</p>
  </main>
  <footer>
    <p>Your checkmarks are saved in this browser only. <button type="button" class="linkbtn" id="resetSeen">Clear my checkmarks</button></p>
    <p>Examples are adapted from <a href="https://openstax.org/details/books/college-algebra-2e">College Algebra 2e</a>
    by Jay Abramson, OpenStax, under a CC BY 4.0 license. These videos are not affiliated with or endorsed by OpenStax.
    Made by %%AUTHOR%%.</p>
  </footer>
</div>
<script>%%INDEX_JS%%</script>
%%THEME_JS%%
</body>
</html>
"""

if __name__ == "__main__":
    try:
        build()
    except Exception as exc:  # keep errors readable for non-programmers
        sys.exit(f"Build failed: {exc}")
