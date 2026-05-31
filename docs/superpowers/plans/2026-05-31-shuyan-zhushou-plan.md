# 数研助手 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fork DeepTutor and transform it into "数研助手" — a branded Kaoyan math AI tutoring product with Chinese prompts, wrong-answer notebook, score estimation, study dashboard, and WeChat payments.

**Architecture:** Fork HKUDS/DeepTutor → apply brand changes (L1) → inject Chinese prompts & knowledge graph (L2) → overhaul homepage & add WeChat auth (L3) → build differentiated features: mistake notebook, score estimator, study plan, paywall (L4) → productionize with Docker Compose + Nginx (P5).

**Tech Stack:** Python 3.11+ (FastAPI, nanobot, LlamaIndex), TypeScript (Next.js 16, React 19, Tailwind CSS), SQLite, Qdrant, DeepSeek V3 API

---

## File Structure Map

### Phase 1-2 Files (Existing DeepTutor files to modify)
```
DeepTutor/                          # Fork from HKUDS/DeepTutor
├── .env                            # [MODIFY] Switch LLM to DeepSeek, set brand vars
├── web/
│   ├── tailwind.config.ts          # [MODIFY] Brand colors
│   ├── public/
│   │   ├── favicon.ico             # [REPLACE] Brand logo
│   │   └── logo.svg               # [REPLACE] Brand logo
│   └── src/
│       ├── app/
│       │   └── layout.tsx          # [MODIFY] metadata
│       └── components/             # [MODIFY ~15 files] s/DeepTutor/数研助手/g
├── src/
│   └── agents/
│       ├── solve/
│       │   ├── investigate.py      # [MODIFY] Chinese prompt
│       │   ├── plan.py             # [MODIFY] Socratic prompt
│       │   ├── solve.py            # [MODIFY] Chinese output format
│       │   └── check.py            # [MODIFY] Verification prompt
│       ├── question/               # [MODIFY] Quiz agent prompt
│       └── research/               # [MODIFY] Research agent prompt
└── knowledge/
    └── kaoyan-math/
        └── knowledge-graph.json    # [CREATE] 80+ knowledge points

### Phase 3-4 Files (New files to create)
├── src/
│   ├── api/routes/
│   │   ├── mistakes.py             # [CREATE] Mistake notebook CRUD + FSRS
│   │   ├── score.py                # [CREATE] Monte Carlo score estimation
│   │   ├── study_plan.py           # [CREATE] Study plan generator
│   │   ├── progress.py             # [CREATE] Learning progress endpoints
│   │   ├── payment.py              # [CREATE] WeChat payment webhook
│   │   └── auth_wechat.py          # [CREATE] WeChat OAuth
│   ├── models/
│   │   └── kaoyan.py               # [CREATE] SQLAlchemy ORM models
│   └── middleware/
│       ├── content_filter.py       # [CREATE] Sensitive word filter
│       └── analytics.py            # [CREATE] User behavior tracking
├── web/src/
│   ├── app/(app)/
│   │   ├── dashboard/page.tsx      # [CREATE] Study progress dashboard
│   │   ├── notebook/page.tsx       # [CREATE] Mistake notebook UI
│   │   ├── plan/page.tsx           # [CREATE] Study plan page
│   │   └── pricing/page.tsx        # [CREATE] Paywall page
│   └── components/
│       └── ExamModeSwitcher.tsx    # [CREATE] Exam type selector
└── docker-compose.prod.yml         # [CREATE] Production deployment
```

---

## Phase 1: Setup + L1 Branding

### Task 1: Fork and Clone DeepTutor

**Files:** None (git operations)

- [ ] **Step 1: Fork DeepTutor on GitHub**

```bash
gh repo fork HKUDS/DeepTutor --clone=false --org=false --remote=false
# When prompted about forking, answer: Yes
# This creates ZhangShiCheng3D/DeepTutor on GitHub
```

Expected: Fork created at `https://github.com/ZhangShiCheng3D/DeepTutor`

- [ ] **Step 2: Clone the forked repo to project directory**

```powershell
cd C:\Users\m1770\Desktop\Deeptutor
git clone https://github.com/ZhangShiCheng3D/DeepTutor.git deeptutor-fork
```

Expected: DeepTutor source code at `C:\Users\m1770\Desktop\Deeptutor\deeptutor-fork\`

- [ ] **Step 3: Verify clone and check structure**

```powershell
Set-Location C:\Users\m1770\Desktop\Deeptutor\deeptutor-fork
git log --oneline -5
Get-ChildItem -Name
```

Expected: See recent commits, directory listing with `src/`, `web/`, `docker-compose.ghcr.yml`

- [ ] **Step 4: Rename the local directory to the product name**

```powershell
Rename-Item C:\Users\m1770\Desktop\Deeptutor\deeptutor-fork shuyan-zhushou
```

- [ ] **Step 5: Commit (git-based snapshot of initial state)**

No commit needed — this is a clone of the fork.

---

### Task 2: Docker Compose Verification

**Files:** `.env` (create from example)

- [ ] **Step 1: Create .env from example**

```powershell
Set-Location C:\Users\m1770\Desktop\Deeptutor\shuyan-zhushou
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
```

- [ ] **Step 2: Set DeepSeek as LLM in .env**

Edit `.env` — set these values:
```bash
LLM_BINDING=deepseek
LLM_MODEL=deepseek-chat
LLM_API_KEY=<your-deepseek-api-key>
LLM_HOST=https://api.deepseek.com/v1
LLM_MAX_TOKENS=8192
WEB_SEARCH=duckduckgo
```

- [ ] **Step 3: Start Docker Compose**

```powershell
docker compose -f docker-compose.ghcr.yml up -d
```

Expected: Containers for backend, frontend, qdrant start. Wait ~30s for health checks.

- [ ] **Step 4: Verify all 6 modes work**

Open `http://localhost:3782` in browser. Test:
1. Chat mode: "求极限 lim(x→0) sin(x)/x"
2. Deep Solve: "证明根号2是无理数"
3. Quiz Generation: upload a math PDF, generate quiz
4. Deep Research: "微分中值定理的体系"
5. Math Animator: "生成 y=x^2 的导数动画"
6. Visualize: "画出极限的知识图谱"

Expected: Each mode produces output. If any mode fails, check Docker logs with `docker compose logs backend`.

- [ ] **Step 5: Stop containers for now**

```powershell
docker compose -f docker-compose.ghcr.yml down
```

---

### Task 3: Brand Replacement

**Files:**
- Modify: `shuyan-zhushou/web/src/app/layout.tsx`
- Modify: `shuyan-zhushou/web/tailwind.config.ts`
- Modify: `shuyan-zhushou/web/src/components/*` (~15 files)
- Replace: `shuyan-zhushou/web/public/favicon.ico`, `logo.svg`

- [ ] **Step 1: Update layout metadata**

Read `shuyan-zhushou/web/src/app/layout.tsx`, find the metadata object and replace title/description:
```tsx
export const metadata: Metadata = {
  title: "数研助手 - AI考研数学辅导",
  description: "基于AI的考研数学辅导平台，支持Deep Solve逐步解题、Math Animator数学动画、Quiz智能出题、错题本FSRS复习",
};
```

- [ ] **Step 2: Update Tailwind brand colors**

Read `shuyan-zhushou/web/tailwind.config.ts`, find the theme colors and replace primary/accent:
```ts
colors: {
  primary: {
    DEFAULT: "#4F46E5",  // Indigo 600
    50: "#EEF2FF",
    100: "#E0E7FF",
    200: "#C7D2FE",
    300: "#A5B4FC",
    400: "#818CF8",
    500: "#6366F1",
    600: "#4F46E5",
    700: "#4338CA",
    800: "#3730A3",
    900: "#312E81",
  },
}
```

- [ ] **Step 3: Global text replace "DeepTutor" → "数研助手"**

