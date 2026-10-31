"""Uploads every "prebuilt table" JSON in a folder to Tigris, at
shares/component_analyzer_tables/<key>.json -- the generalized successor to
upload_ships_tables.py (kept hardcoded to the original 4 ship files; this one
scans for ANY size-tier x category file instead, so a new category -- shields,
engines, and eventually weapons/missiles/turrets/economy wares -- needs no
script change, just dropping the file in alongside the others).

Run wherever AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/AWS_ENDPOINT_URL_S3/
BUCKET_NAME are already set (e.g. `fly ssh console`) -- see
share_storage.py's own get_client() docstring for why those aren't available
locally by default.

    python upload_prebuilt_tables.py [data_dir]

`data_dir` defaults to this script's own directory. Matches any file named
"<size>_<category>_components.json" (e.g. "small_shields_components.json",
"extra_large_engines_components.json", "xl_ships_components.json" -- both
"xl" and "extra_large" are accepted as the XL size token) and skips anything
ending "_starter.json" (an in-progress/incomplete draft, never meant to
upload). The key uploaded is "<size_code>_<category>" -- e.g.
"small_shields_components.json" -> key "s_shields", matching the
s_ships/m_ships/l_ships/xl_ships convention already live.

Also matches "<category>_components.json" with no size prefix at all, for
component types that don't have a size tier (Economy Wares) or where the
table deliberately mixes every size in one file (Missiles, keyed off
`compatibility`, not a `size` column) -- e.g. "economy_wares_components.json"
-> key "economy_wares", "missiles_components.json" -> key "missiles".
"""

import os
import re
import sys
from pathlib import Path

import boto3

DATA_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
KEY_PREFIX = "shares/component_analyzer_tables/"

SIZE_CODES = {
    "small": "s",
    "medium": "m",
    "large": "l",
    "xl": "xl",
    "extra_large": "xl",
}

SIZED_RE = re.compile(r"^(small|medium|large|xl|extra_large)_([a-z_]+)_components\.json$")
UNSIZED_RE = re.compile(r"^([a-z_]+)_components\.json$")


def discover_files():
    found = {}
    for path in sorted(DATA_DIR.glob("*_components.json")):
        if path.name.endswith("_starter.json"):
            print(f"SKIPPED (starter draft): {path.name}")
            continue
        match = SIZED_RE.match(path.name)
        if match:
            size_token, category = match.groups()
            key = f"{SIZE_CODES[size_token]}_{category}"
            found[key] = path
            continue
        match = UNSIZED_RE.match(path.name)
        if match:
            (category,) = match.groups()
            found[category] = path
            continue
        print(f"SKIPPED (name doesn't match <size>_<category>_components.json): {path.name}")
    return found


def main() -> None:
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["AWS_ENDPOINT_URL_S3"],
        region_name=os.environ.get("AWS_REGION", "auto"),
    )
    bucket = os.environ["BUCKET_NAME"]

    files = discover_files()
    if not files:
        print(f"No matching files found in {DATA_DIR}")
        return

    for key, path in files.items():
        body = path.read_bytes()
        full_key = f"{KEY_PREFIX}{key}.json"
        client.put_object(Bucket=bucket, Key=full_key, Body=body, ContentType="application/json")
        print(f"uploaded {full_key} <- {path.name} ({len(body)} bytes)")


if __name__ == "__main__":
    main()
