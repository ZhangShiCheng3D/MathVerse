# 数界 MathVerse — 技术设计文档

> AI数学学习平台 · 微信小程序 · 基于 DeepTutor (Apache 2.0)
> 版本 v2.0 · 2026-06-01

---

## 一、总体架构

### 1.1 架构全景

```
┌─────────────────────────────────────────────────────────────┐
│                       客户端层                               │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ 微信小程序(Taro)  │  │  Web H5       │  │  独立 App     │  │
│  │ (首发)           │  │ (Phase 2)     │  │ (Phase 3)    │  │
│  └────────┬─────────┘  └──────┬───────┘  └──────┬───────┘  │
│           └───────────────────┼──────────────────┘          │
│                               │ HTTPS                       │
└───────────────────────────────┼─────────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Nginx :443           │
                    │   SSL终结 / 路由 / 限流 │
                    └───────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                  ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  MathVerse API  │ │  DeepTutor      │ │  管理后台       │
│  (FastAPI:8002) │ │  (FastAPI:8001) │ │  (Next.js:3782) │
│                 │ │                 │ │                 │
│  • 用户系统     │ │  • Deep Solve   │ │  • 内容管理     │
│  • 错题本       │ │  • Chat/RAG     │ │  • 知识图谱编辑 │
│  • 学习进度     │ │  • Quiz 生成    │ │  • 数据看板     │
│  • 知识地图     │ │  • Math Animator│ │  • 审核工作台   │
│  • 估分引擎     │ │  • Deep Research│ │                 │
│  • 微信登录     │ │  • 知识可视化   │ │                 │
│  • 支付回调     │ │                 │ │                 │
│  • 行为埋点     │ │                 │ │                 │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         └───────────────────┼────────────────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                 ▼
       ┌─────────┐    ┌──────────┐     ┌──────────┐
       │ SQLite  │    │  Qdrant  │     │ 阿里云   │
       │(用户/业务)│   │ (向量库) │     │ OSS(文件)│
       └─────────┘    └──────────┘     └──────────┘
```

### 1.2 核心架构决策

**MathVerse API 与 DeepTutor 解耦部署**

MathVerse API 独立部署，通过 HTTP 调用 DeepTutor 的 Agent 能力。DeepTutor 保持干净，MathVerse 只管业务逻辑。

选择理由：
- DeepTutor 上游持续更新，解耦后不影响 MathVerse 业务迭代
- DeepTutor 的 6 Agent 本质上是"输入→推理→输出"的无状态计算，天然适合微服务调用
- 如果未来替换 Agent 引擎，只需改 AgentClient 调用层

**技术栈**

| 层 | 选型 | 原因 |
|---|------|------|
| 后端框架 | FastAPI (Python 3.11+) | 与 DeepTutor 同技术栈，类型安全 |
| ORM | SQLAlchemy | 从 SQLite 迁移 PostgreSQL 只需换 dialect |
| 小程序框架 | Taro 4.x + React | 未来可编译到 H5、App，组件逻辑复用 |
| 状态管理 | Zustand | 轻量、React hooks 原生体验 |
| 数据库 | SQLite (MVP) → PostgreSQL (增长期) | MVP 阶段 SQLite 完全够用 |
| 向量数据库 | Qdrant | 与 DeepTutor 共享 |
| LLM | DeepSeek V3 (主) + Qwen3 (热备) | 数学推理+中文能力强 |

---

## 二、MathVerse API 端点设计

### 2.1 服务边界

MathVerse API 管理所有业务逻辑（用户、错题、进度、付费），DeepTutor 只负责 AI 推理。MathVerse 通过内部 AgentClient 调用 DeepTutor。

### 2.2 端点清单

**用户 & 认证 `/api/auth`**

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/auth/wechat/login` | GET | 微信 OAuth 入口 |
| `/api/auth/wechat/callback` | GET | 微信回调：换 token → 创建/登录 → JWT |
| `/api/auth/phone/code` | POST | 发送手机验证码（备选） |
| `/api/auth/phone/login` | POST | 验证码登录（备选） |
| `/api/auth/refresh` | POST | 刷新 JWT |
| `/api/auth/me` | GET | 当前用户信息 |

**解题 `/api/solve`**

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/solve/deep` | POST | Deep Solve 解题（核心） — 调用 DeepTutor |
| `/api/solve/quick` | POST | 快速解答（轻量 Chat） |
| `/api/solve/step-explain` | POST | 追问某一步的详细解释 |
| `/api/solve/similar` | POST | 举一反三，生成同类题 |
| `/api/solve/ocr` | POST | 图片 OCR → LaTeX |
| `/api/solve/voice` | POST | 语音 → LaTeX（LLM 转写） |

