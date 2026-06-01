# Overlay that patches upstream DeepTutor so photo-solving works.
#
# Two upstream problems, both fixed by patch.py at build time:
#  1. vision_solver_agent passes an unsupported `verbose=` kwarg to
#     BaseAgent.stream_llm() -> TypeError on every WS /api/v1/vision/solve call.
#  2. The vision router is hard-tied to the active LLM profile (DeepSeek
#     deepseek-chat, text-only), so images can't be processed. We let it use a
#     dedicated vision model via env (VISION_API_KEY / VISION_BASE_URL /
#     VISION_MODEL), falling back to the active profile when unset — keeping
#     text on DeepSeek and vision on a multimodal model (qwen-vl-max).
#
# Wired in via docker-compose.override.yml (deeptutor.build: ./deeptutor-patch).
# Drop this overlay once upstream ships both fixes.
FROM ghcr.io/hkuds/deeptutor:latest
COPY patch.py /tmp/patch.py
RUN python /tmp/patch.py
