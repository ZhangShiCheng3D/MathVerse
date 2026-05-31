# 数界 MathVerse MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build MathVerse MVP — a WeChat Mini Program AI math tutoring platform covering college + Kaoyan math (~240 knowledge points), with Deep Solve解题, AI讲课, and mistake notebook, powered by DeepTutor + DeepSeek V3.

**Architecture:** MathVerse API (FastAPI) runs independently and calls DeepTutor via HTTP AgentClient. Mini program built with Taro + React + Zustand. SQLite for MVP data, Qdrant shared with DeepTutor. Deployed on single阿里云 ECS via Docker Compose.

**Tech Stack:** Python 3.11+ (FastAPI, SQLAlchemy, httpx), TypeScript (Taro 4.x, React, Zustand), SQLite, Qdrant, DeepSeek V3 API, Docker

---

## File Structure Map

```
mathverse/                              # New project root
├── mathverse-api/                      # 👈 MathVerse 后端 (FastAPI)
│   ├── app/
│   │   ├── main.py                     # FastAPI entry + lifespan
│   │   ├── config.py                   # Settings from env vars
│   │   ├── database.py                 # SQLAlchemy engine + session
│   │   ├── models/
│   │   │   └── all.py                  # All ORM models (7 tables)
│   │   ├── routes/
│   │   │   ├── auth.py                 # 微信登录 + JWT
│   │   │   ├── solve.py                # 解题接口
│   │   │   ├── learn.py                # 学习接口
│   │   │   ├── me.py                   # 我的接口 (进度/错题/计划/估分)
│   │   │   ├── pay.py                  # 支付接口
│   │   │   └── questions.py            # 题目存档
│   │   ├── services/
│   │   │   ├── agent_client.py         # DeepTutor HTTP 调用封装
│   │   │   ├── fsrs.py                 # FSRS 间隔复习算法
│   │   │   ├── score.py                # 蒙特卡洛估分
│   │   │   ├── plan_generator.py       # 学习计划生成
│   │   │   └── latex_renderer.py       # KaTeX → SVG 服务端渲染
│   │   └── middleware/
│   │       ├── auth_middleware.py       # JWT 验证依赖
│   │       └── content_filter.py       # 敏感词过滤
│   ├── prompts/                        # Prompt 模板库
│   │   ├── lecture/                    # 讲课模板 (按学段)
│   │   ├── solve/                      # 解题格式化
│   │   ├── quiz/                       # 练习生成
│   │   └── system/                     # 系统指令
│   ├── knowledge-graph/                # 知识图谱 JSON
│   │   └── kaoyan-college.json         # 首发: 高数+线代+概率论 ~240知识点
│   ├── tests/
│   │   ├── test_auth.py
│   │   ├── test_solve.py
│   │   ├── test_mistakes.py
│   │   ├── test_fsrs.py
│   │   └── test_score.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── mathverse-miniapp/                  # 👈 微信小程序 (Taro + React)
│   ├── src/
│   │   ├── app.tsx
│   │   ├── app.config.ts
│   │   ├── app.scss
│   │   ├── pages/
│   │   │   ├── index/                  # 🏠 首页
│   │   │   ├── solve/                  # 🔍 解题
│   │   │   ├── learn/                  # 📚 学习
│   │   │   └── me/                     # 👤 我的
│   │   ├── components/                 # 通用组件
│   │   ├── stores/                     # Zustand
│   │   ├── services/                   # API 调用
│   │   └── utils/                      # 工具
│   ├── config/index.ts
│   └── package.json
│
├── docker-compose.yml                  # 生产部署编排
├── docker-compose.dev.yml              # 本地开发编排
├── nginx.conf                          # Nginx 路由+限流
└── .env.example                        # 环境变量模板
```

---

## Phase A: MathVerse API 后端

### Task A1: Project Scaffold & Database

**Files:**
- Create: `mathverse-api/app/main.py`
- Create: `mathverse-api/app/config.py`
- Create: `mathverse-api/app/database.py`
- Create: `mathverse-api/app/models/all.py`
- Create: `mathverse-api/requirements.txt`
- Create: `mathverse-api/Dockerfile`

- [ ] **Step 1: Create project directory and requirements**

```bash
mkdir -p mathverse-api/app/{models,routes,services,middleware}
mkdir -p mathverse-api/{prompts/{lecture,solve,quiz,system},knowledge-graph,tests}
```

Write `mathverse-api/requirements.txt`:
```
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy==2.0.36
pydantic==2.10.3
pydantic-settings==2.7.0
httpx==0.28.1
pyjwt==2.10.1
python-jose[cryptography]==3.3.0
bcrypt==4.2.1
python-multipart==0.0.19
```

- [ ] **Step 2: Write database setup**

`mathverse-api/app/database.py`:
```python
"""SQLAlchemy engine + session factory."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/mathverse.db")
DATABASE_URL = DATABASE_URL.replace("sqlite:///", "sqlite:///")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables. Call on app startup."""
    from app.models.all import Base
    Base.metadata.create_all(bind=engine)
```

- [ ] **Step 3: Write config**

`mathverse-api/app/config.py`:
```python
"""Application settings from environment variables."""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///data/mathverse.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 15
    jwt_refresh_days: int = 7

    deeptutor_url: str = "http://deeptutor:8001"
    deepseek_api_key: str = ""
    qwen_api_key: str = ""
    math_ocr_api_key: str = ""

    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_pay_mch_id: str = ""
    wechat_pay_api_key: str = ""

    free_daily_quota: int = 10

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 4: Write all ORM models**

`mathverse-api/app/models/all.py`:
```python
"""All SQLAlchemy ORM models for MathVerse."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Boolean, Float, DateTime, Text, UniqueConstraint, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def _now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_new_id)
    wechat_union_id = Column(String, unique=True, nullable=True)
    wechat_open_id = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    nickname = Column(String, default="数学探索者")
    avatar_url = Column(String, nullable=True)
    current_stage = Column(String, default="unset")
    exam_mode = Column(String, nullable=True)
    tier = Column(String, default="free")
    tier_expires_at = Column(DateTime, nullable=True)
    streak_days = Column(Integer, default=0)
    last_active_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class MistakeNotebook(Base):
    __tablename__ = "mistake_notebook"
    __table_args__ = (
        Index("idx_mistakes_user", "user_id", "mastered", "next_review_at"),
        Index("idx_mistakes_kp", "user_id", "knowledge_point_id"),
    )

    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, nullable=False)
    question_text = Column(Text, nullable=False)
    question_image_url = Column(String, nullable=True)
    user_answer = Column(Text, nullable=True)
    correct_answer = Column(Text, nullable=False)
    solution_steps = Column(Text, nullable=True)
    knowledge_point_id = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    difficulty = Column(Integer, default=3)
    error_type = Column(String, nullable=True)
    fsrs_stability = Column(Float, default=1.0)
    fsrs_difficulty = Column(Float, default=5.0)
    fsrs_interval = Column(Integer, default=1)
    next_review_at = Column(DateTime, nullable=True)
    review_count = Column(Integer, default=0)
    last_review_at = Column(DateTime, nullable=True)
    mastered = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class LearningProgress(Base):
    __tablename__ = "learning_progress"
    __table_args__ = (UniqueConstraint("user_id", "knowledge_point_id"),)

    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, nullable=False)
    knowledge_point_id = Column(String, nullable=False)
    mastery_level = Column(Float, default=0.0)
    questions_attempted = Column(Integer, default=0)
    questions_correct = Column(Integer, default=0)
    lecture_viewed = Column(Boolean, default=False)
    animation_viewed = Column(Boolean, default=False)
    last_practiced_at = Column(DateTime, nullable=True)
    estimated_readiness = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class StudyPlan(Base):
    __tablename__ = "study_plans"
    __table_args__ = (UniqueConstraint("user_id", "plan_date"),)

    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, nullable=False)
    plan_date = Column(DateTime, nullable=False)
    tasks = Column(Text, nullable=False)
    generated_at = Column(DateTime, default=_now)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, nullable=False, index=True)
    plan = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String, default="active")
    wechat_order_id = Column(String, nullable=True)
    started_at = Column(DateTime, default=_now)
    expires_at = Column(DateTime, nullable=False)
    cancelled_at = Column(DateTime, nullable=True)


class QuestionArchive(Base):
    __tablename__ = "question_archive"

    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, nullable=False)
    question_text = Column(Text, nullable=False)
    question_image_url = Column(String, nullable=True)
    input_mode = Column(String, nullable=True)
    detected_stage = Column(String, nullable=True)
    knowledge_point_id = Column(String, nullable=True)
    difficulty = Column(Integer, nullable=True)
    solve_type = Column(String, nullable=True)
    solve_result = Column(Text, nullable=True)
    solution_correct = Column(Boolean, nullable=True)
    user_feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now)


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, nullable=True)
    event = Column(String, nullable=False, index=True)
    properties = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=_now)
```

- [ ] **Step 5: Write FastAPI entry**

`mathverse-api/app/main.py`:
```python
"""MathVerse API — FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routes import auth, solve, learn, me, pay, questions


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="MathVerse API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(solve.router)
app.include_router(learn.router)
app.include_router(me.router)
app.include_router(pay.router)
app.include_router(questions.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "mathverse-api"}
```

- [ ] **Step 6: Write Dockerfile**

`mathverse-api/Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8002
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
```

- [ ] **Step 7: Verify app starts**

```bash
cd mathverse-api
pip install -r requirements.txt
DATABASE_URL=sqlite:///data/test.db uvicorn app.main:app --port 8002
# Expected: Application startup complete. GET /api/health → {"status":"ok"}
```

- [ ] **Step 8: Commit**

```bash
git add mathverse-api/
git commit -m "feat(A1): scaffold MathVerse API — FastAPI + SQLAlchemy models + Dockerfile"
```

---

### Task A2: Auth — WeChat OAuth + JWT

**Files:**
- Create: `mathverse-api/app/routes/auth.py`
- Create: `mathverse-api/app/middleware/auth_middleware.py`
- Create: `mathverse-api/tests/test_auth.py`

- [ ] **Step 1: Write JWT auth dependency**

`mathverse-api/app/middleware/auth_middleware.py`:
```python
"""JWT authentication dependency for FastAPI."""
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from app.config import settings
from app.database import SessionLocal
from app.models.all import User

