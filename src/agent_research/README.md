# agent_research

Segundo agente: a partir do `context.json` (gerado pelo `agent_intake`), monta o plano
de busca, busca no OpenAlex, tria os papers e entrega `revisao.csv` para o pesquisador.
Prioridade do desenho: **não perder evidência** (recall) antes de acertar tudo (acurácia).

## Etapas

| Etapa | Pasta | O que faz | Saída |
|---|---|---|---|
| Plano | `planner/planner.py` | Determinístico, sem LLM: um grupo por termo-base, OR entre variantes e expansões, AND entre grupos. Grupos de foco e geografia começam desmarcados | consulta booleana |
| Busca | `search/openalex.py` | Uma consulta no OpenAlex (`pyalex`), 50 resultados, upsert por `openalex_id` | `results.csv` |
| Triagem | `screening/filtros.py` | Descarta retratados e duplicatas (mesmo DOI ou título normalizado sem pontuação) | descartes recalculados a cada triagem |
| Triagem | `screening/juiz.py` | LLM lê título + resumo e responde `objeto`, `mesmo_dominio`, `mesmo_problema`, `trecho`; **o veredito é decidido no código** | `screening.csv` |
| Refino | `refino/loop.py` | Rodadas de busca + triagem sobre uma cópia do plano; piso de precisão 0,3, até 3 rodadas; remove expansões ruins | `loop_log.csv` |
| Refino | `refino/snowball.py` | Snowballing a partir dos relevantes; candidatos com pelo menos 2 ligações, máximo 50 | novos papers em `results.csv` |
| Automático | `refino/automatico.py` | Busca, triagem e snowballing (até 3 rodadas) até parar: menos de 5 relevantes novos, precisão abaixo do piso ou sem candidatos | dados atualizados |
| Revisão | `screening/revisao.py` | Reúne relevantes e "talvez" para o pesquisador | `revisao.csv` |
| Calibração | `screening/calibracao.py` | Compara o juiz com `gabarito.csv` | métricas no terminal |

## Regras do juiz

- domínio diferente → lixo;
- mesmo domínio e mesmo problema → relevante;
- mesmo domínio e outro problema → talvez;
- paper sem resumo nunca vira lixo;
- papers já julgados não voltam ao LLM ("erro" é julgado de novo); para retriar tudo,
  apague `screening.csv`;
- se o tema, o objetivo ou o foco mudarem (`triagem_contexto.json`), todos os vereditos
  são refeitos na próxima triagem; os papers já encontrados e a deduplicação permanecem;
- `screening.csv` é gravado a cada paper julgado: Ctrl+C ou uma falha não perdem o que já
  foi julgado, e a triagem continua de onde parou;
- JSON inválido do modelo marca só aquele paper como "erro"; Ollama fora do ar ou modelo
  ausente interrompe a triagem com uma mensagem clara.

## Como usar

Pelo menu (`python src\main.py`): [1] Pesquisar (automático), [2] Revisar resultados,
[3] Opções avançadas (etapas manuais). Descrição completa dos menus no README da raiz.

Calibração:

    python -c "import sys; sys.path.insert(0, 'src'); from agent_research.screening.calibracao import calibrar; calibrar()"

## Métricas (gabarito de 66 papers, 30/09/2026)

Evidência perdida 1 de 16 (6%) · recall 94% · concordância 44 de 66 (67%) ·
precisão em "relevante" 80% · redução de trabalho 25 de 66 (38%).
Só 5 dos 66 do gabarito não têm resumo, contra 143 de 300 no corpus.

## Limitações

- O gabarito subestima papers sem resumo; recalibrar depois de ampliá-lo.
- Falhas do OpenAlex (429, 500, 503) têm 3 novas tentativas com espera; depois a etapa
  para com mensagem, e rodar de novo continua (a busca é upsert e a triagem é retomada).
- Com `screening.csv` aberto no Excel, a gravação falha (Windows bloqueia o arquivo).
- O upsert em `results.csv` substitui a linha inteira e sobrescreve `consulta_origem` e `data_run`.
- O juiz é restritivo em `mesmo_dominio` quando o contexto varia; relevantes perdidos tendem a cair em "talvez".
- `loop_log.csv` acumula execuções; distinguir pela coluna `data_hora`.
- `screening_v31.csv` em `data/active_research/` não é usado pelo código.
