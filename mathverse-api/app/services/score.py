"""Monte Carlo score estimation for Kaoyan math."""
import random
import statistics
from typing import Any

QUESTION_DISTRIBUTION = {
    "math-1": {"choice": 8, "fill": 6, "solve": 9},
    "math-2": {"choice": 6, "fill": 5, "solve": 7},
    "math-3": {"choice": 8, "fill": 6, "solve": 9},
}
POINT_VALUES = {"choice": 4, "fill": 4, "solve": 10}
TOTAL_SCORE = 150
PASS_THRESHOLD = 90


def estimate_score(
    knowledge_points: dict[str, float],
    exam_mode: str = "math-1",
    num_simulations: int = 2000,
) -> dict[str, Any]:
    dist = QUESTION_DISTRIBUTION.get(exam_mode, QUESTION_DISTRIBUTION["math-1"])
    kp_list = list(knowledge_points.items())
    if not kp_list:
        return {"estimated_score": 0, "pass_probability": 0, "weak_areas": []}

    scores = []
    for _ in range(num_simulations):
        total = 0.0
        for qtype, count in dist.items():
            for _ in range(count):
                _, mastery = random.choice(kp_list)
                if random.random() < mastery:
                    total += POINT_VALUES[qtype]
                elif qtype == "solve" and random.random() < mastery * 0.5:
                    total += POINT_VALUES[qtype] * 0.4
        scores.append(total)

    mean = statistics.mean(scores)
    std = statistics.stdev(scores) if len(scores) > 1 else 0
    pass_prob = sum(1 for s in scores if s >= PASS_THRESHOLD) / num_simulations
    weak = sorted(
        [kp for kp, m in kp_list if m < 0.5],
        key=lambda k: knowledge_points[k],
    )[:5]

    return {
        "estimated_score": round(mean, 1),
        "score_range": f"{round(mean - std)}-{round(mean + std)}",
        "pass_probability": round(pass_prob * 100, 1),
        "weak_areas": weak,
    }
