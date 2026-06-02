"""Shared knowledge-graph loader (used by learn KG endpoint and me/radar).

Cached parse of the static curriculum files. Callers that mutate the result
(e.g. injecting per-user mastery) must deep-copy first — the cached dict is
shared.
"""
import json
import os

_KG_DIR = os.path.join(os.path.dirname(__file__), "../../knowledge-graph")
_cache: dict[str, dict] = {}


def load_kg(stage: str) -> dict:
    if stage not in _cache:
        path = os.path.join(_KG_DIR, f"{stage}.json")
        if not os.path.exists(path):
            path = os.path.join(_KG_DIR, "kaoyan-college.json")
        with open(path, encoding="utf-8") as f:
            _cache[stage] = json.load(f)
    return _cache[stage]


def subject_order(stage: str) -> list[str]:
    return [s["name"] for s in load_kg(stage).get("subjects", [])]


def kp_to_subject(stage: str) -> dict[str, str]:
    """Map knowledge_point_id -> subject name for a stage."""
    m: dict[str, str] = {}
    for subject in load_kg(stage).get("subjects", []):
        for chapter in subject.get("chapters", []):
            for topic in chapter.get("topics", []):
                m[topic["id"]] = subject["name"]
    return m
