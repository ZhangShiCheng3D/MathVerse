# DeepTutor 高并发压测（基线 & 回归）

配套设计文档：`docs/deeptutor-high-concurrency-optimization-20260602.html`

这些脚本用于在每个优化阶段前后，量化 **并发 → 延迟 → 错误率** 曲线，证明改动真的移动了拐点。

## 前置

安装 [k6](https://k6.io/docs/get-started/installation/)（单二进制，无依赖）。在**内网**对 DeepTutor 容器跑，不要打公网边缘。

## 用法

```bash
# 在服务器上，直连 deeptutor 容器（ENABLE_AUTH=false → 无需 token）
TARGET=ws://127.0.0.1:8001 k6 run load-tests/deeptutor-chat-ws.js

# 扫并发找拐点：依次跑 10 / 25 / 50 / 100 / 200 / 400 VU
for v in 10 25 50 100 200 400; do
  echo "=== VUS=$v ==="; TARGET=ws://127.0.0.1:8001 VUS=$v DURATION=90s \
    k6 run load-tests/deeptutor-chat-ws.js
done
```

## 看什么

- `ttft_ms` — 首 token 延迟（p50/p95/p99）
- `result_ms` — 完整解题延迟
- `turn_error` — 失败 turn 比例（超时 / error 事件 / 握手失败）
- `turns_completed` — 吞吐计数

## 基线方法

1. **改动前**：`WEB_CONCURRENCY=1`（当前等价单进程），扫并发记录曲线 —— 这是基线。
2. **P0 后**（gunicorn 多 worker，且仅在 P1+P3 落地后才调大 `WEB_CONCURRENCY`）：同样扫并发，对比拐点右移。
3. 注意：`result_ms` 的绝对值由外部 LLM（DeepSeek）吐字速度主导，关注的是 **拐点处的 VU 数与 error 率**，而非单条延迟。
