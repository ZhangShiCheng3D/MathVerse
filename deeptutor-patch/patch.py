"""Build-time patch for upstream DeepTutor photo-solving. See Dockerfile.

Asserts on every edit so an upstream change that moves the target fails the
build loudly instead of silently shipping an unpatched image.
"""

ROOT = "/app/deeptutor"

# 1) Drop the unsupported `verbose=` kwarg that crashes vision LLM calls.
agent_f = f"{ROOT}/agents/vision_solver/vision_solver_agent.py"
src = open(agent_f, encoding="utf-8").read()
patched = src.replace("            verbose=False,\n", "")
assert patched != src, "verbose=False line not found — upstream changed"
open(agent_f, "w", encoding="utf-8").write(patched)

# 2) Let the vision router use a dedicated vision model/creds from env, falling
#    back to the active LLM profile when the env vars are unset.
router_f = f"{ROOT}/api/routers/vision_solver.py"
r = open(router_f, encoding="utf-8").read()
OLD = (
    "        agent = VisionSolverAgent(\n"
    "            api_key=api_key,\n"
    "            base_url=base_url,\n"
    "            language=language,\n"
    "        )\n"
)
NEW = (
    "        import os as _os\n"
    '        _vk = _os.environ.get("VISION_API_KEY")\n'
    '        _vb = _os.environ.get("VISION_BASE_URL")\n'
    '        _vm = _os.environ.get("VISION_MODEL")\n'
    "        agent = VisionSolverAgent(\n"
    "            api_key=_vk or api_key,\n"
    "            base_url=_vb or base_url,\n"
    "            model=_vm,\n"
    "            vision_model=_vm,\n"
    "            language=language,\n"
    "        )\n"
)
count = r.count(OLD)
assert count >= 1, "vision agent construction block not found — upstream changed"
open(router_f, "w", encoding="utf-8").write(r.replace(OLD, NEW))

print(f"patched ok: verbose removed, {count} vision construction site(s) updated")
