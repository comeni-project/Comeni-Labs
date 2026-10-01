"""Sealing secrets stored from the menu (spec §8).

**Fernet**, keyed by `COMENI_SETTINGS_KEY` in `.env`. Generate one with
`uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

**A missing or malformed key is reported, never raised.** `codec_from_env` returns `None` and the
resolver greys every secret with a reason; `key_problem` is that reason's text when the key is
present but unusable. A menu that crashed because `.env` held a passphrase would hide the one
message that says how to fix it.

**An unreadable secret is not set.** Rotating the key leaves every sealed value unopenable;
`Tolerant` turns that into an empty value, which `Installation.shown` reports as *not set*, so
the person is asked for the key again rather than shown a 500.
"""

from collections.abc import Mapping

from comeni_core.settings import SETTINGS_KEY_ENV
from cryptography.fernet import Fernet, InvalidToken


class UnreadableSecret(ValueError):
    """A sealed value this key cannot open. Its message never includes the value."""


class FernetCodec:
    def __init__(self, key: str):
        self._fernet = Fernet(key.encode())

    def __repr__(self) -> str:
        return "FernetCodec(<key hidden>)"

    __str__ = __repr__

    def seal(self, plain: str) -> str:
        return self._fernet.encrypt(plain.encode()).decode()

    def open(self, sealed: str) -> str:
        try:
            return self._fernet.decrypt(sealed.encode()).decode()
        except InvalidToken:
            raise UnreadableSecret("a stored secret was sealed under another key") from None


class Tolerant:
    """A codec whose `open` answers `""` for a secret it cannot read."""

    def __init__(self, inner: FernetCodec):
        self._inner = inner

    def seal(self, plain: str) -> str:
        return self._inner.seal(plain)

    def open(self, sealed: str) -> str:
        try:
            return self._inner.open(sealed)
        except UnreadableSecret:
            return ""


def _key(env: Mapping[str, str]) -> str:
    return env.get(SETTINGS_KEY_ENV, "").strip()


def codec_from_env(env: Mapping[str, str]) -> FernetCodec | None:
    key = _key(env)
    if not key:
        return None
    try:
        return FernetCodec(key)
    except (ValueError, TypeError):
        return None


def key_problem(env: Mapping[str, str]) -> str | None:
    """Why the key in `.env` cannot be used, or `None` when it can or is absent."""
    if _key(env) and codec_from_env(env) is None:
        return (
            f"{SETTINGS_KEY_ENV} in .env is not a Fernet key; generate one with "
            "Fernet.generate_key()"
        )
    return None
