from app.services.fsrs import fsrs_next, get_next_review_date

def test_fsrs_again_decreases_stability():
    stab, diff, interval = fsrs_next(2.0, 5.0, 1)
    assert stab < 2.0

def test_fsrs_easy_increases_stability():
    stab, diff, interval = fsrs_next(2.0, 5.0, 4)
    assert stab > 2.0

def test_get_next_review_date():
    result = get_next_review_date(3)
    assert "stability" in result
    assert "difficulty" in result
    assert "interval" in result
    assert "next_review_at" in result
