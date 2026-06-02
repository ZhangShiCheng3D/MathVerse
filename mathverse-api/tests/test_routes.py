"""Behavioral safety-net for me / learn / questions / pay routes.

Locks current behavior before the session-management refactor.
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal, init_db
from app.models.all import (
    User, QuestionArchive, MistakeNotebook, StudyPlan, Subscription,
    LearningProgress, AnalyticsEvent,
)
from app.middleware.auth_middleware import create_access_token

init_db()
client = TestClient(app)


@pytest.fixture
def auth():
    db = SessionLocal()
    u = User(tier="free", current_stage="college", exam_mode="math-1")
    db.add(u)
    db.commit()
    db.refresh(u)
    uid = u.id
    db.close()
    headers = {"Authorization": f"Bearer {create_access_token(uid)}"}
    yield uid, headers
    db = SessionLocal()
    for model in (QuestionArchive, MistakeNotebook, StudyPlan, Subscription,
                  LearningProgress, AnalyticsEvent):
        db.query(model).filter(model.user_id == uid).delete()
    db.query(User).filter(User.id == uid).delete()
    db.commit()
    db.close()


# ─── learn ───

def test_get_knowledge_graph():
    resp = client.get("/api/learn/kg/college")
    assert resp.status_code == 200
    assert "subjects" in resp.json()


# ─── questions ───

def test_save_and_fetch_question(auth):
    _, headers = auth
    resp = client.post("/api/questions", headers=headers, json={
        "question_text": "求导 x^2", "knowledge_point_id": "gs-2.1",
        "solve_result": {"answer": "2x"},
    })
    assert resp.status_code == 200
    qid = resp.json()["id"]
    got = client.get(f"/api/questions/{qid}", headers=headers)
    assert got.status_code == 200
    assert got.json()["question_text"] == "求导 x^2"


def test_fetch_other_users_question_404(auth):
    _, headers = auth
    assert client.get("/api/questions/nonexistent", headers=headers).status_code == 404


# ─── me ───

def test_progress_empty(auth):
    _, headers = auth
    resp = client.get("/api/me/progress", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total_questions"] == 0


def test_mistake_lifecycle(auth):
    _, headers = auth
    created = client.post("/api/me/mistakes", headers=headers, json={
        "question_text": "1/0", "correct_answer": "无意义",
        "knowledge_point_id": "gs-1.1", "subject": "高等数学",
    })
    assert created.status_code == 200
    mid = created.json()["id"]

    listed = client.get("/api/me/mistakes", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    rated = client.patch(f"/api/me/mistakes/{mid}", headers=headers, json={"review_rating": 3})
    assert rated.status_code == 200


def test_mistake_populates_learning_progress(auth):
    uid, headers = auth
    client.post("/api/me/mistakes", headers=headers, json={
        "question_text": "∫x dx", "correct_answer": "x^2/2",
        "knowledge_point_id": "gs-3.1", "subject": "高等数学",
    })
    # The mistake created a graded "wrong" signal -> progress now tracks gs-3.1.
    prog = client.get("/api/me/progress", headers=headers)
    assert prog.json()["total_knowledge_points"] >= 1


def test_today_plan(auth):
    _, headers = auth
    resp = client.get("/api/me/plan/today", headers=headers)
    assert resp.status_code == 200
    assert "tasks" in resp.json()


def test_score_estimate(auth):
    _, headers = auth
    resp = client.post("/api/me/score/estimate", headers=headers, json={
        "knowledge_points": {"gs-1.1": 0.8, "gs-2.1": 0.3}, "exam_mode": "math-1",
    })
    assert resp.status_code == 200
    assert "estimated_score" in resp.json()


def test_score_estimate_get_empty(auth):
    # No learning data yet → coarse estimate returns a zeroed result, not 500.
    _, headers = auth
    resp = client.get("/api/me/score/estimate", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["estimated_score"] == 0
    assert body["weak_areas"] == []


def test_score_estimate_get_with_data(auth):
    # A graded mistake writes LearningProgress; GET estimate reads it from DB.
    _, headers = auth
    client.post("/api/me/mistakes", headers=headers, json={
        "question_text": "q", "correct_answer": "a", "knowledge_point_id": "gs-1.1",
    })
    resp = client.get("/api/me/score/estimate?exam_mode=math-2", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "estimated_score" in body
    assert "pass_probability" in body
    assert "weak_areas" in body


def test_streak(auth):
    _, headers = auth
    resp = client.get("/api/me/streak", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["heatmap"]) == 90


# ─── pay ───

def test_plans_public():
    resp = client.get("/api/pay/plans")
    assert resp.status_code == 200
    assert len(resp.json()["plans"]) == 3


def test_prepay_creates_pending(auth):
    _, headers = auth
    resp = client.post("/api/pay/wechat/prepay", headers=headers, json={"plan": "monthly"})
    assert resp.status_code == 200
    assert resp.json()["amount"] == 2900


def test_prepay_rejects_unknown_plan(auth):
    _, headers = auth
    assert client.post("/api/pay/wechat/prepay", headers=headers,
                       json={"plan": "lifetime"}).status_code == 400


# ─── exercise grading (closes the learning loop) ───

def test_grade_correct_updates_mastery(auth):
    uid, headers = auth
    with patch("app.services.deepseek.chat", new_callable=AsyncMock) as m:
        m.return_value = '{"correct": true, "feedback": "答案正确"}'
        resp = client.post("/api/learn/exercise/grade", headers=headers, json={
            "kp_id": "gs-5.1", "question": "1+1=?", "user_answer": "2",
        })
    assert resp.status_code == 200
    assert resp.json()["correct"] is True
    prog = client.get("/api/me/progress", headers=headers)
    assert prog.json()["total_knowledge_points"] >= 1


def test_grade_incorrect(auth):
    _, headers = auth
    with patch("app.services.deepseek.chat", new_callable=AsyncMock) as m:
        m.return_value = '{"correct": false, "feedback": "计算错误"}'
        resp = client.post("/api/learn/exercise/grade", headers=headers, json={
            "kp_id": "gs-5.2", "question": "2*2=?", "user_answer": "5",
        })
    assert resp.status_code == 200
    assert resp.json()["correct"] is False


def test_grade_requires_auth():
    resp = client.post("/api/learn/exercise/grade", json={
        "kp_id": "gs-5.1", "question": "q", "user_answer": "a",
    })
    assert resp.status_code == 401
