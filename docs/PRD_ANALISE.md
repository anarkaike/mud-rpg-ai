# 📋 Análise do PRD de Referência — meu-mud

<p align="center">
  <a href="./README.md">◀ Início</a> | <b>PRD Análise</b> | <a href="./PESQUISA_MUDS.md">Pesquisa de MUDs ▶</a>
</p>

> Análise detalhada do [PRD do projeto meu-mud](https://github.com/lucaseneiva/meu-mud/blob/feature/domain-tests/docs/PRD.md) para servir de baseline e inspiração.

---

## Resumo do PRD Original

O PRD define um **MUD clássico e minimalista** — texto puro, sem combate, sem NPCs, sem inventário. Foco total em estabilidade e experiência multiplayer básica.

### Escopo da v1 (meu-mud)

| Feature | Incluído | Detalhes |
|---------|----------|----------|
| Autenticação | ✅ | Nome único + senha (hash), sessão única por personagem |
| Modelo de Personagem | ✅ | Nome, hash da senha, sala atual (sem stats/inventário) |
| Mundo de Salas | ✅ | ID, título, descrição, exits direcionais |
| Movimentação | ✅ | Comandos textuais (north/n, south/s, etc.) |
| Chat de Sala | ✅ | `say <mensagem>` visível pela sala |
| Comandos Básicos | ✅ | `help`, `look`, direções, `say`, `exit`, `who` |
| Multiplayer | ✅ | Notificações entrada/saída de sala |
| Combate | ❌ | Fora do escopo v1 |
| NPCs/AI | ❌ | Fora do escopo v1 |
| Inventário | ❌ | Fora do escopo v1 |
| Skills/Níveis | ❌ | Fora do escopo v1 |
| GUI | ❌ | Fora do escopo v1 |

### Infraestrutura

- **Interface**: TCP puro (telnet compatível)
- **Persistência**: Personagens em arquivo/DB; mundo em JSON/YAML
- **Segurança**: Hash de senhas obrigatório
- **Erros**: Mensagens claras para todos os casos de erro

### Métricas de Sucesso

1. Criar personagem ✓
2. Fazer login ✓
3. Dois usuários simultâneos ✓
4. Movimentar entre salas ✓
5. Ver outros jogadores ✓
6. Comunicar na sala ✓
7. Persistência após reinício ✓

---

## 🔄 O que Aproveitamos vs. O que Reinventamos

### ✅ Conceitos que Aproveitamos

| Do PRD Original | No Nosso Projeto |
|-----------------|-----------------|
| Mundo de salas conectadas | Salas = locais reais (bares, bairros, eventos) |
| Movimentação direcional | Movimentação por escolhas narrativas + QR Codes |
| Chat de sala | Chat mediado por IA (reformulação, modulação emocional) |
| Personagens persistentes | Perfis com histórias, habilidades, necessidades |
| Multiplayer com notificações | Conexões profundas guiadas por IA |
| Comandos textuais | Linguagem natural via WhatsApp (IA interpreta) |

### 🔀 O que Reinventamos Completamente

| Conceito Tradicional | Nossa Abordagem |
|----------------------|-----------------|
| Terminal/Telnet | **WhatsApp** como interface principal |
| Mundo estático (JSON) | **Mundo emergente** construído pelos jogadores |
| Exploração de fantasia | **Exploração da cidade real** + mapas afetivos |
| Solo/competitivo | **Colaborativo** + conexão de consciências |
| Game loop simples | **IA como Game Master** adaptativo |
| Sem propósito social | **Conscientização, comunidade, network** |

---

## 🎯 Gaps e Oportunidades

### O que o PRD clássico NÃO cobre (e nós precisamos):

1. **Camada de IA** — O agente como intermediário inteligente
2. **Integração WhatsApp** — Via N8N + Twilio/Evolution API
3. **QR Codes físicos** — Bridge mundo real ↔ mundo virtual
4. **Sistema de "consciências"** — Mecânicas de autoconhecimento
5. **Banco de trocas** — Habilidades oferecidas/necessitadas
6. **Construção emergente** — Jogadores criam o mundo (estilo Minecraft)
    7. **Monetização** — [Modelo de negócio sustentável](./desktop/04_MONETIZACAO_E_CRESCIMENTO.md)
8. **Moderação por IA** — Segurança e inclusividade
9. **Arquitetura multi-comunidade** — [Sistema de mundos/reinos em evolução](./desktop/03_ARQUITETURA_TECNICA.md)
10. **Diversidade e neuroatipicidade** — Interfaces que respeitem formas de interação variadas

---

<p align="center">
  <a href="./README.md">◀ Início</a> | <a href="./PESQUISA_MUDS.md">Pesquisa de MUDs ▶</a>
</p>

*Documento de referência — atualizar conforme o projeto evolui*
