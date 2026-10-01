"""Which model answers each call (spec §6).

**Every call names its purpose**, and `PURPOSES` maps it to a setting in Settings → Models. The
fallback is the purpose's own model, then the default, then the environment as it was read
before settings existed — so an installation configured only by `.env`, including the
deprecated `MENDEL_*` names, behaves exactly as it did.

**Invariant 13:** a connection becomes a `ModelAccess` the same way whatever its server is. Only
`where_purposes`, a report for a person, reads the server kind.
"""

from collections.abc import Mapping

from comeni_ai import ModelAccess
from comeni_ai.access import MODEL
from comeni_core.settings import FROM_ENV, Installation, Setting
from comeni_core.settings import catalogue as c

PURPOSES: dict[tuple[str, str], Setting] = {
    ("builder", "goal"): c.MODEL_WANT,
    ("builder", "family"): c.MODEL_WANT,
    ("builder", "chat"): c.MODEL_TALK,
    ("builder", "gap"): c.MODEL_TALK,
    ("builder", "ask"): c.MODEL_TALK,
    ("builder", "tier4"): c.MODEL_TIER4,
    ("builder", "readback"): c.MODEL_READBACK,
    ("forge", "analysis"): c.MODEL_FORGE,
    ("forge", "implementation"): c.MODEL_FORGE,
    ("forge", "repair"): c.MODEL_FORGE,
    ("forge", "chat"): c.MODEL_FORGE,
}


def _access(inst: Installation, choice: dict, env: Mapping[str, str]) -> ModelAccess | None:
    record = inst.record(c.CONNECTIONS, choice["connection"])
    if record is None:
        return None
    # `from_env` with the chosen model reads the timeout and temperature the same way the
    # environment lane always has; the connection then supplies where and with what key.
    base = ModelAccess.from_env({**env, MODEL: choice["model"]})
    assert base is not None
    if choice["connection"] == FROM_ENV:
        return base
    key = record.get("key")  # a `SecretStr`, or None: opened only here, at the call (spec §8)
    return base.model_copy(
        update={
            "api_key": key.get_secret_value() if key is not None else None,
            "base_url": record.get("endpoint") or None,
        }
    )


def access_for(
    inst: Installation, env: Mapping[str, str], agent: str | None = None, purpose: str | None = None
) -> ModelAccess | None:
    if agent is None:
        order = [c.DEFAULT_MODEL, *c.PURPOSE_SETTINGS]
    else:
        order = [PURPOSES[(agent, str(purpose))], c.DEFAULT_MODEL] if purpose else [c.DEFAULT_MODEL]
    for setting in order:
        choice = inst.get(setting)
        if isinstance(choice, dict):
            found = _access(inst, choice, env)
            if found is not None:
                return found
    return ModelAccess.from_env(env)


def _goes(record: dict | None, model: str) -> str:
    if record is None:
        return "no model: nothing is sent"
    server = record.get("server")
    if server == "hosted" or (server is None and not record.get("endpoint")):
        return f"goes to {model.split('/', 1)[0]}"
    return "stays on this machine or your network"


def where_purposes(inst: Installation) -> list[dict]:
    rows = []
    default = inst.get(c.DEFAULT_MODEL)
    for setting in c.PURPOSE_SETTINGS:
        choice = inst.get(setting) or default
        record = inst.record(c.CONNECTIONS, choice["connection"]) if choice else None
        rows.append({
            "purpose": setting.label,
            "connection": choice["connection"] if choice else None,
            "goes": _goes(record, choice["model"] if choice else ""),
        })
    return rows
