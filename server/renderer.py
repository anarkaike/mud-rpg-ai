"""
MUD-AI — Markdown to HTML Renderer.

Converts artifact markdown content into beautiful dark-themed HTML pages.
Used by the /p/{path} public endpoint.
"""

import os
import markdown
from typing import Optional


def render_markdown_to_html(
    content: str,
    title: str = "MUD-AI",
    path: str = "",
) -> str:
    """Convert markdown content to a full HTML page with dark theme."""
    md = markdown.Markdown(
        extensions=[
            "extra",
            "codehilite",
            "meta",
            "toc",
            "nl2br",
            "sane_lists",
        ],
        extension_configs={
            "codehilite": {"css_class": "highlight", "guess_lang": False},
        },
    )
    html_body = md.convert(content)

    # Try to extract title from frontmatter or first heading
    if hasattr(md, "Meta") and "title" in md.Meta:
        title = md.Meta["title"][0]

    return _wrap_in_template(html_body, title, path)


def _wrap_in_template(body_html: str, title: str, path: str) -> str:
    """Wrap HTML body in a complete dark-themed page."""
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — MUD-AI</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

        :root {{
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --text-muted: #484f58;
            --accent: #58a6ff;
            --accent-subtle: #1f6feb22;
            --green: #3fb950;
            --border: #30363d;
            --radius: 8px;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.7;
            min-height: 100vh;
        }}

        .container {{
            max-width: 720px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
        }}

        .breadcrumb {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-bottom: 1.5rem;
            font-family: 'JetBrains Mono', monospace;
            letter-spacing: 0.02em;
        }}

        .breadcrumb span {{
            color: var(--text-secondary);
        }}

        h1, h2, h3, h4, h5, h6 {{
            color: var(--text-primary);
            margin: 1.5em 0 0.5em;
            font-weight: 600;
            line-height: 1.3;
        }}

        h1 {{
            font-size: 1.8rem;
            margin-top: 0;
            padding-bottom: 0.4em;
            border-bottom: 1px solid var(--border);
        }}

        h2 {{
            font-size: 1.4rem;
            margin-top: 2em;
        }}

        h3 {{ font-size: 1.15rem; }}

        p {{ margin: 0.8em 0; color: var(--text-primary); }}

        a {{
            color: var(--accent);
            text-decoration: none;
            border-bottom: 1px solid transparent;
            transition: border-color 0.2s;
        }}

        a:hover {{ border-color: var(--accent); }}

        blockquote {{
            border-left: 3px solid var(--accent);
            margin: 1.2em 0;
            padding: 0.8em 1.2em;
            background: var(--accent-subtle);
            border-radius: 0 var(--radius) var(--radius) 0;
            color: var(--text-secondary);
        }}

        blockquote p {{ color: var(--text-secondary); margin: 0.3em 0; }}

        code {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85em;
            background: var(--bg-tertiary);
            padding: 0.15em 0.4em;
            border-radius: 4px;
            color: var(--green);
        }}

        pre {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 1.2em;
            overflow-x: auto;
            margin: 1.2em 0;
        }}

        pre code {{
            background: none;
            padding: 0;
            color: var(--text-primary);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1.2em 0;
        }}

        th, td {{
            padding: 0.6em 0.8em;
            text-align: left;
            border: 1px solid var(--border);
        }}

        th {{
            background: var(--bg-secondary);
            font-weight: 600;
            color: var(--text-primary);
        }}

        td {{ color: var(--text-secondary); }}

        tr:hover td {{ background: var(--bg-secondary); }}

        ul, ol {{
            margin: 0.8em 0;
            padding-left: 1.5em;
        }}

        li {{ margin: 0.3em 0; color: var(--text-secondary); }}

        hr {{
            border: none;
            border-top: 1px solid var(--border);
            margin: 2em 0;
        }}

        img {{
            max-width: 100%;
            border-radius: var(--radius);
        }}

        em {{ color: var(--text-secondary); }}

        strong {{ color: var(--text-primary); font-weight: 600; }}

        .footer {{
            margin-top: 3rem;
            padding-top: 1.5rem;
            border-top: 1px solid var(--border);
            text-align: center;
            color: var(--text-muted);
            font-size: 0.8rem;
        }}

        .footer a {{ color: var(--text-secondary); }}

        @media (max-width: 600px) {{
            .container {{ padding: 1rem; }}
            h1 {{ font-size: 1.4rem; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="breadcrumb">
            {_path_to_breadcrumb(path)}
        </div>
        {body_html}
        <div class="footer">
            <p>🌱 MUD-AI — <a href="/">mudai.servinder.com.br</a></p>
        </div>
    </div>
</body>
</html>"""


def _path_to_breadcrumb(path: str) -> str:
    """Convert a dot-notation path into an HTML breadcrumb."""
    if not path:
        return "<span>mudai</span>"

    parts = path.split(".")
    breadcrumbs = []
    for i, part in enumerate(parts):
        if i == len(parts) - 1:
            breadcrumbs.append(f"<span>{part}</span>")
        else:
            breadcrumbs.append(part)

    return " · ".join(breadcrumbs)
