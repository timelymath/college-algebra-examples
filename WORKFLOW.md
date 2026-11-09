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

When the section is done, Claude makes its one-page summary PDF and attaches it to the section with `add_resource.py <s> guide …`. It shows only on the index, next to the section playlist, review video and Compendium links.

Once all of a section's videos are done, it can also get a **Section Compendium**: our streamlined rewrite of the section, with a QR code for every example video (model: 8.1). Its source is in `OCA/Claude outputs/8.1 textbook mockup/` (`template.html` + `build.py`, which writes `compendium/8.1.html` here). Add `compendium: compendium/<s>.html` to the section in `course.yaml`; the page is served at `<s>/compendium/`, and its "Section <s> Compendium" link replaces "Read the section" on the index.

### 4. Changing the design

Change `build.py` once. Every page picks up the change on the next build.

## Good to know

- **Video pages:** every example with a video link has its own page, e.g. `.../8.1/6/`. The index's Watch buttons open it. A scheduled video's page says "Coming Nov 11" until it goes public. Previous and Next stand in for YouTube's end screen, which doesn't reliably show in embedded players.
- **Try It:** a video page shows its example's Try It under the Previous and Next buttons, with the hint and the answer collapsed. The math is rendered by KaTeX (from cdnjs), loaded only on pages that have a Try It. Nothing else goes on video pages; section resources show on the index only (Dan, 2026-11-08).
- **No slides:** the site doesn't post slides (Dan, 2026-11-08). Chapter 1's slide files were removed; they're in the git history.
- **Deep links:** every example has its own address, e.g. `.../#ex-8-1-6`, and every section too (`#sec-8-2`). Study guides or video descriptions can point straight to a spot on the page.
- **Feed limit:** each playlist feed shows its newest 15 videos, more than any section has so far. A nightly run covers that as long as fewer than 15 videos post in a day. For bulk uploads, run the workflow between batches, or switch the sync to the YouTube Data API, which uses a free key.
- **Tested 2026-11-08:** the sync matched 8.1 Ex 1 and Ex 7 from the 8.1 playlist feed, and skipped the private 8.2 playlist.
