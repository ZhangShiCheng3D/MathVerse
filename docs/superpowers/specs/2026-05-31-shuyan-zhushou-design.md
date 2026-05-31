# 数研助手 — 实现设计规范

> 基于 HKUDS/DeepTutor (Apache 2.0) 的白标考研数学 AI 辅导产品
> 版本 v1.0 · 2026-05-31

---

## 产品定义

- **名称**: 数研助手
- **定位**: 考研数学 AI 辅导（首发数一/二/三）
- **主 LLM**: DeepSeek V3（备用: 通义千问 Qwen3）
- **部署**: Docker Compose + 阿里云 ECS
- **代码策略**: Fork `HKUDS/DeepTutor` → 增量修改

---

## 一、架构策略

### 代码组织

```
ZhangShiCheng3D/shuyan-zhushou/        (Fork自 HKUDS/DeepTutor)
├── src/                                # Python 后端
│   ├── agents/
│   │   ├── solve/                      # Deep Solve 6 Agent
│   │   │   ├── investigate.py          # [改] 中文Prompt
│   │   │   ├── plan.py                 # [改] 苏格拉底风格Prompt
│   │   │   ├── solve.py                # [改] 中文输出格式
│   │   │   └── check.py                # [改] 中文验证Prompt
│   │   ├── question/                   # [改] Quiz Agent 中文Prompt
│   │   ├── research/                   # [改] Research Agent 中文Prompt
│   │   └── prompts/                    # [改] 全部Prompt汉化
│   ├── api/
│   │   ├── run_server.py               # FastAPI 入口
│   │   └── routes/
│   │       ├── mistakes.py             # [新] 错题本 CRUD + FSRS
│   │       ├── score.py                # [新] 蒙特卡洛估分
│   │       ├── study_plan.py           # [新] 学习计划生成
│   │       ├── progress.py             # [新] 学习进度查询
│   │       ├── payment.py              # [新] 微信支付回调
│   │       └── auth_wechat.py          # [新] 微信 OAuth
│   ├── models/
│   │   └── kaoyan.py                   # [新] 错题/进度/订阅 ORM
│   └── middleware/
│       ├── content_filter.py           # [新] 敏感词过滤
│       └── analytics.py                # [新] 用户行为埋点
├── web/                                # Next.js 前端
│   └── src/
│       ├── app/
│       │   ├── layout.tsx              # [改] metadata
│       │   ├── page.tsx                # [改] 首页重构
│       │   ├── (main)/                 # 原有路由
│       │   └── (app)/                  # [新] 应用内页面
│       │       ├── dashboard/          # 学习进度仪表盘
│       │       ├── notebook/           # 错题本
│       │       ├── plan/               # 学习计划
│       │       └── pricing/            # 付费墙
│       └── components/
│           ├── Sidebar.tsx             # [改] 导航重构
│           ├── ExamModeSwitcher.tsx    # [新] 考试模式切换
│           └── ChatInput.tsx           # [改] 中文快捷操作
├── knowledge/
│   └── kaoyan-math/
│       └── knowledge-graph.json        # [新] 考研数学知识图谱
├── tailwind.config.ts                  # [改] 品牌配色
├── .env.kaoyan                         # [新] 环境变量模板
└── docker-compose.prod.yml             # [新] 生产部署
```

### 不破坏原则

- DeepTutor 原版 6 模式功能保持完整可用
- 新增路由、页面、表，不替换核心 Agent 逻辑
- 通过 `.env` 中的 `BRAND_MODE=kaoyan` 开关控制白标功能

---

## 二、L1 品牌化修改清单

| 文件 | 修改 |
|------|------|
| `web/public/favicon.ico` | 替换为品牌 Logo |
| `web/public/logo.svg` | 替换为品牌 Logo |
| `web/src/app/layout.tsx` | metadata title/description |
| `tailwind.config.ts` | primary: `#4F46E5`, accent: `#818CF8` |
| `web/src/components/*` (~15处) | `DeepTutor` → `数研助手` |
| `.env` | `BRAND_NAME=数研助手` |
| Dockerfile | 镜像名改为 `shuyan-zhushou` |

---

## 三、L2 内容注入

### Agent Prompt 汉化规格

| Agent | 核心指令 |
|-------|---------|
| InvestigateAgent | 优先检索考研知识库；中文搜索词；引用历年真题 |
| PlanAgent | 苏格拉底引导：先确认卡点再给提示；不直接给完整答案 |
| SolveAgent | 输出格式 `解：`/`证：`；步骤标注 `【Step N】`；每一步解释 WHY |
| CheckAgent | 验证数学推导；标记不确定步骤；附加 `※ AI生成，仅供参考` |
| Quiz Agent | 按考研大纲知识点分类；选择题+填空+解答 比例 4:3:3 |
| Research Agent | 中文结构化输出；章节标注；引用来源 |

### 考研数学知识图谱

三层结构：`科目 → 章 → 知识点`，元数据含考频(high/medium/low)、难度(1-5)、分值权重。

