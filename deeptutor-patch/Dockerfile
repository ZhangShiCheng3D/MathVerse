# Overlay that patches an upstream DeepTutor bug blocking photo-solving.
#
# Upstream `ghcr.io/hkuds/deeptutor:latest` ships a vision_solver_agent that
# passes an unsupported `verbose=` kwarg to BaseAgent.stream_llm(), so every
# WS /api/v1/vision/solve call raises:
#   TypeError: BaseAgent.stream_llm() got an unexpected keyword argument 'verbose'
# and returns an empty answer. Removing that single line fixes vision; all other
# paths are unaffected. Drop this overlay once upstream ships the fix.
#
# Wired in via docker-compose.override.yml (deeptutor.build: ./deeptutor-patch).
FROM ghcr.io/hkuds/deeptutor:latest
RUN sed -i '/^[[:space:]]*verbose=False,[[:space:]]*$/d' \
    /app/deeptutor/agents/vision_solver/vision_solver_agent.py
