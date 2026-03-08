# 🎮 MUD-AI

<p align="center">
  <b>🏠 Início</b> | <a href="./ARCHITECTURE_ENGINE.md">Arquitetura & Engine</a> | <a href="./GAMEPLAY_CURRENT.md">Gameplay Atual</a> | <a href="./desktop/01_VISAO_E_CONCEITO.md">Ideaçaõ Original ▶</a>
</p>

> **RPG textual multiplayer mediado por IA, jogado via WhatsApp, com interface web minimalista baseada em Glassmorphism.**

---

## 📂 Estrutura de Documentação (v2 Atualizada)

- [README.md](./README.md) ← Visão Geral (Você está aqui)
- [ARCHITECTURE_ENGINE.md](./ARCHITECTURE_ENGINE.md) ← Documentação técnica do Backend em FastAPI + AI
- [GAMEPLAY_CURRENT.md](./GAMEPLAY_CURRENT.md) ← Economia, Loop Central, Sementes (🪙) e Progressão
- **Histórico & Ideação (Março 2026):**
  - [PRD_ANALISE.md](./PRD_ANALISE.md) | [PESQUISA_MUDS.md](./PESQUISA_MUDS.md)
  - **desktop/** ← Documentos originais de brainstorming, visão e pitch. *(Mantidos para contexto)*

## 🎯 O que é o MUD-AI Hoje?

O projeto evoluiu de uma ideia mediada puramente por fluxos no n8n para um **Motor Próprio (Custom Game Engine)** construído em **FastAPI (Python)**. 

Ele transforma uma conversa pelo WhatsApp em um **MUD (Multi-User Dungeon) Moderno**, focado no poder da linguagem e das narrativas.

Na implementação atual, o produto já combina:
- engine própria em FastAPI
- persistência por artifacts em SQLite
- onboarding conversacional
- salas com estado derivado de mundo vivo
- blocos narrativos estruturados
- memória curta anti-repetição
- base para pool de imagens por sala

### Principais Pilares da Implementação:
1. **Engine FastAPI Super-Rápida:** Todo o processamento mental ocorre no app Python hospedado via Docker (Coolify). O n8n / Chatwoot atua apenas como gateway que passa e recebe mensagens limpas de Webhook.
2. **Sistema VFS Baseado em Artifacts:** Sem tabelas tradicionais relacional-engessadas. Tudo é um artefato persistido e cacheado que pode ser modificado com extrema liberdade `(mudai.users.*, mudai.places.*)`.
3. **Onboarding Guiado e Imersivo por IA:** Ao entrar, uma inteligência artificial cria perguntas de onboarding vastamente criativas (sobre nomes, traços e essência) para evitar repetição massante, premiando dicas personalizadas instantaneamente via JSON (OpenAI flash fallback into Gemini).
4. **Economia Textual de Sementes (🪙):** Uma moeda in-game controlada nos artefatos. Interações longas podem consumir; ser validador de interações engajadoras e trazer novos usuários bonifica e preenche seu personagem.
5. **Perfis Públicos na Web:** Para combater a limitação das caixas apertadas do WhatsApp, links de perfil são criados por hashes (`/p/{token}`), permitindo aos usuários e estranhos visualizarem murais/tags lindamente estilizados em CSS puro.
6. **Camada de Mundo Vivo:** Salas podem manter `evolving_summary`, `visual_summary`, `motifs`, ecos recentes e preparação de assets visuais a partir das contribuições dos jogadores.
7. **n8n como Relay Deliberadamente Fino:** O workflow ativo apenas recebe o webhook do Chatwoot, chama `/api/v1/game/action` e devolve a resposta, deixando a inteligência e a evolução de estado no backend.

## 🌐 Interface Web & Landing

O backend FastAPI também serve uma **interface web navegável**, pensada para complementar o WhatsApp:

- `/` → Landing pública com:
  - resumo do jogo,
  - métricas em tempo quase real (jogadores, salas, artefatos de mundo),
  - CTAs para jogar via WhatsApp e Web.
- `/p` → Índice explorável de salas e jogadores (`mudai.places.*`, `mudai.users.*`).
- `/p/{path}` → Renderização HTML de qualquer artefato (incluindo snapshots de salas com resumo vivo, motivos, ecos e imagens).
- `/p/{token}` → Dashboard pessoal do jogador, com:
  - HUD de nickname, nível e sementes,
  - terminal HTMX para enviar comandos,
  - lista de jogadores presentes na mesma sala,
  - log de eventos recentes daquela sala.

### Login Web

Existem três formas principais de chegar ao dashboard web:

- **Link direto pelo WhatsApp:**  
  o game engine gera URLs do tipo `MUDAI_BASE_URL/p/{token}`, onde o `token` é um hash derivado do telefone. Esses links aparecem automaticamente nas respostas chave (sala, perfil, etc).

- **Token colado na Landing:**  
  na home (`/`), o usuário pode colar apenas o token de 16 caracteres que recebeu pelo WhatsApp; o backend redireciona para `/p/{token}`.

- **Telefone + Código:**  
  para quem já conversa com o MUD-AI pelo WhatsApp:
  - `POST /auth/request-code` registra um código temporário em `mudai.login_codes.{phone}`;
  - um fluxo externo (n8n/Chatwoot) pode enviar esse código ao jogador;
  - `POST /auth/verify-code` valida telefone + código e redireciona para o dashboard `/p/{token}` correspondente.

---

> **Lançamento Original:** Focado em conexões profundas, menos fricção visual e mais essência através do texto. Inicia com um público aberto no WhatsApp.

## 📖 Fluxo Básico de Uso (Devs)

Se deseja entender a fundo como cada sistema interage via código, comece por:
- 🛠️ [Como Funciona o Banco/Engine?](./ARCHITECTURE_ENGINE.md)
- 🎲 [Qual a Teoria da Economia In-Game Hoje?](./GAMEPLAY_CURRENT.md) 

<p align="center">
  *MUD-AI — Onde palavras tornam-se mundos. (Arquitetura Atualizada)*
</p>
