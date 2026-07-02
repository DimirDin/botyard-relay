"""Telegram Mini App `initData` HMAC validation.

This is a hard platform rule, not optional: any data submitted from the Mini App must
be validated against the bot token before it's trusted, otherwise anyone could forge a
request pretending to be any Telegram user. Implements the algorithm documented at
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import HTTPException


class InitDataUser:
    def __init__(self, id: int, first_name: str, username: str | None, last_name: str | None):
        self.id = id
        self.first_name = first_name
        self.username = username
        self.last_name = last_name


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict:
    """Validates raw initData query string. Raises HTTPException(401) if invalid.
    Returns the parsed dict of fields on success."""
    if not init_data:
        raise HTTPException(status_code=401, detail="missing initData")

    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="initData missing hash")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(status_code=401, detail="invalid initData signature")

    auth_date = data.get("auth_date")
    if auth_date is not None and max_age_seconds:
        age = time.time() - int(auth_date)
        if age > max_age_seconds:
            raise HTTPException(status_code=401, detail="initData expired")

    return data


def parse_user(data: dict) -> InitDataUser:
    raw_user = data.get("user")
    if not raw_user:
        raise HTTPException(status_code=401, detail="initData missing user")
    user = json.loads(raw_user)
    return InitDataUser(
        id=user["id"],
        first_name=user.get("first_name", ""),
        username=user.get("username"),
        last_name=user.get("last_name"),
    )
