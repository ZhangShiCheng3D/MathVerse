"""Daily study plan generator based on knowledge point mastery."""
import json
import os

KG_PATH = os.path.join(
    os.path.dirname(__file__), "../../knowledge-graph/kaoyan-college.json"
)


def generate_daily_tasks(
    kp_mastery: dict[str, float], max_tasks: int = 5
) -> list[dict]:
    """Generate prioritized daily study tasks."""
    if not os.path.exists(KG_PATH):
        return []

    with open(KG_PATH, encoding="utf-8") as f:
        kg = json.load(f)

    topics = []
    for subject in kg.get("subjects", []):
        for chapter in subject.get("chapters", []):
            for topic in chapter.get("topics", []):
                mastery = kp_mastery.get(topic["id"], 0.0)
                topics.append({
                    "kp_id": topic["id"],
                    "name": topic["name"],
                    "chapter": chapter["name"],
                    "subject": subject["name"],
                    "mastery": mastery,
                    "difficulty": topic.get("difficulty", 3),
                    "frequency": chapter.get("frequency", "medium"),
                })

    weak_topics = [t for t in topics if t["mastery"] < 0.6]
    weak_topics.sort(key=lambda t: (
        t["mastery"],
        -(t["difficulty"] if t["mastery"] < 0.3 else -t["difficulty"]),
        0 if t["frequency"] == "high" else 1,
    ))

    tasks = []
    for topic in weak_topics[:max_tasks]:
        freq_text = "高频考点" if topic["frequency"] == "high" else "建议加强"
        tasks.append({
            "kp_id": topic["kp_id"],
            "name": topic["name"],
            "chapter": topic["chapter"],
            "task_type": "review" if topic["mastery"] > 0.3 else "learn",
            "reason": f"掌握度 {topic['mastery']:.0%}，{freq_text}",
        })
    return tasks
