"""Explicit connection setup: discover models before saving, or authorize a subscription."""

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

from mendel_api.services import chatgpt_signin, probe
from mendel_api.services.settings_actions import ActionResult

router = APIRouter(prefix="/settings/models", tags=["settings"])


class ConnectionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    server: Literal["ollama", "openai_compatible", "hosted"]
    provider: Literal[
        "custom", "ollama", "lmstudio", "openai", "anthropic", "gemini", "openrouter"
    ] = "custom"
    endpoint: str
    key: SecretStr | None = None

    @field_validator("endpoint")
    @classmethod
    def http_endpoint(cls, value: str) -> str:
        from urllib.parse import urlsplit

        parts = urlsplit(value)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username
            or parts.password
        ):
            raise ValueError(
                "Use an http:// or https:// server address without embedded credentials."
            )
        return value


@router.post("/discover", operation_id="discoverConnectionModels")
async def discover(draft: ConnectionDraft) -> ActionResult:
    try:
        models = await probe.listed(
            draft.endpoint,
            draft.server,
            draft.key.get_secret_value() if draft.key else None,
            provider=draft.provider,
        )
    except probe.ProbeFailed as error:
        return ActionResult(ok=False, says=str(error))
    return ActionResult(
        ok=True, says=f"Connection checked. Found {len(models)} models.", values=models
    )


class LocalProvider(BaseModel):
    provider: Literal["ollama", "lmstudio"]


class DetectedServer(BaseModel):
    endpoint: str
    models: list[str]


@router.post("/detect", operation_id="detectLocalModelServers")
async def detect(draft: LocalProvider) -> list[DetectedServer]:
    port = "11434" if draft.provider == "ollama" else "1234/v1"
    server = "ollama" if draft.provider == "ollama" else "openai_compatible"
    hosts = (
        ["ollama", "host.docker.internal", "127.0.0.1"]
        if draft.provider == "ollama"
        else ["host.docker.internal", "127.0.0.1"]
    )

    async def check(host: str) -> DetectedServer | None:
        endpoint = f"http://{host}:{port}"
        try:
            return DetectedServer(endpoint=endpoint, models=await probe.listed(endpoint, server))
        except probe.ProbeFailed:
            return None

    return [
        found
        for found in await asyncio.gather(*(check(host) for host in hosts))
        if found is not None
    ]


class SigninStatus(BaseModel):
    signed_in: bool


class DeviceSignin(BaseModel):
    session: str
    user_code: str
    verification_url: str
    interval: int
    expires_at: float
    state: Literal["pending"]


class SigninProgress(BaseModel):
    state: Literal["pending", "connected", "expired"]


@router.get("/chatgpt", operation_id="chatgptSigninStatus")
def signin_status() -> SigninStatus:
    try:
        return SigninStatus(signed_in=chatgpt_signin.status())
    except OSError:
        raise HTTPException(503, "The shared ChatGPT sign-in folder is not writable.") from None


@router.post("/chatgpt/models", operation_id="listSubscriptionModels")
def subscription_models() -> ActionResult:
    try:
        models = chatgpt_signin.models()
        return ActionResult(
            ok=True, says=f"Found {len(models)} subscription models.", values=models
        )
    except Exception:
        return ActionResult(
            ok=False,
            says="Could not load subscription models. Sign in again, or enter a model ID manually.",
        )


@router.post("/chatgpt/sign-in", operation_id="startChatgptSignin")
def start_signin() -> DeviceSignin:
    try:
        return DeviceSignin(**chatgpt_signin.start())
    except PermissionError:
        raise HTTPException(
            503,
            "Comeni cannot write its ChatGPT sign-in folder. "
            "The installation's folder ownership or permissions need to be repaired.",
        ) from None
    except OSError:
        raise HTTPException(
            503, "Comeni could not store the ChatGPT sign-in. Check disk space and permissions."
        ) from None
    except Exception:
        # Provider exceptions can contain credentials or response bodies; keep them server-side.
        raise HTTPException(503, "Could not start ChatGPT sign-in. Try again shortly.") from None


@router.post("/chatgpt/sign-in/{session}", operation_id="pollChatgptSignin")
def poll_signin(session: str) -> SigninProgress:
    try:
        return SigninProgress(state=chatgpt_signin.poll(session))
    except Exception:
        raise HTTPException(503, "Could not check ChatGPT sign-in. Please try again.") from None
