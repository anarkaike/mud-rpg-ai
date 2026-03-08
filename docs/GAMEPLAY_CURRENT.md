# 🎲 MUD-AI — Mecânicas do Jogo e Gameplay 

Este documento descreve as principais engrenagens de engajamento, progressão, recompensas (economia) e mecânicas de interação do MUD-AI operando **atualmente** na versão v2.

## 1. O Loop Central (Core Loop)
- **Descoberta:** O jogador encontra diferentes *Salas* (Places) usando comandos de movimentação e exploração.
- **Narrativa e Interação:** Cada sala tem uma temática descritiva. O jogador lê descrições e "Fragmentos" deixados por outros. O jogador deixa suas próprias marcas ou realiza desafios baseados no contexto da sala mediado por IA.
- **Acúmulo de Valor:** Ações gastam ou recompensam *Sementes* (🪙 Seeds).
- **Expressão de Identidade:** O perfil do jogador cresce em Níveis (⭐), Badges (🏅) e Sementes (🪙).

### Onboarding Dinâmico e Sem Fricção
A experiência começa ao enviar a primeira mensagem (ex: *oi*). O jogador passa por um onboarding de **5 etapas conversacionais** guiadas por IA (`CultivIA`):
1. **Nome/Apelido**: Escolha do *nickname*.
2. **Essência**: Uma reflexão leve (Ex: *Se você fosse um som, qual seria?*).
3. **Busca**: O que o jogador procura (conselho, poesia, relaxar).
4. **Oferta**: O que o jogador pode dar (escuta, criatividade, histórias).
5. **Primeiro Fragmento**: Deixar uma marca na parede da sala inicial (A *Recepção*).

> 🤖 **Nota sobre a IA:** As perguntas, o contexto imaginativo e as sugestões no final de cada perqunta do onboarding são **100% geradas via inteligência artificial em tempo real (OpenAI / Gemini).** Não há loops idênticos. Cada usuário tem dicas de nomes misteriosos, sons aleatórios em metáforas completamente diferentes uns dos outros.

Ao finalizar, ele ganha uma Badge (*Primeiro Passo*) e um bônus especial de +3 sementes (iniciando com totais 53 sementes).

## 2. A Economia de Sementes (🪙 Seeds)

As sementes são a engrenagem principal. Para combater a fadiga do texto e recompensar a profundidade:

### Ganho ➕:
* Cadastro completo via Onboarding (Traz 50 seeds bases + bônus de completitude).
* **Indicação (Referral Bonus):** Dar um link especial referencial a alguém. Quando o colega criar a conta via WhatsApp, **ambos** ganham sementes, e o amigo ativador ainda ganha o cobiçado Badge de **Conector** `🏅`.
* Resolvendo desafios contextuais persistentes da sala, gerados dinamicamente por IA com fallback heurístico.
* Adicionando "Fragmentos" valiosos (se a IA achar o texto complexo e engajador, ela avalia uma recompensa de +10, +20 seeds automaticamente).

### Gasto ➖:
* Navegar intensamente entre salas VIPs.
* Deixar Decorações Permanentes ou Fragmentos profundos.
* Fazer perguntas extremamente abertas ao Oráculo sem direcionamento (consumo de tokens = consumo in-game de seeds).

## 2.1. Desafios Dinâmicos Persistentes por Sala

Cada sala agora pode manter um pool próprio de desafios dinâmicos persistidos no mundo vivo.

- **Pool persistente por sala:** o backend mantém múltiplos desafios ativos por sala, em vez de gerar apenas um desafio efêmero por resposta.
- **Geração híbrida:** a engine tenta gerar novas opções com IA a partir do contexto vivo da sala e do perfil do jogador; se falhar, usa fallback heurístico local.
- **Deduplicação por jogador:** o jogador não deve receber de novo desafios já concluídos, nem variantes com a mesma `novelty_key`.
- **Histórico social anônimo:** cada desafio guarda as últimas 5 respostas anônimas e a contagem agregada de respostas, para inspirar novos jogadores sem expor identidade.
- **Progressão contextual:** ao concluir um desafio, o jogador recebe sementes, deixa um novo eco na sala e atualiza o estado vivo do ambiente.
- **Skip com rotação:** quando o jogador pula um desafio dinâmico, a engine tenta oferecer outra opção elegível da mesma sala.

## 3. Comandos e Intenções Híbridas (NLP/RegEx + GenAI)
O jogador **não** é escravo de "slash commands" rígidos (`/ajuda`). 

* **Comandos Estáticos (Fallback Rápido e Barato):**
  * `perfil`, `salas`, `olhar`, `ajuda`, `/sementes`.
  * Estes vão via RegExp sem custo de computação e voltam no instante.
* **Comandos Narrativos Avançados (Context-Aware Game Engine):**
  * Caso o usuário queira só bater papo com a sala livremente ou executar comandos arbitrários ("pegar o lampião na mesa", "deixar um bilhete de adeus no balcão"), isso passará para um `process_interaction` via ChatGPT/Gemini. 
  * A IA vai julgar como o ambiente reage à solicitação e aplicar perdas/ganhos de sementes dinamicamente e salvar artefatos contextuais no Database. 

## 4. Identidade, Sessão Web e Privacidade

- **Sessão web autenticada por token:** a navegação personalizada acontece por token/link seguro, sem exigir exposição pública do telefone.
- **Perfis não são mais listados publicamente:** a superfície pública foi endurecida para privilegiar salas e navegação autenticada, bloqueando acesso público direto a `mudai.users.*`.
- **API protegida sanitizada:** endpoints de estado usados pela interface e QA não retornam o telefone bruto do jogador.
- **UI pública minimizada:** a landing pública não expõe mais fluxo visível baseado em telefone nem listagens abertas de jogadores.

**As Badges representam as "conquistas (achievements)" textuais.** Exemplos:
* **🌱 Primeiro Passo**: Passar de 5 etapas do guia.
* **🤝 Conector**: Indicar um usuário e ele fechar a jornada e cair na Recepção.
* **✍️ Escritor**: Criar um fragmento mais extenso na Caverna ou na Recepção.

O sistema de Salas e Perfis usa Glassmorphism nativo misturando Dark Themes sem excesso visual; foco claro nas intenções e no texto.

## 5. Interface Web da Sala

Quando a navegação ocorre com sessão ativa, a interface web da sala passou a exibir:

- **Missões persistentes da sala** com status disponível, ativa ou concluída.
- **Desafios dinâmicos da sala** com título, instrução, tipo, recompensa e contagem de respostas.
- **Últimas 5 respostas anônimas** de cada desafio, quando existirem.
- **Estado do jogador sem telefone exposto**, mantendo apenas os dados necessários para progressão e personalização.
