"""One-off upload of the 4 size-tier ships-table JSON files to Tigris.

Run this wherever AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/AWS_ENDPOINT_URL_S3/
BUCKET_NAME are already set (e.g. `fly ssh console`, or your own shell if you
keep a local .env for Tigris) -- same env vars share_storage.py's own
get_client() reads, see that module's docstring. Not wired into api.py; this
is a standalone script for a manual upload, run once from the command line:

    python upload_ships_tables.py [data_dir]

`data_dir` defaults to this script's own directory, so copying/sftp-ing the
script and the 4 JSON files into the same folder (locally or on the Fly VM)
is enough -- no hardcoded Downloads/home-directory path to break across
machines.

Uploads each file under shares/component_analyzer_tables/<key>.json -- the
exact same key shape share_storage.py's own _key() builds for a real
UUID-based share, just with a readable id in place of a uuid, so these are
loadable through the app's EXISTING share-link mechanism (a
?share_component_analyzer_tables=<id> query param -- see
applyShareLinksFromUrl() in app.js) with no code changes needed. Overwrites
whatever is already at that key.
"""

import os
import sys
from pathlib import Path

import boto3

DATA_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
KEY_PREFIX = "shares/component_analyzer_tables/"

FILES = {
    "s_ships": DATA_DIR / "small_ships_components.json",
    "m_ships": DATA_DIR / "medium_ships_components.json",
    "l_ships": DATA_DIR / "large_ships_components.json",
    "xl_ships": DATA_DIR / "xl_ships_components.json",
}


def main() -> None:
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["AWS_ENDPOINT_URL_S3"],
        region_name=os.environ.get("AWS_REGION", "auto"),
    )
    bucket = os.environ["BUCKET_NAME"]

    for key, path in FILES.items():
        if not path.exists():
            print(f"SKIPPED {key}: {path} not found")
            continue
        body = path.read_bytes()
        full_key = f"{KEY_PREFIX}{key}.json"
        client.put_object(Bucket=bucket, Key=full_key, Body=body, ContentType="application/json")
        print(f"uploaded {full_key} <- {path} ({len(body)} bytes)")


if __name__ == "__main__":
    main()
