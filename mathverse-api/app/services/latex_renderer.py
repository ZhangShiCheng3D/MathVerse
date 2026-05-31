"""KaTeX server-side rendering to SVG."""
import os


def latex_to_svg(latex: str) -> str:
    """Render LaTeX string to SVG.

    For MVP, returns the LaTeX string wrapped for client-side rendering.
    Full KaTeX server-side rendering requires Node.js KaTeX on the server
    and will be implemented via /api/render/latex endpoint in Phase 2.
    """
    return latex


def batch_render_formulas(formulas: list[str], output_dir: str) -> dict[str, str]:
    """Batch render formulas to SVG files. Returns {latex: svg_filename}."""
    os.makedirs(output_dir, exist_ok=True)
    results = {}
    for i, formula in enumerate(formulas):
        svg = latex_to_svg(formula)
        filename = f"formula_{i}.svg"
        with open(os.path.join(output_dir, filename), "w", encoding="utf-8") as f:
            f.write(svg)
        results[formula] = filename
    return results
