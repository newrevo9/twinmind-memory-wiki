import logging
import re

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


def _client():
    return boto3.client(
        "s3",
        endpoint_url=f"http{'s' if settings.minio_use_ssl else ''}://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        region_name="us-east-1",
    )


def ensure_bucket_exists() -> None:
    s3 = _client()
    try:
        s3.head_bucket(Bucket=settings.minio_bucket)
    except ClientError:
        s3.create_bucket(Bucket=settings.minio_bucket)
        logger.info("Created bucket: %s", settings.minio_bucket)


def put_object(path: str, content: str) -> None:
    _client().put_object(
        Bucket=settings.minio_bucket,
        Key=path.lstrip("/"),
        Body=content.encode("utf-8"),
        ContentType="text/markdown; charset=utf-8",
    )


def get_object(path: str) -> str | None:
    try:
        response = _client().get_object(Bucket=settings.minio_bucket, Key=path.lstrip("/"))
        return response["Body"].read().decode("utf-8")
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return None
        raise


def object_exists(path: str) -> bool:
    try:
        _client().head_object(Bucket=settings.minio_bucket, Key=path.lstrip("/"))
        return True
    except ClientError:
        return False


def list_objects(prefix: str = "") -> list[dict]:
    s3 = _client()
    prefix = prefix.lstrip("/")
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    response = s3.list_objects_v2(
        Bucket=settings.minio_bucket,
        Prefix=prefix,
        Delimiter="/",
    )

    entries: list[dict] = []

    for cp in response.get("CommonPrefixes", []):
        dir_key = cp["Prefix"].rstrip("/")
        entries.append(
            {
                "name": dir_key.split("/")[-1],
                "path": "/" + dir_key,
                "type": "directory",
                "size": None,
                "last_modified": None,
            }
        )

    for obj in response.get("Contents", []):
        key = obj["Key"]
        name = key.split("/")[-1]
        if name:
            entries.append(
                {
                    "name": name,
                    "path": "/" + key,
                    "type": "file",
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                }
            )

    return entries


def grep_objects(pattern: str, prefix: str = "") -> list[dict]:
    s3 = _client()
    prefix = prefix.lstrip("/")

    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error:
        compiled = re.compile(re.escape(pattern), re.IGNORECASE)

    paginator = s3.get_paginator("list_objects_v2")
    matches: list[dict] = []

    for page in paginator.paginate(Bucket=settings.minio_bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".md"):
                continue
            try:
                content = get_object(key)
                if content is None:
                    continue
                for line_num, line in enumerate(content.splitlines(), 1):
                    if compiled.search(line):
                        matches.append(
                            {
                                "path": "/" + key,
                                "line_number": line_num,
                                "line": line.strip(),
                            }
                        )
            except Exception:
                logger.warning("Could not read %s for grep", key, exc_info=True)

    return matches
