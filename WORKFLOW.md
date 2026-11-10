# Course Index Site: How It Works

A static website listing every College Algebra 2e example video in textbook order, with room for extra resources at the chapter, section, and example levels. It's hosted free on GitHub Pages.

## What's in the repo

| File | What it does |
|---|---|
| `data/course.yaml` | **The only file that changes day to day.** Chapters → sections → examples, with video links and resources. |
| `build.py` | Turns the data file into `site/index.html`, plus a clean page per video (`site/8.1/6/`): the YouTube embed, Previous and Next links, and a link back to the index. Only released sections appear. |
| `sync_youtube.py` | Fills in video links from each section's playlist. |
| `add_resource.py` | Attaches a study guide, worksheet, slides, or link to a chapter, section, or example. |
| `files/` | PDFs and other files the site links to (e.g. `files/ch1/1.1-study-guide.pdf`). |
| `.github/workflows/publish.yml` | Rebuilds and publishes the site automatically. |

## Setup (done 2026-11-01)

- Repository: `timelymath/college-algebra-examples` (public), cloned on Dan's Mac at `OCA/_site/college-algebra-examples/`.
- Pages: Source is GitHub Actions. The site is at https://timelymath.github.io/college-algebra-examples/
- Claude pushes with the `gh` sign-in on the Mac (account `timelymath`), so no separate token is needed.
- Local builds use the repo's `.venv` (`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`), since the system Python has no PyYAML.

## Day to day

### 1. A section is released: nothing to do

Since 2026-11-08 the course is released a section at a time: Dan uploads a section's videos privately into its own playlist, then makes the videos and the playlist public together. There's no course-wide playlist for now, and Chapter 8 is the first chapter on the site (Chapter 1 comes back later).

Each section in `course.yaml` has `playlist_id`, `playlist_url` and, once it exists, `review` (the section review video, which isn't in the playlist). A section stays off the page until one of its examples has a `video:` link, so a section in progress is simply absent.

Every video description includes a line like `From Section 8.2, The Hyperbola (Example 1)`. Each night at 3:17 am Eastern (and again at 15:17 UTC), GitHub:

1. reads each section playlist's public feed (no API key needed; a private playlist has no feed, so it's skipped until release),
2. matches each video to its exact example using that line,
3. saves the link into `course.yaml`, and
4. rebuilds and republishes the site, which now shows the section with its playlist and review links.

Want it live sooner? Open the repo's **Actions** tab and click **Run workflow**, or Claude adds the links when Dan says the section is public.

Existing links are never overwritten, and videos that don't match an example are skipped.

### 2. A new resource (study guide, worksheet, slides, link): Claude handles it

When Claude makes a study guide, or you ask for a link to be added, Claude runs:

```bash
python3 add_resource.py 1.2 guide "Section 1.2 study guide" "OCA/Guides/1.2 study guide.pdf"
python3 add_resource.py 1.2/13 link "Try it: scientific notation calculator" https://www.desmos.com/scientific
python3 build.py                              # check that it builds
git commit -am "Add 1.2 study guide" && git push
```

The push triggers the workflow, and the site updates in about a minute.

`where` can be `1` (chapter), `1.2` (section), or `1.2/13` (example). `kind` can be `guide`, `worksheet`, `practice`, `slides`, `video`, or `link`.

### 3. A new section starts: Claude adds its examples

When Claude sets up a new section (`/section`), it adds that section's example list to `course.yaml` in the same session, each example with its `try_it:` (the textbook's Try It, a hint and the answer). The section stays off the page until it's released.

For the home page, Claude also adds the section's `skills:` (a `name` and its `examples` for each skill, the same skills as the compendium's path), a `review_note:` (one line under the review card, e.g. "All seven examples in one 23-minute video."), and, once the videos exist, each example's `duration:` ("3:50"). All three are optional: without them the rows show ungrouped, without lengths, and with a generic review line.

When the section is done, Claude makes its one-page summary PDF and attaches it to the section with `add_resource.py <s> guide …`. It shows only on the index, as a card next to the section's Compendium, review video and playlist cards. Give it `tag: Summary`, `label: One-page summary` and `note: Printable PDF.` in `course.yaml` so the card reads well.

Once all of a section's videos are done, it can also get a **Section Compendium**: our streamlined rewrite of the section, with its videos and study tools built in (model: 8.1). See **Section Compendium spec** below.

### 4. Changing the design

Change `build.py` once. Every page picks up the change on the next build.

## Section Compendium spec

The 8.1 page (`8.1/compendium/`) is the model. Build each new one from its source so every section looks and works the same.

**Source and build.** `OCA/Claude outputs/8.1 textbook mockup/`: `template.html` (the page), `build.py` (fills in QR codes, video stills and links; needs `segno`, so run it from a scratch venv) and `frames/` (one still per example video). `build.py` writes `compendium/<s>.html` in this repo plus a claude.ai mockup with dashed "New" notes. For a new section, copy the folder, replace the content, and keep the structure, CSS and scripts. Then add `compendium: compendium/<s>.html` to the section in `course.yaml`; the page is served at `<s>/compendium/`, and its "Section <s> Compendium" link replaces "Read the section" on the index.

