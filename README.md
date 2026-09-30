# Sistema Agêntico Pesquisador

Workflow agêntico local para apoio à pesquisa científica, agnóstico ao tema.
Modelo local via Ollama (`qwen3:8b`, GPU local); busca científica no OpenAlex.

## Status atual

- Agente 1 V1 concluído: Intake → Planner → Search (OpenAlex) → `results.csv`.
- Agente 2 V1 (triagem) concluído: filtros determinísticos + juiz LLM → `screening.csv`.
- Loop de refinamento V1 concluído: rodadas de busca + triagem com ajustes
  determinísticos → `loop_log.csv`.
- Próximo: V2 do loop por snowballing de citações a partir dos papers relevantes.

## Fluxo do Agente 1

1. **Intake** — 4 perguntas curtas (tema, objetivo, foco, restrição). O LLM sugere
   redação e termos-base; nada entra no contexto sem confirmação do pesquisador.
2. **Pesquisa ativa** — menu Manter / Ajustar (um campo por vez) / Mudar tema
   (apaga tudo, sem histórico).
3. **Planner** — determinístico, sem LLM: um grupo por termo-base (OR entre
   variantes PT/EN e expansões), AND entre grupos; grupos marcáveis antes de confirmar.
   O grupo de foco e o de geografia começam **desmarcados** (o foco é aplicado pelo
   juiz de triagem, não pela consulta).
4. **Search** — uma consulta booleana no OpenAlex (`search`: título, resumo e texto
   completo), **50 resultados**, gravados com upsert por `openalex_id` em
   `data/active_research/results.csv` (inclui a coluna `retratado`).

## Fluxo do Agente 2 (triagem)

Menu: Manter → [2] Triar resultados.

1. **Filtros determinísticos** (`screening/filtros.py`) — descarta retratados e
   duplicatas (mesmo DOI ou mesmo título normalizado, ignorando pontuação).
   Os descartes são recalculados a cada triagem e valem também para papers já triados.
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
   `gabarito.csv` (r/t/l, separador `;`): concordância, matriz, **evidência perdida**
   (relevante → lixo), recall e redução de trabalho.

## Loop de refinamento (V1)

Menu: Manter → [3] Refinar busca (loop).

- Objetivo: **o máximo de relevantes** com precisão ≥ piso (padrão 30%).
- Trabalha numa **cópia** do plano; o `context.json` nunca é alterado.
- Cada rodada: busca → triagem incremental → precisão da consulta
  (relevantes ÷ papers válidos da rodada) → linha em `loop_log.csv`.
- Abaixo do piso, aplica **um** ajuste por rodada, nesta prioridade:
  1. remover a expansão presente em ≥ 2 papers "lixo" da rodada (e em mais lixo
     que relevantes) — termos-base nunca são removidos;
  2. desmarcar o grupo de foco.
- Para quando: piso atingido, limite de rodadas (padrão 3) ou nenhum ajuste
  disponível. Nenhuma rodada no piso → aviso "decisão do pesquisador necessária".
- Melhor rodada = mais relevantes entre as que respeitam o piso; adotar a consulta
  é decisão do pesquisador (menu Ajustar).

## Como rodar

Requer Ollama com `qwen3:8b` e `OPENALEX_API_KEY` no `.env`.

    python src\main.py

Calibração do juiz:

    python -c "import sys; sys.path.insert(0, 'src'); from agent_research.screening.calibracao import calibrar; calibrar()"

## Métricas de referência (26–27/09/2026)

Busca — tema de teste com 3 termos-base (mineral, machine learning, prospecção):

| Configuração | Papers | Relevantes (juiz) | Precisão |
|---|---|---|---|
| Texto completo, 25 resultados, com foco | 25 | 12 | 50% |
| Título + resumo, com foco | 13 | 7 | 58% |
| Título + resumo, sem foco | 15 | 7 | 50% |
| Texto completo, 50 resultados, com foco | 50 | 19 | 39% |
| **Texto completo, 50 resultados, sem foco (padrão atual)** | 50 | **20** | 41% |

Título + resumo alinharia busca e juiz, mas estreita demais (perde evidência);
o texto completo com mais resultados encontra mais relevantes e a triagem filtra.
Sem o conceito central do tema como termo-base, a busca inicial deu 4%.

Juiz de triagem (v3.1, gabarito de 66 papers):
- **evidência perdida (relevante → lixo): 12%; recall (relevante mantido como
  relevante ou talvez): 88%; redução de trabalho (lixo + descartado): 42%**;
- concordância: 74% no conjunto usado para ajustar o prompt (47 papers);
  67% em papers novos (18); 70% no total após re-execução completa;
- 85% de precisão em "relevante"; nenhum lixo classificado como relevante;
- quase determinístico: execuções seguidas idênticas; uma triagem completa
  posterior variou ~3 de 68 vereditos;
- ~2–3 s por paper na GPU local.

Referência externa: Llama 3 70B teve 77,5% de sensibilidade em triagem de
título/resumo (Research Synthesis Methods). Em triagem, a métrica principal é a
evidência perdida, não a acurácia (LLM4SCREENLIT, 2025).

Lição de método: com modelo de 8B, veredito livre (com ou sem justificativa antes)
ficou em 38–51% de concordância; decompor em perguntas simples, forçar tipos por
esquema e decidir no código elevou para 74%.

## Limitações conhecidas

Busca (V1):
- Um conceito do tema pode não virar termo-base, sem aviso.
- Termos-base descritivos (não pesquisáveis) passam na validação e podem zerar a busca.
- Sinônimos da técnica (ex.: "random forest", "deep learning") não entram sozinhos
  no grupo de ML; a V2 (snowballing) deve compensar parte disso.

Triagem (V1):
- O juiz é restritivo em `mesmo_dominio` quando o contexto varia (outro mineral,
  outro sensor); relevantes perdidos tendem a cair em "talvez".
- Recalibrar quando o gabarito tiver ~150 papers; teste em outro tema pendente.

Loop (V1):
- Só remove (expansões, grupo de foco): limpa consulta ruim, mas não encontra
  papers além da consulta. A V2 por snowballing deve ampliar o recall.
- `loop_log.csv` acumula execuções; distinguir pela coluna `data_hora`.
