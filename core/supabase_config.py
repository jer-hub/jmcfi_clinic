"""Supabase connection helpers shared by settings and tests."""

import re


def resolve_supabase_s3_region(
    explicit: str,
    supabase_url: str,
    database_url: str,
) -> str:
    """
    Pick the S3 signing region for Supabase Storage.

    Local CLI (`127.0.0.1:54321`) uses ``local``. Hosted projects must use the
    project's AWS region (e.g. ``ap-southeast-1``); ``local`` causes
    SignatureDoesNotMatch / 403 on HeadObject.
    """
    region = (explicit or "").strip()
    is_local_api = bool(
        supabase_url and any(host in supabase_url for host in ("127.0.0.1", "localhost"))
    )
    if is_local_api:
        return region or "local"

    if region and region != "local":
        return region

    pooler_match = re.search(
        r"aws-\d+-([\w-]+)\.pooler\.supabase\.com",
        database_url or "",
        re.IGNORECASE,
    )
    if pooler_match:
        return pooler_match.group(1)

    return region or "us-east-1"
