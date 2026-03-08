# ⚙️ MUD-AI — Arquitetura do Motor (Engine)

O MUD-AI foi construído em Python usando **FastAPI** e atua como o 'Game Engine' por trás do WhatsApp. Ele armazena os dados, valida a economia do jogo, utiliza IA (OpenAI ou Gemini em fallback) para gerar variações dinâmicas de texto, e empacota tudo na formatação estrita suportada pelo WhatsApp.

## 🧱 Componentes Principais

### 1. Artifact Database (`server/database.py`)
Para manter a natureza textual e "hacker/MUD" do jogo, criamos um banco de dados persistente em um arquivo único SQLite (`mudai.db`). Ele não possui tabelas rígidas de usuários ou locais: tudo é um **Artifact**.
* **Como funciona:** Artifacts são instâncias de Markdown puras que possuem uma chave (ex: `mudai.users.551199999999`), um `content` (texto raw, regras, markdown) e metadados parciais cacheados no SQLite em formato JSON.
* **Templates:** Novos players e salas são instanciados a partir de templates (`mudai.templates.*`).
* **Vantagem:** Muito fácil de modificar o mundo. Se o dev quiser criar uma sala, ele simplesmente cria um nóte-texto na DB.

### 1.1. Camada de Mundo Vivo (`server/world_state.py`)
Sobre os artifacts base, o projeto agora mantém uma camada derivada para aproximar a implementação da visão de mundo emergente descrita nos documentos.
* **Estado evolutivo de sala:** cada sala pode ter um artifact derivado em `mudai.world.rooms.{slug}.state` com `evolving_summary`, `visual_summary`, `motifs`, autores recentes e necessidade de refresh visual.
* **Blocos narrativos estruturados:** decorações e fragmentos relevantes também podem ser persistidos como blocks em `mudai.world.rooms.{slug}.blocks.*`.
* **Pool de imagens por sala:** a base de prompts e assets visuais é preparada em `mudai.world.rooms.{slug}.images.*`, permitindo cache, rotação e regeneração futura.
* **Memória curta anti-repetição:** respostas recentes podem ser registradas em `mudai.world.memory.responses.*` para evitar repetição textual excessiva.

### 2. Game Engine e Parser (`server/game_engine.py`)
É o cérebro que analisa o que o usuário enviou, extrai as sementes (economia) do perfil e roteia para:
* Achar o jogador.
* Chamar o onboarding (se o player for novo).
* Parsear comandos de movimentação (ir norte, leste, etc).
* Avaliar comandos soltos.
* Lidar com interações nas salas, onde o jogador quer colocar uma frase, pegar um item, deixar um conselho, etc (avaliado dinamicamente via IA).
* Oferecer e resolver desafios contextuais por sala, usando o estado vivo da sala para gerar pequenas missões conversacionais com recompensa.
* Persistir missões derivadas por sala como artifacts do mundo vivo, permitindo progresso por jogador e reuso da mesma missão ao longo do tempo.
* Materializar novas salas dinamicamente quando uma saída conhecida aponta para um destino ainda não persistido, preservando o fluxo de exploração sem depender de seed manual prévia no banco.

### 3. AI Client Wrapper (`server/ai_client.py`)
Cliente agnóstico usando `httpx` para interagir com a API da **OpenAI** e com um fallback inteligente para a **Google Gemini 2.0 Flash**.
* Contém suporte especial a injeção JSON (`chat_completion_json`).
* Se a OpenAI falhar por timeout, indisponibilidade ou ausência de chave válida, tenta fallback para Gemini quando disponível.
* Se não houver nenhuma chave configurada, falha explicitamente com erro operacional claro, evitando chamadas inválidas com header vazio.

### 4. Roteamento de Onboarding (`server/onboarding.py`)
Módulo específico com uma máquina de estados de 5 passos. Ao final do cadastro, ele injeta os 50 *seeds* iniciais. Conta com IA super-criativa para que a cada novo usuário as perguntas sobre "A Essência", "O que oferta", "Nomes" e "Dicas" mudem completamente de formatação, contexto poético ou metáforas.

