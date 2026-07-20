from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

DEFAULT_LOGIN_URL = "https://play.pokemonshowdown.com/api/login"
DEFAULT_GUEST_URL = "https://play.pokemonshowdown.com/action.php"
USER_AGENT = "showdown-bot/0.1"


class AuthError(Exception):
    pass


def to_showdown_id(username: str) -> str:
    """Normalize username to Showdown user id (lowercase alphanumeric)."""
    return re.sub(r"[^a-z0-9]", "", username.lower())


def parse_auth_response(body: str) -> str:
    text = body.strip()
    if not text:
        raise AuthError("empty auth response")
    if text.startswith(";;"):
        raise AuthError(text[2:])
    if text.startswith("]"):
        text = text[1:]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        if text.startswith("{"):
            raise AuthError(f"invalid auth JSON: {text[:120]}")
        return text
    assertion = data.get("assertion")
    if not assertion:
        action = data.get("action", "")
        message = data.get("message", data)
        raise AuthError(f"no assertion in response: {action} {message}")
    if str(assertion).startswith(";;"):
        raise AuthError(str(assertion)[2:])
    curuser = data.get("curuser", {})
    if curuser.get("loggedin") is False:
        raise AuthError("username, password, or challstr incorrect")
    return str(assertion)


def _open_auth_request(request: urllib.request.Request) -> str:
    request.add_header("User-Agent", USER_AGENT)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise AuthError(f"auth HTTP {exc.code}") from exc


def fetch_registered_assertion(
    username: str,
    password: str,
    challstr: str,
    login_url: str = DEFAULT_LOGIN_URL,
) -> str:
    user_id = to_showdown_id(username)
    payload = urllib.parse.urlencode(
        {"name": user_id, "pass": password, "challstr": challstr}
    ).encode()
    request = urllib.request.Request(
        login_url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        },
    )
    return parse_auth_response(_open_auth_request(request))


def fetch_guest_assertion(
    username: str,
    challstr: str,
    guest_url: str = DEFAULT_GUEST_URL,
) -> str:
    user_id = to_showdown_id(username)
    params = urllib.parse.urlencode(
        {"act": "getassertion", "userid": user_id, "challstr": challstr}
    )
    url = f"{guest_url}?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return parse_auth_response(_open_auth_request(request))


def fetch_assertion(
    username: str,
    password: str,
    challstr: str,
    *,
    login_url: str = DEFAULT_LOGIN_URL,
    guest_url: str = DEFAULT_GUEST_URL,
) -> str:
    if password:
        logger.info("fetching registered login assertion for %s", username)
        return fetch_registered_assertion(username, password, challstr, login_url)
    logger.info("fetching guest assertion for %s", username)
    return fetch_guest_assertion(username, challstr, guest_url)
