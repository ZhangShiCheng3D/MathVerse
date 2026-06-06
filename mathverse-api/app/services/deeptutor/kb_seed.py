"""Seed the shared curriculum knowledge base from the static knowledge graph.

"先搭管线" — there's no real textbook corpus yet, so the curriculum KB is seeded
with the structured knowledge graph (subjects → chapters → topics) so RAG-grounded
solving has *something* to retrieve. Real教材/课标 PDFs are uploaded later via the
same /api/kb endpoints.
"""
from app.services.kg import load_kg


def build_curriculum_doc(stage: str) -> tuple[str, bytes, str]:
    """Render a stage's knowledge graph into a Markdown doc for KB ingestion.

    Returns an httpx multipart tuple: (filename, bytes, content_type).
    """
    kg = load_kg(stage)
    lines = [f"# {kg.get('stage', stage)} 数学课程知识体系\n"]
    for subject in kg.get("subjects", []):
        lines.append(f"\n## {subject['name']}")
        for chapter in subject.get("chapters", []):
            lines.append(f"\n### {chapter['name']}")
            for topic in chapter.get("topics", []):
                diff = topic.get("difficulty", "?")
                freq = topic.get("frequency", "?")
                lines.append(f"- {topic['name']}（知识点 {topic.get('id', '')}，难度 {diff}，考频 {freq}）")
    text = "\n".join(lines)
    return (f"curriculum_{stage}.md", text.encode("utf-8"), "text/markdown")
