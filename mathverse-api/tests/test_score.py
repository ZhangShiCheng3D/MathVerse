from app.services.score import estimate_score

def test_estimate_perfect_mastery():
    kp = {f"gs-{i}": 1.0 for i in range(1, 20)}
    result = estimate_score(kp, "math-1", num_simulations=500)
    assert result["estimated_score"] > 120
    assert result["pass_probability"] > 90

def test_estimate_zero_mastery():
    kp = {f"gs-{i}": 0.0 for i in range(1, 20)}
    result = estimate_score(kp, "math-1", num_simulations=500)
    assert result["estimated_score"] < 30
    assert result["pass_probability"] < 10

def test_weak_areas_identified():
    kp = {"gs-1": 0.9, "gs-2": 0.3, "gs-3": 0.1}
    result = estimate_score(kp, "math-1", num_simulations=200)
    assert "gs-3" in result["weak_areas"]
    assert "gs-2" in result["weak_areas"]
    assert "gs-1" not in result["weak_areas"]
