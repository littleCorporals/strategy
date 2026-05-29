from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any
from urllib import request as urlrequest
from urllib.error import URLError

from app.core.config import AI_API_KEY_ENV, AI_BASE_URL_ENV, AI_MODEL_ENV


def configured() -> bool:
    return bool(os.getenv(AI_BASE_URL_ENV) and os.getenv(AI_API_KEY_ENV) and os.getenv(AI_MODEL_ENV))


async def stock_recommendation(analysis: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any]:
    base_url = os.getenv(AI_BASE_URL_ENV, "").rstrip("/")
    api_key = os.getenv(AI_API_KEY_ENV, "")
    model = os.getenv(AI_MODEL_ENV, "gpt-5.5")
    prompt = {
        "instruction": (
            "你是A股交易分析助手。先审查消息来源是否足以支持结论，不能编造事实；"
            "再结合趋势、资金、估值、支撑压力给出 action。"
            "action 只能是：观察买入、等待回踩、暂不买入。"
            "必须输出 JSON，不要 Markdown。"
        ),
        "analysis": analysis,
        "sources": sources,
        "schema": {
            "action": "观察买入|等待回踩|暂不买入",
            "confidence": "0-100整数",
            "verification": "消息真实性核验说明",
            "reasons": ["最多4条"],
            "risks": ["最多4条"],
            "conditions": ["最多4条"],
        },
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "只输出严格 JSON。"},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        "temperature": 0.2,
    }

    def _post() -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urlrequest.Request(
            f"{base_url}/v1/chat/completions",
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
        )
        with urlrequest.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    result = await asyncio.to_thread(_post)
    content = result["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.DOTALL)
    parsed = json.loads(content)
    parsed["model_used"] = model
    return parsed


AI_CLIENT_ERRORS = (KeyError, json.JSONDecodeError, URLError, TimeoutError, OSError, RuntimeError)