### 5. Message Formatter (`server/message_formatter.py`)
Componente UI central para a interface via **WhatsApp**. A UI do WhatsApp só aceita: `*negrito*`, `_itálico_`, ````monospace````.
* Trabalha dentro da regra de não estourar a tela do usuário com mensagens massivas (limite não oficial de ~800-1000 carbs visuais).
* Adota estilo consistente com divisores `━━━━━━━━━━━━━━━━━━━━` (linhas horizontais Unicode) e estatísticas em linha `🪙 50  ·  ⭐ Nv.1`.
* Construtores pré-prontos para Salas, Perfis e Menus/Lista de Descobertas.

### 6. Public Profiles e Renderer HTML (`server/routers/pages.py` & `server/renderer.py`)
Como links para páginas extensas ajudam na visualização dos usuários (nem tudo cabe no WhatsApp), temos endpoints públicos (`/p/{token} `). 
Eles mapeiam um artefato Markdown em HTML nativamente, usando `markdown2` e estilos de **Dark Mode / Glassmorphism** puros via CSS injetado e substituição dinâmica via expressões regulares para os campos do Profile `{nickname}`.
Quando a navegação ocorre com sessão web ativa, o renderer também projeta o estado vivo da sala em componentes visuais próprios, incluindo painel de missões persistentes, status da missão ativa, progresso já concluído pelo jogador e sincronização parcial via HTMX para manter barras laterais e terminal coerentes após cada ação.

### 7. Expansão Dinâmica do Mundo (`server/room_manager.py`)
O backend consegue transformar saídas textuais em salas reais quando o jogador tenta atravessá-las e o destino ainda não existe como artifact.
* **Materialização sob demanda:** ao seguir uma direção válida, o `room_manager` pode criar automaticamente `mudai.places.{slug}` com conteúdo mínimo, metadados e saída de retorno.
* **Bootstrap imediato:** a nova sala já nasce com `world_state`, missões persistentes iniciais e tags derivadas do contexto de origem.
* **Exploração contínua:** isso reduz dependência de seed manual e permite que o mapa cresça incrementalmente a partir das conexões já descritas nos markdowns das salas.
* **Governança da expansão:** salas geradas carregam linhagem (`generated_root_room`, `generated_depth`) e respeitam limites de profundidade e quantidade de filhos para evitar crescimento descontrolado do mapa.

### 8. Matching Social (`server/room_manager.py` & `server/game_engine.py`)
O backend também cruza o que cada jogador busca com o que outros jogadores oferecem, e vice-versa, para sugerir conexões potencialmente úteis.
* **Base do score:** interseção entre `seeks` e `offers`, com bônus quando os jogadores estão na mesma sala.
* **Acesso por comando:** o engine expõe as sugestões via `/conexoes`, `conexoes` e aliases equivalentes, sem depender da interface web.
* **Memória persistida:** cada consulta pode registrar artifacts em `mudai.users.{phone}.social_matches.{other_phone}` com score, termos em comum e contagem de vezes em que aquela conexão foi sugerida.
* **Consulta histórica:** o backend também permite revisar essa memória social via `/historico-conexoes` e aliases equivalentes, ordenando conexões por recência e recorrência.
* **Curadoria social:** conexões persistidas podem ser marcadas como favoritas via `/favoritar-conexao` e revisitadas em `/conexoes-favoritas`, preservando esse estado entre novas consultas.
* **Objetivo:** incentivar conversas, trocas e afinidades reais usando os dados já coletados no onboarding e no perfil do jogador.

---

## 🚀 Fluxo de um Webhook

Quando um usuário manda mensagem no WhatsApp:
1. Pela **Evolution API / Chatwoot**, cai no **n8n**.
2. O **n8n** despacha via POST um payload normalizado para o endpoint FastAPI (`/api/v1/game/action`).
3. O endpoint coleta a string da mensagem, telefone, `conversation_id` e `account_id`.
4. Repassa para `process_action()` no `game_engine.py`.
5. Se for o primeiro acesso, aciona `start_onboarding()`.
6. Se não, avalia os comandos via regras rápidas e/ou IA, computa movimentação, conversa, decoração e atualização de estado de sala.
7. Ao decorar ou concluir interações relevantes, o engine também atualiza a camada de `world_state` da sala, incluindo resumo vivo, ecos recentes e preparação de imagem.
8. O endpoint devolve um payload JSON com a resposta formatada para WhatsApp.
9. O **n8n** responde o Chatwoot.
