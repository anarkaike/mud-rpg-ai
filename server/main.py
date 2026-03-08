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
from .routers import artifacts, search, pages, game


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
app.include_router(game.router)


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
        # ─── Themed Rooms ─────────────────────────────────────
        {
            "path": "mudai.places.versos",
            "content": """---
type: place
theme: criatividade
---
# 📝 Cantinho dos Versos

> Um espaço silencioso com paredes cobertas de palavras. Folhas soltas flutuam no ar, cada uma carregando um verso diferente.

## Atmosfera
O som suave de uma caneta deslizando sobre papel preenche o ambiente. Aqui, cada palavra tem peso e beleza.

## Saídas
- **sul** → Recepção
- **leste** → Fogueira dos Contos

## Fragmentos
_Aguardando o primeiro verso..._

---

*Sala de poesias e poemas*
""",
            "is_template": False,
            "metadata": {"tags": ["poesia", "escrita", "arte"], "emoji": "📝", "purpose": "Ler e escrever poesias e poemas", "unlock_level": 1, "system_prompt": "Nesta sala, incentive o jogador a escrever poesias, ler versos, e decorar a sala com poemas. Sugira que use 'decorar' seguido de um verso. Fale sobre ritmo, rima e emoção de forma leve."},
        },
        {
            "path": "mudai.places.fogueira",
            "content": """---
type: place
theme: colaboração
---
# 🔥 Fogueira dos Contos

> Uma fogueira crepita no centro de um círculo de pedras. As sombras dançam nas paredes, projetando histórias que mudam de forma.

## Atmosfera
Calor suave e cheiro de lenha. Cada pessoa que senta ao redor adiciona um capítulo à história que nunca termina.

## Saídas
- **oeste** → Cantinho dos Versos
- **sul** → Recepção

## Fragmentos
_A fogueira espera a primeira história..._

---

*Sala de histórias colaborativas*
""",
            "is_template": False,
            "metadata": {"tags": ["escrita", "colaboração", "fantasia"], "emoji": "🔥", "purpose": "Criar histórias colaborativas", "unlock_level": 1, "system_prompt": "Nesta sala, incentive o jogador a contribuir com trechos de histórias. Cada fragmento pode ser o próximo capítulo. Sugira ideias de enredo e peça que use 'decorar' para adicionar partes à história."},
        },
        {
            "path": "mudai.places.jardim",
            "content": """---
type: place
theme: reflexão
---
# 🌿 Jardim dos Ecos

> Um jardim onde as plantas sussurram. Cada flor guarda uma reflexão de alguém que passou. A fonte no centro reflete não o rosto, mas a essência.

## Atmosfera
Paz profunda. O vento carrega fragments de pensamentos. Aqui, o silêncio fala mais alto.

## Saídas
- **norte** → Recepção
- **leste** → Espelho d\'Água

## Fragmentos
_O jardim aguarda suas reflexões..._

---

*Lugar de reflexão e autoconhecimento*
""",
            "is_template": False,
            "metadata": {"tags": ["reflexão", "consciência", "meditação"], "emoji": "🌿", "purpose": "Reflexão e autoconhecimento", "unlock_level": 1, "system_prompt": "Nesta sala, faça perguntas reflexivas ao jogador. Sugira que compartilhe pensamentos e reflexões. Mantenha um tom calmo e acolhedor, sem ser excessivamente filosófico."},
        },
        {
            "path": "mudai.places.espelho",
            "content": """---
type: place
theme: vulnerabilidade
---
# 💧 Espelho d'Água

> Uma piscina de água cristalina num ambiente protegido. A superfície reflete emoções, não imagens. As paredes absorvem segredos e guardam gentilmente.

## Atmosfera
Uma calma profunda. O som da água gotejando é o único ruído. Aqui é seguro sentir.

## Saídas
- **oeste** → Jardim dos Ecos
- **norte** → Praça das Trocas

## Fragmentos
_As águas esperam seus sentimentos..._

---

*Espaço de escuta e vulnerabilidade*
""",
            "is_template": False,
            "metadata": {"tags": ["sentimento", "acolhimento", "escuta"], "emoji": "💧", "purpose": "Sentimentos e vulnerabilidade", "unlock_level": 1, "system_prompt": "Nesta sala, ofereça escuta ativa. Se o jogador compartilhar algo pessoal, valide seus sentimentos de forma gentil. Sugira que deixe um fragmento anônimo se quiser."},
        },
        {
            "path": "mudai.places.trocas",
            "content": """---
type: place
theme: network
---
# 🏛 Praça das Trocas

> Uma praça aberta e movimentada. Bancas coloridas exibem habilidades, ideias e talentos. Pessoas conversam animadamente, trocando o que sabem pelo que querem aprender.

## Atmosfera
Energia vibrante. Vozes se cruzam em conversas empolgadas. O ar cheira a possibilidade.

## Saídas
- **sul** → Recepção
- **leste** → Bancada do Empreendedor
- **oeste** → Espelho d\'Água

## Fragmentos
_A praça espera sua oferta..._

---

*Onde habilidades se encontram*
""",
            "is_template": False,
            "metadata": {"tags": ["networking", "troca", "habilidade"], "emoji": "🏛", "purpose": "Trocar habilidades e ideias", "unlock_level": 1, "system_prompt": "Nesta sala, ajude o jogador a formular o que sabe e o que quer aprender. Incentive trocas e conexões. Pergunte sobre habilidades e interesses."},
        },
        {
            "path": "mudai.places.empreendedor",
            "content": """---
type: place
theme: inovação
---
# 💡 Bancada do Empreendedor

> Uma oficina iluminada por lâmpadas de Edison. Quadros brancos cobrem as paredes, cheios de ideias, setas e sonhos mapeados. Protótipos de papel se espalham pelas mesas.

## Atmosfera
Criatividade elétrica. O som de ideias nascendo. Cada conversa pode virar um projeto.

## Saídas
- **oeste** → Praça das Trocas
- **sul** → Recepção

## Fragmentos
_A bancada espera sua ideia..._

---

*Inspiração e ideias de negócio*
""",
            "is_template": False,
            "metadata": {"tags": ["empreendedorismo", "negócios", "inovação"], "emoji": "💡", "purpose": "Inspiração empreendedora e ideias", "unlock_level": 1, "system_prompt": "Nesta sala, ajude o jogador com brainstorming de ideias de negócio. Faça perguntas sobre o problema que quer resolver. Dê dicas práticas e objetivas."},
        },
        {
            "path": "mudai.places.verdade",
            "content": """---
type: place
theme: jogo
---
# 🎲 Mesa da Verdade

> Uma mesa redonda de madeira escura num salão misterioso. Velas iluminam os rostos dos jogadores. No centro, um dado antigo espera ser lançado.

## Atmosfera
Tensão divertida. Risos nervosos. Cada rodada revela algo novo sobre quem joga.

## Saídas
- **oeste** → Recepção
- **norte** → Arena de Dilemas

## Fragmentos
_A mesa espera seus segredos..._

---

*Jogos de verdade e perguntas por turnos*
""",
            "is_template": False,
            "metadata": {"tags": ["jogo", "verdade", "social"], "emoji": "🎲", "purpose": "Jogos de verdade e perguntas", "unlock_level": 1, "system_prompt": "Nesta sala, proponha jogos de verdade ou consequência por texto. Faça perguntas divertidas e desafiadoras. Mantenha um tom leve e animado."},
        },
        {
            "path": "mudai.places.dilemas",
            "content": """---
type: place
theme: debate
---
# ⚖️ Arena de Dilemas

> Um anfiteatro circular onde as palavras ecoam. Dois púlpitos se enfrentam. O chão é um mosaico de perspectivas diferentes que, juntas, formam algo belo.

## Atmosfera
Respeito e curiosidade. Cada opinião é ouvida. Aqui não se vence — se expande.

## Saídas
- **sul** → Mesa da Verdade
- **oeste** → Praça das Trocas

## Fragmentos
_A arena espera sua perspectiva..._

---

*Dilemas morais e debates respeitosos*
""",
            "is_template": False,
            "metadata": {"tags": ["debate", "filosofia", "perspectiva"], "emoji": "⚖️", "purpose": "Dilemas morais e debates", "unlock_level": 2, "system_prompt": "Nesta sala, proponha dilemas morais e perguntas filosóficas. Apresente dois lados do argumento. Peça a opinião do jogador e explore diferentes perspectivas."},
        },
        {
            "path": "mudai.places.atlas",
            "content": """---
type: place
theme: descoberta
---
# 🗺 Atlas dos Lugares Mágicos

> Uma sala repleta de mapas antigos, globos giratórios e fotografias textuais de lugares que parecem impossíveis. Cada parede é uma janela para outro canto do mundo.

## Atmosfera
Wanderlust. O cheiro de terra molhada se mistura com ar de montanha. Cada descrição te transporta.

## Saídas
- **sul** → Recepção
- **leste** → Fogueira dos Contos

## Fragmentos
_O atlas espera seus lugares..._

---

*Compartilhe e descubra lugares incríveis*
""",
            "is_template": False,
            "metadata": {"tags": ["viagem", "aventura", "descoberta"], "emoji": "🗺", "purpose": "Lugares mágicos e intrigantes", "unlock_level": 1, "system_prompt": "Nesta sala, ajude o jogador a descrever e compartilhar lugares incríveis que conheceu ou gostaria de conhecer. Peça detalhes sensoriais."},
        },
        {
            "path": "mudai.places.maes",
            "content": """---
type: place
theme: apoio
---
# 🤱 Roda das Mães

> Um círculo aconchegante com almofadas macias e chá sempre quente. Brinquedos coloridos ocupam um canto, e as paredes são cobertas de desenhos feitos por pequenas mãos.

## Atmosfera
Acolhimento puro. O som de risadas infantis ao fundo. Sem julgamento, só apoio.

## Saídas
- **oeste** → Recepção

## Fragmentos
_A roda espera sua experiência..._

---

*Experiências de maternidade e apoio mútuo*
""",
            "is_template": False,
            "metadata": {"tags": ["maternidade", "família", "apoio"], "emoji": "🤱", "purpose": "Experiências de maternidade", "unlock_level": 1, "system_prompt": "Nesta sala, ofereça apoio e escuta sobre maternidade. Seja acolhedor e evite julgamentos. Incentive troca de experiências."},
        },
        {
            "path": "mudai.places.biblioteca",
            "content": """---
type: place
theme: livre
---
# 📚 Biblioteca do Infinito

> Estantes que se estendem até onde a vista alcança. Mas os livros aqui são escritos por quem entra. Cada conversa vira uma página.

## Atmosfera
Silêncio confortável. O cheiro de páginas antigas. Aqui, qualquer assunto é bem-vindo.

## Saídas
- **norte** → Recepção
- **leste** → Cantinho dos Versos

## Fragmentos
_A biblioteca espera sua página..._

---

*Sala livre — qualquer assunto, qualquer conversa*
""",
            "is_template": False,
            "metadata": {"tags": ["livre", "geral", "tudo"], "emoji": "📚", "purpose": "Conversa livre sobre qualquer tema", "unlock_level": 1, "system_prompt": "Nesta sala, converse sobre qualquer assunto que o jogador quiser. Seja versátil e interessado."},
        },
        {
            "path": "mudai.places.expansao",
            "content": """---
type: place
theme: consciência
---
# 🌀 Portal da Expansão

> Uma câmara circular cujas paredes pulsam com padrões fractais. A iluminação é suave e cíclica. O espaço parece maior por dentro do que por fora.

## Atmosfera
Percepção alterada. O tempo se dilata. As fronteiras entre o interno e o externo se dissolvem.

## Saídas
- **norte** → Jardim dos Ecos
- **oeste** → Espelho d\'Água

## Fragmentos
_O portal espera sua expansão..._

---

*Experiências de expansão de consciência*
""",
            "is_template": False,
            "metadata": {"tags": ["consciência", "expansão", "adulto"], "emoji": "🌀", "purpose": "Experiências de consciência expandida", "unlock_level": 2, "system_prompt": "Nesta sala, converse sobre experiências de expansão de consciência com respeito e curiosidade. Incentive relatos e reflexões sem julgamento."},
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
