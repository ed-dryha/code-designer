#!/usr/bin/env python3
"""Write VERSION into every manifest listed in .version-bump.json."""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=ROOT)
    args = ap.parse_args(argv)
    with open(os.path.join(args.root, "VERSION"), encoding="utf-8") as fh:
        version = fh.read().strip()
    with open(os.path.join(args.root, ".version-bump.json"), encoding="utf-8") as fh:
        entries = json.load(fh)["files"]
    for entry in entries:
        path = os.path.join(args.root, entry["path"])
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        data[entry["field"]] = version
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        print(f"{entry['path']}: {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
