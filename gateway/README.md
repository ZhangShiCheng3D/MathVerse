# LLM 网关（多账户外部 API 负载均衡 + 全局限流）

配套设计文档：`docs/deeptutor-high-concurrency-optimization-20260602.html` · 阶段 **P2**

## 为什么需要它

万级**在飞解题**会同时向 DeepSeek 流式产出。单个 DeepSeek 账户有 RPM/TPM/并发限额，远扛不住。这层 [LiteLLM](https://docs.litellm.ai/) 网关：

- **多 key / 多账户负载均衡** —— 加账户 = 在 `litellm-config.yaml` 的 `model_list` 里多加一条同名 `model_name` 的条目。
- **全局限流**（Redis 协调，跨网关副本生效）—— 真正的「物理上限」管理点。
- **重试 / 回退 / 冷却** —— 某个 key 限流或失败，自动换另一个 key 重试。
- **背压** —— 所有 key 都打满时返回明确的 429，让上游排队/重试，而不是把账户打爆。

## 它如何接入（DeepTutor 零代码改动）

LiteLLM 暴露 OpenAI 兼容端点。把 DeepTutor 的 `data/user/settings/model_catalog.json` 里**生效 profile** 的 `base_url` 指向网关、`api_key` 用网关 master key：

| profile | model | base_url | api_key |
|---|---|---|---|
| LLM | `deepseek-chat` | `http://litellm:4000` | `${LITELLM_MASTER_KEY}` |
| EMBEDDING | `text-embedding-v3` | `http://litellm:4000` | `${LITELLM_MASTER_KEY}` |
| VISION | `qwen-vl-max` | `http://litellm:4000` | `${LITELLM_MASTER_KEY}` |

`binding` 保持 `openai` 不变。改完重启 deeptutor 容器。

> 真实 key 现在只配在网关（`DEEPSEEK_KEY_1…`、`DASHSCOPE_KEY_1`），不再散落在 DeepTutor 配置里 —— 也更安全。

## 启动（docker-compose）

`.env` 增加：

```
LITELLM_MASTER_KEY=sk-<随机长串>
DEEPSEEK_KEY_1=sk-<账户1>
DEEPSEEK_KEY_2=sk-<账户2>   # 可选，加账户就加 _3 _4…
DASHSCOPE_KEY_1=sk-<dashscope>
```

```bash
docker compose -f docker-compose.yml -f gateway/docker-compose.gateway.yml up -d litellm litellm-redis
# 自检：
curl -s http://localhost:4000/health -H "Authorization: Bearer $LITELLM_MASTER_KEY"
```

## 与 DeepTutor 自带 TrafficController 的关系

DeepTutor 进程内已有 `services/llm/traffic_control.py`（信号量 + 令牌桶，默认并发 20 / 600 RPM）。引入网关后**职责分层**：

- **全局限流 / 跨账户负载均衡 → 网关**（唯一权威，Redis 全局）。
- **每副本本地 bulkhead → DeepTutor 的 TrafficController**（防单副本自身资源耗尽，保持进程内即可）。

所以**不需要**把 `traffic_control.py` 改成分布式 —— 省一处侵入改动。把它的 `max_concurrency` 调到 ≥ 每副本期望在飞数即可。

## Kubernetes

compose 服务可 1:1 翻译为 k8s：
- `litellm` → Deployment（多副本）+ Service `litellm:4000` + HPA（按 CPU/请求数）。
- `litellm-redis` → 小型 Redis（managed Redis 或单实例 StatefulSet）；多副本网关共享它做全局限流。
- key 走 k8s Secret 注入为环境变量。
- DeepTutor 的 `model_catalog.json` 里 `base_url` 用集群内 DNS `http://litellm.<ns>.svc:4000`。

## 容量提示

`model_list` 每条的 `rpm`/`tpm` **必须填成对应账户的真实 DeepSeek/DashScope 限额**（占位值仅示意）。聚合吞吐 ≈ 各账户限额之和；要更高就加账户。这是整套架构里 **成本与上限的真实锚点**（见设计文档 §5）。