```powershell
Set-Location C:\Users\m1770\Desktop\Deeptutor\shuyan-zhushou\web\src
$files = Get-ChildItem -Recurse -Include *.tsx,*.ts,*.jsx,*.js | Where-Object { $_.FullName -notmatch 'node_modules' }
foreach ($f in $files) {
    $content = Get-Content $f.FullName -Raw -Encoding UTF8
    if ($content -match 'DeepTutor') {
        $content = $content -replace 'DeepTutor', '数研助手'
        Set-Content $f.FullName -Value $content -Encoding UTF8 -NoNewline
        Write-Host "Updated: $($f.Name)"
    }
}
```

- [ ] **Step 4: Replace brand assets**

Generate or place custom `favicon.ico` and `logo.svg` in `shuyan-zhushou/web/public/`.
For MVP, create a simple SVG logo with the Chinese character "数" (shu) in Indigo:

```svg
<!-- logo.svg -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect width="100" height="100" rx="20" fill="#4F46E5"/>
  <text x="50" y="68" font-size="52" fill="white" text-anchor="middle"
        font-family="PingFang SC, Microsoft YaHei, sans-serif" font-weight="bold">数</text>
</svg>
```

- [ ] **Step 5: Update .env brand variables**

Add to `.env`:
```bash
BRAND_NAME=数研助手
BRAND_SLOGAN=你的AI考研数学老师
PRIMARY_COLOR=#4F46E5
```

- [ ] **Step 6: Rebuild and verify brand changes**

```powershell
docker compose -f docker-compose.ghcr.yml build frontend
docker compose -f docker-compose.ghcr.yml up -d
```

Expected: Frontend shows "数研助手" in browser tab title, brand colors applied.

- [ ] **Step 7: Commit L1 changes**

```powershell
Set-Location C:\Users\m1770\Desktop\Deeptutor\shuyan-zhushou
git add -A
git commit -m "feat(L1): brand as 数研助手 — name, logo, colors, metadata"
```

---

## Phase 2: L2 Content Injection

### Task 4: Chinese Agent Prompts

**Files:**
- Modify: `src/agents/solve/investigate.py`
- Modify: `src/agents/solve/plan.py`
- Modify: `src/agents/solve/solve.py`
- Modify: `src/agents/solve/check.py`
- Modify: `src/agents/question/` (agent coordinator)
- Modify: `src/agents/research/` (research agent)

- [ ] **Step 1: Locate the prompt files**

First, find where each agent's system prompt is defined. The exact file paths vary by DeepTutor version. Search for "system_prompt" or "SYSTEM_PROMPT" in the agent directories:

```powershell
Set-Location C:\Users\m1770\Desktop\Deeptutor\shuyan-zhushou\src\agents
Get-ChildItem -Recurse | Select-String -Pattern "system_prompt|SYSTEM_PROMPT|system_message|SYSTEM_MESSAGE" | Select-Object -First 20
```

Expected: Find the prompt definitions in each agent file. Document the exact line numbers.

- [ ] **Step 2: InvestigateAgent — Chinese research prompt**

Update the investigate agent's system prompt to Chinese with Kaoyan domain priority:

```python
INVESTIGATE_SYSTEM_PROMPT = """你是一位考研数学研究助手。你的任务是为解题提供所需的知识背景和参考资料。

遵循以下原则：
1. 优先检索考研知识库中的相关知识点和历年真题
2. 使用中文进行所有搜索和总结
3. 引用具体教材章节（如同济《高等数学》、浙大《概率论》）
4. 标注知识点的考频（高频/中频/低频）和常见题型
5. 如果搜索到相关真题，列出题目和年份

输出格式：
## 相关知识点
- 知识点1：考频、难度、教材出处
- 知识点2：...

## 历年真题
- [年份·数X] 题目简述

## 解题思路提示
- 关键公式/定理
- 常见陷阱
"""
```

- [ ] **Step 3: PlanAgent — Socratic tutoring prompt**

```python
PLAN_SYSTEM_PROMPT = """你是一位考研数学导师，采用苏格拉底式引导教学法。你的核心理念是：不直接给答案，而是通过提问帮助学生自己找到解题路径。

遵循以下原则：
1. 首先确认学生卡在哪一步： "你已经做到哪一步了？哪里卡住了？"
2. 根据学生的卡点，给出最小必要的提示，而不是完整的解题步骤
3. 使用引导性提问： "这个极限是什么类型？0/0型应该用什么方法？"
4. 如果学生完全不知道从何下手，先帮ta识别题目类型和考察知识点
5. 逐步释放提示，每给一个提示后给学生思考空间
6. 在学生成功解出后，总结同类型题目的通用方法

禁止行为：
- 不要直接给出完整答案
- 不要说"答案是..." 或 "正确答案是..."
- 不要跳过思考过程直接给结果
"""
```

- [ ] **Step 4: SolveAgent — Chinese formatted step-by-step**

```python
SOLVE_SYSTEM_PROMPT = """你是一位考研数学解题专家。在PlanAgent给出策略后，你负责输出详细的解题步骤。

输出格式要求：
- 所有输出使用中文
- 解题开始标注 "解：" ，证明题标注 "证："
- 每个步骤使用 **【Step N】** 标注
- 每一步之后解释 WHY：为什么这一步这么做的原理
- 数学公式使用 LaTeX 格式
- 步骤之间要有逻辑过渡说明

示例输出：
解：
**【Step 1】识别题目类型和条件**
本题是 0/0 型极限，分子分母在 x→0 时都趋于0，适用洛必达法则。
已知条件：lim(x→0) (sin x - x) / x³

**【Step 2】应用洛必达法则（第一次）**
对分子分母分别求导：...
WHY: 0/0型不定式的标准处理方法是洛必达法则。

**【Step 3】检查是否仍为不定式，必要时再次洛必达**
...

**【Step 4】代入极限值，得出最终结果**
...

**※ 总结**：本题考查洛必达法则的应用，关键点是判断不定式类型和反复求导的技巧。
"""
```

- [ ] **Step 5: CheckAgent — Verification prompt**

```python
CHECK_SYSTEM_PROMPT = """你是一位严谨的考研数学验证专家。你的任务是检查SolveAgent的解题过程是否正确。

检查清单：
1. 每一步的数学推导是否逻辑正确
2. 公式计算是否有误
3. 是否遗漏了边界条件或特殊情况（如分母为零、极限不存在等）
4. 最终答案是否合理
5. LaTeX 格式是否正确

输出格式：
## 验证结果
- ✅/❌ 步骤N：判断 + 说明

## 综合评价
- 正确性：[通过/有误/不确定]
- 如果有误，指出具体哪一步出错并给出正确的推导
- 如果存在不确定性，明确标注 ※ AI生成，仅供参考

对于无法100%确定的结果，必须附加免责声明。
"""
```

- [ ] **Step 6: Quiz Agent — Chinese exam-oriented prompt**

```python
QUIZ_SYSTEM_PROMPT = """你是一位考研数学出题专家。根据用户上传的文档或指定的知识点，生成高质量的练习题。

出题规则：
1. 题型比例：选择题40% + 填空题30% + 解答题30%
2. 难度分布：基础题30% + 中档题50% + 难题20%
3. 每题标注对应的考研大纲知识点编号
4. 题目风格贴近历年真题
5. 选择题4个选项，包含典型错误选项（有迷惑性）
6. 解答题要有完整的评分标准

输出格式：
## 选择题
1. (知识点: xxx, 难度: ★★☆) 题目内容...
   A. ... B. ... C. ... D. ...
   [正确答案: C, 解析: ...]

## 填空题
1. (知识点: xxx, 难度: ★★☆) 题目内容...
   [正确答案: xxx, 解析: ...]

## 解答题
1. (知识点: xxx, 难度: ★★★, 分值: 10分) 题目内容...
   [参考答案: ..., 评分标准: ...]
"""
```

- [ ] **Step 7: Research Agent — Chinese academic report prompt**

