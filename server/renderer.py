"""
MUD-AI — Markdown to HTML Renderer.

Converts artifact markdown content into beautiful dark-themed HTML pages.
Used by the /p/{path} public endpoint.
"""

import os
import html
import markdown
from typing import Optional


def render_markdown_to_html(
    content: str,
    title: str = "MUD-AI",
    path: str = "",
    full_page: bool = True,
    room_state: Optional[dict] = None,
    player_stats: Optional[dict] = None,
    player_state: Optional[dict] = None,
    players_here: Optional[list[dict]] = None,
) -> str:
    """Convert markdown content to HTML page or inner container content."""
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
    
    # If we have a room state (snapshot), prepend dynamic info to the markdown
    if room_state:
        # Check if it's the new snapshot format or the old artifact format
        if "state" in room_state and "image" in room_state:
            # Snapshot format
            meta = room_state.get("state", {})
            image = room_state.get("image")
        else:
            # Artifact format
            meta = room_state.get("metadata_parsed", {})
            image = meta.get("image") or room_state.get("image")

        dynamic_info = []
        evolving_summary = meta.get("evolving_summary")
        motifs = meta.get("motifs", [])
        
        if evolving_summary:
            dynamic_info.append(f"> ✨ **Resumo Vivo:** {evolving_summary}\n")
        
        if motifs:
            motifs_str = ", ".join(f"#{m}" for m in motifs[:5])
            dynamic_info.append(f"*{motifs_str}*\n")
            
        if dynamic_info:
            content = "\n".join(dynamic_info) + "\n---\n" + content

    html_body = md.convert(content)

    mission_panel_html = ""

    # If we have room state, handle images, gallery and echoes
    if room_state:
        # Check format again
        if "state" in room_state and "image" in room_state:
            meta = room_state.get("state", {})
            active_image = room_state.get("image")
        else:
            meta = room_state.get("metadata_parsed", {})
            active_image = meta.get("image") or room_state.get("image")
        
        # 1. Handle Active Room Image
        if active_image and active_image.get("status") == "ready" and active_image.get("url"):
            image_html = f"""
            <div class="room-image-container">
                <img src="{active_image['url']}" alt="Visual da Sala" class="room-visual">
                <div class="image-caption">👁️ Visão atual da sala</div>
            </div>
            """
            html_body = image_html + html_body

        # 2. Handle Room Gallery (other images)
        all_images = meta.get("all_images", []) # We'll need to pass this or fetch it
        ready_images = [img for img in all_images if img.get("status") == "ready" and img.get("url") != active_image.get("url")]
        if ready_images:
            gallery_html = '<div class="room-gallery"><h4>🖼️ Galeria de Memórias</h4><div class="gallery-grid">'
            for img in ready_images[:4]:
                gallery_html += f'<img src="{img["url"]}" class="gallery-thumb" onclick="window.open(this.src)">'
            gallery_html += '</div></div>'
            html_body += gallery_html

        # 3. Handle Recent Echoes
        recent_contributions = meta.get("recent_contributions", [])
        if recent_contributions:
            echoes_html = '<div class="room-echoes"><h3>🗣️ Ecos Recentes</h3><ul>'
            for contrib in recent_contributions[:5]:
                excerpt = contrib.get("excerpt", "")
                author = contrib.get("author_name", "Alguém")
                if excerpt:
                    echoes_html += f'<li><strong>{author}:</strong> <em>"{excerpt}"</em></li>'
            echoes_html += '</ul></div>'
            html_body += echoes_html

        # 4. Handle Missions
        missions = meta.get("missions", room_state.get("missions", []))
        if missions:
            room_progress = {}
            active_challenge = {}
            if player_state:
                current_room_path = player_state.get("current_room") or meta.get("room_path") or ""
                mission_progress = player_state.get("mission_progress", {})
                if isinstance(mission_progress, dict):
                    room_progress = mission_progress.get(current_room_path, {}) if current_room_path else {}
                active_challenge = player_state.get("active_challenge") or {}

            mission_cards = []
            for mission in missions[:4]:
                mission_id = mission.get("id", "")
                title_text = html.escape(mission.get("title", "Missão"))
                instruction = html.escape(mission.get("instruction", ""))
                reward = mission.get("reward_seeds", 0)
                completions = mission.get("times_completed", 0)
                progress_meta = room_progress.get(mission_id, {}) if isinstance(room_progress, dict) else {}
                is_completed = progress_meta.get("status") == "completed"
                is_active = active_challenge.get("mission_id") == mission_id
                status_label = "Concluída" if is_completed else "Ativa agora" if is_active else "Disponível"
                status_class = "completed" if is_completed else "active" if is_active else "available"
                mission_cards.append(f"""
                <div class="mission-card {status_class}">
                    <div class="mission-card-header">
                        <div class="mission-title">🎯 {title_text}</div>
                        <div class="mission-status {status_class}">{status_label}</div>
                    </div>
                    <div class="mission-instruction">{instruction}</div>
                    <div class="mission-meta">
                        <span>🪙 {reward} sementes</span>
                        <span>🏁 {completions} conclusões</span>
                    </div>
                </div>
                """)

            helper_html = ""
            if player_state:
                helper_html = '<div class="mission-helper">Dica: responda no terminal com uma frase autoral para avançar a missão ativa.</div>'

            mission_panel_html = f"""
            <div id="mission-panel" class="mission-panel">
                <div class="mission-panel-header">🎯 MISSÕES DA SALA</div>
                <div class="mission-panel-list">{''.join(mission_cards)}</div>
                {helper_html}
            </div>
            """

        # 5. Handle Game Log / System Messages
        game_log = meta.get("game_log", [])
        if game_log:
            log_entries_html = "".join([
                f'<div class="log-entry"><span class="log-time">{entry.get("time", "")}</span><span class="log-text">{entry.get("text", "")}</span></div>'
                for entry in game_log[:10]
            ])
            log_html = f"""
            <div class="game-log">
                <div class="log-header">📜 Crônicas da Sala</div>
                {log_entries_html}
            </div>
            """
            html_body += log_html

    # Try to extract title from frontmatter or first heading
    if hasattr(md, "Meta") and "title" in md.Meta:
        title = md.Meta["title"][0]

    if not full_page:
        # If we have player stats in a partial, send them OOB
        player_bar_oob = ""
        if player_stats:
            seeds = player_stats.get("seeds", 0)
            level = player_stats.get("level", 1)
            nickname = player_stats.get("nickname", "Viajante")
            
            # Add a script to trigger the animation if seeds changed
            seeds_script = f"""
            <script>
                (function() {{
                    const el = document.querySelector('#player-stats-bar .player-seeds');
                    if (el && el.innerText.indexOf('{seeds}') === -1) {{
                        el.classList.add('updated');
                        setTimeout(() => el.classList.remove('updated'), 1000);
                    }}
                }})();
            </script>
            """

            player_bar_oob = f"""
            <div id="player-stats-bar" hx-swap-oob="true" class="player-stats-bar">
                {seeds_script}
                <div class="player-info">
                    <span class="player-nickname">👤 {nickname}</span>
                    <span class="player-level">⭐ Nv.{level}</span>
                </div>
                <div class="player-resources">
                    <span class="player-seeds">🪙 {seeds} sementes</span>
                </div>
            </div>
            """
        
        # If we have players here in a partial, send them OOB
        players_sidebar_oob = ""
        if players_here is not None:
            players_html = "".join([
                f'<div class="presence-tag" title="Nv.{p["level"]}">{p["nickname"]}</div>'
                for p in players_here
            ])
            players_sidebar_oob = f"""
            <div id="presence-sidebar" hx-swap-oob="true" class="presence-sidebar">
                <div class="presence-header">👥 PRESENTES</div>
                <div class="presence-list">{players_html or '<div class="presence-empty">Apenas você aqui.</div>'}</div>
            </div>
            """

        mission_panel_oob = ""
        if mission_panel_html:
            mission_panel_oob = f"""
            <div id="mission-panel" hx-swap-oob="true" class="mission-panel">
                {mission_panel_html.split('>', 1)[1].rsplit('</div>', 1)[0]}
            </div>
            """
            
        return f"""
        {player_bar_oob}
        {players_sidebar_oob}
        {mission_panel_oob}
        <div class="breadcrumb">
            {_path_to_breadcrumb(path)}
        </div>
        {html_body}
        """

    return _wrap_in_template(html_body, title, path, player_stats=player_stats, players_here=players_here, mission_panel_html=mission_panel_html)


