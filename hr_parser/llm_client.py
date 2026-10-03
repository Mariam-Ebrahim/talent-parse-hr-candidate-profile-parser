"""LLM backends: a remote server (Kaggle + ngrok) and an offline demo backend."""
from __future__ import annotations

import json
import re
from typing import Protocol

import requests

from .errors import LLMUnavailable


class LLM(Protocol):
    def generate(self, prompt: str, max_new_tokens: int = 900) -> str: ...


class RemoteLLM:
    """Calls the FastAPI server in server/llm_server.py through its ngrok URL."""

    def __init__(self, url: str, token: str, timeout: int = 300):
        self.url, self.token, self.timeout = url.rstrip("/"), token, timeout

    def generate(self, prompt: str, max_new_tokens: int = 900) -> str:
        try:
            response = requests.post(
                f"{self.url}/generate",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "ngrok-skip-browser-warning": "true",
                },
                json={"prompt": prompt, "max_new_tokens": max_new_tokens},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise LLMUnavailable(
                "Could not reach the LLM server. Check that the Kaggle notebook is running and the URL is current."
            ) from exc
        if response.status_code == 401:
            raise LLMUnavailable("The server rejected the API key.")
        if not response.ok:
            raise LLMUnavailable(f"The LLM server returned an error ({response.status_code}).")
        return response.json()["response"]


class DemoLLM:
    """Rule-based stand-in so the UI runs without a GPU. Handles the lab's sample format only."""

    def generate(self, prompt: str, max_new_tokens: int = 900) -> str:
        match = re.search(r"<resume>\n(.*?)\n</resume>", prompt, re.DOTALL)
        data = _demo_parse(match.group(1) if match else prompt)
        return "```json\n" + json.dumps(data, ensure_ascii=False) + "\n```"


def _demo_parse(text: str) -> dict:
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    email = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text)
    first = lines[0] if lines else ""
    name = re.split(r"\s[–—-]\s|[\w.+-]+@", first)[0].strip()
    data = {"full_name": name, "email": email.group() if email else "",
            "education": [], "skills": [], "experience": []}
    for line in lines:
        edu = re.match(r"education\s*:\s*(.+)", line, re.I)
        skills = re.match(r"skills\s*:\s*(.+)", line, re.I)
        job = re.match(r"[-•*]\s*(.+?)\s+at\s+(.+?)\s*\((.+?)\)\s*$", line)
        if edu:
            parts = [p.strip() for p in edu.group(1).split(",")]
            if len(parts) >= 3:
                data["education"].append(
                    {"degree": parts[0], "institution": ", ".join(parts[1:-1]), "year": parts[-1]})
        elif skills:
            data["skills"] = [s.strip() for s in skills.group(1).split(",")]
        elif job:
            data["experience"].append(
                {"role": job.group(1), "company": job.group(2), "years": job.group(3)})
    return data


def get_llm(mode: str, url: str = "", token: str = "") -> LLM:
    if mode == "demo":
        return DemoLLM()
    if not url or not token:
        raise LLMUnavailable("Enter the server URL and API key in the sidebar.")
    return RemoteLLM(url, token)