覆盖: 高等数学 40+ 知识点 | 线性代数 20+ | 概率论 20+

---

## 四、L3 体验改造

### 首页 (page.tsx)

- Hero: "你的AI考研数学老师" + CTA "开始学习"
- 三卡片: Deep Solve 逐步解题 | Math Animator 动画 | Quiz 智能出题
- 首次访问 → 弹出考试选择 (数一/数二/数三)

### 考试模式切换 (ExamModeSwitcher.tsx)

- 三选一按钮组，存 localStorage + user session
- 联动知识图谱范围 + 题目难度分布

### Chat 中文适配

- Placeholder: "输入你的题目..."
- 快捷按钮: `[出5道题] [总结知识点] [生成动画] [我不会]`
- 数学公式: KaTeX 行内渲染

### 微信登录

- OAuth 流程: `/api/auth/wechat/login` → 微信授权 → `/api/auth/wechat/callback`
- 首次登录自动创建用户，绑定微信 UnionID
- 保留原版邮箱登录

---

## 五、L4 差异化功能

### 错题本

- 页面: `/notebook` — 筛选栏 + 错题卡片 + 展开解析
- API: CRUD + FSRS 间隔复习排期
- FSRS 算法参数: stability, difficulty, interval → `next_review_at`

### 估分引擎

- 输入: 知识点掌握度列表
- 算法: 蒙特卡洛 1000 次模拟
- 按真实考研题型分布 (选择:填空:解答 = 4:3:3) 构建虚拟卷
- 输出: `估分 X/150 | 通过概率 Y% | 薄弱: [知识点列表]`

### 学习进度仪表盘

- 雷达图 (Chart.js): 各维度掌握度 0-100%
- 本周学习时长 + 做题趋势折线图

### 付费体系

- 免费: 10题/天 + Chat + RAG
- 月卡 ¥29/月 | 年卡 ¥199/年
- 微信 JSAPI 支付 → 回调 webhook → 自动开通

### 用户行为埋点

- 事件: 注册 / 付费 / 每日活跃 / 题目提交 / 错题收藏
- 存储: SQLite（MVP 阶段），后续可迁至 ClickHouse

---

## 六、数据库新增表

```sql
CREATE TABLE mistake_notebook (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    question_text TEXT NOT NULL,
    question_snapshot JSON,
    user_answer TEXT,
    correct_answer TEXT NOT NULL,
    solution_steps JSON,
    knowledge_points JSON,
    subject TEXT,
    difficulty INTEGER,
    fsrs_state JSON,
    next_review_at TIMESTAMP,
    review_count INTEGER DEFAULT 0,
    mastered BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE learning_progress (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    kp_id TEXT NOT NULL,
    mastery_level REAL DEFAULT 0,
    questions_attempted INTEGER DEFAULT 0,
    questions_correct INTEGER DEFAULT 0,
    last_practiced_at TIMESTAMP,
    estimated_readiness REAL,
    UNIQUE(user_id, kp_id)
);

CREATE TABLE study_plans (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    plan_date DATE NOT NULL,
    tasks JSON NOT NULL,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE subscriptions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    plan TEXT NOT NULL,
    amount INTEGER NOT NULL,
    status TEXT DEFAULT 'active',
    wechat_order_id TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);
```

---

## 七、新增 API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/mistakes` | GET | 错题列表(分页+筛选) |
| `/api/mistakes` | POST | 添加错题 |
| `/api/mistakes/{id}` | PATCH | 更新掌握状态 |
| `/api/mistakes/review-queue` | GET | FSRS 今日复习列表 |
| `/api/score/estimate` | POST | 蒙特卡洛估分 |
| `/api/study-plan/today` | GET | 今日学习计划 |
| `/api/study-plan/generate` | POST | 生成新计划 |
| `/api/progress` | GET | 学习进度数据 |
| `/api/subscription/status` | GET | 订阅状态 |
| `/api/payment/wechat-callback` | POST | 微信支付回调 |
| `/api/auth/wechat/login` | GET | 微信OAuth入口 |
| `/api/auth/wechat/callback` | GET | 微信OAuth回调 |

---

## 八、实施顺序

```
Phase 1: L1 品牌化
  ├── Fork DeepTutor → 克隆 → Docker 验证
  ├── .env 切换 DeepSeek
  └── 品牌名/Logo/配色替换

Phase 2: L2 内容注入
  ├── 6 Agent Prompt 汉化
  ├── 考研知识图谱 JSON
  └── 真题 PDF 导入

Phase 3: L3 体验改造
  ├── 首页重构 + 考试模式切换
  ├── Chat UI 中文适配
  └── 微信登录

Phase 4: L4 差异化功能
  ├── 错题本 + FSRS
  ├── 估分引擎
  ├── 学习进度仪表盘
  ├── 学习计划生成
  └── 付费墙 + 微信支付

Phase 5: 部署
  ├── Docker Compose 生产配置
  └── Nginx + SSL
```