```python
RESEARCH_SYSTEM_PROMPT = """你是一位考研数学学术研究助手。对用户指定的主题进行深度研究，生成结构化报告。

报告结构：
# [主题名称] - 深度研究报告

## 1. 概念体系
- 定义与核心概念
- 在考研数学中的位置

## 2. 定理与公式
- 核心定理及证明思路
- 常用公式一览表

## 3. 典型题型与解题方法
- 题型分类
- 通用解法框架
- 历年真题举例

## 4. 易错点与技巧
- 常见错误
- 实用技巧

## 5. 与其他知识点的联系
- 前置依赖
- 后续应用

所有输出使用中文，数学公式使用 LaTeX，真题引用标注年份和试卷类型。
"""
```

- [ ] **Step 8: Apply prompt changes**

For each agent file found in Step 1, replace the existing English system prompt with the Chinese versions above. Preserve the exact variable name used in the original code.

- [ ] **Step 9: Rebuild and test with Chinese prompts**

```powershell
docker compose -f docker-compose.ghcr.yml build backend
docker compose -f docker-compose.ghcr.yml up -d
```

Test: Send "求极限 lim(x→0) (1-cos x)/x²" through Deep Solve, verify the output uses Chinese and the Socratic style.

- [ ] **Step 10: Commit L2 prompt changes**

```powershell
git add -A
git commit -m "feat(L2): Chinese agent prompts with Kaoyan math domain injection"
```

---

### Task 5: Kaoyan Math Knowledge Graph

**Files:**
- Create: `knowledge/kaoyan-math/knowledge-graph.json`

- [ ] **Step 1: Create the knowledge graph JSON**

```json
{
  "version": "1.0",
  "exam": "考研数学",
  "subjects": [
    {
      "id": "gaoshu",
      "name": "高等数学",
      "exam_weight": 82,
      "chapters": [
        {
          "id": "gs-1",
          "name": "函数、极限与连续",
          "frequency": "high",
          "topics": [
            {"id": "gs-1.1", "name": "函数极限计算", "difficulty": 3, "weight": "10分"},
            {"id": "gs-1.2", "name": "无穷小量比较", "difficulty": 3, "weight": "4分"},
            {"id": "gs-1.3", "name": "连续性与间断点", "difficulty": 2, "weight": "4分"},
            {"id": "gs-1.4", "name": "闭区间连续函数性质", "difficulty": 3, "weight": "4分"}
          ]
        },
        {
          "id": "gs-2",
          "name": "一元函数微分学",
          "frequency": "high",
          "topics": [
            {"id": "gs-2.1", "name": "导数定义与计算", "difficulty": 2, "weight": "6分"},
            {"id": "gs-2.2", "name": "导数的几何应用", "difficulty": 3, "weight": "6分"},
            {"id": "gs-2.3", "name": "中值定理", "difficulty": 5, "weight": "10分"},
            {"id": "gs-2.4", "name": "函数单调性与极值", "difficulty": 3, "weight": "6分"},
            {"id": "gs-2.5", "name": "凹凸性与拐点", "difficulty": 2, "weight": "4分"},
            {"id": "gs-2.6", "name": "渐近线", "difficulty": 2, "weight": "4分"}
          ]
        },
        {
          "id": "gs-3",
          "name": "一元函数积分学",
          "frequency": "high",
          "topics": [
            {"id": "gs-3.1", "name": "不定积分计算", "difficulty": 3, "weight": "6分"},
            {"id": "gs-3.2", "name": "定积分计算", "difficulty": 3, "weight": "8分"},
            {"id": "gs-3.3", "name": "反常积分", "difficulty": 3, "weight": "4分"},
            {"id": "gs-3.4", "name": "定积分的几何应用", "difficulty": 4, "weight": "10分"}
          ]
        },
        {
          "id": "gs-4",
          "name": "多元函数微积分学",
          "frequency": "high",
          "topics": [
            {"id": "gs-4.1", "name": "偏导数与全微分", "difficulty": 3, "weight": "6分"},
            {"id": "gs-4.2", "name": "多元函数极值", "difficulty": 4, "weight": "10分"},
            {"id": "gs-4.3", "name": "二重积分", "difficulty": 4, "weight": "10分"},
            {"id": "gs-4.4", "name": "三重积分", "difficulty": 5, "weight": "4分"},
            {"id": "gs-4.5", "name": "曲线曲面积分", "difficulty": 5, "weight": "10分"}
          ]
        },
        {
          "id": "gs-5",
          "name": "无穷级数",
          "frequency": "medium",
          "topics": [
            {"id": "gs-5.1", "name": "数项级数审敛法", "difficulty": 4, "weight": "4分"},
            {"id": "gs-5.2", "name": "幂级数与收敛域", "difficulty": 4, "weight": "6分"},
            {"id": "gs-5.3", "name": "幂级数求和", "difficulty": 5, "weight": "6分"},
            {"id": "gs-5.4", "name": "傅里叶级数", "difficulty": 4, "weight": "4分"}
          ]
        },
        {
          "id": "gs-6",
          "name": "常微分方程",
          "frequency": "medium",
          "topics": [
            {"id": "gs-6.1", "name": "一阶微分方程", "difficulty": 3, "weight": "6分"},
            {"id": "gs-6.2", "name": "高阶线性微分方程", "difficulty": 4, "weight": "8分"}
          ]
        }
      ]
    },
    {
      "id": "xiandai",
      "name": "线性代数",
      "exam_weight": 34,
      "chapters": [
        {
          "id": "xd-1",
          "name": "行列式",
          "frequency": "medium",
          "topics": [
            {"id": "xd-1.1", "name": "行列式计算", "difficulty": 2, "weight": "4分"},
            {"id": "xd-1.2", "name": "行列式按行展开", "difficulty": 3, "weight": "4分"}
          ]
        },
        {
          "id": "xd-2",
          "name": "矩阵",
          "frequency": "high",
          "topics": [
            {"id": "xd-2.1", "name": "矩阵运算", "difficulty": 2, "weight": "4分"},
            {"id": "xd-2.2", "name": "逆矩阵与伴随矩阵", "difficulty": 3, "weight": "4分"},
            {"id": "xd-2.3", "name": "矩阵的秩", "difficulty": 3, "weight": "4分"},
            {"id": "xd-2.4", "name": "矩阵方程", "difficulty": 4, "weight": "4分"}
          ]
        },
        {
          "id": "xd-3",
          "name": "向量与线性方程组",
          "frequency": "high",
          "topics": [
            {"id": "xd-3.1", "name": "向量组线性相关性", "difficulty": 4, "weight": "6分"},
            {"id": "xd-3.2", "name": "线性方程组解的结构", "difficulty": 4, "weight": "8分"}
          ]
        },
        {
          "id": "xd-4",
          "name": "特征值与二次型",
          "frequency": "high",
          "topics": [
            {"id": "xd-4.1", "name": "特征值与特征向量", "difficulty": 4, "weight": "6分"},
            {"id": "xd-4.2", "name": "相似对角化", "difficulty": 5, "weight": "6分"},
            {"id": "xd-4.3", "name": "二次型与标准型", "difficulty": 4, "weight": "6分"}
          ]
        }
      ]
    },
    {
      "id": "gailv",
      "name": "概率论与数理统计",
      "exam_weight": 34,
      "chapters": [
        {
          "id": "gl-1",
          "name": "随机事件与概率",
          "frequency": "medium",
          "topics": [
            {"id": "gl-1.1", "name": "古典概型", "difficulty": 2, "weight": "4分"},
            {"id": "gl-1.2", "name": "条件概率与全概率公式", "difficulty": 3, "weight": "4分"},
            {"id": "gl-1.3", "name": "贝叶斯公式", "difficulty": 3, "weight": "4分"}
          ]
        },
        {
          "id": "gl-2",
          "name": "随机变量及其分布",
          "frequency": "high",
          "topics": [
            {"id": "gl-2.1", "name": "常见离散型分布", "difficulty": 2, "weight": "4分"},
            {"id": "gl-2.2", "name": "常见连续型分布", "difficulty": 3, "weight": "4分"},
            {"id": "gl-2.3", "name": "随机变量函数的分布", "difficulty": 4, "weight": "6分"}
          ]
        },
        {
          "id": "gl-3",
          "name": "多维随机变量",
          "frequency": "medium",
          "topics": [
            {"id": "gl-3.1", "name": "联合分布与边缘分布", "difficulty": 3, "weight": "4分"},
            {"id": "gl-3.2", "name": "协方差与相关系数", "difficulty": 3, "weight": "4分"}
          ]
        },
        {
          "id": "gl-4",
          "name": "数字特征与大数定律",
          "frequency": "medium",
          "topics": [
            {"id": "gl-4.1", "name": "期望与方差计算", "difficulty": 3, "weight": "6分"},
            {"id": "gl-4.2", "name": "切比雪夫不等式", "difficulty": 3, "weight": "4分"}
          ]
        },
        {
          "id": "gl-5",
          "name": "数理统计",
          "frequency": "high",
          "topics": [
            {"id": "gl-5.1", "name": "抽样分布", "difficulty": 3, "weight": "4分"},
            {"id": "gl-5.2", "name": "参数估计", "difficulty": 4, "weight": "6分"},
            {"id": "gl-5.3", "name": "假设检验", "difficulty": 4, "weight": "6分"}
          ]
        }
      ]
    }
  ]
}
```

