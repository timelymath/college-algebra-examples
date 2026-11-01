#!/usr/bin/env python3
"""Attach a resource to a chapter, section, or example.

    python3 add_resource.py <where> <kind> "<label>" <file-or-url>

  <where>  1        chapter 1
           1.2      section 1.2
           1.2/6    section 1.2, example 6
  <kind>   guide | worksheet | practice | slides | video | link

A local file is copied into files/ch<N>/ and linked from there; a URL is
linked as is. Adding the same label twice replaces the earlier entry.

Examples:
    python3 add_resource.py 1.2 guide "Section 1.2 study guide" ~/OCA/Guides/1.2.pdf
    python3 add_resource.py 1.1/5 link "Desmos: sets of numbers" https://www.desmos.com/...
"""
import pathlib
import shutil
import sys

from ruamel.yaml import YAML

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data" / "course.yaml"
KINDS = {"guide", "worksheet", "practice", "slides", "video", "link"}


def find_target(data, where):
    sec_id, _, ex_n = where.partition("/")
    ch_n = int(sec_id.split(".")[0])
    ch = next((c for c in data["chapters"] if int(c["number"]) == ch_n), None)
    if ch is None:
        sys.exit(f"No chapter {ch_n} in the data file.")
    if "." not in sec_id:
        return ch, ch_n
    sec = next((s for s in ch.get("sections") or [] if str(s["number"]) == sec_id), None)
    if sec is None:
        sys.exit(f"No section {sec_id} in the data file.")
    if not ex_n:
        return sec, ch_n
    ex = next((x for x in sec.get("examples") or [] if int(x["n"]) == int(ex_n)), None)
    if ex is None:
        sys.exit(f"No example {ex_n} in section {sec_id}.")
    return ex, ch_n


def main(argv):
    if len(argv) != 4 or argv[1] not in KINDS:
        sys.exit(__doc__)
    where, kind, label, src = argv
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    data = yaml.load(DATA)
    target, ch_n = find_target(data, where)

    if src.startswith(("http://", "https://")):
        url = src
    else:
        path = pathlib.Path(src).expanduser()
        if not path.is_file():
            sys.exit(f"File not found: {path}")
        dest = ROOT / "files" / f"ch{ch_n}" / path.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        url = f"files/ch{ch_n}/{path.name}"

    res = target.get("resources")
    if res is None:
        res = []
        # keep resources above the list of sections/examples, where they're easy to spot
        child = next((k for k in ("sections", "examples") if k in target), None)
        if child:
            target.insert(list(target.keys()).index(child), "resources", res)
        else:
            target["resources"] = res
    res[:] = [r for r in res if r.get("label") != label]
    res.append({"kind": kind, "label": label, "url": url})
    yaml.dump(data, DATA)
    print(f"Added '{label}' to {where} -> {url}")


if __name__ == "__main__":
    main(sys.argv[1:])