**Page order.**

1. Top bar: link back to the index, the page name, and the Light mode button.
2. Header: section number and title, a hook that an example later pays off, a prerequisites line, and an animated or interactive hero figure.
3. Your path: one card per skill (A, B, C…) with its examples, total video time and a Try It count. Beside it: QR tiles for the playlist, the review video and the summary PDF.
4. Section bar (sticks to the top): a link to every part of the page with the current one highlighted, a reading-progress line, the Try It count (tap to jump to the next unfinished one), and a Formulas button that opens the key formulas from anywhere.
5. Concept sections: the big idea with something to drag, the parts with the video color code, and the key formulas side by side on one card, followed by the numbered "moves".
6. Hands-on pair, right after the key formulas: one explorer where sliders drive the equation, the graph and the key points together (8.1: Build an ellipse), and one Quick check that drills the first decision every problem in the section starts with, with a new random question each time.
7. One section per skill: a short routine, then each example as a card with numbered steps, the answer, a figure, and a margin rail with the video still and its QR code. Each example is followed by its Try It.
8. Mistakes to avoid, each linking to the example where it comes up.
9. Summary in four lines, with the summary PDF.
10. Practice: a core set grouped by skill with the book's exercise numbers, each group linking back to its examples.
11. Footer: clear-checkmarks button, OpenStax attribution, Timely Math Tutor credit.

**Study tools every compendium has.**

- Worked examples: a "One step at a time" button hides the steps (and the figure) so students predict each step before revealing it. Everything is shown by default.
- Try It: a hint first (the same hint as `try_it.hint` in `course.yaml`), then the answer, then "I got it" and "Not yet? Back to Example n". "I got it" feeds the counts in the section bar and on the path cards.
- Practice: answers open one problem at a time, and each problem has "Mark done". In the template the answers stay grouped in one `<details class="ans">` per set; the page splits them up after the math is typeset, and the printed answer key is built from the same lists.
- Progress is saved in the student's browser only (`localStorage`, key `oca-<s>-progress`). Change the key and the skill-to-Try-It map (`SK`) in the script for each section.

**Rules.**

- Colors mean the same thing as in the videos. Math is MathJax with the color macros (`\ka`, `\kb`, `\kc`, `\kh`, `\kn`).
- Dark by default, like every page on the site (see Good to know). Paper is always light.
- Phones (900px and under): QR codes are hidden and become tap buttons, since a phone can't scan its own screen. Print keeps the QR codes and hides the interactive tools.
- No page-wide sideways scrolling at phone width. Long equations scroll inside their own box.
- Before publishing, load the page locally and check: no console errors, the section bar highlights as you scroll, every Try It has a hint, each practice problem shows its own answer, and the page looks right at phone width.

## Good to know

- **Dark by default:** every page (index, video pages, compendiums) is dark unless the visitor clicks Light mode. The choice is saved in the browser as `tm-theme` and applies to the whole site. It does not follow the device's light or dark setting (Dan, 2026-11-10). For the index and video pages the colors are in `BASE_CSS` in `build.py`; a compendium carries its own copy in its template.
- **Home page:** a "Start here" card that becomes "Up next" (the first example this visitor hasn't watched, then the newest compendium's practice set once everything is watched), three how-to-use steps, and one card per section: the visitor's own progress, link cards (Compendium first, with their Try It count from the compendium page), and example rows grouped by skill with a thumbnail, length and Try It link. Thumbnails come straight from YouTube (`i.ytimg.com/vi/<id>/mqdefault.jpg`), so a new section needs no image files. Same typefaces (Archivo, Source Serif 4) and colors as the compendium.
- **Watched checkmarks:** opening a posted example's video page marks it watched in that browser (`localStorage`, key `tm-watched`). The home page reads it, and a visitor can mark or unmark an example with its number circle. Nothing is sent anywhere, so checkmarks don't follow a student to another device.
- **Video pages:** every example with a video link has its own page, e.g. `.../8.1/6/`. The index's Watch buttons open it. A scheduled video's page says "Coming Nov 11" until it goes public. Previous and Next stand in for YouTube's end screen, which doesn't reliably show in embedded players.
- **Try It:** a video page shows its example's Try It under the Previous and Next buttons, with the hint and the answer collapsed. The math is rendered by KaTeX (from cdnjs), loaded only on pages that have a Try It. Nothing else goes on video pages; section resources show on the index only (Dan, 2026-11-08).
- **No slides:** the site doesn't post slides (Dan, 2026-11-08). Chapter 1's slide files were removed; they're in the git history.
- **Deep links:** every example has its own address, e.g. `.../#ex-8-1-6`, and every section too (`#sec-8-2`). Study guides or video descriptions can point straight to a spot on the page.
- **Feed limit:** each playlist feed shows its newest 15 videos, more than any section has so far. A nightly run covers that as long as fewer than 15 videos post in a day. For bulk uploads, run the workflow between batches, or switch the sync to the YouTube Data API, which uses a free key.
- **Tested 2026-11-08:** the sync matched 8.1 Ex 1 and Ex 7 from the 8.1 playlist feed, and skipped the private 8.2 playlist.
