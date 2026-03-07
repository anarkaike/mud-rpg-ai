# 🔍 Pesquisa — MUDs, Engines e Projetos Relacionados

<div align="center">
  [◀ PRD Análise](./PRD_ANALISE.md) | [🏠 Início](./README.md) | [Visão e Conceito ▶](./desktop/01_VISAO_E_CONCEITO.md)
</div>

> Comparação de engines, jogos e projetos modernos do ecossistema MUD para fundamentar decisões de design.

---

## 1. Engines MUD Open Source

### Evennia (Python) ⭐ Mais relevante

| Aspecto | Detalhes |
|---------|---------|
| **Linguagem** | Python 3.10-3.12 |
| **Stack** | Django (DB) + Twisted (networking) |
| **Versão atual** | 6.0.0 (Fev 2026) |
| **Conectividade** | Telnet, SSH, WebSocket, HTML5 web client |
| **Integrações** | Discord, IRC |
| **DB** | SQLite3, PostgreSQL, MySQL |
| **Destaques** | Altamente customizável, `contribs/` com módulos prontos, desenvolvimento in-game, comunidade ativa |
| **Relevância p/ nós** | 🟡 Bom para MUD clássico, mas muito pesado para nosso caso (WhatsApp + IA) |

### MuOxi (Rust)

| Aspecto | Detalhes |
|---------|---------|
| **Linguagem** | Rust + Python (game logic) |
| **Foco** | Performance e segurança |
| **Status** | Em desenvolvimento inicial |
| **Relevância p/ nós** | 🔴 Pouco maduro, foco diferente |

### DikuMUD (C/C++)

| Aspecto | Detalhes |
|---------|---------|
| **Linguagem** | C/C++ (clássico) |
| **Licença** | LGPL (re-release) |
| **Futuro** | Diku3 explorando WebSockets + HTML |
| **Relevância p/ nós** | 🔴 Legado, não se encaixa na arquitetura |

### MUD by Lattice (On-chain)

| Aspecto | Detalhes |
|---------|---------|
| **Foco** | "Autonomous worlds" na blockchain (Ethereum) |
| **Stack** | React, Three.js |
| **Relevância p/ nós** | 🟡 Conceito de "mundos autônomos" interessante, mas blockchain é overcomplication |

---

## 2. MUDs Clássicos — Benchmark de Features

| MUD | Tema | Destaque | Feature Inspiradora |
|-----|------|----------|-------------------|
| **Aardwolf** | Fantasia | 60+ áreas, acessibilidade | Sistema de áreas extenso |
| **GemStone IV** | Fantasia | Um dos mais antigos, skill-based | Progressão por habilidades (não por nível) |
| **Discworld** | Humor/Fantasia | Baseado em Terry Pratchett | Narrativa com humor e personalidade |
| **Alter Aeon** | Fantasia | Multi-class, sistema de doação | **Doação de XP** entre jogadores 🔥 |
| **Astaria** | Fantasia | Player-driven content | **Jogadores constroem cidades** 🔥 |
| **Threshold RPG** | Fantasia | Deep roleplay | Política e alianças entre jogadores |
| **DragonRealms** | Medieval | Skill-based | Progressão orgânica |
| **Legends of the Jedi** | Star Wars | Roleplay forte | Acessibilidade (screen readers) |

### 🔥 Features que mais nos inspiram:

1. **Alter Aeon — Doação de XP**: Jogadores ajudam outros a progredir → nosso "[Banco de Trocas](./desktop/01_VISAO_E_CONCEITO.md)"
2. **Astaria — Construção por jogadores**: Mundo player-driven → nosso "[Minecraft narrativo](./desktop/02_GAMEPLAY_E_MECANICAS.md)"
3. **Threshold — Política e alianças**: Relações complexas → nossas "[Conexões de consciência](./desktop/01_VISAO_E_CONCEITO.md)"
4. **Discworld — Narrativa com personalidade**: Tom único → nossa voz autêntica e consciente por comunidade

---

## 3. WhatsApp + RPG + IA — Estado da Arte

### Projetos existentes

| Projeto/Conceito | Como funciona | Insight |
|------------------|---------------|---------|
| **WhatsApp Text RPG (dev.to)** | Twilio API + ChatGPT = Game Master que avança história por capítulos | Validação do conceito: funciona! |
| **AI Dungeon Master (Gemini)** | Google Gemini roda aventuras text-based | IA como GM é viável com LLMs modernos |
| **Meta AI no WhatsApp** | Llama 2 integrado nativamente | Infraestrutura nativa disponível |

### Desafios identificados

- **Manter narrativa linear**: IA tende a "desviar" da história
- **Contexto por jogador**: Cada sessão WhatsApp precisa carregar contexto do personagem
- **Latência**: Respostas da IA precisam ser rápidas para boa UX
- **Moderação**: Conteúdo gerado precisa ser seguro/inclusivo

---

## 4. Nossa Posição Única

> **Nenhum MUD existente combina TUDO isso:**

```
MUD Clássico     → Mundo de salas + multiplayer + texto
    +
Inteligência AI  → IA como Game Master + mediadora consciente
    +
WhatsApp         → Interface universal, sem fricção
    +
Mundo Real       → QR Codes + empreendimentos + tours urbanos
    +
Propósito Social → Comunidades diversas + consciência + network
    +
Construção Emergente → Jogadores criam o mundo
    +
Multi-Comunidade → Escalável para qualquer grupo humano
```

### Vantagens competitivas

1. **Zero fricção**: Não precisa instalar nada (WhatsApp já está no celular)
2. **Público definido**: Lançamento com comunidade LGBTQIA+ (Guia Gay), expansível para qualquer comunidade
3. **Ponte real-virtual**: QR Codes transformam locais em portais do jogo
4. **IA como diferencial**: Não é um MUD com IA "colada", a IA É o jogo
5. **Propósito**: Vai além de "jogar" — conecta, cura, fortalece
6. **Arquitetura multi-comunidade**: Cada comunidade pode ter seu "mundo" com identidade própria, mas com portais para os outros

---

<div align="center">
  [◀ PRD Análise](./PRD_ANALISE.md) | [🏠 Início](./README.md) | [Visão e Conceito ▶](./desktop/01_VISAO_E_CONCEITO.md)
</div>

*Pesquisa realizada em Março/2026 — Atualizar conforme novas referências surgirem*
