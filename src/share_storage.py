"""Reads/writes share-link payloads to Fly's Tigris object storage (S3-compatible).

Provisioned via `fly storage create` (see fly.toml/CHANGELOG) -- that command sets
AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/AWS_ENDPOINT_URL_S3/AWS_REGION/BUCKET_NAME as
Fly app secrets automatically, no manual config beyond running it once. Not configured
for local dev by default; see get_client()'s own docstring.

Each share is one JSON blob under key f"shares/{section}/{uuid}.json" -- section is
part of the key (not just metadata) both so the bucket reads legibly in Tigris's own
console and per the exact API shape requested (GET /api/share/{section}/{uuid}), which
needs the caller to already know the section rather than looking it up from the uuid
alone. `section` is caller-controlled (api.py restricts it to a fixed allow-list before
ever reaching here -- see ShareSection) rather than validated in this module, since this
module has no opinion on what sections exist.
"""

import json
import os
import uuid as uuid_module

import boto3
from botocore.exceptions import ClientError

_client = None


def get_client():
    """Lazily builds (and caches) the S3 client -- lazy so importing this module
    doesn't require Tigris env vars to be set at all (e.g. every other endpoint in
    api.py still works fine locally without them; only share endpoints would fail,
    the first time they're actually used).
    """
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=os.environ["AWS_ENDPOINT_URL_S3"],
            region_name=os.environ.get("AWS_REGION", "auto"),
        )
    return _client


def _bucket() -> str:
    return os.environ["BUCKET_NAME"]


def _key(section: str, share_uuid: str) -> str:
    return f"shares/{section}/{share_uuid}.json"


def put_share(section: str, data: dict | list) -> str:
    """Uploads `data` as a new share under `section`, returning the generated uuid."""
    share_uuid = str(uuid_module.uuid4())
    get_client().put_object(
        Bucket=_bucket(),
        Key=_key(section, share_uuid),
        Body=json.dumps(data).encode("utf-8"),
        ContentType="application/json",
    )
    return share_uuid


def get_share(section: str, share_uuid: str) -> dict | list | None:
    """Returns the shared payload, or None if this section/uuid pair doesn't exist
    (a bad/typo'd link, or one that's since been deleted) -- deliberately not an
    exception, since "not found" is an expected, everyday outcome here, not a bug.
    """
    try:
        response = get_client().get_object(Bucket=_bucket(), Key=_key(section, share_uuid))
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            return None
        raise
    return json.loads(response["Body"].read())
