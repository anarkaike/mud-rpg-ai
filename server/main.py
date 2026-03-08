"""
MUD-AI — FastAPI Server Entry Point.

A lightweight artifact server with path-based key-value storage.
Everything is stored as markdown and accessible via dot-notation paths.

    mudai.users.junio           → player profile
    mudai.places.start          → starting room
    mudai.templates.player      → player template

Start with: python -m uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
"""

import os
from dotenv import load_dotenv

# Load environment variables before anything else
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .auth import BearerAuthMiddleware
from .routers import artifacts, search, pages


app = FastAPI(
    title="MUD-AI Artifact Server",
    description="Key-value artifact store with path-based access for the MUD-AI game.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow everything in dev, restrict in prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware
app.add_middleware(BearerAuthMiddleware)

# Mount routers
app.include_router(artifacts.router)
app.include_router(search.router)
app.include_router(pages.router)


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    init_db()
    print("🌱 MUD-AI server started")
    print(f"📂 Database: {os.environ.get('MUDAI_DB_PATH', 'server/data/mudai.db')}")
    print(f"📄 API docs: http://0.0.0.0:8000/docs")
    print(f"🌐 Public pages: http://0.0.0.0:8000/p/")


@app.get("/health", tags=["system"])
async def health():
    """Health check — no auth required."""
    from .database import count_artifacts
    return {
        "status": "ok",
        "service": "mudai-artifact-server",
        "version": "0.1.0",
        "artifacts": count_artifacts(),
    }


@app.post("/api/v1/seed", tags=["system"])
async def seed_data():
    """Load initial templates and seed data into the database."""
    from .database import put_artifact, count_artifacts

    seeds = [
        {
            "path": "mudai.templates.player",
            "content": """---
type: player
seeds: 10
level: 1
---
# {nickname}

> {avatar_textual}

## Traços
{tracos}

## Habilidades que Ofereço
{habilidades_ofereco}

## Habilidades que Busco
{habilidades_busco}

---

*Jogador desde {data_criacao}*
""",
            "is_template": True,
            "metadata": {"description": "Template base para perfil de jogador"},
        },
        {
            "path": "mudai.templates.place",
            "content": """---
type: place
theme: neutral
max_players: 20
---
# {nome}

> {descricao}

## Atmosfera
{atmosfera}

## Saídas
{saidas}

## Fragmentos
_Nenhum fragmento ainda. Seja o primeiro a contribuir._

---

*Criado por {criador} em {data_criacao}*
""",
            "is_template": True,
            "metadata": {"description": "Template base para sala/local"},
        },
        {
            "path": "mudai.templates.place.start",
            "content": """---
type: place
theme: acolhimento
is_start: true
max_players: 100
---
# 🌱 Recepção

> Um espaço aberto, iluminado suavemente. O chão é de terra macia. No centro, uma árvore jovem com raízes visíveis. Ao redor, caminhos se abrem em várias direções, cada um com uma placa discreta.

## Atmosfera
O ar é fresco. Você ouve murmúrios distantes — conversas, risadas, perguntas. Uma voz gentil diz: "Bem-vindo. Aqui, o que importa é o que você traz por dentro."

## Saídas
- **norte** → Praça das Trocas _(onde habilidades se encontram)_
- **leste** → Rua da Consolação _(bairro urbano)_
- **oeste** → Ateliê Aberto _(espaço criativo)_
- **sul** → Jardim dos Ecos _(lugar de reflexão)_

## Fragmentos
- _"Cheguei sem saber o que esperar. Saí sabendo o que perguntar."_ — anônimo
- _"Numa sala de texto, ninguém julga sua aparência."_ — eco

---

*Sala inicial padrão — pode ser customizada por comunidade/número*
""",
            "is_template": True,
            "metadata": {"description": "Template da sala inicial padrão", "is_start": True},
        },
        {
            "path": "mudai.templates.challenge",
            "content": """---
type: challenge
difficulty: easy
reward_seeds: 1
---
# {nome_desafio}

## Tipo
{tipo}: perspectiva | sentimento | história | pergunta | livre | troca

## Pergunta / Instrução
{instrucao}

## Recompensa
🌱 {reward_seeds} sementes

---

*Desafio criado por {criador}*
""",
            "is_template": True,
            "metadata": {"description": "Template para desafio de entrada"},
        },
        {
            "path": "mudai.templates.mission",
            "content": """---
type: mission
difficulty: medium
reward_seeds: 3
status: active
---
# {nome_missao}

## Objetivo
{descricao}

## Passos
1. {passo_1}
2. {passo_2}
3. {passo_3}

## Recompensa
🌱 {reward_seeds} sementes

## Local
{sala_path}

---

*Missão criada por {criador}*
""",
            "is_template": True,
            "metadata": {"description": "Template para missão"},
        },
        # Seed data — an actual starting room instance
        {
            "path": "mudai.places.start",
            "content": """---
type: place
theme: acolhimento
is_start: true
community: default
---
# 🌱 Recepção

> Um espaço aberto, iluminado suavemente. O chão é de terra macia. No centro, uma árvore jovem com raízes visíveis. Ao redor, caminhos se abrem em várias direções, cada um com uma placa discreta.

## Atmosfera
O ar é fresco. Você ouve murmúrios distantes — conversas, risadas, perguntas. Uma voz gentil diz: "Bem-vindo. Aqui, o que importa é o que você traz por dentro."

## Saídas
- **norte** → Praça das Trocas
- **leste** → Rua da Consolação
- **oeste** → Ateliê Aberto
- **sul** → Jardim dos Ecos

## Fragmentos
_Seja o primeiro a deixar sua marca aqui._

---

*Sala inicial — comunidade padrão*
""",
            "is_template": False,
            "metadata": {"is_start": True, "community": "default"},
        },
        # System config
        {
            "path": "mudai.config.welcome",
            "content": """# Bem-vindo ao MUD-AI 🌱

Você acaba de entrar num mundo feito de palavras, histórias e conexões.

Aqui, o que importa é a sua essência — não a aparência.

**Comandos básicos:**
- Diga *"olhar"* para ver onde você está
- Diga *"norte"*, *"sul"*, *"leste"* ou *"oeste"* para se mover
- Diga *"perfil"* para ver seu personagem
- Diga *"ajuda"* para mais opções

> Cada interação é uma semente. O que você planta?
""",
            "is_template": False,
            "metadata": {"type": "system", "description": "Mensagem de boas-vindas"},
        },
    ]

    created = 0
    for seed in seeds:
        put_artifact(
            path=seed["path"],
            content=seed["content"],
            is_template=seed.get("is_template", False),
            metadata=seed.get("metadata"),
        )
        created += 1

    return {
        "seeded": created,
        "total_artifacts": count_artifacts(),
        "templates": [s["path"] for s in seeds if s.get("is_template")],
    }
