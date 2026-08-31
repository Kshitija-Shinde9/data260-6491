# src/model_client.py - part 4's model adapter
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import ollama


@dataclass
class TurnUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass
class CompletionResult:
    content: str
    usage: TurnUsage
    latency_ms: int
    raw: Any = field(repr=False, default=None)


class ModelClient:
    # wraps ollama's chat api behind one complete() method, so callers don't
    # need to know anything about ollama specifically
    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.0,
    ):
        self.model = model or os.environ.get("SMOL_MODEL", "qwen3:8b")
        self.base_url = base_url or os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.temperature = temperature
        self._client = ollama.Client(host=self.base_url)

    def complete(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> CompletionResult:
        # messages is the full conversation so far (system/user/assistant dicts).
        # tools just gets passed through to ollama untouched - hw1_client.py never
        # actually uses it, it's there so this matches a real complete(messages, tools=None)
        # interface in case something later needs tool calling.
        t0 = time.time()
        response = self._client.chat(
            model=self.model,
            messages=messages,
            tools=tools,
            think=False,
            options={"temperature": self.temperature},
        )
        latency_ms = int((time.time() - t0) * 1000)

        input_tokens = response.get("prompt_eval_count", 0) or 0
        output_tokens = response.get("eval_count", 0) or 0
        usage = TurnUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        )
        content = response.get("message", {}).get("content", "")

        return CompletionResult(content=content, usage=usage, latency_ms=latency_ms, raw=response)
