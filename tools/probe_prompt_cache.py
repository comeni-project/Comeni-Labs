"""Compare Ollama timings for repeated prompts and shared instruction prefixes.

Send a warm-up request, an identical request and a different question sharing the fixed
instructions. Print Ollama's loading, prompt-evaluation and generation timings and token
counts. These are real model requests, with a 600-second timeout each.

Run inside the API container, where registry/prompt helpers and ollama:11434 are available:

    docker cp tools/probe_prompt_cache.py mendel-api:/tmp/
    docker exec mendel-api python /tmp/probe_prompt_cache.py gemma3:12b --split

The optional model defaults to gemma3:12b. --split separates fixed instructions into a
system message and the question into a user message. Otherwise send the combined prompt."""

import json
import sys
import urllib.request

from comeni_ai.access import ModelAccess
from comeni_ai.client import _messages, _prompt
from mendel_api.authoring import prompts
from mendel_api.authoring.types import WantUnderstanding
from mendel_api.services import authoring_ai as ai
from mendel_api.services import registry

SPLIT = "--split" in sys.argv
ARGS = [a for a in sys.argv[1:] if a != "--split"]
MODEL = ARGS[0] if ARGS else "gemma3:12b"
BASE = "http://ollama:11434/api/chat"


def prompt_for(request: str) -> list[dict]:
    values = {
        "vocabulary": ai._vocabulary_text(registry.stack()),
        "conversation": "",
        "request": request,
    }
    template = prompts.template(prompts.GOAL)
    if SPLIT:
        system, user = template.render_split(values)
        return _messages(ModelAccess(model=f"ollama_chat/{MODEL}"), system, user, WantUnderstanding)
    whole = _prompt(template.render(values).text, WantUnderstanding, [])
    return [{"role": "user", "content": whole}]


def chat(messages: list[dict]) -> str:
    body = json.dumps(
        {
            "model": MODEL,
            "stream": False,
            "options": {"temperature": 0},
            "messages": messages,
        }
    ).encode()
    request = urllib.request.Request(BASE, data=body, headers={"content-type": "application/json"})
    reply = json.load(urllib.request.urlopen(request, timeout=600))

    def seconds(key: str) -> float:
        return round(reply.get(key, 0) / 1e9, 1)

    return (
        f"load={seconds('load_duration')}s "
        f"prompt={reply.get('prompt_eval_count')}tok/{seconds('prompt_eval_duration')}s "
        f"gen={reply.get('eval_count')}tok/{seconds('eval_duration')}s"
    )


if __name__ == "__main__":
    a = prompt_for("paired-end RNA-seq to gene counts, 150 bp reads, I have the human genome")
    b = prompt_for("single-cell RNA-seq to a counts matrix")
    print("warm-up      ", chat(a))
    print("identical    ", chat(a))
    print("shared prefix", chat(b))
