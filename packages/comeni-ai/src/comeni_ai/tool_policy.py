"""Optional provider enforcement; the caller's tool protocol must work without it."""

from urllib.parse import urlsplit

from comeni_ai.access import ModelAccess

LOCAL = {"ollama", "ollama_chat", "vllm", "hosted_vllm", "lm_studio"}
HOSTED = {
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "openrouter.ai",
    "chatgpt.com",
}


def complete(
    access: ModelAccess, parameters: dict, *, required: bool, unsupported: set[tuple[str, str]]
) -> tuple[object, str | None]:
    """Retry only a specific unsupported-tool-choice refusal, never a general provider error.

    Local/custom servers default to auto even when their protocol claims OpenAI compatibility.
    Negative capability knowledge belongs to the transport instance and exact model/endpoint.
    """
    import litellm

    endpoint = (access.model, access.base_url or "")
    local = access.model.split("/", 1)[0] in LOCAL or (
        bool(access.base_url) and urlsplit(access.base_url).hostname not in HOSTED
    )
    enforce = False
    if required and parameters.get("tools") and not local and endpoint not in unsupported:
        try:
            supported = litellm.get_supported_openai_params(model=access.model) or []
        except (litellm.BadRequestError, ValueError):
            supported = []
        enforce = "tool_choice" in supported
    if not enforce:
        return litellm.completion(**parameters), None
    try:
        return litellm.completion(**parameters, tool_choice="required"), "required"
    except litellm.UnsupportedParamsError as error:
        if "tool_choice" not in str(error):
            raise
        unsupported.add(endpoint)
        return litellm.completion(**parameters), None
