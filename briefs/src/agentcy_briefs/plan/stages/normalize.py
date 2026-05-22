from __future__ import annotations

from typing import Any


def _ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _split_scalar_text(value: str) -> list[str]:
    text = value.strip()
    if not text:
        return []
    normalized = text.replace("\r", "\n").replace("•", "\n").replace(";", "\n")
    parts = [part.strip("- \t") for part in normalized.split("\n")]
    return [part for part in parts if part]


def coerce_str_list(value: Any) -> list[str]:
    items: list[str] = []
    for item in _ensure_list(value):
        if item is None:
            continue
        if isinstance(item, str):
            items.extend(_split_scalar_text(item))
            continue
        if isinstance(item, dict):
            for key in ("text", "name", "title", "description", "metric", "channel"):
                candidate = item.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    items.extend(_split_scalar_text(candidate))
                    break
            continue
        items.append(str(item))
    return items


def _coerce_source(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        text = item.strip()
        if not text:
            return None
        return {"url": "", "title": text, "snippet": None}
    if isinstance(item, dict):
        title = str(item.get("title") or item.get("name") or item.get("url") or "").strip()
        if not title:
            return None
        return {
            "url": str(item.get("url") or "").strip(),
            "title": title,
            "snippet": str(item.get("snippet") or "").strip() or None,
        }
    return None


def _coerce_competitor(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        name = item.strip()
        if not name:
            return None
        return {
            "name": name,
            "positioning": "",
            "strengths": [],
            "weaknesses": [],
        }
    if isinstance(item, dict):
        name = str(item.get("name") or item.get("title") or item.get("positioning") or "").strip()
        if not name:
            return None
        return {
            "name": name,
            "positioning": str(item.get("positioning") or item.get("description") or "").strip(),
            "strengths": coerce_str_list(item.get("strengths")),
            "weaknesses": coerce_str_list(item.get("weaknesses")),
        }
    return None


def _coerce_segment(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        name = item.strip()
        if not name:
            return None
        return {
            "name": name,
            "description": name,
            "pain_points": [],
            "motivations": [],
        }
    if isinstance(item, dict):
        name = str(item.get("name") or item.get("title") or item.get("description") or "").strip()
        if not name:
            return None
        description = str(item.get("description") or name).strip()
        return {
            "name": name,
            "description": description,
            "pain_points": coerce_str_list(item.get("pain_points")),
            "motivations": coerce_str_list(item.get("motivations")),
        }
    return None


def _coerce_pillar(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        name = item.strip()
        if not name:
            return None
        return {"name": name, "description": name, "topics": []}
    if isinstance(item, dict):
        name = str(item.get("name") or item.get("title") or item.get("description") or "").strip()
        if not name:
            return None
        return {
            "name": name,
            "description": str(item.get("description") or name).strip(),
            "topics": coerce_str_list(item.get("topics")),
        }
    return None


def _coerce_headline(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        text = item.strip()
        if not text:
            return None
        return {"text": text, "variant": None}
    if isinstance(item, dict):
        text = str(item.get("text") or item.get("headline") or item.get("title") or "").strip()
        if not text:
            return None
        return {"text": text, "variant": item.get("variant")}
    return None


def _coerce_asset(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        text = item.strip()
        if not text:
            return None
        return {
            "type": "asset",
            "description": text,
            "dimensions": None,
            "platform": None,
        }
    if isinstance(item, dict):
        description = str(
            item.get("description") or item.get("text") or item.get("type") or ""
        ).strip()
        if not description:
            return None
        return {
            "type": str(item.get("type") or "asset").strip(),
            "description": description,
            "dimensions": item.get("dimensions"),
            "platform": item.get("platform"),
        }
    return None


def _coerce_channel(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        name = item.strip()
        if not name:
            return None
        return {
            "channel": name,
            "objective": "",
            "tactics": [],
            "content_types": [],
            "frequency": None,
            "budget_allocation": None,
        }
    if isinstance(item, dict):
        channel = str(item.get("channel") or item.get("name") or "").strip()
        if not channel:
            return None
        frequency = item.get("frequency")
        budget_allocation = item.get("budget_allocation")
        return {
            "channel": channel,
            "objective": str(item.get("objective") or "").strip(),
            "tactics": coerce_str_list(item.get("tactics")),
            "content_types": coerce_str_list(item.get("content_types")),
            "frequency": str(frequency).strip() if frequency is not None else None,
            "budget_allocation": (
                str(budget_allocation).strip() if budget_allocation is not None else None
            ),
        }
    return None


def _coerce_calendar_item(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        text = item.strip()
        if not text:
            return None
        return {
            "date": None,
            "week": None,
            "channel": "unknown",
            "content_type": "content",
            "topic": text,
            "notes": None,
        }
    if isinstance(item, dict):
        topic = str(item.get("topic") or item.get("title") or item.get("notes") or "").strip()
        channel = str(item.get("channel") or "unknown").strip() or "unknown"
        if not topic:
            topic = channel
        date = item.get("date")
        week = item.get("week")
        notes = item.get("notes")
        return {
            "date": str(date).strip() if date is not None else None,
            "week": str(week).strip() if week is not None else None,
            "channel": channel,
            "content_type": str(item.get("content_type") or item.get("type") or "content").strip(),
            "topic": topic,
            "notes": str(notes).strip() if notes is not None else None,
        }
    return None


def _coerce_kpi(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        metric = item.strip()
        if not metric:
            return None
        return {"metric": metric, "target": "", "channel": None}
    if isinstance(item, dict):
        metric = str(
            item.get("metric") or item.get("name") or item.get("description") or ""
        ).strip()
        if not metric:
            return None
        channel = item.get("channel")
        return {
            "metric": metric,
            "target": str(item.get("target") or "").strip(),
            "channel": str(channel).strip() if channel is not None else None,
        }
    return None


def normalize_research_result(result: dict[str, Any] | None, *, brief: str) -> dict[str, Any]:
    payload = dict(result or {})
    payload["brief"] = str(payload.get("brief") or brief)
    payload["insights"] = coerce_str_list(payload.get("insights"))
    payload["competitors"] = [
        item
        for item in (
            _coerce_competitor(item)
            for item in _ensure_list(payload.get("competitors"))
        )
        if item
    ]
    payload["sources"] = [
        item
        for item in (_coerce_source(item) for item in _ensure_list(payload.get("sources")))
        if item
    ]
    payload["assumptions"] = coerce_str_list(payload.get("assumptions"))
    payload["trends"] = coerce_str_list(payload.get("trends"))
    payload["market_size"] = (
        str(payload.get("market_size")).strip() if payload.get("market_size") is not None else None
    )
    return payload


def normalize_strategy_result(result: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(result or {})
    payload["positioning"] = str(payload.get("positioning") or "")
    payload["value_proposition"] = (
        str(payload.get("value_proposition")).strip()
        if payload.get("value_proposition") is not None
        else None
    )
    payload["audience"] = [
        item
        for item in (_coerce_segment(item) for item in _ensure_list(payload.get("audience")))
        if item
    ]
    target_audience = _coerce_segment(payload.get("target_audience"))
    payload["target_audience"] = target_audience
    payload["pillars"] = [
        item
        for item in (_coerce_pillar(item) for item in _ensure_list(payload.get("pillars")))
        if item
    ]
    payload["messaging_pillars"] = coerce_str_list(payload.get("messaging_pillars"))
    payload["proof_points"] = coerce_str_list(payload.get("proof_points"))
    payload["differentiators"] = coerce_str_list(payload.get("differentiators"))
    payload["messaging_guidelines"] = coerce_str_list(payload.get("messaging_guidelines"))
    payload["risks"] = coerce_str_list(payload.get("risks"))
    payload["budget_recommendation"] = (
        str(payload.get("budget_recommendation")).strip()
        if payload.get("budget_recommendation") is not None
        else None
    )
    payload["timeline"] = (
        str(payload.get("timeline")).strip()
        if payload.get("timeline") is not None
        else None
    )
    return payload


def normalize_creative_result(result: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(result or {})
    payload["headlines"] = [
        item
        for item in (_coerce_headline(item) for item in _ensure_list(payload.get("headlines")))
        if item
    ]
    payload["body_copy"] = coerce_str_list(payload.get("body_copy"))
    payload["ctas"] = coerce_str_list(payload.get("ctas"))
    payload["taglines"] = coerce_str_list(payload.get("taglines"))
    payload["assets"] = [
        item
        for item in (_coerce_asset(item) for item in _ensure_list(payload.get("assets")))
        if item
    ]
    payload["tone_notes"] = coerce_str_list(payload.get("tone_notes"))
    return payload


def normalize_activation_result(result: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(result or {})
    payload["channels"] = [
        item
        for item in (_coerce_channel(item) for item in _ensure_list(payload.get("channels")))
        if item
    ]
    payload["calendar"] = [
        item
        for item in (
            _coerce_calendar_item(item)
            for item in _ensure_list(payload.get("calendar"))
        )
        if item
    ]
    payload["kpis"] = [
        item for item in (_coerce_kpi(item) for item in _ensure_list(payload.get("kpis"))) if item
    ]
    budget = payload.get("budget_allocation")
    if not isinstance(budget, dict):
        budget = {}
    payload["budget_allocation"] = {str(key): str(value) for key, value in budget.items()}
    payload["launch_checklist"] = coerce_str_list(payload.get("launch_checklist"))
    payload["risks"] = coerce_str_list(payload.get("risks"))
    return payload
