---
name: review-gotchas
description: MathVerse 审查执行须知 — 三套测试如何跑、deeptutor-patch 本地 pytest 必然报 14 errors（镜像内专用）
metadata:
  type: project
---

跑全量验证的正确姿势（2026-06-12 验证）：
- `mathverse-api/` 下 `python -m pytest -q`（Windows 直接跑，约 40s）。
- `mathverse-miniapp/` 下 `npm run test`（Vitest）。
- `deeptutor-patch/` 下本地 `pytest tests/` 会出现 **14 errors（ModuleNotFoundError: deeptutor）— 这是预期**：`test_session_store_parity.py` 的 sqlite 参数化分支只能在构建后的镜像内跑（PG/Redis 分支会 skip，sqlite 分支不会 skip 而是 ERROR）。本地有效信号 = `test_turn_bus_unit.py` + `test_patch_codegen.py` 的 10 passed。

**Why:** 第一次审查时差点把 14 errors 当成回归上报。
**How to apply:** 报告 deeptutor-patch 测试结果时只看 10 个本地测试；可建议改 pytest.importorskip 让其优雅 skip（P2）。

另：`tests/test_tutor.py` 的 `_auth_user()` 创建的 User 不清理，会污染本地 dev DB（test_activity 有 teardown，test_tutor 没有）。
