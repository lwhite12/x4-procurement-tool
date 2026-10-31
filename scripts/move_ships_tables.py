"""One-off: relocates the 4 ships-table keys already uploaded to Tigris
(see upload_ships_tables.py) from the bucket root into shares/component_analyzer_tables/,
keeping the same bare key names.

S3-compatible storage has no native rename/move -- this does the standard
copy-then-delete-the-original two-step. Run on the Fly VM (same reason as
upload_ships_tables.py: AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/
AWS_ENDPOINT_URL_S3/BUCKET_NAME only exist there, not locally):

    python3 move_ships_tables.py
"""

import os

import boto3

KEYS = ["s_ships", "m_ships", "l_ships", "xl_ships"]
NEW_PREFIX = "shares/component_analyzer_tables/"


def main() -> None:
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["AWS_ENDPOINT_URL_S3"],
        region_name=os.environ.get("AWS_REGION", "auto"),
    )
    bucket = os.environ["BUCKET_NAME"]

    for key in KEYS:
        new_key = f"{NEW_PREFIX}{key}"
        client.copy_object(Bucket=bucket, CopySource={"Bucket": bucket, "Key": key}, Key=new_key)
        client.delete_object(Bucket=bucket, Key=key)
        print(f"moved {key} -> {new_key}")


if __name__ == "__main__":
    main()
