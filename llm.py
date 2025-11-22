import json
import os
from typing import List, Optional

import requests

from models import CompanyProfile, FundingInstrument


class LLMNotConfigured(Exception):
    pass


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")


def is_configured() -> bool:
    return bool(OPENAI_API_KEY)


def _call_llm(messages: List[dict], max_tokens: int = 320, temperature: float = 0.2) -> str:
    if not OPENAI_API_KEY:
        raise LLMNotConfigured("OPENAI_API_KEY not set; cannot call LLM.")

    url = f"{OPENAI_BASE.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=20)
    if resp.status_code >= 400:
        raise RuntimeError(f"LLM API error {resp.status_code}: {resp.text}")

    data = resp.json()
    choice = data.get("choices", [{}])[0].get("message", {}).get("content")
    if not choice:
        raise RuntimeError("LLM returned no content.")
    return choice


def summarize_company(company: CompanyProfile) -> Optional[str]:
    """
    Produce a short summary of the company context to surface in UI/report.
    """
    try:
        content = _call_llm(
            [
                {"role": "system", "content": "You are a concise funding advisor. Respond in under 60 words."},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": "summarize_company",
                            "company": {
                                "name": company.name,
                                "industry": company.industry,
                                "stage": company.stage,
                                "revenue_class": company.revenue_class,
                                "employees": company.employees,
                                "country": company.country,
                                "funding_need_types": company.funding_need_types,
                                "funding_amount_min": company.funding_amount_min,
                                "funding_amount_max": company.funding_amount_max,
                            },
                        }
                    ),
                },
            ],
            max_tokens=150,
        )
        parsed = json.loads(content)
        return parsed.get("summary") if isinstance(parsed, dict) else None
    except LLMNotConfigured:
        raise
    except Exception:
        return None


def generate_explanations(company: CompanyProfile, recos: List[dict]) -> List[Optional[str]]:
    """
    Re-write reasoning for each recommendation using an LLM.
    Returns list aligned with recos (same order).
    """
    try:
        payload = {
            "task": "rewrite_recommendations",
            "company": {
                "name": company.name,
                "industry": company.industry,
                "stage": company.stage,
                "country": company.country,
                "funding_need_types": company.funding_need_types,
            },
            "recommendations": [
                {
                    "name": r["instrument"].name,
                    "provider": r["instrument"].provider,
                    "application_window": r["instrument"].application_window,
                    "application_type": r["instrument"].application_type,
                    "score": r["score"],
                    "reasons": r["reasons"],
                }
                for r in recos
            ],
            "format": "Return JSON with key 'explanations' as an array of strings (same length/order as recommendations). Keep each under 90 words and cite why it fits.",
        }

        content = _call_llm(
            [
                {"role": "system", "content": "You are a funding advisor. Be precise, concise, and factual."},
                {"role": "user", "content": json.dumps(payload)},
            ],
            max_tokens=600,
            temperature=0.3,
        )
        parsed = json.loads(content)
        explanations = parsed.get("explanations")
        if not isinstance(explanations, list):
            return [None for _ in recos]
        # Ensure length alignment
        if len(explanations) < len(recos):
            explanations.extend([None] * (len(recos) - len(explanations)))
        return explanations[: len(recos)]
    except LLMNotConfigured:
        raise
    except Exception:
        return [None for _ in recos]
