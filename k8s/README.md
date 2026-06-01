# Kubernetes 编排（万级并发 · P2 编排层）

配套设计文档：`docs/deeptutor-high-concurrency-optimization-20260602.html`

参数化 kustomize base，把 MathVerse + DeepTutor 全栈跑成**无状态副本 + 自动扩缩**。前置是 P0/P1/P2/P3a 改动已构建进镜像。**P3a 已去亲和 → ingress 无需 session 亲和**，所以这套清单是普通 WS 代理，简单可靠。

## 拓扑

```
Ingress(公网, 仅 mathverse-api) ─▶ mathverse-api (HPA 3-20)
                                        │ 有界并发(P-MV)
                                        ▼
                                   deeptutor-web (HPA 3-40, WEB_CONCURRENCY=4, ROLE=web)
                                   deeptutor-bot (1 副本, ROLE=bot)
                                        │
                 ┌──────────────┬───────┴────────┬──────────────┐
                 ▼              ▼                ▼              ▼
              postgres(P1)   litellm 网关(P2)   redis        qdrant
                            (多账户LB+全局限流)  (限流/未来P3b)  (RAG)
```

## 你必须填的占位符

| 占位符 | 文件 | 含义 |
|---|---|---|
| `REPLACE_ME_REGISTRY` / `REPLACE_ME_TAG` | kustomization.yaml | 镜像仓库 + tag |
| `REPLACE_ME_STORAGECLASS` | data.yaml | 集群 storage class |
| `REPLACE_ME_DOMAIN` | edge.yaml | 公网域名（如 kuangyebar.cn） |
| `REPLACE_ME_INGRESS_CLASS` | edge.yaml | ingress class（如 nginx） |
| `REPLACE_ME_MATHVERSE_DB_URL` | mathverse-api.yaml | mathverse-api 自己的业务库（多副本要托管 PG，非 SQLite） |
| secret 里的 `REPLACE_ME_*` | secret.example.yaml | 各类 key/密码 |

## 部署

```bash
# 1) 构建并推镜像
docker build -t <REGISTRY>/deeptutor-patched:<TAG> deeptutor-patch/
docker build -t <REGISTRY>/mathverse-api:<TAG>     mathverse-api/
docker push <REGISTRY>/deeptutor-patched:<TAG>
docker push <REGISTRY>/mathverse-api:<TAG>

# 2) 准备 secret（不要提交进 git）
cp k8s/secret.example.yaml k8s/secret.yaml && $EDITOR k8s/secret.yaml
kubectl apply -f k8s/secret.yaml

# 3) 填好占位符后一键部署
kubectl apply -k k8s/
```

## ⚠️ 必须人工核对的一处：model_catalog.json schema

`k8s/files/model_catalog.json` 的**结构是按 CLAUDE.md 的描述推断的**（active LLM/embedding profile，binding=openai，base_url 指向网关）。**DeepTutor 真实的 `data/user/settings/model_catalog.json` 字段名可能不同。** 部署前请：

1. 在一个能跑的 DeepTutor 实例上 `cat data/user/settings/model_catalog.json` 看真实结构；
2. 据此修正 `k8s/files/model_catalog.json`（保持 `base_url=http://litellm:4000`、`api_key=__LITELLM_MASTER_KEY__` 占位，由 initContainer 替换）。

否则 DeepTutor 可能读不到网关配置、LLM 调用超时（见 CLAUDE.md 的 DeepTutor 配置踩坑）。

## 生产建议

- **托管 PG/Redis** 优先（RDS/CloudSQL/腾讯云 TencentDB）：删掉 data.yaml 里对应 StatefulSet，把 `DEEPTUTOR_PG_DSN`/`REDIS_HOST` 指向托管端点。
- **mathverse-api 的 `DATABASE_URL`** 默认 SQLite 是每 pod 独立、不跨副本 → 多副本务必换共享 PG。
- DeepTutor `ENABLE_AUTH=false`，**只能内网可达**（已只暴露 mathverse-api）。
- HPA 对 deeptutor-web 默认按 CPU；万级建议换**自定义指标（在飞 turn / 活跃 WS 连接数）**——chat turn 是 LLM IO 密集，CPU 会低估负载（见设计文档 §5）。
- qdrant 单实例起步，万级 RAG QPS 需分片+副本。

## 与各阶段的关系

清单消费的 env 开关全部来自 patch：`WEB_CONCURRENCY`(P0)、`DEEPTUTOR_PG_DSN`(P1)、`DEEPTUTOR_ROLE`(P2)、面 A 去亲和(P3a 自动生效于多副本)、`DEEPTUTOR_MAX_CONCURRENCY`(P-MV)。**输出转对象存储**（动画/可视化产物）仍是 P2 尾巴未做项——当前 deeptutor-web 多副本下，一个副本生成的 `/api/outputs` 产物另一副本取不到；若你们用到可视化/动画能力需补这块（COS/S3）。