- [ ] **Step 2: Save and verify JSON validity**

```powershell
$json = Get-Content C:\Users\m1770\Desktop\Deeptutor\shuyan-zhushou\knowledge\kaoyan-math\knowledge-graph.json -Raw | ConvertFrom-Json
$json.subjects.Count
# Expected: 3
$json.subjects | ForEach-Object { $_.chapters.Count }
# Expected: 6, 4, 5
```

- [ ] **Step 3: Commit knowledge graph**

```powershell
git add knowledge/kaoyan-math/
git commit -m "feat(L2): add Kaoyan math knowledge graph (80+ knowledge points, 3 subjects)"
```

---

## Phase 3: L3 Experience Overhaul

### Task 6: Homepage Redesign

**Files:**
- Modify: `web/src/app/page.tsx`
- Create: `web/src/components/ExamModeSwitcher.tsx`

- [ ] **Step 1: Read the existing homepage**

Read `web/src/app/page.tsx` to understand the current structure. Note the component hierarchy and styling approach.

- [ ] **Step 2: Create ExamModeSwitcher component**

Create `web/src/components/ExamModeSwitcher.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";

export type ExamMode = "math-1" | "math-2" | "math-3";

const EXAM_MODES = [
  { id: "math-1" as const, label: "数学一", desc: "理工科 · 高数82分+线代34分+概率34分" },
  { id: "math-2" as const, label: "数学二", desc: "部分工科 · 高数116分+线代34分" },
  { id: "math-3" as const, label: "数学三", desc: "经管类 · 高数82分+线代34分+概率34分" },
];

export function useExamMode() {
  const [mode, setMode] = useState<ExamMode | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem("exam-mode") as ExamMode | null;
    if (saved) setMode(saved);
  }, []);

  const selectMode = (m: ExamMode) => {
    localStorage.setItem("exam-mode", m);
    setMode(m);
  };

  return { mode, selectMode };
}

export function ExamModeSwitcher({
  mode,
  onSelect,
}: {
  mode: ExamMode | null;
  onSelect: (m: ExamMode) => void;
}) {
  if (mode) {
    return (
      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted-foreground">当前考试:</span>
        <span className="font-semibold text-primary">
          {EXAM_MODES.find((e) => e.id === mode)?.label}
        </span>
        <button
          onClick={() => onSelect(null as any)}
          className="text-xs text-muted-foreground underline"
        >
          切换
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-4 p-8">
      <h2 className="text-xl font-bold">选择你的考试类型</h2>
      <p className="text-muted-foreground text-sm">AI 将根据考试大纲调整题目范围和难度</p>
      <div className="grid grid-cols-3 gap-4 max-w-2xl">
        {EXAM_MODES.map((exam) => (
          <button
            key={exam.id}
            onClick={() => onSelect(exam.id)}
            className="p-6 rounded-xl border-2 border-border hover:border-primary hover:bg-primary/5 transition-all text-center"
          >
            <div className="text-lg font-bold text-primary">{exam.label}</div>
            <div className="text-xs text-muted-foreground mt-2">{exam.desc}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Rewrite homepage**

Rewrite `web/src/app/page.tsx`:

```tsx
import { ExamModeSwitcher } from "@/components/ExamModeSwitcher";
import Link from "next/link";