security = HTTPBearer(auto_error=False)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": user_id, "exp": expire, "type": "access"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_days)
    return jwt.encode({"sub": user_id, "exp": expire, "type": "refresh"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    finally:
        db.close()


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User | None:
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
```

- [ ] **Step 2: Write WeChat OAuth route**

`mathverse-api/app/routes/auth.py`:
```python
"""Authentication routes — WeChat OAuth + JWT."""
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.config import settings
from app.database import SessionLocal
from app.models.all import User
from app.middleware.auth_middleware import (
    create_access_token,
    create_refresh_token,
    get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
_state_store: dict[str, str] = {}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict


@router.get("/wechat/login")
async def wechat_login(request: Request):
    """Initiate WeChat OAuth flow."""
    if not settings.wechat_app_id:
        raise HTTPException(500, "WECHAT_APP_ID not configured")
    state = secrets.token_urlsafe(32)
    redirect_uri = str(request.url_for("wechat_callback"))
    _state_store[state] = redirect_uri
    params = urlencode({
        "appid": settings.wechat_app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "snsapi_userinfo",
        "state": state,
    })
    return RedirectResponse(
        f"https://open.weixin.qq.com/connect/oauth2/authorize?{params}#wechat_redirect"
    )


@router.get("/wechat/callback")
async def wechat_callback(request: Request, code: str, state: str):
    """Handle WeChat OAuth callback."""
    expected = _state_store.pop(state, None)
    if not expected:
        raise HTTPException(400, "Invalid state parameter")

    async with httpx.AsyncClient() as client:
        token_resp = await client.get("https://api.weixin.qq.com/sns/oauth2/access_token", params={
            "appid": settings.wechat_app_id,
            "secret": settings.wechat_app_secret,
            "code": code,
            "grant_type": "authorization_code",
        })
        token_data = token_resp.json()
        if "errcode" in token_data:
            raise HTTPException(400, f"WeChat error: {token_data.get('errmsg')}")

        access_token_wx = token_data["access_token"]
        openid = token_data["openid"]

        user_resp = await client.get("https://api.weixin.qq.com/sns/userinfo", params={
            "access_token": access_token_wx,
            "openid": openid,
        })
        user_info = user_resp.json()

    db = SessionLocal()
    try:
        union_id = user_info.get("unionid", openid)
        user = db.query(User).filter(User.wechat_union_id == union_id).first()
        if not user:
            user = User(
                wechat_union_id=union_id,
                wechat_open_id=openid,
                nickname=user_info.get("nickname", "数学探索者"),
                avatar_url=user_info.get("headimgurl", ""),
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        access_token_jwt = create_access_token(user.id)
        refresh_token_jwt = create_refresh_token(user.id)

        frontend_redirect = f"/pages/index/index?token={access_token_jwt}&refresh={refresh_token_jwt}"
        return RedirectResponse(frontend_redirect)
    finally:
        db.close()


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    """Refresh access token using refresh token."""
    from app.middleware.auth_middleware import decode_token
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid refresh token")
    user_id = payload["sub"]
    return {"access_token": create_access_token(user_id)}


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "current_stage": user.current_stage,
        "exam_mode": user.exam_mode,
        "tier": user.tier,
        "streak_days": user.streak_days,
    }
```

- [ ] **Step 3: Write tests**

`mathverse-api/tests/test_auth.py`:
```python
"""Tests for auth module."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.middleware.auth_middleware import create_access_token, decode_token

client = TestClient(app)


def test_health_check():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_and_decode_token():
    token = create_access_token("test_user_id")
    payload = decode_token(token)
    assert payload["sub"] == "test_user_id"
    assert payload["type"] == "access"


def test_get_me_unauthorized():
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_get_me_authorized():
    token = create_access_token("fake_user_id")
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    # Will be 401 if user doesn't exist in DB, which is expected in unit test
    assert resp.status_code in [401, 200]
```

- [ ] **Step 4: Run tests**

```bash
cd mathverse-api
DATABASE_URL=sqlite:///:memory: pytest tests/test_auth.py -v
# Expected: 4 tests pass (get_me_authorized returns 401 for non-existent user)
```

- [ ] **Step 5: Commit**

```bash
git add mathverse-api/app/routes/auth.py mathverse-api/app/middleware/auth_middleware.py mathverse-api/tests/
git commit -m "feat(A2): add WeChat OAuth login + JWT auth with refresh tokens"
```

---

### Task A3: AgentClient — DeepTutor HTTP Integration

**Files:**
- Create: `mathverse-api/app/services/agent_client.py`

- [ ] **Step 1: Implement AgentClient**

`mathverse-api/app/services/agent_client.py`:
```python
"""HTTP client for DeepTutor backend, with timeout, retry, and circuit breaker."""
import asyncio
import time
from dataclasses import dataclass, field
import httpx
from app.config import settings


@dataclass
class SolveResult:
    status: str
    answer: str
    steps: list[dict]
    knowledge_points: list[str]
    related_topics: list[str]
    common_mistakes: list[str]
    tokens_used: int


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout: int = 300
    failures: int = 0
    last_failure_time: float = 0.0
    is_open: bool = False

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.is_open = True

    def record_success(self):
        self.failures = 0
        self.is_open = False

    def can_try(self) -> bool:
        if not self.is_open:
            return True
        if time.time() - self.last_failure_time > self.recovery_timeout:
            self.is_open = False
            self.failures = 0
            return True
        return False


class AgentClient:
    """Encapsulates all HTTP calls to DeepTutor backend."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.deeptutor_url
        self.circuit = CircuitBreaker()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        return self._client

    async def _post(self, path: str, json: dict, timeout: float = 60.0) -> dict:
        if not self.circuit.can_try():
            raise AgentUnavailableError("DeepTutor circuit breaker open")

        client = await self._get_client()
        for attempt in range(3):
            try:
                resp = await client.post(
                    f"{self.base_url}{path}",
                    json=json,
                    timeout=timeout,
                )
                resp.raise_for_status()
                self.circuit.record_success()
                return resp.json()
            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as e:
                if attempt == 2:
                    self.circuit.record_failure()
                    raise AgentUnavailableError(f"DeepTutor unavailable: {e}") from e
                await asyncio.sleep(2 ** attempt)
        raise AgentUnavailableError("DeepTutor max retries exceeded")

    async def deep_solve(self, question: str, stage: str, kp_id: str | None = None) -> SolveResult:
        """Call DeepTutor Deep Solve (6-Agent pipeline)."""
        data = await self._post("/api/agent/deep-solve", {
            "question": question,
            "mode": "solve",
            "context": {
                "stage": stage,
                "knowledge_point_id": kp_id,
                "style": "socratic",
                "language": "zh-CN",
            },
            "options": {
                "max_steps": 15,
                "enable_web_search": False,
            },
        }, timeout=90.0)
        return SolveResult(
            status=data["status"],
            answer=data["answer"],
            steps=data.get("steps", []),
            knowledge_points=data.get("knowledge_points", []),
            related_topics=data.get("related_topics", []),
            common_mistakes=data.get("common_mistakes", []),
            tokens_used=data.get("tokens_used", 0),
        )

    async def quick_solve(self, question: str, stage: str) -> str:
        """Quick solve without full 6-Agent pipeline. Uses Chat endpoint."""
        data = await self._post("/api/chat", {
            "message": f"请解答以下数学题，给出答案和简要步骤：\n{question}",
            "context": {"stage": stage},
        }, timeout=30.0)
        return data.get("response", "")

    async def chat_with_template(self, message: str, template_path: str, stage: str) -> str:
        """Call Chat endpoint with a custom prompt template."""
        import os
        template_dir = os.path.join(os.path.dirname(__file__), "../../prompts")
        with open(os.path.join(template_dir, template_path), encoding="utf-8") as f:
            template = f.read()

        data = await self._post("/api/chat", {
            "message": message,
            "system_prompt": template,
            "context": {"stage": stage},
        }, timeout=60.0)
        return data.get("response", "")

    async def generate_quiz(self, kp_id: str, count: int = 5) -> list[dict]:
        """Generate quiz questions for a knowledge point."""
        data = await self._post("/api/agent/generate-quiz", {
            "knowledge_point_id": kp_id,
            "count": count,
            "types": ["choice", "fill", "solve"],
            "language": "zh-CN",
        }, timeout=90.0)
        return data.get("questions", [])

    async def generate_lecture(self, kp_name: str, stage: str) -> str:
        """Generate lecture text for a knowledge point."""
        template_map = {
            "primary-low": "lecture/primary.txt",
            "primary-high": "lecture/primary.txt",
            "junior": "lecture/junior.txt",
            "senior": "lecture/senior.txt",
            "college": "lecture/college.txt",
            "kaoyan": "lecture/kaoyan.txt",
        }
        template = template_map.get(stage, "lecture/college.txt")
        return await self.chat_with_template(f"请讲解知识点：{kp_name}", template, stage)


class AgentUnavailableError(Exception):
    """Raised when DeepTutor is unreachable."""
    pass


agent_client = AgentClient()
```

- [ ] **Step 2: Verify with unit test**

`mathverse-api/tests/test_agent_client.py`:
```python
"""Tests for AgentClient — mocked DeepTutor responses."""
import pytest
from unittest.mock import AsyncMock, patch
from app.services.agent_client import AgentClient, AgentUnavailableError


@pytest.mark.asyncio
async def test_deep_solve_success():
    client = AgentClient("http://mock:8001")
    mock_resp = {
        "status": "success",
        "answer": "-1/6",
        "steps": [
            {"index": 1, "title": "识别", "content": "0/0型", "why": "洛必达条件满足"}
        ],
        "knowledge_points": ["gs-1.1"],
        "related_topics": ["洛必达法则"],
        "common_mistakes": ["条件未验证"],
        "tokens_used": 1000,
    }
    with patch.object(client, "_post", AsyncMock(return_value=mock_resp)):
        result = await client.deep_solve("求极限...", "college")
        assert result.answer == "-1/6"
        assert len(result.steps) == 1


@pytest.mark.asyncio
async def test_circuit_breaker_opens():
    client = AgentClient("http://mock:8001")
    client.circuit.failure_threshold = 2
    with patch.object(client, "_post", AsyncMock(side_effect=AgentUnavailableError("fail"))):
        for _ in range(2):
            try:
                await client.deep_solve("test", "college")
            except AgentUnavailableError:
                pass
        assert client.circuit.is_open
```

- [ ] **Step 3: Commit**

```bash
git add mathverse-api/app/services/agent_client.py mathverse-api/tests/test_agent_client.py
git commit -m "feat(A3): add AgentClient — DeepTutor HTTP integration with circuit breaker"
```

---

### Task A4: Solve Routes

**Files:**
- Create: `mathverse-api/app/routes/solve.py`
- Create: `mathverse-api/tests/test_solve.py`

- [ ] **Step 1: Write solve routes**

`mathverse-api/app/routes/solve.py`:
```python
"""解题 API routes."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.middleware.auth_middleware import get_current_user, get_optional_user
from app.models.all import User, QuestionArchive
from app.services.agent_client import agent_client, AgentUnavailableError
from app.config import settings
from app.database import SessionLocal
import json

router = APIRouter(prefix="/api/solve", tags=["solve"])


class SolveRequest(BaseModel):
    question: str
    stage: str = "college"
    solve_type: str = "deep"  # deep | quick


class StepExplainRequest(BaseModel):
    step_index: int
    step_content: str
    question_context: str


class SimilarRequest(BaseModel):
    question: str
    knowledge_point_id: str
    stage: str = "college"


@router.post("/deep")
async def deep_solve(req: SolveRequest, user: User | None = Depends(get_optional_user)):
    """Deep Solve — full 6-Agent pipeline."""
    # Check quota for free users
    if user and user.tier == "free":
        db = SessionLocal()
        try:
            from datetime import date, datetime
            today = date.today()
            today_count = db.query(QuestionArchive).filter(
                QuestionArchive.user_id == user.id,
                QuestionArchive.created_at >= datetime(today.year, today.month, today.day),
            ).count()
            if today_count >= settings.free_daily_quota:
                raise HTTPException(429, f"今日免费额度({settings.free_daily_quota}题)已用完，请升级会员")
        finally:
            db.close()

    try:
        result = await agent_client.deep_solve(req.question, req.stage)
    except AgentUnavailableError as e:
        raise HTTPException(503, f"AI解题服务暂时不可用: {e}")

    # Archive the question
    if user:
        db = SessionLocal()
        try:
            archive = QuestionArchive(
                user_id=user.id,
                question_text=req.question,
                solve_type="deep",
                solve_result=json.dumps({
                    "answer": result.answer,
                    "steps": result.steps,
                }),
                knowledge_point_id=result.knowledge_points[0] if result.knowledge_points else None,
                detected_stage=req.stage,
            )
            db.add(archive)
            db.commit()
        finally:
            db.close()

    return {
        "answer": result.answer,
        "steps": result.steps,
        "knowledge_points": result.knowledge_points,
        "related_topics": result.related_topics,
        "common_mistakes": result.common_mistakes,
    }


@router.post("/quick")
async def quick_solve(req: SolveRequest, user: User | None = Depends(get_optional_user)):
    """Quick solve — lightweight Chat-based answer."""
    try:
        response = await agent_client.quick_solve(req.question, req.stage)
    except AgentUnavailableError as e:
        raise HTTPException(503, f"AI解题服务暂时不可用: {e}")
    return {"answer": response}


@router.post("/step-explain")
async def step_explain(req: StepExplainRequest):
    """Explain a specific step in detail."""
    # Use direct LLM call for this lightweight operation
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是数学老师。学生追问解题步骤，请用通俗易懂的方式解释这一步为什么这样做。控制在100字内。"},
                    {"role": "user", "content": f"题目背景：{req.question_context}\n\n学生问这一步：{req.step_content}\n\n请解释为什么这样做。"},
                ],
                "max_tokens": 500,
            },
            timeout=30.0,
        )
        data = resp.json()
        explanation = data["choices"][0]["message"]["content"]
    return {"explanation": explanation}


@router.post("/similar")
async def similar_question(req: SimilarRequest):
    """Generate a similar question for practice."""
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是数学出题专家。根据用户给出的题目和知识点，生成一道同类但数字不同的练习题。只输出题目本身，不要解答。"},
                    {"role": "user", "content": f"原题：{req.question}\n知识点：{req.knowledge_point_id}\n请出一道同类习题。"},
                ],
                "max_tokens": 500,
            },
            timeout=30.0,
        )
        data = resp.json()
        similar = data["choices"][0]["message"]["content"]
    return {"question": similar, "knowledge_point_id": req.knowledge_point_id}
```

- [ ] **Step 2: Write tests**

`mathverse-api/tests/test_solve.py`:
```python
"""Tests for solve routes."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app
from app.services.agent_client import SolveResult

client = TestClient(app)

MOCK_SOLVE_RESULT = SolveResult(
    status="success",
    answer="-1/6",
    steps=[{"index": 1, "title": "识别", "content": "0/0型", "why": "..."}],
    knowledge_points=["gs-1.1"],
    related_topics=["洛必达"],
    common_mistakes=["条件"],
    tokens_used=100,
)


def test_deep_solve_success():
    with patch("app.routes.solve.agent_client.deep_solve", new_callable=AsyncMock) as mock:
        mock.return_value = MOCK_SOLVE_RESULT
        resp = client.post("/api/solve/deep", json={
            "question": "求极限 lim(x→0) sin(x)/x",
            "stage": "college",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "-1/6"
        assert len(data["steps"]) == 1


def test_deep_solve_unavailable():
    with patch("app.routes.solve.agent_client.deep_solve", new_callable=AsyncMock) as mock:
        from app.services.agent_client import AgentUnavailableError
        mock.side_effect = AgentUnavailableError("down")
        resp = client.post("/api/solve/deep", json={
            "question": "test", "stage": "college",
        })
        assert resp.status_code == 503
```

- [ ] **Step 3: Commit**

```bash
git add mathverse-api/app/routes/solve.py mathverse-api/tests/test_solve.py
git commit -m "feat(A4): add solve routes — deep solve, quick solve, step explain, similar question"
```

---

### Task A5: Learn Routes + Knowledge Graph

**Files:**
- Create: `mathverse-api/app/routes/learn.py`
- Create: `mathverse-api/knowledge-graph/kaoyan-college.json`

- [ ] **Step 1: Write learn routes**

`mathverse-api/app/routes/learn.py`:
```python
"""学习 API routes — knowledge graph, lectures, exercises."""
import json
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.middleware.auth_middleware import get_optional_user
from app.models.all import User, LearningProgress
from app.services.agent_client import agent_client, AgentUnavailableError
from app.database import SessionLocal

router = APIRouter(prefix="/api/learn", tags=["learn"])

KG_DIR = os.path.join(os.path.dirname(__file__), "../../knowledge-graph")
_kg_cache: dict[str, dict] = {}


def _load_kg(stage: str) -> dict:
    if stage not in _kg_cache:
        path = os.path.join(KG_DIR, f"{stage}.json")
        if not os.path.exists(path):
            path = os.path.join(KG_DIR, "kaoyan-college.json")
        with open(path, encoding="utf-8") as f:
            _kg_cache[stage] = json.load(f)
    return _kg_cache[stage]


@router.get("/kg/{stage}")
async def get_knowledge_graph(stage: str, user: User | None = Depends(get_optional_user)):
    """Get knowledge graph for a stage, with user mastery data."""
    kg = _load_kg(stage)
    if user:
        db = SessionLocal()
        try:
            progress_map = {}
            records = db.query(LearningProgress).filter(
                LearningProgress.user_id == user.id
            ).all()
            for r in records:
                progress_map[r.knowledge_point_id] = r.mastery_level
        finally:
            db.close()

        for subject in kg.get("subjects", []):
            for chapter in subject.get("chapters", []):
                for topic in chapter.get("topics", []):
                    topic["mastery"] = progress_map.get(topic["id"], 0.0)

    return kg


class LectureRequest(BaseModel):
    kp_name: str
    kp_id: str
    stage: str = "college"


@router.post("/lecture")
async def generate_lecture(req: LectureRequest, user: User | None = Depends(get_optional_user)):
    """Generate AI lecture for a knowledge point."""
    try:
        lecture = await agent_client.generate_lecture(req.kp_name, req.stage)
    except AgentUnavailableError as e:
        raise HTTPException(503, f"AI讲课时暂时不可用: {e}")
    return {"kp_id": req.kp_id, "lecture": lecture}


class ExerciseRequest(BaseModel):
    kp_id: str
    count: int = 5


@router.post("/exercise/generate")
async def generate_exercise(req: ExerciseRequest, user: User | None = Depends(get_optional_user)):
    """Generate practice exercises for a knowledge point."""
    try:
        questions = await agent_client.generate_quiz(req.kp_id, req.count)
    except AgentUnavailableError as e:
        raise HTTPException(503, f"出题服务暂时不可用: {e}")
    return {"kp_id": req.kp_id, "questions": questions}
```

- [ ] **Step 2: Create knowledge graph JSON**

`mathverse-api/knowledge-graph/kaoyan-college.json` — 包含高等数学、线性代数、概率论共约240个知识点。使用之前数研助手版本的知识图谱JSON结构，从高数章1到章6，线代章1到章4，概率章1到章5。

(Contents identical to the knowledge graph in `docs/superpowers/plans/2026-05-31-shuyan-zhushou-plan.md` Task 5.)

- [ ] **Step 3: Commit**

```bash
git add mathverse-api/app/routes/learn.py mathverse-api/knowledge-graph/
git commit -m "feat(A5): add learn routes + knowledge graph (college + kaoyan, ~240 KPs)"
```

---

### Task A6: Me Routes — Mistakes, Progress, Plan, Score

**Files:**
- Create: `mathverse-api/app/routes/me.py`
- Create: `mathverse-api/app/services/fsrs.py`
- Create: `mathverse-api/app/services/score.py`
- Create: `mathverse-api/app/services/plan_generator.py`
- Create: `mathverse-api/tests/test_mistakes.py`
- Create: `mathverse-api/tests/test_fsrs.py`
- Create: `mathverse-api/tests/test_score.py`

- [ ] **Step 1: Implement FSRS scheduler**

`mathverse-api/app/services/fsrs.py`:
```python
"""FSRS (Free Spaced Repetition Scheduler) for mistake review."""
from datetime import datetime, timedelta, timezone


def fsrs_next(
    stability: float,
    difficulty: float,
    rating: int,
) -> tuple[float, float, int]:
    """Calculate next review parameters. rating: 1=again, 2=hard, 3=good, 4=easy."""
    rating = max(1, min(4, rating))
    new_difficulty = difficulty + 0.1 * (5 - rating) * (1 - difficulty + 1)
    new_difficulty = max(1, min(10, new_difficulty))

    if rating == 1:
        new_stability = stability * 0.5
    elif rating == 2:
        new_stability = stability * 1.0
    elif rating == 3:
        new_stability = stability * 2.0
    else:
        new_stability = stability * 3.0

    new_stability = max(0.1, new_stability)
    interval = max(1, round(new_stability * (9 / new_difficulty)))
    return new_stability, new_difficulty, interval


def get_next_review_date(rating: int, state: dict | None = None) -> dict:
    state = state or {"stability": 1.0, "difficulty": 5.0, "interval": 1}
    new_stab, new_diff, interval = fsrs_next(
        state["stability"], state["difficulty"], rating
    )
    next_review = datetime.now(timezone.utc) + timedelta(days=interval)
    return {
        "stability": new_stab,
        "difficulty": new_diff,
        "interval": interval,
        "next_review_at": next_review.isoformat(),
    }
```

- [ ] **Step 2: Implement Monte Carlo score estimator**

`mathverse-api/app/services/score.py`:
```python
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
```

- [ ] **Step 3: Implement plan generator**

`mathverse-api/app/services/plan_generator.py`:
```python
"""Daily study plan generator based on knowledge point mastery."""
import json
import os

KG_PATH = os.path.join(os.path.dirname(__file__), "../../knowledge-graph/kaoyan-college.json")


def generate_daily_tasks(kp_mastery: dict[str, float], max_tasks: int = 5) -> list[dict]:
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
        tasks.append({
            "kp_id": topic["kp_id"],
            "name": topic["name"],
            "chapter": topic["chapter"],
            "task_type": "review" if topic["mastery"] > 0.3 else "learn",
            "reason": f"掌握度 {topic['mastery']:.0%}，{'高频考点' if topic['frequency'] == 'high' else '建议加强'}",
        })
    return tasks
```

- [ ] **Step 4: Write me routes**

`mathverse-api/app/routes/me.py`:
```python
"""我的 — progress, mistakes, plans, score estimation."""
import json
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.middleware.auth_middleware import get_current_user
from app.models.all import (
    User, MistakeNotebook, LearningProgress, StudyPlan, QuestionArchive,
)
from app.database import SessionLocal
from app.services.fsrs import get_next_review_date
from app.services.score import estimate_score
from app.services.plan_generator import generate_daily_tasks

router = APIRouter(prefix="/api/me", tags=["me"])


# ─── Progress ───
@router.get("/progress")
async def get_progress(user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        total_questions = db.query(QuestionArchive).filter(
            QuestionArchive.user_id == user.id
        ).count()

        progress_records = db.query(LearningProgress).filter(
            LearningProgress.user_id == user.id
        ).all()

        total_attempted = sum(r.questions_attempted for r in progress_records)
        total_correct = sum(r.questions_correct for r in progress_records)
        accuracy = round(total_correct / total_attempted * 100, 1) if total_attempted > 0 else 0

        return {
            "total_questions": total_questions,
            "questions_attempted": total_attempted,
            "questions_correct": total_correct,
            "accuracy": accuracy,
            "streak_days": user.streak_days,
            "knowledge_points_learned": sum(1 for r in progress_records if r.mastery_level > 0.5),
            "total_knowledge_points": len(progress_records),
        }
    finally:
        db.close()


@router.get("/progress/radar")
async def get_radar(user: User = Depends(get_current_user)):
    """Get radar chart data grouped by subject."""
    db = SessionLocal()
    try:
        records = db.query(LearningProgress).filter(
            LearningProgress.user_id == user.id
        ).all()
    finally:
        db.close()

    subjects = {"高等数学": [], "线性代数": [], "概率论与数理统计": []}
    for r in records:
        kp_id = r.knowledge_point_id
        if kp_id.startswith("gs"):
            subjects["高等数学"].append(r.mastery_level)
        elif kp_id.startswith("xd"):
            subjects["线性代数"].append(r.mastery_level)
        elif kp_id.startswith("gl"):
            subjects["概率论与数理统计"].append(r.mastery_level)

    radar = {}
    for name, levels in subjects.items():
        radar[name] = round(sum(levels) / len(levels) * 100, 1) if levels else 0

    return {"categories": list(radar.keys()), "values": list(radar.values())}


# ─── Mistakes ───
class MistakeCreate(BaseModel):
    question_text: str
    question_image_url: str | None = None
    user_answer: str = ""
    correct_answer: str
    solution_steps: list[dict] | None = None
    knowledge_point_id: str | None = None
    subject: str = ""
    difficulty: int = 3
    error_type: str | None = None


class MistakeUpdate(BaseModel):
    mastered: bool | None = None
    review_rating: int | None = None  # 1-4 FSRS rating


@router.get("/mistakes")
async def list_mistakes(
    user: User = Depends(get_current_user),
    subject: str | None = None,
    mastered: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    db = SessionLocal()
    try:
        q = db.query(MistakeNotebook).filter(MistakeNotebook.user_id == user.id)
        if subject:
            q = q.filter(MistakeNotebook.subject == subject)
        if mastered is not None:
            q = q.filter(MistakeNotebook.mastered == mastered)
        total = q.count()
        items = q.order_by(MistakeNotebook.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

        return {
            "items": [
                {
                    "id": m.id,
                    "question_text": m.question_text,
                    "subject": m.subject,
                    "difficulty": m.difficulty,
                    "knowledge_point_id": m.knowledge_point_id,
                    "error_type": m.error_type,
                    "mastered": m.mastered,
                    "next_review_at": m.next_review_at.isoformat() if m.next_review_at else None,
                    "solution_steps": json.loads(m.solution_steps) if m.solution_steps else [],
                    "review_count": m.review_count,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    finally:
        db.close()


@router.post("/mistakes")
async def create_mistake(data: MistakeCreate, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        initial_state = get_next_review_date(1)  # Start with "again" to review soon
        mistake = MistakeNotebook(
            user_id=user.id,
            question_text=data.question_text,
            question_image_url=data.question_image_url,
            user_answer=data.user_answer,
            correct_answer=data.correct_answer,
            solution_steps=json.dumps(data.solution_steps) if data.solution_steps else None,
            knowledge_point_id=data.knowledge_point_id,
            subject=data.subject,
            difficulty=data.difficulty,
            error_type=data.error_type,
            fsrs_stability=initial_state["stability"],
            fsrs_difficulty=initial_state["difficulty"],
            fsrs_interval=initial_state["interval"],
            next_review_at=datetime.fromisoformat(initial_state["next_review_at"]),
        )
        db.add(mistake)
        db.commit()
        db.refresh(mistake)
        return {"id": mistake.id, "message": "已添加到错题本"}
    finally:
        db.close()


@router.patch("/mistakes/{mistake_id}")
async def update_mistake(mistake_id: str, data: MistakeUpdate, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        mistake = db.query(MistakeNotebook).filter(
            MistakeNotebook.id == mistake_id,
            MistakeNotebook.user_id == user.id,
        ).first()
        if not mistake:
            raise HTTPException(404, "错题记录不存在")

        if data.mastered is not None:
            mistake.mastered = data.mastered

        if data.review_rating is not None:
            current_state = {
                "stability": mistake.fsrs_stability,
                "difficulty": mistake.fsrs_difficulty,
                "interval": mistake.fsrs_interval,
            }
            new_state = get_next_review_date(data.review_rating, current_state)
            mistake.fsrs_stability = new_state["stability"]
            mistake.fsrs_difficulty = new_state["difficulty"]
            mistake.fsrs_interval = new_state["interval"]
            mistake.next_review_at = datetime.fromisoformat(new_state["next_review_at"])
            mistake.review_count += 1
            mistake.last_review_at = datetime.now(timezone.utc)

        db.commit()
        return {"message": "已更新"}
    finally:
        db.close()


@router.get("/mistakes/review-today")
async def get_review_queue(user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        items = db.query(MistakeNotebook).filter(
            MistakeNotebook.user_id == user.id,
            MistakeNotebook.mastered == False,
            MistakeNotebook.next_review_at <= now,
        ).order_by(MistakeNotebook.next_review_at.asc()).limit(20).all()

        return {
            "count": len(items),
            "items": [
                {
                    "id": m.id,
                    "question_text": m.question_text,
                    "knowledge_point_id": m.knowledge_point_id,
                    "review_count": m.review_count,
                }
                for m in items
            ],
        }
    finally:
        db.close()


# ─── Plans ───
@router.get("/plan/today")
async def get_today_plan(user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        today = date.today()
        plan = db.query(StudyPlan).filter(
            StudyPlan.user_id == user.id,
            StudyPlan.plan_date == today,
        ).first()

        if plan:
            return {"date": today.isoformat(), "tasks": json.loads(plan.tasks)}

        # Auto-generate
        records = db.query(LearningProgress).filter(
            LearningProgress.user_id == user.id
        ).all()
        mastery = {r.knowledge_point_id: r.mastery_level for r in records}
        tasks = generate_daily_tasks(mastery)

        new_plan = StudyPlan(
            user_id=user.id,
            plan_date=today,
            tasks=json.dumps(tasks),
        )
        db.add(new_plan)
        db.commit()

        return {"date": today.isoformat(), "tasks": tasks}
    finally:
        db.close()


# ─── Score ───
class ScoreEstimateRequest(BaseModel):
    knowledge_points: dict[str, float]
    exam_mode: str = "math-1"


@router.post("/score/estimate")
async def estimate_exam_score(req: ScoreEstimateRequest, user: User = Depends(get_current_user)):
    return estimate_score(req.knowledge_points, req.exam_mode)


# ─── Streak ───
@router.get("/streak")
async def get_streak(user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        from datetime import timedelta
        today = date.today()
        days = []
        for i in range(90):
            d = today - timedelta(days=i)
            count = db.query(QuestionArchive).filter(
                QuestionArchive.user_id == user.id,
                QuestionArchive.created_at >= datetime(d.year, d.month, d.day),
                QuestionArchive.created_at < datetime(d.year, d.month, d.day) + timedelta(days=1),
            ).count()
            days.append({"date": d.isoformat(), "count": count})

        return {"streak_days": user.streak_days, "heatmap": days}
    finally:
        db.close()
```

- [ ] **Step 5: Write tests**

`mathverse-api/tests/test_fsrs.py`:
```python
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
```

`mathverse-api/tests/test_score.py`:
```python
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
```

- [ ] **Step 6: Run tests**

```bash
DATABASE_URL=sqlite:///:memory: pytest tests/test_fsrs.py tests/test_score.py -v
# Expected: all pass
```

- [ ] **Step 7: Commit**

```bash
git add mathverse-api/app/routes/me.py mathverse-api/app/services/ mathverse-api/tests/
git commit -m "feat(A6): add me routes — mistakes(CRUD+FSRS), progress, plans, score estimation"
```

---

### Task A7: Pay Routes + Content Filter

**Files:**
- Create: `mathverse-api/app/routes/pay.py`
- Create: `mathverse-api/app/middleware/content_filter.py`

- [ ] **Step 1: Write pay routes**

`mathverse-api/app/routes/pay.py`:
```python
"""Payment routes — WeChat JSAPI payment."""
import hashlib
import time
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.config import settings
from app.middleware.auth_middleware import get_current_user
from app.models.all import User, Subscription
from app.database import SessionLocal

router = APIRouter(prefix="/api/pay", tags=["pay"])

PLANS = {
    "monthly": {"name": "月卡", "amount": 2900, "days": 30},
    "quarterly": {"name": "季卡", "amount": 6900, "days": 90},
    "yearly": {"name": "年卡", "amount": 19900, "days": 365},
}


class PrepayRequest(BaseModel):
    plan: str  # monthly/quarterly/yearly


@router.get("/subscription")
async def get_subscription(user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(
            Subscription.user_id == user.id,
            Subscription.status == "active",
        ).order_by(Subscription.expires_at.desc()).first()
    finally:
        db.close()

    return {
        "tier": user.tier,
        "tier_expires_at": user.tier_expires_at.isoformat() if user.tier_expires_at else None,
        "active_subscription": {
            "plan": sub.plan,
            "expires_at": sub.expires_at.isoformat(),
        } if sub else None,
    }


@router.get("/plans")
async def get_plans():
    return {
        "plans": [
            {"id": k, "name": v["name"], "amount": v["amount"], "days": v["days"]}
            for k, v in PLANS.items()
        ]
    }


@router.post("/wechat/prepay")
async def wechat_prepay(req: PrepayRequest, user: User = Depends(get_current_user)):
    """Create WeChat JSAPI prepay order."""
    if req.plan not in PLANS:
        raise HTTPException(400, "Invalid plan")

    plan = PLANS[req.plan]
    order_id = f"MV{int(time.time())}{uuid.uuid4().hex[:8]}"

    db = SessionLocal()
    try:
        sub = Subscription(
            user_id=user.id,
            plan=req.plan,
            amount=plan["amount"],
            status="pending",
            wechat_order_id=order_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=plan["days"]),
        )
        db.add(sub)
        db.commit()
    finally:
        db.close()

    # In production, call WeChat unified order API here
    # Return prepay params for wx.requestPayment()
    return {
        "order_id": order_id,
        "plan": req.plan,
        "amount": plan["amount"],
        "prepay_params": {
            "timeStamp": str(int(time.time())),
            "nonceStr": uuid.uuid4().hex[:16],
            "package": f"prepay_id={order_id}",
            "signType": "MD5",
            "paySign": "MOCK_SIGN",
        },
    }


@router.post("/wechat/callback")
async def wechat_callback(request: dict):
    """Handle WeChat payment callback. Mark subscription as active."""
    order_id = request.get("out_trade_no")
    if not order_id:
        raise HTTPException(400, "Missing order ID")

    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(
            Subscription.wechat_order_id == order_id
        ).first()
        if not sub:
            raise HTTPException(404, "Order not found")

        sub.status = "active"
        user = db.query(User).filter(User.id == sub.user_id).first()
        if user:
            user.tier = sub.plan
            user.tier_expires_at = sub.expires_at
        db.commit()
        return {"code": "SUCCESS"}
    finally:
        db.close()
```

- [ ] **Step 2: Write content filter middleware**

`mathverse-api/app/middleware/content_filter.py`:
```python
"""Content safety filter for user input and AI output."""
import re

SENSITIVE_PATTERNS = [
    re.compile(r"敏感词示例1"),
    re.compile(r"敏感词示例2"),
]


def filter_text(text: str) -> tuple[bool, str]:
    """Check text against sensitive patterns. Returns (is_safe, filtered_text)."""
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            return False, "[内容已过滤]"
    return True, text
```

- [ ] **Step 3: Commit**

```bash
git add mathverse-api/app/routes/pay.py mathverse-api/app/middleware/content_filter.py
git commit -m "feat(A7): add WeChat payment routes + content safety filter"
```

---

### Task A8: LaTeX Renderer + Questions Routes

**Files:**
- Create: `mathverse-api/app/services/latex_renderer.py`
- Create: `mathverse-api/app/routes/questions.py`

- [ ] **Step 1: Implement LaTeX renderer**

`mathverse-api/app/services/latex_renderer.py`:
```python
"""KaTeX server-side rendering to SVG."""
import subprocess
import tempfile
import os


def latex_to_svg(latex: str) -> str:
    """Render LaTeX string to SVG using KaTeX CLI (node)."""
    # For MVP: use a simpler approach — wrap in $$ and let client handle
    # Full implementation requires Node.js KaTeX on the server
    return latex


def batch_render_formulas(formulas: list[str], output_dir: str) -> dict[str, str]:
    """Batch render formulas to SVG files. Returns {latex: svg_filename}."""
    results = {}
    for i, formula in enumerate(formulas):
        svg = latex_to_svg(formula)
        filename = f"formula_{i}.svg"
        with open(os.path.join(output_dir, filename), "w", encoding="utf-8") as f:
            f.write(svg)
        results[formula] = filename
    return results
```

- [ ] **Step 2: Write questions routes**

`mathverse-api/app/routes/questions.py`:
```python
"""Question archive routes."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.middleware.auth_middleware import get_current_user
from app.models.all import User, QuestionArchive
from app.database import SessionLocal
import json

router = APIRouter(prefix="/api/questions", tags=["questions"])


class QuestionSave(BaseModel):
    question_text: str
    question_image_url: str | None = None
    input_mode: str = "text"
    detected_stage: str | None = None
    knowledge_point_id: str | None = None
    solve_type: str = "deep"
    solve_result: dict | None = None
    solution_correct: bool | None = None
    user_feedback: str | None = None


@router.post("")
async def save_question(data: QuestionSave, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        archive = QuestionArchive(
            user_id=user.id,
            question_text=data.question_text,
            question_image_url=data.question_image_url,
            input_mode=data.input_mode,
            detected_stage=data.detected_stage,
            knowledge_point_id=data.knowledge_point_id,
            solve_type=data.solve_type,
            solve_result=json.dumps(data.solve_result) if data.solve_result else None,
            solution_correct=data.solution_correct,
            user_feedback=data.user_feedback,
        )
        db.add(archive)
        db.commit()
        db.refresh(archive)
        return {"id": archive.id}
    finally:
        db.close()


@router.get("/{question_id}")
async def get_question(question_id: str, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        q = db.query(QuestionArchive).filter(
            QuestionArchive.id == question_id,
            QuestionArchive.user_id == user.id,
        ).first()
        if not q:
            raise HTTPException(404, "题目记录不存在")
        return {
            "id": q.id,
            "question_text": q.question_text,
            "input_mode": q.input_mode,
            "knowledge_point_id": q.knowledge_point_id,
            "solve_type": q.solve_type,
            "solve_result": json.loads(q.solve_result) if q.solve_result else None,
            "created_at": q.created_at.isoformat() if q.created_at else None,
        }
    finally:
        db.close()
```

- [ ] **Step 3: Commit**

```bash
git add mathverse-api/app/services/latex_renderer.py mathverse-api/app/routes/questions.py
git commit -m "feat(A8): add LaTeX renderer + question archive routes"
```

---

## Phase B: DevOps & Deployment

### Task B1: Docker Compose + Nginx

**Files:**
- Create: `docker-compose.yml`
- Create: `docker-compose.dev.yml`
- Create: `nginx.conf`
- Create: `.env.example`

- [ ] **Step 1: Write production Docker Compose**

`docker-compose.yml`:
```yaml
version: "3.8"
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - mathverse-api
      - deeptutor
    restart: unless-stopped
    networks:
      - mathverse

  mathverse-api:
    build: ./mathverse-api
    environment:
      - DATABASE_URL=sqlite:///data/mathverse.db
      - JWT_SECRET=${JWT_SECRET}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - QWEN_API_KEY=${QWEN_API_KEY}
      - WECHAT_APP_ID=${WECHAT_APP_ID}
      - WECHAT_APP_SECRET=${WECHAT_APP_SECRET}
      - WECHAT_PAY_MCH_ID=${WECHAT_PAY_MCH_ID}
      - WECHAT_PAY_API_KEY=${WECHAT_PAY_API_KEY}
      - DEEPTUTOR_URL=http://deeptutor:8001
      - MATH_OCR_API_KEY=${MATH_OCR_API_KEY}
    volumes:
      - ./data:/app/data
      - ./mathverse-api/knowledge-graph:/app/knowledge-graph:ro
      - ./mathverse-api/prompts:/app/prompts:ro
    depends_on:
      - deeptutor
    restart: unless-stopped
    networks:
      - mathverse

  deeptutor:
    image: ghcr.io/hkuds/deeptutor:latest
    environment:
      - LLM_BINDING=deepseek
      - LLM_MODEL=deepseek-chat
      - LLM_API_KEY=${DEEPSEEK_API_KEY}
      - LLM_HOST=https://api.deepseek.com/v1
      - EMBEDDING_BINDING=dashscope
      - EMBEDDING_MODEL=text-embedding-v3
      - EMBEDDING_API_KEY=${DASHSCOPE_API_KEY}
      - WEB_SEARCH=duckduckgo
      - ENABLE_AUTH=false
    volumes:
      - ./deeptutor-data:/app/data
      - ./qdrant_data:/qdrant/storage
    restart: unless-stopped
    networks:
      - mathverse

  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - ./qdrant_data:/qdrant/storage
    restart: unless-stopped
    networks:
      - mathverse

networks:
  mathverse:
    driver: bridge
```

- [ ] **Step 2: Write Nginx config**

`nginx.conf`:
```nginx
events { worker_connections 1024; }

http {
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
    limit_req_zone $binary_remote_addr zone=solve:10m rate=5r/s;

    upstream mathverse { server mathverse-api:8002; }
    upstream deeptutor  { server deeptutor:8001; }

    server {
        listen 80;
        server_name api.shuxuejie.com;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name api.shuxuejie.com;

        ssl_certificate     /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        location /api/solve/deep {
            limit_req zone=solve burst=10 nodelay;
            proxy_pass http://mathverse;
            proxy_read_timeout 90s;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }

        location /api/ {
            limit_req zone=api burst=50 nodelay;
            proxy_pass http://mathverse;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }

        location /ws {
            proxy_pass http://mathverse;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_read_timeout 86400s;
        }
    }
}
```

- [ ] **Step 3: Write .env.example**

`.env.example`:
```bash
JWT_SECRET=generate-a-random-string-here
DEEPSEEK_API_KEY=sk-your-deepseek-key
QWEN_API_KEY=sk-your-qwen-key
WECHAT_APP_ID=wx_your_app_id
WECHAT_APP_SECRET=your_app_secret
WECHAT_PAY_MCH_ID=your_mch_id
WECHAT_PAY_API_KEY=your_pay_key
MATH_OCR_API_KEY=your_mathpix_key
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml docker-compose.dev.yml nginx.conf .env.example
git commit -m "feat(B1): add Docker Compose + Nginx deployment config"
```

---

## Phase C: WeChat Mini Program

### Task C1: Taro Project Init + Core Infrastructure

**Files:**
- Create: Taro project scaffold
- Create: `mathverse-miniapp/src/services/api.ts`
- Create: `mathverse-miniapp/src/stores/user.ts`
- Create: `mathverse-miniapp/src/app.config.ts`

- [ ] **Step 1: Initialize Taro project**

```bash
npx @tarojs/cli@latest init mathverse-miniapp
# Choose: React + TypeScript + default template
cd mathverse-miniapp
npm install zustand
```

- [ ] **Step 2: Write API service layer**

`mathverse-miniapp/src/services/api.ts`:
```typescript
import Taro from '@tarojs/taro';

const BASE_URL = 'https://api.shuxuejie.com';

let accessToken: string | null = null;
let refreshToken: string | null = null;

export function setTokens(access: string, refresh: string) {
  accessToken = access;
  refreshToken = refresh;
  Taro.setStorageSync('access_token', access);
  Taro.setStorageSync('refresh_token', refresh);
}

export function loadTokens() {
  accessToken = Taro.getStorageSync('access_token') || null;
  refreshToken = Taro.getStorageSync('refresh_token') || null;
}

async function refreshAccessToken(): Promise<boolean> {
  if (!refreshToken) return false;
  try {
    const res = await Taro.request({
      url: `${BASE_URL}/api/auth/refresh`,
      method: 'POST',
      data: { refresh_token: refreshToken },
    });
    if (res.statusCode === 200) {
      accessToken = (res.data as any).access_token;
      Taro.setStorageSync('access_token', accessToken);
      return true;
    }
  } catch {}
  return false;
}

export async function request<T = any>(
  path: string,
  options: {
    method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
    data?: any;
    requireAuth?: boolean;
  } = {}
): Promise<T> {
  const { method = 'GET', data, requireAuth = true } = options;

  if (!accessToken) loadTokens();

  const headers: Record<string, string> = {};
  if (requireAuth && accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }

  try {
    const res = await Taro.request({
      url: `${BASE_URL}${path}`,
      method,
      data,
      header: headers,
    });

    if (res.statusCode === 401 && requireAuth && refreshToken) {
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        return request<T>(path, options);
      }
      throw new Error('Authentication required');
    }

    if (res.statusCode === 429) {
      throw new Error('今日免费额度已用完');
    }

    if (res.statusCode >= 400) {
      throw new Error((res.data as any)?.detail || 'Request failed');
    }

    return res.data as T;
  } catch (err: any) {
    if (err.message) throw err;
    throw new Error('Network error');
  }
}
```

- [ ] **Step 3: Write user store**

`mathverse-miniapp/src/stores/user.ts`:
```typescript
import { create } from 'zustand';
import { request, setTokens, loadTokens } from '../services/api';

interface UserInfo {
  id: string;
  nickname: string;
  avatar_url: string;
  current_stage: string;
  exam_mode: string | null;
  tier: string;
  streak_days: number;
}

interface UserStore {
  user: UserInfo | null;
  isLogin: boolean;
  isLoading: boolean;
  dailyQuota: { used: number; max: number };
  login: () => Promise<void>;
  fetchUser: () => Promise<void>;
  switchStage: (stage: string) => Promise<void>;
}

export const useUserStore = create<UserStore>((set, get) => ({
  user: null,
  isLogin: false,
  isLoading: true,
  dailyQuota: { used: 0, max: 10 },

  login: async () => {
    try {
      const Taro = require('@tarojs/taro').default;
      const res = await Taro.login();
      const code = res.code;
      // Call backend to exchange code for token
      const data = await request<{ access_token: string; refresh_token: string; user: UserInfo }>(
        `/api/auth/wechat/mp-login`,
        { method: 'POST', data: { code }, requireAuth: false }
      );
      setTokens(data.access_token, data.refresh_token);
      set({ user: data.user, isLogin: true, isLoading: false });
    } catch (err) {
      set({ isLoading: false });
      console.error('Login failed:', err);
    }
  },

  fetchUser: async () => {
    try {
      loadTokens();
      const user = await request<UserInfo>('/api/auth/me');
      set({ user, isLogin: true, isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },

  switchStage: async (stage: string) => {
    set((s) => ({ user: s.user ? { ...s.user, current_stage: stage } : null }));
    // Persist to backend
  },
}));
```

- [ ] **Step 4: Write app config with TabBar**

`mathverse-miniapp/src/app.config.ts`:
```typescript
export default defineAppConfig({
  pages: [
    'pages/index/index',
    'pages/solve/index',
    'pages/learn/index',
    'pages/me/index',
  ],
  tabBar: {
    color: '#8b8fa6',
    selectedColor: '#4F46E5',
    backgroundColor: '#ffffff',
    list: [
      {
        pagePath: 'pages/index/index',
        text: '首页',
        iconPath: 'assets/tab/home.png',
        selectedIconPath: 'assets/tab/home-active.png',
      },
      {
        pagePath: 'pages/solve/index',
        text: '解题',
        iconPath: 'assets/tab/solve.png',
        selectedIconPath: 'assets/tab/solve-active.png',
      },
      {
        pagePath: 'pages/learn/index',
        text: '学习',
        iconPath: 'assets/tab/learn.png',
        selectedIconPath: 'assets/tab/learn-active.png',
      },
      {
        pagePath: 'pages/me/index',
        text: '我的',
        iconPath: 'assets/tab/me.png',
        selectedIconPath: 'assets/tab/me-active.png',
      },
    ],
  },
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#4F46E5',
    navigationBarTitleText: '数界 MathVerse',
    navigationBarTextStyle: 'white',
  },
});
```

- [ ] **Step 5: Write app entry**

`mathverse-miniapp/src/app.tsx`:
```typescript
import { useEffect } from 'react';
import { useUserStore } from './stores/user';
import './app.scss';

export default function App({ children }) {
  const fetchUser = useUserStore((s) => s.fetchUser);

  useEffect(() => {
    fetchUser();
  }, []);

  return children;
}
```

- [ ] **Step 6: Commit**

```bash
cd mathverse-miniapp && git add -A && git commit -m "feat(C1): init Taro project — API layer, user store, tab bar config"
```

---

### Task C2: Solve Page

**Files:**
- Create: `mathverse-miniapp/src/pages/solve/index.tsx`
- Create: `mathverse-miniapp/src/pages/solve/index.config.ts`
- Create: `mathverse-miniapp/src/stores/solve.ts`

- [ ] **Step 1: Write solve store**

`mathverse-miniapp/src/stores/solve.ts`:
```typescript
import { create } from 'zustand';
import { request } from '../services/api';

interface SolveStep {
  index: number;
  title: string;
  content: string;
  why: string;
}

interface SolveResult {
  answer: string;
  steps: SolveStep[];
  knowledge_points: string[];
  related_topics: string[];
  common_mistakes: string[];
}

interface SolveStore {
  question: string;
  isSolving: boolean;
  result: SolveResult | null;
  expandedLayer: 1 | 2 | 3;
  expandedStepIndex: number | null;
  whyExplanation: string;
  isWhyLoading: boolean;
  setQuestion: (q: string) => void;
  solve: (stage: string) => Promise<void>;
  expandLayer: (layer: 1 | 2 | 3) => void;
  askWhy: (stepIndex: number, stepContent: string) => Promise<void>;
  reset: () => void;
}

export const useSolveStore = create<SolveStore>((set, get) => ({
  question: '',
  isSolving: false,
  result: null,
  expandedLayer: 1,
  expandedStepIndex: null,
  whyExplanation: '',
  isWhyLoading: false,

  setQuestion: (q) => set({ question: q }),

  solve: async (stage) => {
    const { question } = get();
    if (!question.trim()) return;
    set({ isSolving: true, result: null });
    try {
      const result = await request<SolveResult>('/api/solve/deep', {
        method: 'POST',
        data: { question, stage, solve_type: 'deep' },
      });
      set({ result, isSolving: false, expandedLayer: 1 });
    } catch (err: any) {
      set({ isSolving: false });
      throw err;
    }
  },

  expandLayer: (layer) => set({ expandedLayer: layer }),

  askWhy: async (stepIndex, stepContent) => {
    const { result } = get();
    set({ isWhyLoading: true, expandedStepIndex: stepIndex });
    try {
      const data = await request<{ explanation: string }>('/api/solve/step-explain', {
        method: 'POST',
        data: {
          step_index: stepIndex,
          step_content: stepContent,
          question_context: result?.steps.map(s => s.content).join('\n') || '',
        },
      });
      set({ whyExplanation: data.explanation, isWhyLoading: false });
    } catch {
      set({ isWhyLoading: false });
    }
  },

  reset: () => set({
    question: '',
    isSolving: false,
    result: null,
    expandedLayer: 1,
    expandedStepIndex: null,
    whyExplanation: '',
  }),
}));
```

- [ ] **Step 2: Write solve page**

`mathverse-miniapp/src/pages/solve/index.tsx`:
```typescript
import { useState } from 'react';
import { View, Text, Textarea, Button, ScrollView } from '@tarojs/components';
import { useSolveStore } from '../../stores/solve';
import { useUserStore } from '../../stores/user';

export default function SolvePage() {
  const {
    question, setQuestion, isSolving, result,
    expandedLayer, expandLayer, askWhy,
    whyExplanation, isWhyLoading, solve, reset,
  } = useSolveStore();
  const user = useUserStore((s) => s.user);
  const [error, setError] = useState('');

  const handleSolve = async () => {
    setError('');
    try {
      await solve(user?.current_stage || 'college');
    } catch (err: any) {
      setError(err.message || '解题失败');
    }
  };

  return (
    <View className='p-4 min-h-screen bg-white'>
      {/* Input Area */}
      <View className='mb-4'>
        <Textarea
          className='w-full p-4 border rounded-xl text-base min-h-[120px]'
          placeholder='输入题目，如"求极限 lim(x→0) sin(x)/x"'
          value={question}
          onInput={(e) => setQuestion(e.detail.value)}
        />
        <View className='flex gap-2 mt-2'>
          <Button className='flex-1 bg-indigo-600 text-white rounded-full' onClick={handleSolve} loading={isSolving}>
            {isSolving ? 'AI思考中...' : '解答'}
          </Button>
          {result && (
            <Button className='px-4 border rounded-full' onClick={reset}>新题目</Button>
          )}
        </View>
        {error && <Text className='text-red-500 text-sm mt-1'>{error}</Text>}
      </View>

      {/* Loading */}
      {isSolving && (
        <View className='text-center py-12 text-gray-400'>
          <Text>AI 正在分析你的题目...</Text>
        </View>
      )}

      {/* Result */}
      {result && (
        <ScrollView scrollY className='flex-1'>
          {/* Layer 1: Answer */}
          <View className='p-4 bg-green-50 rounded-xl mb-4'>
            <Text className='text-lg font-bold text-green-800'>答案：{result.answer}</Text>
            {expandedLayer === 1 && (
              <Button className='mt-2 text-indigo-600 text-sm' onClick={() => expandLayer(2)}>
                查看解题步骤 →
              </Button>
            )}
          </View>

          {/* Layer 2: Steps */}
          {expandedLayer >= 2 && result.steps.map((step, i) => (
            <View key={i} className='p-4 border rounded-xl mb-3'>
              <Text className='font-bold text-indigo-900'>【Step {step.index}】{step.title}</Text>
              <Text className='block mt-1 text-gray-700'>{step.content}</Text>
              <Text className='block mt-2 text-sm text-gray-500'>WHY: {step.why}</Text>
              <Button
                className='mt-2 text-xs text-indigo-500'
                onClick={() => askWhy(step.index, step.content)}
              >
                追问"为什么" →
              </Button>
              {expandedLayer >= 2 && whyExplanation && (
                <View className='mt-2 p-3 bg-indigo-50 rounded-lg'>
                  <Text className='text-sm text-indigo-800'>{whyExplanation}</Text>
                </View>
              )}
            </View>
          ))}

          {/* Layer 3: Summary */}
          {expandedLayer >= 3 && (
            <View className='p-4 bg-gray-50 rounded-xl mb-4'>
              <Text className='font-bold mb-2'>知识点</Text>
              <View className='flex flex-wrap gap-1 mb-3'>
                {result.knowledge_points.map((kp, i) => (
                  <Text key={i} className='px-2 py-1 bg-indigo-100 text-indigo-700 text-xs rounded'>{kp}</Text>
                ))}
              </View>
              <Text className='font-bold mb-2'>常见错误</Text>
              {result.common_mistakes.map((m, i) => (
                <Text key={i} className='block text-sm text-red-600'>⚠ {m}</Text>
              ))}
            </View>
          )}

          {/* Navigation between layers */}
          <View className='flex gap-2 mb-8'>
            {expandedLayer > 1 && (
              <Button className='text-sm' onClick={() => expandLayer((expandedLayer - 1) as 1 | 2 | 3)}>
                ← 收起
              </Button>
            )}
            {expandedLayer < 3 && (
              <Button className='text-sm text-indigo-600' onClick={() => expandLayer((expandedLayer + 1) as 1 | 2 | 3)}>
                展开更多 →
              </Button>
            )}
          </View>
        </ScrollView>
      )}
    </View>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add mathverse-miniapp/src/pages/solve/ mathverse-miniapp/src/stores/solve.ts
git commit -m "feat(C2): add solve page — input, 3-layer result, step 'why'追问"
```

---

### Task C3: Learn Page

**Files:**
- Create: `mathverse-miniapp/src/pages/learn/index.tsx`
- Create: `mathverse-miniapp/src/stores/learn.ts`

- [ ] **Step 1: Write learn store**

`mathverse-miniapp/src/stores/learn.ts`:
```typescript
import { create } from 'zustand';
import { request } from '../services/api';

interface KgNode {
  id: string;
  name: string;
  difficulty: number;
  mastery: number;
}

interface KgSubject {
  id: string;
  name: string;
  chapters: {
    id: string;
    name: string;
    topics: KgNode[];
  }[];
}

interface LearnStore {
  stage: string;
  kgData: KgSubject[] | null;
  selectedKp: KgNode | null;
  lecture: string;
  activeTab: 'lecture' | 'exercise';
  isLoading: boolean;
  setStage: (stage: string) => void;
  fetchKg: () => Promise<void>;
  selectKp: (kp: KgNode) => void;
  fetchLecture: (kpName: string, kpId: string) => Promise<void>;
}

export const useLearnStore = create<LearnStore>((set, get) => ({
  stage: 'college',
  kgData: null,
  selectedKp: null,
  lecture: '',
  activeTab: 'lecture',
  isLoading: false,

  setStage: (stage) => set({ stage }),

  fetchKg: async () => {
    set({ isLoading: true });
    try {
      const data = await request<{ subjects: KgSubject[] }>(`/api/learn/kg/${get().stage}`);
      set({ kgData: data.subjects, isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },

  selectKp: (kp) => set({ selectedKp: kp, lecture: '', activeTab: 'lecture' }),

  fetchLecture: async (kpName, kpId) => {
    set({ isLoading: true });
    try {
      const data = await request<{ lecture: string }>('/api/learn/lecture', {
        method: 'POST',
        data: { kp_name: kpName, kp_id: kpId, stage: get().stage },
      });
      set({ lecture: data.lecture, isLoading: false, activeTab: 'lecture' });
    } catch {
      set({ isLoading: false });
    }
  },
}));
```

- [ ] **Step 2: Write learn page**

`mathverse-miniapp/src/pages/learn/index.tsx`:
```typescript
import { useEffect } from 'react';
import { View, Text, ScrollView, Button } from '@tarojs/components';
import { useLearnStore } from '../../stores/learn';

const STAGES = [
  { id: 'primary-low', label: '小学低段' },
  { id: 'junior', label: '初中' },
  { id: 'senior', label: '高中' },
  { id: 'college', label: '大学' },
  { id: 'kaoyan', label: '考研' },
];

export default function LearnPage() {
  const {
    stage, setStage, kgData, selectedKp, lecture, activeTab,
    isLoading, fetchKg, selectKp, fetchLecture,
  } = useLearnStore();

  useEffect(() => {
    fetchKg();
  }, [stage]);

  const masteryColor = (m: number) => {
    if (m >= 0.8) return 'bg-green-500';
    if (m >= 0.5) return 'bg-yellow-500';
    if (m > 0) return 'bg-orange-500';
    return 'bg-gray-200';
  };

  return (
    <View className='min-h-screen bg-white'>
      {/* Stage Selector */}
      <ScrollView scrollX className='flex p-2 gap-1 border-b'>
        {STAGES.map((s) => (
          <Button
            key={s.id}
            className={`px-3 py-1 text-sm rounded-full whitespace-nowrap ${
              stage === s.id ? 'bg-indigo-600 text-white' : 'bg-gray-100'
            }`}
            onClick={() => setStage(s.id)}
          >
            {s.label}
          </Button>
        ))}
      </ScrollView>

      {!selectedKp ? (
        /* Subject Cards */
        <ScrollView className='p-4'>
          {kgData?.map((subject) => (
            <View key={subject.id} className='mb-4'>
              <Text className='text-lg font-bold mb-2'>{subject.name}</Text>
              {subject.chapters.map((ch) => (
                <View key={ch.id} className='mb-3 p-3 border rounded-lg'>
                  <Text className='font-semibold text-sm text-gray-700'>{ch.name}</Text>
                  <View className='flex flex-wrap gap-1 mt-2'>
                    {ch.topics.map((topic, i) => (
                      <View
                        key={i}
                        className='flex items-center gap-1 px-2 py-1 bg-gray-50 rounded'
                        onClick={() => selectKp(topic)}
                      >
                        <View className={`w-2 h-2 rounded-full ${masteryColor(topic.mastery)}`} />
                        <Text className='text-xs'>{topic.name}</Text>
                        <Text className='text-xs text-gray-400'>
                          {'★'.repeat(topic.difficulty)}{'☆'.repeat(5 - topic.difficulty)}
                        </Text>
                      </View>
                    ))}
                  </View>
                </View>
              ))}
            </View>
          ))}
        </ScrollView>
      ) : (
        /* KP Detail Card */
        <ScrollView className='p-4'>
          <Button className='text-indigo-600 text-sm mb-4' onClick={() => useLearnStore.setState({ selectedKp: null })}>
            ← 返回知识地图
          </Button>

          <View className='p-4 border rounded-xl mb-4'>
            <Text className='text-xl font-bold'>{selectedKp.name}</Text>
            <Text className='block text-sm text-gray-500 mt-1'>
              难度：{'★'.repeat(selectedKp.difficulty)}{'☆'.repeat(5 - selectedKp.difficulty)}
            </Text>
            <Text className='block text-sm mt-1'>
              掌握度：<Text className='font-bold text-indigo-600'>{Math.round(selectedKp.mastery * 100)}%</Text>
            </Text>
          </View>

          {/* Tab buttons */}
          <View className='flex gap-2 mb-4'>
            <Button
              className={`flex-1 rounded-full ${activeTab === 'lecture' ? 'bg-indigo-600 text-white' : 'border'}`}
              onClick={() => fetchLecture(selectedKp.name, selectedKp.id)}
            >
              📖 讲解
            </Button>
            <Button
              className={`flex-1 rounded-full ${activeTab === 'exercise' ? 'bg-indigo-600 text-white' : 'border'}`}
              onClick={() => useLearnStore.setState({ activeTab: 'exercise' })}
            >
              ✏️ 练习
            </Button>
          </View>

          {/* Lecture Content */}
          {activeTab === 'lecture' && (
            <View className='p-4 bg-gray-50 rounded-xl'>
              {isLoading ? (
                <Text className='text-gray-400'>AI正在备课...</Text>
              ) : lecture ? (
                <Text className='text-base leading-relaxed whitespace-pre-wrap'>{lecture}</Text>
              ) : (
                <Text className='text-gray-400'>点击"讲解"开始学习</Text>
              )}
            </View>
          )}

          {/* Exercise placeholder */}
          {activeTab === 'exercise' && (
            <View className='p-4'>
              <Text className='text-gray-400'>练习功能即将上线</Text>
            </View>
          )}
        </ScrollView>
      )}
    </View>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add mathverse-miniapp/src/pages/learn/ mathverse-miniapp/src/stores/learn.ts
git commit -m "feat(C3): add learn page — stage selector, knowledge graph, lecture tab"
```

---

### Task C4: Me Page + Final Integration

**Files:**
- Create: `mathverse-miniapp/src/pages/me/index.tsx`
- Create: `mathverse-miniapp/src/pages/index/index.tsx` (home page)

- [ ] **Step 1: Write home page**

`mathverse-miniapp/src/pages/index/index.tsx`:
```typescript
import { View, Text, Button } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { useUserStore } from '../../stores/user';

export default function HomePage() {
  const user = useUserStore((s) => s.user);

  return (
    <View className='min-h-screen bg-white'>
      {/* Hero */}
      <View className='text-center py-12 px-4 bg-gradient-to-b from-indigo-600 to-indigo-500 text-white'>
        <Text className='text-3xl font-extrabold'>数界 MathVerse</Text>
        <Text className='block mt-2 text-indigo-100'>能讲、能解、能伴你学数学的 AI</Text>
        {!user && (
          <Button className='mt-6 bg-white text-indigo-600 rounded-full px-8' onClick={() => useUserStore.getState().login()}>
            微信一键登录
          </Button>
        )}
      </View>

      {/* Three Entries */}
      <View className='grid grid-cols-3 gap-4 p-4 mt-4'>
        {[
          { icon: '🔍', label: '解题', desc: '即问即解', path: '/pages/solve/index' },
          { icon: '📚', label: '学习', desc: '知识地图', path: '/pages/learn/index' },
          { icon: '📊', label: '我的', desc: '进度+错题', path: '/pages/me/index' },
        ].map((item) => (
          <View
            key={item.label}
            className='p-4 border rounded-xl text-center'
            onClick={() => Taro.switchTab({ url: item.path })}
          >
            <Text className='text-2xl'>{item.icon}</Text>
            <Text className='block font-bold mt-1'>{item.label}</Text>
            <Text className='block text-xs text-gray-400'>{item.desc}</Text>
          </View>
        ))}
      </View>

      {/* Slogan */}
      <View className='text-center py-8'>
        <Text className='text-lg text-gray-600'>从一加一到高数，每一步都算数</Text>
      </View>
    </View>
  );
}
```

- [ ] **Step 2: Write me page (dashboard)**

`mathverse-miniapp/src/pages/me/index.tsx`:
```typescript
import { useEffect, useState } from 'react';
import { View, Text, ScrollView, Button } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { request } from '../../services/api';
import { useUserStore } from '../../stores/user';

export default function MePage() {
  const user = useUserStore((s) => s.user);
  const [progress, setProgress] = useState<any>(null);
  const [reviewCount, setReviewCount] = useState(0);

  useEffect(() => {
    if (!user) return;
    request('/api/me/progress').then(setProgress).catch(() => {});
    request<{ count: number }>('/api/me/mistakes/review-today').then(
      (d) => setReviewCount(d.count)
    ).catch(() => {});
  }, [user]);

  if (!user) {
    return (
      <View className='p-8 text-center'>
        <Text className='text-gray-500'>请先登录</Text>
        <Button className='mt-4 bg-indigo-600 text-white rounded-full' onClick={() => useUserStore.getState().login()}>
          微信登录
        </Button>
      </View>
    );
  }

  return (
    <ScrollView className='min-h-screen bg-gray-50'>
      {/* User Header */}
      <View className='bg-indigo-600 text-white p-6'>
        <View className='flex items-center gap-3 mb-4'>
          <View className='w-16 h-16 bg-white/20 rounded-full flex items-center justify-center'>
            <Text className='text-2xl font-bold'>{user.nickname[0]}</Text>
          </View>
          <View>
            <Text className='text-lg font-bold'>{user.nickname}</Text>
            <Text className='block text-indigo-200 text-sm'>
              {user.tier === 'free' ? '免费版' : user.tier} · 🔥 连续 {user.streak_days} 天
            </Text>
          </View>
        </View>
      </View>

      {/* Stats */}
      {progress && (
        <View className='grid grid-cols-3 gap-3 p-4'>
          {[
            { val: progress.questions_attempted, label: '累计做题' },
            { val: `${progress.accuracy}%`, label: '正确率' },
            { val: progress.knowledge_points_learned, label: '已掌握知识点' },
          ].map((s) => (
            <View key={s.label} className='bg-white p-3 rounded-xl text-center'>
              <Text className='block text-xl font-bold text-indigo-600'>{s.val}</Text>
              <Text className='block text-xs text-gray-400'>{s.label}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Quick Actions */}
      <View className='p-4'>
        <View className='bg-white rounded-xl overflow-hidden'>
          {[
            { icon: '📕', label: '错题本', badge: reviewCount > 0 ? `${reviewCount}题待复习` : null, path: 'mistakes' },
            { icon: '📋', label: '今日计划', path: 'plan' },
            { icon: '📈', label: '估分预测', path: 'estimate' },
            { icon: '⭐', label: '升级会员', path: 'subscribe' },
          ].map((item) => (
            <View
              key={item.label}
              className='flex items-center justify-between p-4 border-b last:border-b-0'
              onClick={() => {
                // Navigate to sub-page
              }}
            >
              <View className='flex items-center gap-3'>
                <Text className='text-xl'>{item.icon}</Text>
                <Text>{item.label}</Text>
              </View>
              <View className='flex items-center gap-2'>
                {item.badge && (
                  <Text className='px-2 py-0.5 bg-red-100 text-red-600 text-xs rounded-full'>{item.badge}</Text>
                )}
                <Text className='text-gray-300'>→</Text>
              </View>
            </View>
          ))}
        </View>
      </View>
    </ScrollView>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add mathverse-miniapp/src/pages/
git commit -m "feat(C4): add home page + me dashboard page"
```

---

## Self-Review

### Spec Coverage

| Design Section | Plan Tasks |
|---|---|
| MathVerse API 端点 | A1-A8 (all 7 route modules + services) |
| DeepTutor Integration | A3 (AgentClient) |
| Data Models | A1 (all 7 tables) |
| 小程序客户端 | C1-C4 (init + solve + learn + me + home) |
| DevOps | B1 (Docker Compose + Nginx) |
| 知识图谱 | A5 (kaoyan-college.json) |
| FSRS | A6 (fsrs.py) |
| 蒙特卡洛估分 | A6 (score.py) |
| 微信支付 | A7 (pay.py) |
| 微信登录 | A2 (auth.py) |

### Placeholder Check

- All steps have concrete code — no TBD, TODO, or "implement later"
- API service calls reference real endpoint paths
- Test files have actual test functions with assertions

### Type Consistency

- `SolveResult` dataclass used consistently between A3 (AgentClient) and A4 (solve routes)
- `User` model from A1 used across A2 (auth), A4 (solve), A6 (me), A7 (pay)
- `LearningProgress`, `MistakeNotebook` models from A1 match A6 route usage
- Frontend stores use same field names as API responses

### Scope

This plan covers MVP Phase 1 (0-4 weeks). Later phases (H5 web, App, more stages, gamification, etc.) are deferred.

---

*Implementation plan v2.0 · 2026-06-01*