**学习 `/api/learn`**

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/learn/kg/:stage` | GET | 获取指定学段的知识图谱 |
| `/api/learn/kg/:stage/:kpId` | GET | 获取知识点详情（含掌握度） |
| `/api/learn/lecture` | POST | AI 生成知识点讲课内容 |
| `/api/learn/examples/:kpId` | GET | 获取知识点的经典例题 |
| `/api/learn/exercise/generate` | POST | AI 生成配套练习 |
| `/api/learn/exercise/grade` | POST | 提交作答，AI 判分并更新掌握度 |
| `/api/learn/animation/:kpId` | GET | 获取数学动画（预渲染缓存/CDN URL） |

**我的 `/api/me`**

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/me/progress` | GET | 学习进度总览 |
| `/api/me/progress/radar` | GET | 知识掌握雷达图数据 |
| `/api/me/mistakes` | GET/POST | 错题列表 / 添加错题 |
| `/api/me/mistakes/:id` | PATCH | 更新错题状态（FSRS 评分 / 已掌握） |
| `/api/me/mistakes/review-today` | GET | 今日待复习错题（FSRS 调度） |
| `/api/me/plan/today` | GET | 今日学习计划 |
| `/api/me/plan/generate` | POST | 生成新学习计划 |
| `/api/me/score/estimate` | POST | 蒙特卡洛估分 |
| `/api/me/streak` | GET | 打卡信息（连续天数+热力图） |
| `/api/me/weekly-report` | GET | 周报数据 |

**付费 `/api/pay`**

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/pay/subscription` | GET | 当前订阅状态 |
| `/api/pay/plans` | GET | 定价方案列表 |
| `/api/pay/wechat/prepay` | POST | 微信 JSAPI 预支付 |
| `/api/pay/wechat/callback` | POST | 微信支付结果回调 |

**题目存档 `/api/questions`**

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/questions` | POST | 保存题目记录（题+解答+知识点） |
| `/api/questions/:id` | GET | 查询题目详情 |
| `/api/questions/search` | GET | 搜索题库 |

### 2.3 AgentClient — DeepTutor 调用封装

```python
class AgentClient:
    """封装对 DeepTutor 后端的 HTTP 调用"""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5, recovery_timeout=300
        )

    async def deep_solve(self, question: str, context: dict) -> SolveResult:
        """POST /api/agent/deep-solve — 超时60s，重试2次"""
        ...

    async def chat(self, message: str, history: list, prompt_template: str) -> str:
        """POST /api/chat — 超时30s，注入讲课Prompt模板"""
        ...

    async def generate_quiz(self, kp_id: str, count: int, types: list) -> list[Question]:
        """POST /api/agent/generate-quiz — 超时90s"""
        ...

    async def generate_animation(self, kp_id: str) -> AnimationResult:
        """POST /api/animator/generate — 超时120s，结果进缓存"""
        ...
```

关键设计：
- 超时：Deep Solve 60s, Chat 30s, Quiz 90s, Animator 120s
- 重试：最多2次，指数退避
- 熔断：连续5次失败 → 5分钟内直接返回降级响应
- 降级：DeepTutor 不可用时 → 解题用 DeepSeek 直调（简化版），学习讲解提示不可用

---

## 三、数据模型

### 3.1 设计原则

- SQLite MVP，SQLAlchemy ORM，换 PostgreSQL 只需改 dialect
- 知识图谱作为静态数据（JSON + 内存缓存），不入数据库
- 行为事件单独存储

### 3.2 核心表

**users** — 用户

