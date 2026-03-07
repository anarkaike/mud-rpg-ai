# 🎮 Gameplay e Mecânicas — MUD-AI

> **Mesa de trabalho** — Rascunho vivo de mecânicas de jogo em amadurecimento.

---

## Ciclo de Jogo Principal

```
┌──────────────────────────────────────┐
│       JOGADOR ABRE O WHATSAPP        │
│              ↓                        │
│    IA recebe e contextualiza         │
│              ↓                        │
│  ┌───────────────────────┐           │
│  │   LOOP PRINCIPAL      │           │
│  │                       │           │
│  │  Explorar → Conectar  │           │
│  │      ↕          ↕     │           │
│  │  Construir → Evoluir  │           │
│  │                       │           │
│  └───────────────────────┘           │
│              ↓                        │
│     QR Code? Evento? Outro player?   │
│     → Desbloqueia/Ativa conteúdo     │
└──────────────────────────────────────┘
```

---

## 1. 🗺️ Exploração

### Mundo = Cidade Real
- Cada **bairro** é um território com energia/temática própria
  - Ex: Liberdade = ancestralidade, Vila Madalena = experimentação, Centro = visibilidade
- Cada **bar/empreendimento** é uma "sala" no MUD
- **QR Codes** em locais físicos destravam conteúdo exclusivo

### Como se Move
- **Texto**: "Ir para o Bar X" / "Explorar a Consolação"
- **QR Code**: Escaneia no local e entra automaticamente na "sala"
- **Convite de Player**: Outro jogador te leva a um local
- **Missão**: Completar tarefa te abre novo território

### O que Acontece numa Sala
- Ver descrição (gerada/curada por IA com base em contribuições dos jogadores)
- Ver quem está ali (outros jogadores)
- Interagir (conversar, trocar, colaborar)
- Completar desafios/missões

---

## 2. 🤝 Conexão entre Jogadores

### Interação Mediada por IA
A IA atua como intermediária em TODA comunicação:

| Função da IA | Como funciona |
|--------------|---------------|
| **Reformulação** | Melhora clareza e modulação emocional do texto |
| **Contextualização** | Adiciona contexto relevante sobre o jogador (com permissão) |
| **Perguntas provocadoras** | Insere perguntas que aprofundam a conversa |
| **Segurança** | Filtra conteúdo tóxico ou abusivo |
| **Sugestão de conexões** | "Você e Fulano compartilham interesse em X..." |

### Tipos de Interação
1. **Chat de sala** — Conversa aberta em um local
2. **Conversa privada** — Diálogo 1:1 mediado
3. **Círculo** — Diálogos em grupo temáticos
4. **Mentoria** — Um-para-um com foco em crescimento
5. **Colaboração** — Trabalho conjunto em missão/projeto

---

## 3. 🧱 Construção (Estilo Minecraft)

### Como os Jogadores Criam o Mundo

> O universo nasce da interação — cada texto, história, reflexão é um "bloco".

1. **Fragmentos narrativos**: Jogador escreve um trecho (história, sensação, descrição de local) → IA transforma em "bloco" no mapa
2. **Crafting narrativo**: Combinar blocos de diferentes jogadores cria novos locais/eventos
   - _1 insight de autoconhecimento + 1 bar + 1 habilidade = 1 checkpoint_
3. **Conexão por similaridade**: IA sugere links entre blocos de jogadores diferentes
4. **Mapa vivo**: O mundo se expande a cada contribuição

### Regras de Construção
- Qualquer jogador pode criar blocos narrativos
- Combinações precisam de consenso (os envolvidos aprovam)
- Blocos mais populares viram "landmarks" permanentes
- A IA curadoria garante qualidade e coerência

---

## 4. 📈 Progressão e Evolução

### Sem "Nível" Tradicional
Em vez de XP e level, usamos **consciências** e **conexões**:

| Métrica | O que significa |
|---------|-----------------|
| **Consciências desbloqueadas** | Temas que o jogador explorou (acolhimento, corpo, desejo, criatividade...) |
| **Conexões feitas** | Pessoas com quem interagiu significativamente |
| **Blocos criados** | Contribuições ao mundo |
| **Trocas realizadas** | Habilidades compartilhadas ou recebidas |
| **Locais visitados** | Explorações no mundo real |

### Conquistas/Badges
- 🌱 **Semente** — Primeiro dia no jogo
- 🔥 **Chama Acesa** — Compartilhou uma história profunda
- 🌉 **Ponte** — Conectou duas pessoas
- 🏗️ **Arquiteto** — Criou um bloco que foi combinado com outros
- 🗺️ **Desbravador** — Visitou 10 locais reais
- 🤝 **Mentor** — Guiou 5 pessoas
- 💎 **Gema** — Reconhecido pela comunidade

---

## 5. 🎯 Missões e Desafios

### Tipos de Missão

| Tipo | Exemplo | Onde |
|------|---------|------|
| **Exploração** | "Visite o bar X e descubra a carta secreta" | Mundo real |
| **Conexão** | "Converse com alguém sobre seu maior medo" | Dentro do jogo |
| **Criação** | "Escreva a descrição de um lugar que te acolhe" | Dentro do jogo |
| **Troca** | "Ofereça 30min de sua habilidade para outro jogador" | Real ou virtual |
| **Ritual** | "Participe do círculo de consciência desta semana" | Evento |
| **Tour** | "Faça o roteiro dos 5 bares indicados e registre" | Mundo real |

### Eventos Especiais
- **Noites temáticas** em bares reais com missões exclusivas
- **Círculos semanais** de conversa (online ou presencial)
- **Festivais narrativos** — construção coletiva de histórias

---

## 6. 🃏 Cartas de Consciência

Deck digital de cartas que provocam reflexão e ação:

### Exemplos
| Carta | Tipo | Provocação |
|-------|------|-----------|
| **Acolhimento** | Consciência | "Que parte de você quer ser acolhida hoje?" |
| **Coragem** | Desafio | "Compartilhe algo que nunca contou a ninguém" |
| **Potência** | Habilidade | "Qual talento seu o mundo precisa conhecer?" |
| **Espelho** | Reflexão | "O que o último comentário que te incomodou diz sobre você?" |
| **Ponte** | Conexão | "Quem nesta sala poderia te ensinar algo?" |

---

## 7. 🏠 O Bar como Hub

### Integração Física

- **Quests do bar**: Montar noite temática, acolher pessoa isolada, criar mural
- **QR Codes espalhados**: Ativam cenas, diálogos secretos, cartas especiais
- **Selos**: Completar missão no bar = selo no perfil + narrativa no feed
- **Intenção do bar**: Definida no início da sessão, guia o gameplay

---

*Rascunho de trabalho — Iterar conforme testamos conceitos — Março/2026*
