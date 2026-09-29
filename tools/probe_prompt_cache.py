"""Measure whether Ollama re-reads a prompt's fixed part — issue 185.

Sends the builder's goal prompt to /api/chat three ways and prints Ollama's own timings: a
warm-up, the same prompt again (a repeat should read almost nothing), and a second request
sharing the fixed part (prefix reuse across different questions). Run inside the api container:

    docker cp tools/probe_prompt_cache.py mendel-api:/tmp/
    docker exec mendel-api python /tmp/probe_prompt_cache.py [model]

A measuring tool, run by hand; its numbers are recorded on issue 185.
"""

import json
import sys
import urllib.request

from comeni_ai.client import _prompt
from mendel_api.authoring import prompts
from mendel_api.authoring.types import WantUnderstanding
from mendel_api.services import authoring_ai as ai
from mendel_api.services import registry

MODEL = sys.argv[1] if len(sys.argv) > 1 else "gemma3:12b"
BASE = "http://ollama:11434/api/chat"


def prompt_for(request: str) -> str:
    text = prompts.template(prompts.GOAL).render(
        {
            "vocabulary": ai._vocabulary_text(registry.stack()),
            "conversation": "",
            "request": request,
        }
    ).text
    return _prompt(text, WantUnderstanding, [])


def chat(prompt: str) -> str:
    body = json.dumps(
        {
            "model": MODEL,
            "stream": False,
            "options": {"temperature": 0},
            "messages": [{"role": "user", "content": prompt}],
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
