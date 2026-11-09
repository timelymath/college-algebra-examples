#!/usr/bin/env python3
"""Fill in video links in data/course.yaml from each section's YouTube playlist (`playlist_id`).

    python3 sync_youtube.py                 # reads the live playlist feed
    python3 sync_youtube.py --feed file.xml # reads a saved feed (for testing)

How it matches: every video description already contains a line like
    From Section 1.1, Real Numbers: Algebra Essentials (Example 6)
so each video lands on exactly the right example, even when two examples
in the book share a title. Videos without that line are matched by exact
title, but only when the title is unique in the course.

It never removes or overwrites a link that's already there. It needs no
API key: it uses YouTube's public RSS feed for each playlist (the newest 15
videos). A private playlist has no feed yet, so it's skipped until the section
is released; sections go public whole, so their links all land on the same night.
A course-level `playlist_id`, if one comes back, is read too.
"""
import argparse
import pathlib
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

from ruamel.yaml import YAML

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data" / "course.yaml"
NS = {"a": "http://www.w3.org/2005/Atom", "media": "http://search.yahoo.com/mrss/"}
LOCATION = re.compile(r"From Section (\d+\.\d+)\b.*?\(Example (\d+)\)")


def read_feed(args, playlist_id):
    if args.feed:
        return pathlib.Path(args.feed).read_bytes()
    url = f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feed", help="path to a saved playlist feed XML")
    args = ap.parse_args()

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=2, offset=0)  # same layout as course.yaml (and site.py)
    data = yaml.load(DATA)

    index, by_title = {}, {}
    for ch in data["chapters"]:
        for sec in ch.get("sections") or []:
            for ex in sec.get("examples") or []:
                index[(str(sec["number"]), int(ex["n"]))] = (sec, ex)
                by_title.setdefault(ex["title"].strip().lower(), []).append((sec, ex))

    ids = [data["course"]["playlist_id"]] if data["course"].get("playlist_id") else []
    ids += [s["playlist_id"] for ch in data["chapters"] for s in ch.get("sections") or [] if s.get("playlist_id")]
    if args.feed:
        ids = ids[:1] or ["feed"]
    entries = []
    for pid in ids:
        try:
            entries += ET.fromstring(read_feed(args, pid)).findall("a:entry", NS)
        except Exception as exc:  # a private playlist has no public feed until its section is released
            print(f"  playlist {pid}: no public feed yet ({exc})")
    added = []
    for entry in entries:
        title = entry.findtext("a:title", "", NS).strip()
        link = entry.find("a:link", NS).get("href")
        desc = entry.findtext("media:group/media:description", "", NS)
        m = LOCATION.search(desc)
        if m:
            hit = index.get((m.group(1), int(m.group(2))))
        else:
            cands = by_title.get(title.lower(), [])
            hit = cands[0] if len(cands) == 1 else None
        if not hit:
            print(f"  skipped (no match): {title}")
            continue
        sec, ex = hit
        if ex.get("video"):
            continue
        ex["video"] = link
        added.append(f'{sec["number"]} Ex {ex["n"]} {ex["title"]}')

    if added:
        yaml.dump(data, DATA)
        print(f"Added {len(added)} video link(s):")
        for a in added:
            print("  +", a)
    else:
        print("No new videos.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.exit(f"Sync failed: {exc}")
