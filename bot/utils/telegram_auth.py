import hashlib
import hmac
import json
from urllib.parse import parse_qsl


def verify_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    """Verifies Telegram WebApp initData HMAC. Returns parsed params or None."""
    if not init_data or not bot_token:
        return None
    params = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = params.pop("hash", None)
    if not received_hash:
        return None
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        return None
    return params


def extract_tg_id(init_data: str, bot_token: str) -> int | None:
    """Returns verified tg_id from initData, or None if invalid/absent."""
    params = verify_telegram_init_data(init_data, bot_token)
    if not params:
        return None
    try:
        return int(json.loads(params["user"])["id"])
    except (KeyError, json.JSONDecodeError, ValueError, TypeError):
        return None