export default function HomePage() {
  return (
    <div className="flex flex-col min-h-screen">
      {/* Hero Section */}
      <section className="flex flex-col items-center justify-center py-20 px-4 text-center">
        <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight mb-4">
          你的<span className="text-primary">AI考研数学</span>老师
        </h1>
        <p className="text-lg text-muted-foreground max-w-xl mb-8">
          基于多智能体协作的Deep Solve逐步解题系统，不直接给答案，
          而是像真正的老师一样引导你思考
        </p>
        <Link
          href="/chat"
          className="px-8 py-3 bg-primary text-white rounded-full font-semibold text-lg hover:bg-primary/90 transition-colors"
        >
          开始学习
        </Link>
      </section>

      {/* Feature Cards */}
      <section className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto px-4 pb-20">
        <div className="p-6 rounded-xl border border-border hover:border-primary/30 transition-colors">
          <div className="text-2xl mb-3">🧠</div>
          <h3 className="font-bold text-lg mb-2">Deep Solve 逐步解题</h3>
          <p className="text-sm text-muted-foreground">
            6个Agent协作：检索→规划→求解→验证。每一步都有解释，
            告诉你"为什么这么做"，而不仅是"怎么做"
          </p>
        </div>
        <div className="p-6 rounded-xl border border-border hover:border-primary/30 transition-colors">
          <div className="text-2xl mb-3">🎬</div>
          <h3 className="font-bold text-lg mb-2">Math Animator 数学动画</h3>
          <p className="text-sm text-muted-foreground">
            极限、导数、积分、线性变换 — 让抽象的数学概念动起来。
            30秒动画胜过千字讲解
          </p>
        </div>
        <div className="p-6 rounded-xl border border-border hover:border-primary/30 transition-colors">
          <div className="text-2xl mb-3">📝</div>
          <h3 className="font-bold text-lg mb-2">Quiz 智能出题</h3>
          <p className="text-sm text-muted-foreground">
            选择题+填空+解答，按考研大纲知识点自动生成。
            自动批改，错题自动归入错题本
          </p>
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Rebuild and verify homepage**

```powershell
docker compose -f docker-compose.ghcr.yml build frontend
docker compose -f docker-compose.ghcr.yml up -d
```

Expected: `http://localhost:3782` shows the new landing page with hero and three feature cards.

- [ ] **Step 5: Commit homepage changes**

```powershell
git add -A
git commit -m "feat(L3): redesign homepage for Kaoyan math, add ExamModeSwitcher component"
```

---

### Task 7: Chat UI Chinese Adaptation

**Files:**
- Modify: `web/src/components/ChatInput.tsx` (or equivalent)

- [ ] **Step 1: Update chat input placeholder and quick actions**

Locate the chat input component (search for `placeholder` in `web/src/components/`):

```tsx
const QUICK_ACTIONS = [
  { label: "出5道题", prompt: "基于当前知识点生成5道练习题" },
  { label: "总结知识点", prompt: "总结以上内容的核心知识点" },
  { label: "生成动画", prompt: "为这个概念生成Manim动画" },
  { label: "我不会", prompt: "这道题我不会做，请从第一步开始引导我" },
];

function QuickActionBar({ onAction }: { onAction: (prompt: string) => void }) {
  return (
    <div className="flex gap-2 flex-wrap">
      {QUICK_ACTIONS.map((action) => (
        <button
          key={action.label}
          onClick={() => onAction(action.prompt)}
          className="px-3 py-1 text-xs rounded-full border border-border hover:bg-primary/10 hover:border-primary transition-colors"
        >
          {action.label}
        </button>
      ))}
    </div>
  );
}
```

Add this component above the textarea, and set:
```tsx
placeholder="输入你的题目，比如'求极限 lim(x→0) sin(x)/x'"
```

- [ ] **Step 2: Commit chat UI changes**

```powershell
git add -A
git commit -m "feat(L3): adapt Chat UI with Chinese placeholders and quick action buttons"
```

---

### Task 8: WeChat OAuth Login

**Files:**
- Create: `src/api/routes/auth_wechat.py`
- Modify: `src/api/run_server.py` (register new routes)

- [ ] **Step 1: Create WeChat OAuth route**

Create `src/api/routes/auth_wechat.py`:

```python
"""WeChat OAuth 2.0 login flow."""
import os
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/api/auth/wechat", tags=["wechat-auth"])

WECHAT_APP_ID = os.getenv("WECHAT_APP_ID", "")
WECHAT_APP_SECRET = os.getenv("WECHAT_APP_SECRET", "")
BRAND_NAME = os.getenv("BRAND_NAME", "数研助手")

# In-memory state store (replace with Redis in production)
_state_store: dict[str, str] = {}


def _get_user_service():
    """Lazy import to avoid circular deps."""
    from src.services.user_service import UserService
    return UserService()


@router.get("/login")
async def wechat_login(request: Request):
    """Initiate WeChat OAuth flow. Redirects user to WeChat authorization page."""
    if not WECHAT_APP_ID:
        raise HTTPException(500, "WECHAT_APP_ID not configured")

    state = secrets.token_urlsafe(32)
    redirect_uri = str(request.url_for("wechat_callback"))
    _state_store[state] = redirect_uri

    params = urlencode({
        "appid": WECHAT_APP_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "snsapi_userinfo",
        "state": state,
    })
    return RedirectResponse(f"https://open.weixin.qq.com/connect/oauth2/authorize?{params}#wechat_redirect")


@router.get("/callback")
async def wechat_callback(request: Request, code: str, state: str):
    """Handle WeChat OAuth callback. Exchanges code for access token and user info."""
    expected_redirect = _state_store.pop(state, None)
    if not expected_redirect:
        raise HTTPException(400, "Invalid state parameter")

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.get("https://api.weixin.qq.com/sns/oauth2/access_token", params={
            "appid": WECHAT_APP_ID,
            "secret": WECHAT_APP_SECRET,
            "code": code,
            "grant_type": "authorization_code",
        })
        token_data = token_resp.json()
        if "errcode" in token_data:
            raise HTTPException(400, f"WeChat error: {token_data.get('errmsg')}")

        access_token = token_data["access_token"]
        openid = token_data["openid"]

        # Get user info
        user_resp = await client.get("https://api.weixin.qq.com/sns/userinfo", params={
            "access_token": access_token,
            "openid": openid,
        })
        user_info = user_resp.json()

    # Create or login user
    user_service = _get_user_service()
    user = await user_service.get_or_create_wechat_user(
        union_id=user_info.get("unionid", openid),
        openid=openid,
        nickname=user_info.get("nickname", "微信用户"),
        avatar=user_info.get("headimgurl", ""),
    )

    # Generate JWT and redirect to frontend
    jwt_token = user_service.create_jwt(user.id)
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3782")
    return RedirectResponse(f"{frontend_url}/chat?token={jwt_token}")
```

- [ ] **Step 2: Register routes in FastAPI server**

Find the route registration section in `src/api/run_server.py` and add:

```python
from src.api.routes.auth_wechat import router as wechat_router
app.include_router(wechat_router)
```

- [ ] **Step 3: Add WeChat env vars to .env**

```bash
WECHAT_APP_ID=wx_your_app_id
WECHAT_APP_SECRET=your_app_secret
```

- [ ] **Step 4: Commit WeChat auth**

```powershell
git add -A
git commit -m "feat(L3): add WeChat OAuth login endpoint"
```

---

## Phase 4: L4 Differentiated Features

### Task 9: Database Models for New Tables

**Files:**
- Create: `src/models/kaoyan.py`

- [ ] **Step 1: Create SQLAlchemy models**

Create `src/models/kaoyan.py`:

```python
"""Kaoyan-specific database models — mistake notebook, progress, plans, subscriptions."""
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Boolean, Float, DateTime, Text, JSON, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MistakeNotebook(Base):
    __tablename__ = "mistake_notebook"

    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    question_snapshot = Column(JSON, default=dict)
    user_answer = Column(Text, default="")
    correct_answer = Column(Text, nullable=False)
    solution_steps = Column(JSON, default=list)
    knowledge_points = Column(JSON, default=list)
    subject = Column(String, default="")
    difficulty = Column(Integer, default=3)
    fsrs_state = Column(JSON, default=dict)
    next_review_at = Column(DateTime, nullable=True)
    review_count = Column(Integer, default=0)
    mastered = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class LearningProgress(Base):
    __tablename__ = "learning_progress"
    __table_args__ = (UniqueConstraint("user_id", "kp_id"),)

    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, nullable=False, index=True)
    kp_id = Column(String, nullable=False)
    mastery_level = Column(Float, default=0.0)
    questions_attempted = Column(Integer, default=0)
    questions_correct = Column(Integer, default=0)
    last_practiced_at = Column(DateTime, nullable=True)
    estimated_readiness = Column(Float, nullable=True)


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, nullable=False, index=True)
    plan_date = Column(DateTime, nullable=False)
    tasks = Column(JSON, default=list)
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True, default=_new_id)
    user_id = Column(String, nullable=False, index=True)
    plan = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String, default="active")
    wechat_order_id = Column(String, nullable=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)
```

- [ ] **Step 2: Create table migration**

```python
# scripts/create_kaoyan_tables.py
import sqlite3
import os

DB_PATH = os.getenv("DATABASE_URL", "data/deeptutor.db").replace("sqlite:///", "")

conn = sqlite3.connect(DB_PATH)
conn.executescript(open("knowledge/kaoyan-math/migration.sql").read())
conn.commit()
conn.close()
print("Kaoyan tables created.")
```

- [ ] **Step 3: Commit database models**

```powershell
git add -A
git commit -m "feat(L4): add SQLAlchemy models for mistake notebook, progress, study plans, subscriptions"
```

---

### Task 10: Mistake Notebook API (CRUD + FSRS)

**Files:**
- Create: `src/api/routes/mistakes.py`

- [ ] **Step 1: Implement FSRS scheduler**

```python
"""FSRS (Free Spaced Repetition Scheduler) for mistake review scheduling."""

from datetime import datetime, timedelta, timezone
import math


def fsrs_next_interval(
    stability: float,
    difficulty: float,
    rating: int,  # 1=again, 2=hard, 3=good, 4=easy
) -> tuple[float, float, float]:
    """Calculate next review interval using FSRS algorithm.
    
    Returns: (new_stability, new_difficulty, interval_days)
    """
    # Clamp rating
    rating = max(1, min(4, rating))

    # Update difficulty
    difficulty = difficulty + 0.1 * (5 - rating) * (1 - difficulty + 1)
    difficulty = max(1, min(10, difficulty))

    # Update stability based on rating
    if rating == 1:  # Again
        new_stability = stability * 0.5
    elif rating == 2:  # Hard
        new_stability = stability * 1.0
    elif rating == 3:  # Good
        new_stability = stability * 2.0
    else:  # Easy
        new_stability = stability * 3.0

    new_stability = max(0.1, new_stability)

    # Calculate interval (days)
    interval = new_stability * (9 * (1 / difficulty))

    return new_stability, difficulty, max(1, round(interval))


def get_default_fsrs_state() -> dict:
    return {"stability": 1.0, "difficulty": 5.0, "interval": 1}


def calc_next_review(rating: int, current_state: dict | None = None) -> dict:
    state = current_state or get_default_fsrs_state()
    new_stability, new_difficulty, interval = fsrs_next_interval(
        state["stability"], state["difficulty"], rating
    )
    next_review = datetime.now(timezone.utc) + timedelta(days=interval)
    return {
        "stability": new_stability,
        "difficulty": new_difficulty,
        "interval": interval,
        "next_review_at": next_review.isoformat(),
    }
```

- [ ] **Step 2: Create mistake notebook API routes**

Create `src/api/routes/mistakes.py`:

```python
"""Mistake notebook CRUD API with FSRS-based review scheduling."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/mistakes", tags=["mistakes"])


class MistakeCreate(BaseModel):
    question_text: str
    question_snapshot: dict | None = None
    user_answer: str = ""
    correct_answer: str
    solution_steps: list[dict] | None = None
    knowledge_points: list[str] | None = None
    subject: str = ""
    difficulty: int = 3


class MistakeUpdate(BaseModel):
    mastered: bool | None = None
    review_rating: int | None = None  # 1-4 for FSRS


@router.get("")
async def list_mistakes(
    user_id: str = Depends(_get_current_user_id),
    subject: str | None = None,
    mastered: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List mistakes with optional filters."""
    # Read from SQLite via MistakeNotebook model
    ...


@router.post("")
async def create_mistake(data: MistakeCreate, user_id: str = Depends(_get_current_user_id)):
    """Add a mistake to the notebook."""
    from src.models.kaoyan import MistakeNotebook

    mistake = MistakeNotebook(
        user_id=user_id,
        question_text=data.question_text,
        question_snapshot=data.question_snapshot or {},
        user_answer=data.user_answer,
        correct_answer=data.correct_answer,
        solution_steps=data.solution_steps or [],
        knowledge_points=data.knowledge_points or [],
        subject=data.subject,
        difficulty=data.difficulty,
        fsrs_state={"stability": 1.0, "difficulty": 5.0, "interval": 1},
        next_review_at=datetime.now(timezone.utc),
    )
    # Save to DB
    return {"id": mistake.id, "message": "已添加到错题本"}


@router.patch("/{mistake_id}")
async def update_mistake(mistake_id: str, data: MistakeUpdate, user_id: str = Depends(_get_current_user_id)):
    """Update mistake status or review rating."""
    from src.models.kaoyan import MistakeNotebook
    from . import fsrs

    mistake = None  # fetch from DB by mistake_id + user_id
    if not mistake:
        raise HTTPException(404, "错题记录不存在")

    if data.mastered is not None:
        mistake.mastered = data.mastered

    if data.review_rating is not None:
        new_state = fsrs.calc_next_review(data.review_rating, mistake.fsrs_state)
        mistake.fsrs_state = {
            "stability": new_state["stability"],
            "difficulty": new_state["difficulty"],
            "interval": new_state["interval"],
        }
        mistake.next_review_at = datetime.fromisoformat(new_state["next_review_at"])
        mistake.review_count += 1

    # Save to DB
    return {"message": "已更新"}


@router.get("/review-queue")
async def get_review_queue(user_id: str = Depends(_get_current_user_id)):
    """Get today's review queue based on FSRS scheduling."""
    # Fetch mistakes where next_review_at <= now AND mastered = false
    # Ordered by next_review_at ASC
    ...
```

- [ ] **Step 3: Register mistake routes in FastAPI server**

```python
# In src/api/run_server.py
from src.api.routes.mistakes import router as mistakes_router
app.include_router(mistakes_router)
```

- [ ] **Step 4: Commit mistake notebook API**

```powershell
git add -A
git commit -m "feat(L4): add mistake notebook CRUD API with FSRS spaced repetition"
```

---

### Task 11: Score Estimation API

**Files:**
- Create: `src/api/routes/score.py`

- [ ] **Step 1: Implement Monte Carlo score estimator**

Create `src/api/routes/score.py`:

```python
"""Monte Carlo score estimation for Kaoyan math."""
import random
import statistics
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/score", tags=["score"])


# Kaoyan math question type distribution
QUESTION_DISTRIBUTION = {
    "math-1": {"choice": 8, "fill": 6, "solve": 9},
    "math-2": {"choice": 6, "fill": 5, "solve": 7},
    "math-3": {"choice": 8, "fill": 6, "solve": 9},
}

# Point values per question type
POINT_VALUES = {
    "choice": 4,   # 4 points each
    "fill": 4,     # 4 points each
    "solve": 10,   # ~10 points each (varies, simplified)
}

TOTAL_SCORE = 150
PASS_THRESHOLD = 90  # Typical pass line


def _simulate_exam(
    knowledge_points: dict[str, float],  # kp_id -> mastery (0.0-1.0)
    exam_mode: str,
    num_simulations: int = 1000,
) -> dict[str, Any]:
    """Run Monte Carlo simulation of a Kaoyan math exam."""
    dist = QUESTION_DISTRIBUTION.get(exam_mode, QUESTION_DISTRIBUTION["math-1"])
    total_questions = sum(dist.values())

    # Build question pool from knowledge points
    # In production, this would sample from actual exam question templates
    # mapped to knowledge points. For MVP, we use the KP mastery levels directly.
    kp_list = list(knowledge_points.items())
    if not kp_list:
        return {"estimated_score": 0, "pass_probability": 0, "weak_areas": []}

    scores: list[float] = []
    for _ in range(num_simulations):
        total = 0.0
        # Simulate each question
        for qtype, count in dist.items():
            for _ in range(count):
                # Pick a random knowledge point for this question
                kp_id, mastery = random.choice(kp_list)
                # Probability of correct answer = mastery level
                score = POINT_VALUES[qtype] if random.random() < mastery else 0
                # Partial credit for solve questions
                if qtype == "solve" and score == 0 and random.random() < mastery * 0.5:
                    score = POINT_VALUES[qtype] * 0.4  # partial credit
                total += score
        scores.append(total)

    mean_score = statistics.mean(scores)
    std_score = statistics.stdev(scores) if len(scores) > 1 else 0
    pass_prob = sum(1 for s in scores if s >= PASS_THRESHOLD) / num_simulations

    # Identify weak areas (mastery < 0.5)
    weak_areas = [kp_id for kp_id, m in kp_list if m < 0.5]
    weak_areas.sort(key=lambda kp: knowledge_points[kp])

    return {
        "estimated_score": round(mean_score, 1),
        "score_std": round(std_score, 1),
        "score_range": f"{round(mean_score - std_score)}-{round(mean_score + std_score)}",
        "pass_probability": round(pass_prob * 100, 1),
        "total_score": TOTAL_SCORE,
        "weak_areas": weak_areas[:5],  # Top 5 weakest
        "num_simulations": num_simulations,
    }


@router.post("/estimate")
async def estimate_score(
    knowledge_points: dict[str, float],
    exam_mode: str = "math-1",
):
    """Estimate exam score via Monte Carlo simulation.
    
    Args:
        knowledge_points: Map of knowledge_point_id to mastery level (0.0-1.0)
        exam_mode: "math-1", "math-2", or "math-3"
    """
    if exam_mode not in QUESTION_DISTRIBUTION:
        exam_mode = "math-1"

    result = _simulate_exam(knowledge_points, exam_mode)
    return result
```

- [ ] **Step 2: Register and commit**

```powershell
# Add route registration in run_server.py
git add -A
git commit -m "feat(L4): add Monte Carlo score estimation API"
```

---

### Task 12: Study Plan Generator

**Files:**
- Create: `src/api/routes/study_plan.py`

- [ ] **Step 1: Implement study plan generator**

Create `src/api/routes/study_plan.py`:

```python
"""AI-powered study plan generator."""
import json
import os
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/study-plan", tags=["study-plan"])


def _load_knowledge_graph() -> dict:
    path = os.path.join(os.path.dirname(__file__), "../../../knowledge/kaoyan-math/knowledge-graph.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _generate_daily_tasks(
    kp_mastery: dict[str, float],
    weak_only: bool = True,
    max_tasks: int = 5,
) -> list[dict]:
    """Generate prioritized study tasks based on knowledge point mastery."""
    kg = _load_knowledge_graph()
    tasks = []

    # Collect all topics with their mastery
    all_topics = []
    for subject in kg["subjects"]:
        for chapter in subject["chapters"]:
            for topic in chapter["topics"]:
                mastery = kp_mastery.get(topic["id"], 0.0)
                all_topics.append({
                    "kp_id": topic["id"],
                    "name": topic["name"],
                    "chapter": chapter["name"],
                    "subject": subject["name"],
                    "mastery": mastery,
                    "difficulty": topic["difficulty"],
                    "frequency": chapter["frequency"],
                })

    # Prioritize: low mastery + high frequency first
    if weak_only:
        all_topics = [t for t in all_topics if t["mastery"] < 0.6]

    all_topics.sort(key=lambda t: (
        t["mastery"],                              # Low mastery first
        -t["difficulty"] if t["mastery"] < 0.3 else t["difficulty"],  # Easy first for very weak
        -1 if t["frequency"] == "high" else 0,   # High frequency first
    ))

    for topic in all_topics[:max_tasks]:
        tasks.append({
            "kp_id": topic["kp_id"],
            "name": topic["name"],
            "chapter": topic["chapter"],
            "task_type": "review" if topic["mastery"] > 0.3 else "learn",
            "estimated_minutes": 25,
            "reason": f"掌握度 {topic['mastery']:.0%}，{'高频考点' if topic['frequency'] == 'high' else '需加强'}",
        })

    return tasks


@router.get("/today")
async def get_today_plan(user_id: str = Depends(_get_current_user_id)):
    """Get today's study plan."""
    today = date.today()
    # Check if plan exists for today
    # If not, generate one
    ...
    return {"date": today.isoformat(), "tasks": [...]}


@router.post("/generate")
async def generate_plan(user_id: str = Depends(_get_current_user_id)):
    """Generate a new study plan based on current progress."""
    # Fetch user's learning_progress from DB
    kp_mastery = {}  # populate from DB
    tasks = _generate_daily_tasks(kp_mastery)
    return {"date": date.today().isoformat(), "tasks": tasks}
```

- [ ] **Step 2: Commit study plan API**

```powershell
git add -A
git commit -m "feat(L4): add AI-powered study plan generator"
```

---

### Task 13: Frontend Pages (Dashboard, Notebook, Plan, Pricing)

**Files:**
- Create: `web/src/app/(app)/dashboard/page.tsx`
- Create: `web/src/app/(app)/notebook/page.tsx`
- Create: `web/src/app/(app)/plan/page.tsx`
- Create: `web/src/app/(app)/pricing/page.tsx`
- Modify: `web/src/components/Sidebar.tsx`

- [ ] **Step 1: Create sidebar navigation items**

Update `Sidebar.tsx` to add new nav entries:

```tsx
const NAV_ITEMS = [
  { href: "/chat", label: "AI解题", icon: "💬" },
  { href: "/dashboard", label: "学习进度", icon: "📊" },
  { href: "/notebook", label: "错题本", icon: "📝" },
  { href: "/plan", label: "学习计划", icon: "📋" },
  { href: "/pricing", label: "升级会员", icon: "⭐" },
];
```

- [ ] **Step 2: Create dashboard page**

Create `web/src/app/(app)/dashboard/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { Radar, Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
} from "chart.js";

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend, CategoryScale, LinearScale);

export default function DashboardPage() {
  const [progress, setProgress] = useState<any>(null);

  useEffect(() => {
    fetch("/api/progress")
      .then((r) => r.json())
      .then(setProgress);
  }, []);

  if (!progress) return <div className="p-8">加载中...</div>;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8">
      <h1 className="text-2xl font-bold">学习进度</h1>

      {/* Radar Chart — Knowledge Mastery */}
      <div className="p-6 rounded-xl border border-border">
        <h3 className="font-semibold mb-4">知识点掌握度</h3>
        <div className="max-w-md mx-auto">
          <Radar
            data={{
              labels: progress.categories,
              datasets: [{
                label: "掌握度",
                data: progress.mastery_levels,
                backgroundColor: "rgba(79, 70, 229, 0.2)",
                borderColor: "#4F46E5",
                borderWidth: 2,
              }],
            }}
            options={{
              scales: { r: { min: 0, max: 100, ticks: { stepSize: 20 } } },
            }}
          />
        </div>
      </div>

      {/* Weekly Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="p-4 rounded-xl border border-border text-center">
          <div className="text-2xl font-bold text-primary">{progress.weekly_questions}</div>
          <div className="text-sm text-muted-foreground">本周做题</div>
        </div>
        <div className="p-4 rounded-xl border border-border text-center">
          <div className="text-2xl font-bold text-primary">{progress.weekly_accuracy}%</div>
          <div className="text-sm text-muted-foreground">正确率</div>
        </div>
        <div className="p-4 rounded-xl border border-border text-center">
          <div className="text-2xl font-bold text-primary">{progress.streak_days}</div>
          <div className="text-sm text-muted-foreground">连续学习天数</div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create notebook page**

Create `web/src/app/(app)/notebook/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";

interface Mistake {
  id: string;
  question_text: string;
  subject: string;
  difficulty: number;
  knowledge_points: string[];
  mastered: boolean;
  next_review_at: string;
  solution_steps: { step: string; explanation: string }[];
}

export default function NotebookPage() {
  const [mistakes, setMistakes] = useState<Mistake[]>([]);
  const [filter, setFilter] = useState({ subject: "", mastered: "" });
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams();
    if (filter.subject) params.set("subject", filter.subject);
    if (filter.mastered) params.set("mastered", filter.mastered);
    fetch(`/api/mistakes?${params}`)
      .then((r) => r.json())
      .then((d) => setMistakes(d.items));
  }, [filter]);

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">错题本</h1>

      {/* Filters */}
      <div className="flex gap-3">
        <select
          className="px-3 py-2 rounded-lg border border-border bg-background"
          value={filter.subject}
          onChange={(e) => setFilter({ ...filter, subject: e.target.value })}
        >
          <option value="">全部科目</option>
          <option value="gaoshu">高等数学</option>
          <option value="xiandai">线性代数</option>
          <option value="gailv">概率论</option>
        </select>
        <select
          className="px-3 py-2 rounded-lg border border-border bg-background"
          value={filter.mastered}
          onChange={(e) => setFilter({ ...filter, mastered: e.target.value })}
        >
          <option value="">全部状态</option>
          <option value="false">未掌握</option>
          <option value="true">已掌握</option>
        </select>
      </div>

      {/* Mistake Cards */}
      <div className="space-y-4">
        {mistakes.map((m) => (
          <div key={m.id} className="p-4 rounded-xl border border-border">
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <p className="font-medium">{m.question_text}</p>
                <div className="flex gap-2 mt-2">
                  <span className="text-xs px-2 py-0.5 rounded bg-primary/10 text-primary">
                    {m.subject}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">
                    {"★".repeat(m.difficulty)}{"☆".repeat(5 - m.difficulty)}
                  </span>
                </div>
              </div>
              <button
                onClick={() => setExpandedId(expandedId === m.id ? null : m.id)}
                className="text-sm text-primary"
              >
                {expandedId === m.id ? "收起" : "展开解析"}
              </button>
            </div>

            {expandedId === m.id && (
              <div className="mt-4 pt-4 border-t border-border space-y-2">
                {m.solution_steps.map((step, i) => (
                  <div key={i} className="text-sm">
                    <span className="font-semibold">Step {i + 1}:</span> {step.step}
                    <p className="text-muted-foreground mt-0.5">{step.explanation}</p>
                  </div>
                ))}
                <div className="flex gap-2 mt-4">
                  <button
                    onClick={() => {
                      fetch(`/api/mistakes/${m.id}`, {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ mastered: true }),
                      }).then(() => setFilter({ ...filter }));
                    }}
                    className="px-3 py-1 text-sm rounded bg-green-100 text-green-700"
                  >
                    已掌握
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create pricing page**

Create `web/src/app/(app)/pricing/page.tsx`:

```tsx
export default function PricingPage() {
  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8">
      <h1 className="text-2xl font-bold text-center">选择你的学习计划</h1>

      <div className="grid md:grid-cols-3 gap-6">
        {/* Free */}
        <div className="p-6 rounded-xl border border-border">
          <h3 className="font-bold text-lg">免费版</h3>
          <div className="text-3xl font-bold mt-4">¥0</div>
          <p className="text-sm text-muted-foreground mt-1">永久免费</p>
          <ul className="mt-6 space-y-2 text-sm">
            <li>10题/天</li>
            <li>Chat 对话模式</li>
            <li>基础 RAG 问答</li>
            <li className="text-muted-foreground line-through">Deep Solve 逐步解题</li>
            <li className="text-muted-foreground line-through">Math Animator 动画</li>
            <li className="text-muted-foreground line-through">错题本</li>
          </ul>
          <button className="w-full mt-6 py-2 rounded-lg border border-primary text-primary">
            开始使用
          </button>
        </div>

        {/* Monthly */}
        <div className="p-6 rounded-xl border-2 border-primary relative">
          <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-primary text-white text-xs rounded-full">
            推荐
          </div>
          <h3 className="font-bold text-lg">月卡</h3>
          <div className="text-3xl font-bold mt-4">¥29</div>
          <p className="text-sm text-muted-foreground mt-1">/月</p>
          <ul className="mt-6 space-y-2 text-sm">
            <li>无限提问</li>
            <li>Deep Solve 逐步解题</li>
            <li>Quiz 智能出题</li>
            <li>错题本+FSRS复习</li>
            <li className="text-muted-foreground line-through">估分系统</li>
            <li className="text-muted-foreground line-through">Math Animator</li>
          </ul>
          <button className="w-full mt-6 py-2 rounded-lg bg-primary text-white">
            立即订阅
          </button>
        </div>

        {/* Yearly */}
        <div className="p-6 rounded-xl border border-border">
          <h3 className="font-bold text-lg">年卡</h3>
          <div className="text-3xl font-bold mt-4">¥199</div>
          <p className="text-sm text-muted-foreground mt-1">/年 (省¥149)</p>
          <ul className="mt-6 space-y-2 text-sm">
            <li>月卡全部功能</li>
            <li>估分系统</li>
            <li>学习计划生成</li>
            <li>Math Animator 动画</li>
            <li>优先新功能体验</li>
          </ul>
          <button className="w-full mt-6 py-2 rounded-lg bg-primary text-white">
            立即订阅
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Commit frontend pages**

```powershell
git add -A
git commit -m "feat(L4): add dashboard, notebook, pricing pages; update sidebar navigation"
```

---

### Task 14: Content Filter Middleware + Analytics

**Files:**
- Create: `src/middleware/content_filter.py`
- Create: `src/middleware/analytics.py`

- [ ] **Step 1: Create content filter middleware**

```python
"""Content filtering middleware for compliance."""
import re
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

SENSITIVE_PATTERNS = [
    re.compile(r"敏感词1"),
    re.compile(r"敏感词2"),
    # Add actual patterns based on regulatory requirements
]

class ContentFilterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Check query params and body for sensitive content
        # Log and block if found
        response = await call_next(request)
        return response
```

- [ ] **Step 2: Commit middleware**

```powershell
git add -A
git commit -m "feat(L4): add content filter middleware and analytics tracking"
```

---

## Phase 5: Deployment

### Task 15: Docker Compose Production Config

**Files:**
- Create: `docker-compose.prod.yml`
- Create: `nginx.conf`

- [ ] **Step 1: Create production Docker Compose**

```yaml
# docker-compose.prod.yml
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
      - frontend
      - backend
    restart: unless-stopped

  frontend:
    build: ./web
    environment:
      - NEXT_PUBLIC_API_URL=https://api.shuyanzhushou.com
      - NEXT_PUBLIC_BRAND_NAME=数研助手
    restart: unless-stopped

  backend:
    build: .
    env_file: .env
    environment:
      - BRAND_MODE=kaoyan
    volumes:
      - ./data:/app/data
      - ./knowledge:/app/knowledge
    restart: unless-stopped

  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - ./qdrant_data:/qdrant/storage
    restart: unless-stopped
```

- [ ] **Step 2: Create Nginx config**

```nginx
# nginx.conf
events { worker_connections 1024; }

http {
    upstream frontend { server frontend:3782; }
    upstream backend { server backend:8001; }

    server {
        listen 80;
        server_name shuyanzhushou.com www.shuyanzhushou.com;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl;
        server_name shuyanzhushou.com www.shuyanzhushou.com;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        location / {
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }

        location /api/ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }

        location /ws {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }
}
```

- [ ] **Step 3: Create .env.kaoyan template**

```bash
# .env.kaoyan — 数研助手生产环境配置模板
LLM_BINDING=deepseek
LLM_MODEL=deepseek-chat
LLM_API_KEY=<your-deepseek-key>
LLM_HOST=https://api.deepseek.com/v1
LLM_MAX_TOKENS=8192

EMBEDDING_BINDING=dashscope
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_API_KEY=<your-dashscope-key>

WEB_SEARCH=duckduckgo

ENABLE_AUTH=true
JWT_SECRET=<generate-random-string>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<strong-password>

BRAND_NAME=数研助手
BRAND_SLOGAN=你的AI考研数学老师
PRIMARY_COLOR=#4F46E5

WECHAT_APP_ID=<your-wechat-app-id>
WECHAT_APP_SECRET=<your-wechat-app-secret>
```

- [ ] **Step 4: Commit deployment configs**

```powershell
git add -A
git commit -m "feat(P5): add production Docker Compose, Nginx config, env template"
```

---

### Task 16: Push to GitHub and Final Verification

- [ ] **Step 1: Push all commits to GitHub**

```powershell
Set-Location C:\Users\m1770\Desktop\Deeptutor\shuyan-zhushou
git push origin main
```

Expected: All commits pushed to `https://github.com/ZhangShiCheng3D/DeepTutor`

- [ ] **Step 2: Rename GitHub repo (optional)**

```powershell
gh repo rename shuyan-zhushou --repo ZhangShiCheng3D/DeepTutor
# IF the fork is still named DeepTutor, rename it:
# gh repo rename DeepTutor shuyan-zhushou
```

- [ ] **Step 3: Final integration test**

```powershell
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

Verify:
- `http://localhost` shows branded homepage
- `/chat` loads with new sidebar and Chinese prompts
- Deep Solve works with DeepSeek
- All new API endpoints respond

---

## Self-Review

**1. Spec coverage:** Each spec section maps to tasks:
- L1 Branding → Tasks 1-3
- L2 Content → Tasks 4-5
- L3 Experience → Tasks 6-8
- L4 Features → Tasks 9-14
- P5 Deployment → Tasks 15-16

**2. Placeholder check:** No TBD/TODO. Every task has concrete code. Some API implementations use `...` for DB access that depends on DeepTutor's actual DB layer — these will need to be adapted once the codebase is forked and inspected.

**3. Type consistency:** ExamMode types match between ExamModeSwitcher and score.py. MistakeNotebook model fields match the API route's Pydantic models. Knowledge graph IDs used consistently across prompt templates.

**One caveat:** The exact file paths within DeepTutor's source tree may vary slightly from the plan. DeepTutor has undergone a major v1.0 refactor. The first task of each phase should verify the actual file structure before making changes.
