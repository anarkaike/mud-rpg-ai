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
    """Convert markdown content to a full HTML page with premium design."""
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
    """Wrap HTML body in a premium dark-themed page with glassmorphism."""
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — MUD-AI</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

        :root {{
            --bg-deep: #05070a;
            --bg-card: rgba(22, 27, 34, 0.7);
            --bg-glass: rgba(30, 41, 59, 0.4);
            --accent-glow: rgba(56, 189, 248, 0.15);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent: #38bdf8;
            --accent-gradient: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
            --green: #10b981;
            --border: rgba(51, 65, 85, 0.5);
            --radius-lg: 20px;
            --radius-md: 12px;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Outfit', sans-serif;
            background: var(--bg-deep);
            background-image: 
                radial-gradient(circle at 0% 0%, rgba(56, 189, 248, 0.08) 0, transparent 50%),
                radial-gradient(circle at 100% 100%, rgba(129, 140, 248, 0.08) 0, transparent 50%);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}

        .container {{
            width: 100%;
            max-width: 800px;
            margin: 2rem auto;
            padding: 2.5rem;
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }}

        .breadcrumb {{
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-bottom: 2rem;
            font-family: 'JetBrains Mono', monospace;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .breadcrumb span {{
            color: var(--accent);
            font-weight: 500;
        }}

        h1, h2, h3 {{
            font-weight: 700;
            letter-spacing: -0.02em;
        }}

        h1 {{
            font-size: 2.5rem;
            margin-bottom: 2rem;
            background: var(--accent-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            border-bottom: 2px solid var(--border);
            padding-bottom: 0.5rem;
        }}

        h2 {{
            font-size: 1.5rem;
            margin-top: 2.5rem;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}

        h2::before {{
            content: '';
            display: block;
            width: 4px;
            height: 1.2em;
            background: var(--accent-gradient);
            border-radius: 2px;
        }}

        p {{ margin: 1rem 0; color: var(--text-secondary); font-size: 1.05rem; }}

        a {{
            color: var(--accent);
            text-decoration: none;
            transition: all 0.2s;
            position: relative;
        }}

        a:hover {{
            color: #fff;
            text-shadow: 0 0 10px var(--accent-glow);
        }}

        blockquote {{
            margin: 2rem 0;
            padding: 1.5rem 2rem;
            background: var(--bg-glass);
            border-left: 4px solid var(--accent);
            border-radius: 0 var(--radius-md) var(--radius-md) 0;
            font-style: italic;
            font-size: 1.1rem;
            color: var(--text-primary);
        }}

        code {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9em;
            background: rgba(15, 23, 42, 0.6);
            padding: 0.2rem 0.5rem;
            border-radius: 6px;
            color: var(--accent);
            border: 1px solid var(--border);
        }}

        pre {{
            background: #0f172a;
            padding: 1.5rem;
            border-radius: var(--radius-md);
            overflow-x: auto;
            margin: 1.5rem 0;
            border: 1px solid var(--border);
        }}

        pre code {{
            background: transparent;
            border: none;
            padding: 0;
            color: #cbd5e1;
        }}

        ul, ol {{
            margin: 1.5rem 0;
            padding-left: 1.5rem;
            list-style: none;
        }}

        li {{
            margin: 0.75rem 0;
            color: var(--text-secondary);
            position: relative;
        }}

        li::before {{
            content: '→';
            position: absolute;
            left: -1.5rem;
            color: var(--accent);
            opacity: 0.6;
        }}

        hr {{
            border: none;
            border-top: 1px solid var(--border);
            margin: 3rem 0;
        }}

        .badge-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin: 1.5rem 0;
        }}

        .badge {{
            padding: 0.4rem 1rem;
            background: var(--bg-glass);
            border: 1px solid var(--border);
            border-radius: 30px;
            font-size: 0.85rem;
            font-weight: 500;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .footer {{
            margin-top: auto;
            padding: 3rem 0;
            text-align: center;
            color: var(--text-muted);
            font-size: 0.9rem;
        }}

        .footer a {{
            font-weight: 500;
            margin-top: 0.5rem;
            display: inline-block;
        }}

        @media (max-width: 640px) {{
            .container {{ margin: 1rem; padding: 1.5rem; }}
            h1 {{ font-size: 2rem; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="breadcrumb">
            {_path_to_breadcrumb(path)}
        </div>
        {body_html}
    </div>
    <div class="footer">
        <p>MUD-AI — Onde palavras tornam-se mundos.</p>
        <a href="https://mudai.servinder.com.br">mudai.servinder.com.br</a>
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