```sql
CREATE TABLE users (
    id              TEXT PRIMARY KEY,
    wechat_union_id TEXT UNIQUE,
    wechat_open_id  TEXT,
    phone           TEXT,
    nickname        TEXT DEFAULT '数学探索者',
    avatar_url      TEXT,
    current_stage   TEXT DEFAULT 'unset',
    exam_mode       TEXT,
    tier            TEXT DEFAULT 'free',
    tier_expires_at TIMESTAMP,
    streak_days     INTEGER DEFAULT 0,
    last_active_at  TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**mistake_notebook** — 错题本（含 FSRS 字段）

```sql
CREATE TABLE mistake_notebook (
    id                TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL REFERENCES users(id),
    question_text     TEXT NOT NULL,
    question_image_url TEXT,
    user_answer       TEXT,
    correct_answer    TEXT NOT NULL,
    solution_steps    TEXT,               -- JSON
    knowledge_point_id TEXT,
    subject           TEXT,
    difficulty        INTEGER DEFAULT 3,
    error_type        TEXT,               -- concept/formula/calculation/reasoning/careless
    fsrs_stability    REAL DEFAULT 1.0,
    fsrs_difficulty   REAL DEFAULT 5.0,
    fsrs_interval     INTEGER DEFAULT 1,
    next_review_at    TIMESTAMP,
    review_count      INTEGER DEFAULT 0,
    last_review_at    TIMESTAMP,
    mastered          BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_mistakes_user ON mistake_notebook(user_id, mastered, next_review_at);
CREATE INDEX idx_mistakes_kp ON mistake_notebook(user_id, knowledge_point_id);
```

**learning_progress** — 学习进度

```sql
CREATE TABLE learning_progress (
    id                  TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL REFERENCES users(id),
    knowledge_point_id  TEXT NOT NULL,
    mastery_level       REAL DEFAULT 0.0,
    questions_attempted INTEGER DEFAULT 0,
    questions_correct   INTEGER DEFAULT 0,
    lecture_viewed      BOOLEAN DEFAULT FALSE,
    animation_viewed    BOOLEAN DEFAULT FALSE,
    last_practiced_at   TIMESTAMP,
    estimated_readiness REAL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, knowledge_point_id)
);
```

**study_plans** — 每日学习计划

```sql
CREATE TABLE study_plans (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id),
    plan_date    DATE NOT NULL,
    tasks        TEXT NOT NULL,           -- JSON
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, plan_date)
);
```

**subscriptions** — 订阅记录

```sql
CREATE TABLE subscriptions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id),
    plan            TEXT NOT NULL,
    amount          INTEGER NOT NULL,
    status          TEXT DEFAULT 'active',
    wechat_order_id TEXT,
    started_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMP NOT NULL,
    cancelled_at    TIMESTAMP
);
```

**question_archive** — 题目存档

```sql
CREATE TABLE question_archive (
    id                TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL REFERENCES users(id),
    question_text     TEXT NOT NULL,
    question_image_url TEXT,
    input_mode        TEXT,
    detected_stage    TEXT,
    knowledge_point_id TEXT,
    difficulty        INTEGER,
    solve_type        TEXT,
    solve_result      TEXT,               -- JSON
    solution_correct  BOOLEAN,
    user_feedback     TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**analytics_events** — 行为埋点

```sql
CREATE TABLE analytics_events (
    id         TEXT PRIMARY KEY,
    user_id    TEXT,
    event      TEXT NOT NULL,
    properties TEXT,                      -- JSON
    timestamp  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 四、DeepTutor 集成协议

### 4.1 Deep Solve 调用

**请求：** `POST /api/agent/deep-solve`
```json
{
  "question": "求极限 lim(x→0) (sin x - x) / x³",
  "mode": "solve",
  "context": {
    "stage": "college",
    "knowledge_point_id": "gs-1.1",
    "style": "socratic",
    "language": "zh-CN"
  },
  "options": {
    "max_steps": 15,
    "enable_web_search": false,
    "knowledge_filter": ["gs-1.*"]
  }
}
```

**响应：**
```json
{
  "status": "success",
  "answer": "-1/6",
  "steps": [
    {
      "index": 1,
      "title": "识别题目类型",
      "content": "当 x→0 时分子 sin x - x → 0，分母 x³ → 0，属于 0/0 型不定式。适用洛必达法则。",
      "latex": null,
      "why": "洛必达法则要求分子分母在极限点都是无穷小，且导数之比极限存在。"
    }
  ],
  "knowledge_points": ["gs-1.1", "gs-1.2"],
  "related_topics": ["洛必达法则", "高阶无穷小", "泰勒展开"],
  "common_mistakes": ["未验证洛必达适用条件", "无穷小阶数判断错误"],
  "tokens_used": 4520
}
```

### 4.2 Prompt 模板管理

MathVerse 维护自己的 Prompt 模板库，不修改 DeepTutor 源码。调用时注入。

```
mathverse-api/prompts/
├── lecture/        # 讲课风格（按学段分：primary/junior/senior/college/kaoyan）
├── solve/          # 解题格式化指令 + 追问模板
├── quiz/           # 练习生成 + 举一反三
└── system/         # 内容安全指令 + 学段识别
```

### 4.3 Math Animator 缓存策略

Manim 渲染慢（30-120s），采用预渲染+缓存：

- MVP 阶段预渲染 Top 40 核心动画，随版本部署
- 命中缓存 → 直接返回 CDN URL
- 未命中 → 提交后台渲染队列 → 完成后通过微信服务通知提醒
- 渲染结果上传 OSS + 写入缓存

---

## 五、小程序客户端

### 5.1 技术栈

| 层 | 选型 |
|---|------|
| 框架 | Taro 4.x + React |
| 状态管理 | Zustand |
| 数学公式 | KaTeX → SVG（服务端预渲染） |
| 图表 | ECharts for Taro |
| 样式 | Tailwind (Taro 插件) |

### 5.2 页面结构

```
mathverse-miniapp/src/
├── pages/
│   ├── index/           # 🏠 首页
│   ├── solve/           # 🔍 解题（输入+结果三层展示+追问弹窗）
│   ├── learn/           # 📚 学习（学段选择+知识地图+学习卡片）
│   └── me/              # 👤 我的（仪表盘+错题本+复习+计划+估分+设置）
├── components/          # 通用组件（AiFloatBall, FormulaRenderer, PaywallModal...）
├── stores/              # Zustand (user, solve, learn, me)
├── services/            # API 调用层
├── utils/               # 工具函数
└── constants/           # 常量定义
```

### 5.3 三个核心页面组件树

**🔍 解题页**
```
SolvePage → InputBar (VoiceButton / TextInput / CameraButton)
          → QuestionPreview
          → SolveResult (AnswerCard → StepsList → SummaryCard)
          → ActionBar (再来一题 / 加入错题本 / 分享)
          → WhySheet (追问弹窗)
```

**📚 学习页**
```
LearnPage → StageSelector
          → (未选) SubjectCards → 进入知识地图
          → (已选) KgCanvas → KpCard (讲解/动画/例题/练习 Tab)
```

**👤 我的页**
```
MePage → UserHeader + StatsRow + RadarChart + TodayPlan + QuickActions
```

### 5.4 数学公式渲染

小程序不支持 DOM 操作，采用**服务端预渲染**：

1. 存储：所有公式以 LaTeX 字符串存储
2. API 提供 `/api/render/latex` 端点，KaTeX 服务端渲染为 SVG
3. 批量预渲染：部署时预渲染知识图谱中的公式为 SVG，上传 OSS/CDN
4. 客户端降级：简单公式用 Unicode，复杂公式通过 WebView 展示

### 5.5 语音输入

```
长按录音 → wx.getRecorderManager() → 上传 → API转文字 → LLM转LaTeX → 题目预览 → 确认提交
```

---

## 六、部署 & DevOps

### 6.1 Docker Compose 服务拓扑

```
Nginx :443 → MathVerse API :8002 (2 workers)
           → DeepTutor :8001 (4 workers)
           → Admin :3782
共享: SQLite (data/), Qdrant (:6333), 阿里云 OSS
```

### 6.2 资源 & 成本 (MVP 阶段)

| 资源 | 配置 | 月成本 |
|------|------|--------|
| 阿里云 ECS | 4C8G, 100G SSD, 5Mbps | ~¥300 |
| 阿里云 OSS | 100G + 50G 流量 | ~¥15 |
| 域名 | .com | ~¥60/年 |
| SSL | Let's Encrypt | ¥0 |
| 微信小程序认证 | — | ~¥300/年 |
| **基础设施合计** | | **~¥350/月** |
| DeepSeek API | 1000 DAU × 5次操作 | ~¥300-500/月 |
| **总运营成本** | | **~¥650-850/月** |

### 6.3 CI/CD

```
Git Push → GitHub Actions (lint/test/build/push image) → Webhook → ECS docker pull + compose up
```

### 6.4 监控告警

| 层面 | 工具 | 监控项 |
|------|------|--------|
| 服务存活 | 阿里云云监控 | CPU/内存/磁盘 |
| API 健康 | heartbeat + 定时 curl | 状态码、响应时间 |
| DeepTutor 连通 | AgentClient 健康检查 | 连续失败 → 企业微信通知 |
| 业务指标 | analytics_events | 日活、付费转化、功能使用率 |

### 6.5 安全

- 全站 HTTPS + HSTS
- JWT（15min access + 7d refresh）
- Nginx 限流（通用30r/s，解题5r/s）
- 微信支付签名验证 + 回调幂等
- 双向敏感词过滤
- user_id 贯穿所有查询
- 所有 Secret 走环境变量
- SQLAlchemy ORM 参数化查询

---

## 七、分阶段实施路线

| 阶段 | 时间 | 范围 | 核心交付 |
|------|------|------|---------|
| Phase 1 | 0-4周 | MVP | 小程序上线，大学高数+考研数学，解题+讲解+错题本 |
| Phase 2 | 4-12周 | 扩展 | Web H5、小学初中学段、知识地图、学习计划、付费 |
| Phase 3 | 12-24周 | 增长 | 高中学段、竞赛、估分、组队学习、周报推送 |
| Phase 4 | 24周+ | 生态 | App、教师后台、API开放 |

---

*技术设计文档 v2.0 · 2026-06-01*
