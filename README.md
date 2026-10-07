# Sistema Agêntico Pesquisador

Workflow agêntico local para apoio à pesquisa científica, agnóstico ao tema.
Modelo local via Ollama (`qwen3:8b`, GPU local); busca científica no OpenAlex.
O pesquisador decide nos pontos-chave (human-in-the-loop); o sistema faz o trabalho repetitivo.

## Status atual (30/09/2026)

- `agent_intake`: concluído (V1) — coleta e confirma o contexto da pesquisa.
- `agent_research`: concluído (V1) — plano de busca, busca no OpenAlex, triagem,
  refino por loop e snowballing, com modo automático.
- Em preparação: tratamento de falhas (Ollama/OpenAlex) no modo automático e
  ampliação do gabarito de calibração.
- Ainda não existe: agente de escrita, agente de código/ML, orquestrador.
  A pasta de um agente só é criada quando ele começa a ser construído.

## Como rodar

Requer Ollama com `qwen3:8b` e `OPENALEX_API_KEY` no `.env`.

    python src\main.py

Menu inicial (pesquisa ativa): [1] Manter · [2] Ajustar (um campo por vez; se tema, objetivo ou foco mudam, pergunta se reavalia a triagem agora ou depois) ·
[3] Começar pesquisa nova (apaga tudo em `data/active_research/`; antes, oferece backup em zip em `data/backups/`).

Ao manter a pesquisa:
- [1] Pesquisar (automático) — busca, triagem e snowballing até parar;
- [2] Revisar resultados — relevantes e "talvez" em `revisao.csv`;
- [3] Textos completos — importa os PDFs de `entrada/`, baixa do OpenAlex os que ele tem
  (US$ 0,01 cada; a chave grátis cobre US$ 1 por dia) e lista os que faltam em `faltantes.csv`;
- [4] Opções avançadas — etapas manuais, uma por vez (plano, triagem, loop, snowballing);
- [5] Sair.

Calibração do juiz:

    python -c "import sys; sys.path.insert(0, 'src'); from agent_research.screening.calibracao import calibrar; calibrar()"

Avaliação do aprendizado (só leitura; precisa de `python -m pip install scikit-learn==1.7.2` e do `bge-m3` no Ollama):

    python scripts\avaliar_aprendizado.py

Comparação de juízes no gabarito (só leitura; não altera o `screening.csv`). Modelos de API
precisam de `python -m pip install langchain-openai==1.6.7` e da chave no `.env`
(`DEEPSEEK_API_KEY`, `GEMINI_API_KEY`); as respostas vão para `comparacao_juizes/` e o custo
de cada chamada paga para `custos.csv`:

    python scripts\comparar_juizes.py

## Estrutura

    src/main.py             ponto de entrada (menus)
    src/core/               código compartilhado (pasta da pesquisa ativa, textos)
    src/agent_intake/       coleta do contexto        -> ver README da pasta
    src/agent_research/     busca, triagem e refino   -> ver README da pasta
    data/active_research/   dados da pesquisa ativa (fora do git)
    tests/                  testes (ainda vazio)
    scripts/                avaliações e experimentos (só leitura)
    config/                 modelo de cada tarefa, preços e teto de gasto (modelos.json)

Regras: uma pasta por agente (`agent_<função>`, nome em inglês; arquivos em português
descrevendo o que fazem). Agentes nunca importam um ao outro: conversam por arquivos
em `data/active_research/` e usam `core/`.

## Arquivos de dados (`data/active_research/`)

| Arquivo | Conteúdo |
|---|---|
| `context.json` | contexto confirmado no intake e plano de busca |
| `results.csv` | papers encontrados (upsert por `openalex_id`) |
| `screening.csv` | veredito, justificativa e trecho literal por paper; `tema_confirmado` (`não` = veredito de um tema anterior) e `veredito_anterior` |
| `triagem_contexto.json` | tema, objetivo e foco usados na última triagem; se mudarem, os vereditos são refeitos |
| `loop_log.csv` | histórico de rodadas do loop (acumula execuções; ver `data_hora`) |
| `revisao.csv` | relevantes e "talvez" para o pesquisador revisar (`;`), com `tema_confirmado` e `veredito_anterior` |
| `gabarito.csv` | rótulos manuais r/t/l para calibrar o juiz (`;`) |
| `textos/` | texto completo dos relevantes e "talvez", um PDF por paper: `<ID do OpenAlex>.pdf`; `<ID>.defeituoso` marca um PDF que veio com defeito do OpenAlex (não é baixado de novo) |
| `entrada/` | PDFs que você obteve, com qualquer nome; a opção [3] reconhece pelo DOI ou pelo título e move para `textos/` |
| `faltantes.csv` | relevantes e "talvez" ainda sem texto, relevantes primeiro, com link (`;`) |

## Métricas de referência

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

Juiz de triagem (gabarito de 66 papers, recontado em 30/09/2026):
- **evidência perdida (relevante → lixo): 1 de 16 (6%); recall: 94%;
  redução de trabalho: 25 de 66 (38%)**;
- concordância: 44 de 66 (67%); precisão em "relevante": 80%;
- só 5 dos 66 papers do gabarito não têm resumo, contra 143 de 300 no corpus:
  o gabarito não representa bem a metade do corpus sem resumo;
- ~2–3 s por paper na GPU local.

Referência externa: Llama 3 70B teve 77,5% de sensibilidade em triagem de
título/resumo (Research Synthesis Methods). Em triagem, a métrica principal é a
evidência perdida, não a acurácia (LLM4SCREENLIT, 2025).

Lição de método: com modelo de 8B, veredito livre (com ou sem justificativa antes)
ficou em 38–51% de concordância; decompor em perguntas simples, forçar tipos por
esquema e decidir no código elevou para cerca de 70%.

## Limitações conhecidas

- Metade do corpus não tem resumo; o juiz nunca classifica esses papers como lixo
  (vão para "talvez"), o que aumenta a revisão manual.
- O gabarito é pequeno e pouco representativo de papers sem resumo; recalibrar depois de ampliá-lo.
- Falhas de Ollama/OpenAlex no modo automático ainda não são tratadas.
- Um conceito do tema pode não virar termo-base, sem aviso.
- Testado com um único tema; teste em outro tema pendente.

## Pendências

1. Ampliar o gabarito com papers sem resumo, recalibrar e manter backup fora de `data/active_research/`.
2. Tratar falhas de Ollama/OpenAlex no caminho automático.
3. Decidir sobre `screening_v31.csv` (sem uso no código).
