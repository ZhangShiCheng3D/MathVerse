---
name: open-findings-20260612
description: 2026-06-12 系统审查未关闭的发现 — /ws/solve 缺 cost-guard、匿名 tutor 前后端契约错位、get_current_user 不校验 token type
metadata:
  type: project
---

2026-06-12 对 PR #15 分支（含 2026-06-07 未提交的 session 租户改动）做了系统审查。租户隔离本身验证干净（dashboard/tutor ownership 过滤正确、匿名不能 regenerate/续接、测试真实覆盖）。未关闭的发现：

- **P1 `/ws/solve` 缺 cost_guard**（enforce_cost_budget + record 都没有，solve metrics 也没有）——前端优先走 WS，主路径绕过支出护栏。
- **P1 匿名 tutor 契约错位**：后端 `done` 仍向匿名返回 engine session_id，前端存下后续传（被后端忽略→无上下文假连续），且 `canRegen` 不看登录态 → 匿名点「重答」会弹掉最后答案并报错。
- **P1 `get_current_user` 不校验 `payload["type"]=="access"`** → refresh token（7 天）可直接当 access token 打所有 HTTP 端点（WS 的 `_user_from_token` 有校验）。
- P2：`dt_ownership.record` check-then-insert 非原子且 IntegrityError 不捕获/不 rollback；DtResource 新 UniqueConstraint 无迁移，生产旧表不会有该约束。
- P2：tutor.py 匿名 + use_rag + kb_name → `mv_anon_<kb>`（solve_ws 有 `req_kb and user` 防护，tutor 没有）。
- P2：learn.py `/lecture`、`/exercise/generate` 匿名可用且无 quota/cost_guard/content-filter。

**How to apply:** 下次审查先核对这些是否已修；若已修则删除本条目。
