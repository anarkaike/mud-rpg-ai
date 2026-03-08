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
* Resolvendo Desafios temáticos diários na IA.
* Adicionando "Fragmentos" valiosos (se a IA achar o texto complexo e engajador, ela avalia uma recompensa de +10, +20 seeds automaticamente).

### Gasto ➖:
* Navegar intensamente entre salas VIPs.
* Deixar Decorações Permanentes ou Fragmentos profundos.
* Fazer perguntas extremamente abertas ao Oráculo sem direcionamento (consumo de tokens = consumo in-game de seeds).

## 3. Comandos e Intenções Híbridas (NLP/RegEx + GenAI)
O jogador **não** é escravo de "slash commands" rígidos (`/ajuda`). 

* **Comandos Estáticos (Fallback Rápido e Barato):**
  * `perfil`, `salas`, `olhar`, `ajuda`, `/sementes`.
  * Estes vão via RegExp sem custo de computação e voltam no instante.
* **Comandos Narrativos Avançados (Context-Aware Game Engine):**
  * Caso o usuário queira só bater papo com a sala livremente ou executar comandos arbitrários ("pegar o lampião na mesa", "deixar um bilhete de adeus no balcão"), isso passará para um `process_interaction` via ChatGPT/Gemini. 
  * A IA vai julgar como o ambiente reage à solicitação e aplicar perdas/ganhos de sementes dinamicamente e salvar artefatos contextuais no Database. 

## 4. Identidade (Public Profiles & Badges)

Nenhum progresso é mantido às escondidas na tela do celular. Todo usuário tem um Hash único de Profile criptografado exposto publicamente como um link na web para o mundo enxergar suas criações e traços (através do roteador em `/p/{hash}`).

**As Badges representam as "conquistas (achievements)" textuais.** Exemplos:
* **🌱 Primeiro Passo**: Passar de 5 etapas do guia.
* **🤝 Conector**: Indicar um usuário e ele fechar a jornada e cair na Recepção.
* **✍️ Escritor**: Criar um fragmento mais extenso na Caverna ou na Recepção.

O sistema de Salas e Perfis usa Glassmorphism nativo misturando Dark Themes sem excesso visual; foco claro nas intenções e no texto.
