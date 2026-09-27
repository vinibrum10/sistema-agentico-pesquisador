# Sistema Agêntico Pesquisador

Workflow agêntico local para apoio à pesquisa científica, agnóstico ao tema.
Modelo local via Ollama (`qwen3:8b`, GPU local); busca científica no OpenAlex.

## Status atual

- Agente 1 V1 concluído: Intake → Planner → Search (OpenAlex) → `results.csv`.
- Agente 2 V1 (triagem) concluído: filtros determinísticos + juiz LLM → `screening.csv`.
- Loop de refinamento V1 concluído: rodadas de busca + triagem com ajustes
  determinísticos → `loop_log.csv`.

## Fluxo do Agente 1

1. **Intake** — 4 perguntas curtas (tema, objetivo, foco, restrição). O LLM sugere
   redação e termos-base; nada entra no contexto sem confirmação do pesquisador.
2. **Pesquisa ativa** — menu Manter / Ajustar (um campo por vez) / Mudar tema
   (apaga tudo, sem histórico).
3. **Planner** — determinístico, sem LLM: um grupo por termo-base (OR entre
   variantes PT/EN e expansões), AND entre grupos; grupos marcáveis antes de confirmar.
4. **Search** — uma consulta booleana no OpenAlex (25 resultados), gravados com
   upsert por `openalex_id` em `data/active_research/results.csv`
   (inclui a coluna `retratado`).

## Fluxo do Agente 2 (triagem)

Menu: Manter → [2] Triar resultados.

1. **Filtros determinísticos** (`screening/filtros.py`) — descarta retratados e
   duplicatas (mesmo DOI ou mesmo título normalizado).
2. **Juiz LLM** (`screening/juiz.py`) — um paper por vez, título + resumo. O modelo
   responde campos simples com saída estruturada por esquema (`objeto`,
   `mesmo_dominio`, `mesmo_problema`, `trecho`); o **veredito é decidido pelo código**:
   domínio diferente → lixo; mesmo domínio e mesmo problema → relevante;
   mesmo domínio e outro problema → talvez.
3. **Incremental** — papers já julgados não voltam ao LLM ("erro" é julgado de novo).
   Para retriar tudo (ex.: depois de mudar o prompt do juiz), apague `screening.csv`.
4. **Saída** — `data/active_research/screening.csv` (veredito, justificativa,
   trecho literal do resumo e confiança) e resumo por veredito no terminal.
5. **Calibração** (`screening/calibracao.py`) — compara o juiz com
   `gabarito.csv` (r/t/l, separador `;`) e mostra concordância e matriz.

## Loop de refinamento (V1)

Menu: Manter → [3] Refinar busca (loop).

- Trabalha numa **cópia** do plano; o `context.json` nunca é alterado.
- Cada rodada: busca → triagem incremental → precisão da consulta
  (relevantes ÷ papers válidos da rodada) → linha em `loop_log.csv`.
- Abaixo da meta, aplica **um** ajuste por rodada, nesta prioridade:
  1. remover a expansão presente em ≥ 2 papers "lixo" da rodada (e em mais lixo
     que relevantes) — termos-base nunca são removidos;
  2. desmarcar o grupo de foco.
- Para quando: meta atingida (padrão 50%), limite de rodadas (padrão 3) ou
  nenhum ajuste disponível. Sem meta → aviso "decisão do pesquisador necessária".
- Mostra a **melhor** rodada e a consulta; adotar é decisão do pesquisador (menu Ajustar).

## Como rodar

Requer Ollama com `qwen3:8b` e `OPENALEX_API_KEY` no `.env`.

    python src\main.py

Calibração do juiz:

    python -c "import sys; sys.path.insert(0, 'src'); from agents.screening.calibracao import calibrar; calibrar()"

## Métricas de referência (26–27/09/2026)

Busca — tema de teste com 3 termos-base (mineral, machine learning, prospecção) + foco em métodos:
56% relevantes, 36% talvez, 8% descartáveis (classificação manual de 25 títulos).
Sem o conceito central do tema como termo-base, o mesmo teste deu 4%.

Juiz de triagem (v3.1, gabarito de 66 papers):
- 74% de concordância no conjunto usado para ajustar o prompt (47 papers);
- 67% em papers novos, nunca vistos pelo juiz (18 papers);
- 85% de precisão em "relevante"; nenhum lixo classificado como relevante;
- quase determinístico: execuções seguidas deram vereditos idênticos, mas uma
  triagem completa posterior variou ~3 de 68 vereditos (concordância global 70%);
- ~3 min para 68 papers na GPU local.

Loop V1 — mesma pesquisa: rodada 1 com 50% de precisão (juiz); desmarcar o grupo
de foco trouxe só 1 paper novo e manteve 50% (o grupo de foco praticamente não filtra).

Lição de método: com modelo de 8B, veredito livre (com ou sem justificativa antes)
ficou em 38–51%; decompor em perguntas simples, forçar tipos por esquema e decidir
no código elevou para 74%.

## Limitações conhecidas

Busca (V1):
- Um conceito do tema pode não virar termo-base, sem aviso.
- Termos-base descritivos (não pesquisáveis) passam na validação e podem zerar a busca.
- A busca considera texto completo, não só título e resumo.

Triagem (V1):
- Duplicatas cujos títulos diferem só na pontuação (ex.: "–" e "—") não são detectadas.
- O juiz é restritivo em `mesmo_dominio` quando o contexto varia (outro mineral,
  outro sensor); relevantes perdidos tendem a cair em "talvez".
- Recalibrar quando o gabarito tiver ~150 papers; teste em outro tema pendente.

Loop (V1):
- Só remove (expansões, grupo de foco): limpa consulta ruim, mas não melhora uma
  consulta razoável. A V2 deve propor termos novos a partir dos papers relevantes.
- `loop_log.csv` acumula execuções; distinguir pela coluna `data_hora`.