def _wrap_in_template(body_html: str, title: str, path: str, player_stats: Optional[dict] = None, players_here: Optional[list[dict]] = None, mission_panel_html: str = "") -> str:
    """Wrap HTML body in a premium dark-themed page with glassmorphism."""
    # Check if we have a session token (16-char path)
    session_token = path if len(path) == 16 else None
    
    # HTMX support and basic interaction layout
    htmx_script = '<script src="https://unpkg.com/htmx.org@1.9.10"></script>'
    
    player_bar_html = ""
    if session_token and player_stats:
        seeds = player_stats.get("seeds", 0)
        level = player_stats.get("level", 1)
        nickname = player_stats.get("nickname", "Viajante")
        
        # Add a script to trigger the animation if seeds changed
        seeds_script = f"""
        <script>
            (function() {{
                const el = document.querySelector('.player-seeds');
                if (el && el.innerText.indexOf('{seeds}') === -1) {{
                    el.classList.add('updated');
                    setTimeout(() => el.classList.remove('updated'), 1000);
                }}
            }})();
        </script>
        """

        player_bar_html = f"""
        <div id="player-stats-bar" class="player-stats-bar">
            {seeds_script}
            <div class="player-info">
                <span class="player-nickname">👤 {nickname}</span>
                <span class="player-level">⭐ Nv.{level}</span>
            </div>
            <div class="player-resources">
                <span class="player-seeds">🪙 {seeds} sementes</span>
            </div>
        </div>
        """

    presence_sidebar_html = ""
    if players_here is not None:
        players_html = "".join([
            f'<div class="presence-tag" title="Nv.{p["level"]}">{p["nickname"]}</div>'
            for p in players_here
        ])
        presence_sidebar_html = f"""
        <div id="presence-sidebar" class="presence-sidebar">
            <div class="presence-header">👥 PRESENTES</div>
            <div class="presence-list">{players_html or '<div class="presence-empty">Apenas você aqui.</div>'}</div>
        </div>
        """

    mission_sidebar_html = mission_panel_html

    terminal_html = ""
    polling_attrs = ""
    if session_token:
        polling_attrs = f'hx-get="/api/v1/game/web-sync/{session_token}" hx-trigger="every 3s" hx-swap="innerHTML transition:true"'
        terminal_html = f"""
        <div class="terminal-container">
            <div class="sync-indicator">
                <div class="sync-led"></div>
                SYNC
            </div>
            <form hx-post="/api/v1/game/web-action" 
                  hx-target=".container" 
                  hx-swap="innerHTML transition:true"
                  hx-on::after-request="this.reset()"
                  class="terminal-form">
                <input type="hidden" name="token" value="{session_token}">
                <input type="text" 
                       name="message" 
                       placeholder="Digite seu comando..." 
                       autocomplete="off"
                       autofocus
                       class="terminal-input">
                <button type="submit" class="terminal-button">ENVIAR</button>
            </form>
            <div class="terminal-shortcuts">
                <button hx-post="/api/v1/game/web-action" hx-vals='{{"token": "{session_token}", "message": "olhar"}}' hx-target=".container" hx-swap="innerHTML transition:true" class="shortcut-btn">👁️ Olhar</button>
                <button hx-post="/api/v1/game/web-action" hx-vals='{{"token": "{session_token}", "message": "perfil"}}' hx-target=".container" hx-swap="innerHTML transition:true" class="shortcut-btn">👤 Perfil</button>
                <button hx-post="/api/v1/game/web-action" hx-vals='{{"token": "{session_token}", "message": "salas"}}' hx-target=".container" hx-swap="innerHTML transition:true" class="shortcut-btn">🗺️ Salas</button>
                <button hx-post="/api/v1/game/web-action" hx-vals='{{"token": "{session_token}", "message": "ajuda"}}' hx-target=".container" hx-swap="innerHTML transition:true" class="shortcut-btn">❓ Ajuda</button>
            </div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — MUD-AI</title>
    {htmx_script}
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
            padding-bottom: 120px; /* Space for terminal */
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
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }}

        .container.htmx-swapping {{
            opacity: 0;
            transform: translateY(10px);
        }}

        .container.htmx-added {{
            opacity: 0;
            transform: translateY(-10px);
        }}

        .htmx-request .container {{
            opacity: 0.8;
            filter: grayscale(0.5);
        }}

        .terminal-container {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(20px);
            border-top: 1px solid var(--border);
            padding: 1rem 2rem;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0.75rem;
            z-index: 1000;
        }}

        /* Sync Indicator */
        .sync-indicator {{
            position: absolute;
            top: 0.5rem;
            right: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.65rem;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
        }}

        .sync-led {{
            width: 6px;
            height: 6px;
            background: var(--green);
            border-radius: 50%;
            box-shadow: 0 0 5px var(--green);
            opacity: 0.3;
            transition: opacity 0.2s;
        }}

        .htmx-request .sync-led {{
            opacity: 1;
            animation: pulse 1s infinite;
        }}

        @keyframes pulse {{
            0% {{ transform: scale(1); opacity: 1; }}
            50% {{ transform: scale(1.5); opacity: 0.5; }}
            100% {{ transform: scale(1); opacity: 1; }}
        }}

        .room-echoes {{
            margin-top: 3rem;
            padding: 1.5rem;
            background: rgba(15, 23, 42, 0.4);
            border-radius: var(--radius-md);
            border: 1px dashed var(--border);
        }}

        .room-echoes h3 {{
            font-size: 1rem;
            color: var(--text-muted);
            margin-bottom: 1rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .room-echoes ul {{
            padding-left: 0;
            margin: 0;
        }}

        .room-echoes li {{
            margin: 0.5rem 0;
            font-size: 0.95rem;
            color: var(--text-secondary);
        }}

        .room-echoes li::before {{
            content: none;
        }}

        .room-echoes li strong {{
            color: var(--accent);
            font-weight: 500;
        }}

        /* Player Stats Bar */
        .player-stats-bar {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: rgba(15, 23, 42, 0.8);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid var(--border);
            padding: 0.5rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 1001;
            font-family: 'Outfit', sans-serif;
            font-size: 0.85rem;
        }}

        .player-info {{
            display: flex;
            gap: 1.5rem;
        }}

        .player-nickname {{
            font-weight: 600;
            color: var(--text-primary);
        }}

        .player-level {{
            color: var(--accent);
            font-family: 'JetBrains Mono', monospace;
        }}

        .player-seeds {{
            color: var(--green);
            font-weight: 500;
            transition: all 0.5s;
        }}

        .player-seeds.updated {{
            color: #fff;
            text-shadow: 0 0 10px var(--green);
            transform: scale(1.2);
        }}

        /* Room Visuals */
        .room-image-container {{
            margin-bottom: 2rem;
            border-radius: var(--radius-md);
            overflow: hidden;
            border: 1px solid var(--border);
            position: relative;
        }}

        .room-visual {{
            width: 100%;
            height: auto;
            display: block;
            aspect-ratio: 16 / 9;
            object-fit: cover;
            filter: brightness(0.8) contrast(1.1);
            transition: filter 0.3s;
        }}

        /* Room Gallery */
        .room-gallery {{
            margin: 2rem 0;
            padding: 1.5rem;
            background: rgba(15, 23, 42, 0.3);
            border-radius: var(--radius-md);
            border: 1px solid var(--border);
        }}

        .room-gallery h4 {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-bottom: 1rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .gallery-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 1rem;
        }}

        .gallery-thumb {{
            width: 100%;
            aspect-ratio: 1;
            object-fit: cover;
            border-radius: 8px;
            cursor: pointer;
            border: 1px solid var(--border);
            transition: all 0.2s;
            filter: grayscale(0.5) brightness(0.7);
        }}

        .gallery-thumb:hover {{
            filter: grayscale(0) brightness(1);
            transform: scale(1.05);
            border-color: var(--accent);
            box-shadow: 0 0 15px var(--accent-glow);
        }}

        /* Presence Sidebar */
        .presence-sidebar {{
            position: fixed;
            top: 100px;
            right: 2rem;
            width: 180px;
            background: var(--bg-card);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 1rem;
            z-index: 100;
        }}

        .presence-header {{
            font-size: 0.7rem;
            font-weight: 700;
            color: var(--text-muted);
            letter-spacing: 0.1em;
            margin-bottom: 0.75rem;
            border-bottom: 1px solid var(--border);
            padding-bottom: 0.5rem;
        }}

        .presence-list {{
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}

        .presence-tag {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .presence-tag::before {{
            content: '';
            width: 6px;
            height: 6px;
            background: var(--green);
            border-radius: 50%;
            box-shadow: 0 0 5px var(--green);
        }}

        .presence-empty {{
            font-size: 0.75rem;
            color: var(--text-muted);
            font-style: italic;
        }}

        .mission-panel {{
            margin: 2rem 0;
            padding: 1.25rem;
            background: rgba(15, 23, 42, 0.35);
            border-radius: var(--radius-md);
            border: 1px solid var(--border);
        }}

        .mission-panel-header {{
            font-size: 0.75rem;
            font-weight: 700;
            color: var(--text-muted);
            letter-spacing: 0.1em;
            margin-bottom: 1rem;
        }}

        .mission-panel-list {{
            display: flex;
            flex-direction: column;
            gap: 0.85rem;
        }}

        .mission-card {{
            padding: 1rem;
            border-radius: 10px;
            border: 1px solid var(--border);
            background: rgba(2, 6, 23, 0.45);
        }}

        .mission-card.active {{
            border-color: var(--accent);
            box-shadow: 0 0 0 1px var(--accent-glow);
        }}

        .mission-card.completed {{
            border-color: rgba(16, 185, 129, 0.45);
            background: rgba(16, 185, 129, 0.08);
        }}

        .mission-card-header {{
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 0.5rem;
            align-items: center;
        }}

        .mission-title {{
            font-weight: 600;
            color: var(--text-primary);
        }}

        .mission-status {{
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            padding: 0.2rem 0.5rem;
            border-radius: 999px;
            border: 1px solid var(--border);
            color: var(--text-muted);
            white-space: nowrap;
        }}

        .mission-status.active {{
            color: var(--accent);
            border-color: rgba(56, 189, 248, 0.35);
        }}

        .mission-status.completed {{
            color: var(--green);
            border-color: rgba(16, 185, 129, 0.35);
        }}

        .mission-instruction {{
            color: var(--text-secondary);
            font-size: 0.95rem;
        }}

        .mission-meta {{
            margin-top: 0.75rem;
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            font-size: 0.8rem;
            color: var(--text-muted);
        }}

        .mission-helper {{
            margin-top: 1rem;
            color: var(--text-muted);
            font-size: 0.85rem;
        }}

        /* Game Log / Notifications */
        .game-log {{
            margin: 2rem 0;
            padding: 1.25rem;
            background: rgba(15, 23, 42, 0.3);
            border-radius: var(--radius-md);
            border: 1px solid var(--border);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            max-height: 250px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}

        .log-header {{
            font-size: 0.65rem;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-bottom: 0.5rem;
            border-bottom: 1px solid var(--border);
            padding-bottom: 0.25rem;
        }}

        .log-entry {{
            padding: 0.25rem 0.5rem;
            border-left: 2px solid var(--border);
            transition: all 0.3s;
            cursor: pointer;
        }}

        .log-entry.new {{
            background: var(--accent-glow);
            border-left-color: var(--accent);
            animation: slideIn 0.3s ease-out;
        }}

        .log-entry.reward {{
            background: rgba(16, 185, 129, 0.1);
            border-left-color: var(--green);
        }}

        @keyframes slideIn {{
            from {{ transform: translateX(-10px); opacity: 0; }}
            to {{ transform: translateX(0); opacity: 1; }}
        }}

        .log-time {{ color: var(--text-muted); font-size: 0.75rem; margin-right: 0.5rem; }}
        .log-text {{ color: var(--text-secondary); }}
        .log-accent {{ color: var(--accent); font-weight: 500; }}
        .log-entry:hover {{
            background: rgba(56, 189, 248, 0.1);
            border-left-color: var(--accent);
            transform: translateX(5px);
        }}

        .game-log::-webkit-scrollbar {{
            width: 4px;
        }}

        .game-log::-webkit-scrollbar-track {{
            background: transparent;
        }}

        .game-log::-webkit-scrollbar-thumb {{
            background: var(--border);
            border-radius: 10px;
        }}

        /* Visual polish for images and gallery */
        .gallery-thumb {{
            filter: brightness(1);
        }}

        .image-caption {{
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            padding: 0.75rem 1rem;
            background: linear-gradient(to top, rgba(0,0,0,0.8), transparent);
            font-size: 0.75rem;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
            text-transform: uppercase;
        }}

        .terminal-form {{
            width: 100%;
            max-width: 800px;
            display: flex;
            gap: 1rem;
        }}

        .terminal-input {{
            flex: 1;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 0.75rem 1.25rem;
            color: var(--text-primary);
            font-family: 'JetBrains Mono', monospace;
            font-size: 1rem;
            outline: none;
            transition: border-color 0.2s;
        }}

        .terminal-input:focus {{
            border-color: var(--accent);
        }}

        .terminal-button {{
            background: var(--accent-gradient);
            border: none;
            border-radius: var(--radius-md);
            padding: 0 1.5rem;
            color: white;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.1s, opacity 0.2s;
        }}

        .terminal-button:active {{ transform: scale(0.95); }}
        .terminal-button:hover {{ opacity: 0.9; }}

        .terminal-shortcuts {{
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            justify-content: center;
        }}

        .shortcut-btn {{
            background: var(--bg-glass);
            border: 1px solid var(--border);
            border-radius: 30px;
            padding: 0.25rem 0.75rem;
            font-size: 0.8rem;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.2s;
        }}

        .shortcut-btn:hover {{
            background: var(--accent-glow);
            border-color: var(--accent);
            color: var(--text-primary);
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
            box-shadow: 0 10px 30px -10px var(--accent-glow);
        }}

        /* Special style for Evolving Summary in blockquotes */
        blockquote strong {{
            color: var(--accent);
            font-weight: 600;
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
    {player_bar_html}
    {presence_sidebar_html}
    <div class="container" {polling_attrs}>
        <div class="breadcrumb">
            {_path_to_breadcrumb(path)}
        </div>
        {mission_sidebar_html}
        {body_html}
    </div>
    {terminal_html}
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
