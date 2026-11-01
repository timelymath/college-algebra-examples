# Course Index Site: How It Works

A static website listing every College Algebra 2e example video in textbook order, with room for extra resources at the chapter, section, and example levels. It's hosted free on GitHub Pages.

## What's in the repo

| File | What it does |
|---|---|
| `data/course.yaml` | **The only file that changes day to day.** Chapters → sections → examples, with video links and resources. |
| `build.py` | Turns the data file into `site/index.html`, plus a clean page per video (`site/1.1/6/`): the YouTube embed, Previous and Next links, and a link back to the index. |
| `sync_youtube.py` | Fills in video links from the course playlist. |
| `add_resource.py` | Attaches a study guide, worksheet, slides, or link to a chapter, section, or example. |
| `files/` | PDFs and other files the site links to (e.g. `files/ch1/1.1-study-guide.pdf`). |
| `.github/workflows/publish.yml` | Rebuilds and publishes the site automatically. |

## Setup (done 2026-11-01)

- Repository: `timelymath/college-algebra-examples` (public), cloned on Dan's Mac at `OCA/_site/college-algebra-examples/`.
- Pages: Source is GitHub Actions. The site is at https://timelymath.github.io/college-algebra-examples/
- Claude pushes with the `gh` sign-in on the Mac (account `timelymath`), so no separate token is needed.
- Local builds use the repo's `.venv` (`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`), since the system Python has no PyYAML.

## Day to day

### 1. A video goes up on YouTube: nothing to do

A video scheduled ahead can be listed early: give it its `video:` link and `public_at: "2026-11-02T15:00:00Z"`. The page shows "Coming Nov 2" until that time and the Watch button on the first build after it.

Every video description already includes the line `From Section 1.1, Real Numbers: Algebra Essentials (Example 6)`. Each night at 3:17 am Eastern (and again at 15:17 UTC, just after scheduled releases), GitHub:

1. reads the playlist's public feed (no API key needed),
2. matches each video to its exact example using that line,
3. saves the link into `course.yaml`, and
4. rebuilds and republishes the site.

Want it live sooner? Open the repo's **Actions** tab and click **Run workflow**.

Existing links are never overwritten, and videos that don't match an example (a channel trailer, say) are skipped.

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

When Claude drafts a new section's decks, it adds that section's example list to `course.yaml` in the same session. The examples show as "Coming soon" until their videos post.

### 4. Changing the design

Change `build.py` once. Every page picks up the change on the next build.

## Good to know

- **Video pages:** every example with a video link has its own page, e.g. `.../1.1/6/`. The index's Watch buttons open it. A scheduled video's page says "Coming Nov 11" until it goes public. Previous and Next stand in for YouTube's end screen, which doesn't reliably show in embedded players.
- **Deep links:** every example has its own address, e.g. `.../#ex-1-1-6`, and every section too (`#sec-1-2`). Study guides or video descriptions can point straight to a spot on the page.
- **Feed limit:** YouTube's playlist feed shows the newest 15 videos. A nightly run covers that as long as fewer than 15 videos post in a day. For bulk uploads, run the workflow between batches, or switch the sync to the YouTube Data API, which uses a free key.
- **Tested live 2026-11-01:** the sync matched 1.1 Ex 1 from the real playlist feed.
