"""Measure whether Ollama re-reads a prompt's fixed part — issue 185.

Sends the builder's goal prompt to /api/chat three ways and prints Ollama's own timings: a
warm-up, the same prompt again (a repeat should read almost nothing), and a second request
sharing the fixed part (prefix reuse across different questions). Run inside the api container:

    docker cp tools/probe_prompt_cache.py mendel-api:/tmp/
    docker exec mendel-api python /tmp/probe_prompt_cache.py [model] [--split]

`--split` sends the prompt as the builder does since 14.7.4.3: a system message (the fixed part)
and a user message (the per-call part), so a shared fixed part can be reused.

A measuring tool, run by hand; its numbers are recorded on issue 185.
"""

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
