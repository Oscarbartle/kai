"""ETag helpers for optimistic concurrency on record-level writes.

Usage:
  - On GET: set `ETag: "<hash>"` in the response.
  - On PUT/DELETE: read `If-Match` header; call `check_etag(record, if_match)`
    which raises 412 if the record has changed since the client last fetched it.
"""
import hashlib
import json

from fastapi import Header, HTTPException
from typing import Annotated


def record_etag(record: dict) -> str:
    """Return a stable ETag for a record dict."""
    blob = json.dumps(record, sort_keys=True, default=str).encode()
    return hashlib.sha1(blob).hexdigest()[:16]


def check_etag(record: dict, if_match: str | None) -> None:
    """Raise 412 if the record's current ETag doesn't match *if_match*."""
    if if_match is None:
        raise HTTPException(
            status_code=428,
            detail="If-Match header required for mutating requests.",
        )
    current = record_etag(record)
    # Strip surrounding quotes if present (RFC 7232 format)
    client_tag = if_match.strip('"')
    if client_tag != current:
        raise HTTPException(
            status_code=412,
            detail="Precondition failed — record has changed. Refetch and retry.",
        )
