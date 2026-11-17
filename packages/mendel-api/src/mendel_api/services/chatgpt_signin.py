"""Browser setup for the existing LiteLLM subscription transport.

Pending authorizations live beside its shared token file so polling survives API restarts and
multiple workers. Only the device code reaches the UI; access and refresh tokens stay here.
The small adapter to LiteLLM's authentication internals is kept in this module.
"""

import fcntl
import json
import os
import re
import secrets
import tempfile
import time
from pathlib import Path

import httpx

LIFETIME = 15 * 60
# A working minimum when public release metadata is temporarily unavailable.
CATALOGUE_CLIENT_VERSION = "0.166.0"
_catalogue_version = CATALOGUE_CLIENT_VERSION
_catalogue_version_until = 0.0
TRANSPORT: httpx.BaseTransport | None = None


def catalogue_client_version(client: httpx.Client) -> str:
    """Refresh release metadata every six hours; never install or execute remote code.

    The account catalogue gates newer models by client version. Keep the last known
    version during an outage and retry metadata after ten minutes. No credentials are
    sent to the public package registry.
    """
    global _catalogue_version, _catalogue_version_until

    now = time.monotonic()
    if now < _catalogue_version_until:
        return _catalogue_version
    try:
        response = client.get("https://registry.npmjs.org/@openai/codex/latest", timeout=3)
        response.raise_for_status()
        version = response.json()["version"]
        if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
            raise ValueError("Invalid release version")
        if tuple(map(int, version.split("."))) >= tuple(map(int, _catalogue_version.split("."))):
            _catalogue_version = version
        _catalogue_version_until = now + 6 * 60 * 60
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        _catalogue_version_until = now + 10 * 60
    return _catalogue_version


def authenticator():
    from litellm.llms.chatgpt.authenticator import Authenticator

    return Authenticator()


def status() -> bool:
    auth = authenticator()
    data = auth._read_auth_file() or {}
    token = data.get("access_token")
    return bool(data.get("refresh_token") or (token and not auth._is_token_expired(data, token)))


def models() -> list[str]:
    """Read the same account catalogue used by the existing subscription transport."""
    import uuid

    from litellm.llms.chatgpt.common_utils import get_chatgpt_default_headers

    auth = authenticator()
    data = auth._read_auth_file() or {}
    token = data.get("access_token")
    if not token or auth._is_token_expired(data, token):
        if not data.get("refresh_token"):
            raise ValueError("Sign in first")
        token = auth._refresh_tokens(data["refresh_token"])["access_token"]
    headers = get_chatgpt_default_headers(token, auth.get_account_id(), str(uuid.uuid4()))
    headers["accept"] = "application/json"
    with httpx.Client(timeout=10, transport=TRANSPORT) as client:
        version = catalogue_client_version(client)
        response = client.get(
            auth.get_api_base().rstrip("/") + "/models",
            params={"client_version": version},
            headers=headers,
        )
        response.raise_for_status()
    return sorted(
        "chatgpt/" + item["slug"]
        for item in response.json()["models"]
        if item.get("visibility", "list") == "list"
    )


def _atomic(path: Path, data: dict) -> None:
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def start() -> dict:
    from litellm.llms.chatgpt.common_utils import CHATGPT_DEVICE_VERIFY_URL

    auth = authenticator()
    directory = Path(auth.token_dir) / "pending"
    directory.mkdir(mode=0o700, exist_ok=True)
    # Remove only our expired authorization files, never the installation's saved sign-in.
    for old in directory.glob("*.json"):
        if old.stat().st_mtime < time.time() - LIFETIME:
            old.unlink(missing_ok=True)
    code = auth._request_device_code()
    session = secrets.token_hex(24)
    interval = max(5, int(code.get("interval", "5")))
    expires = time.time() + LIFETIME
    _atomic(directory / f"{session}.json", {**code, "expires": expires, "next_poll": 0})
    return {
        "session": session,
        "user_code": code["user_code"],
        "verification_url": CHATGPT_DEVICE_VERIFY_URL,
        "interval": interval,
        "expires_at": expires,
        "state": "pending",
    }


def poll(session: str) -> str:
    from litellm.llms.chatgpt.common_utils import CHATGPT_DEVICE_TOKEN_URL

    if len(session) != 48 or any(c not in "0123456789abcdef" for c in session):
        return "expired"
    auth = authenticator()
    path = Path(auth.token_dir) / "pending" / f"{session}.json"
    try:
        stream = path.open("r+")
    except FileNotFoundError:
        return "expired"
    with stream:
        # Serialise exchanges across workers: one authorization code is redeemed only once.
        fcntl.flock(stream, fcntl.LOCK_EX)
        data = json.load(stream)
        if data.get("state") == "connected":
            return "connected"
        if time.time() >= data["expires"]:
            return "expired"
        if time.time() < data["next_poll"]:
            return "pending"
        data["next_poll"] = time.time() + max(5, int(data.get("interval", "5")))
        stream.seek(0)
        json.dump(data, stream)
        stream.truncate()
        stream.flush()
        with httpx.Client(timeout=10, transport=TRANSPORT) as client:
            response = client.post(
                CHATGPT_DEVICE_TOKEN_URL,
                json={
                    "device_auth_id": data["device_auth_id"],
                    "user_code": data["user_code"],
                },
            )
        if response.status_code in (403, 404, 429):
            return "pending"
        response.raise_for_status()
        tokens = auth._exchange_code_for_tokens(response.json())
        _atomic(Path(auth.auth_file), auth._build_auth_record(tokens))
        stream.seek(0)
        json.dump({"state": "connected"}, stream)
        stream.truncate()
        return "connected"
