# Sistema Agêntico Pesquisador

Workflow agêntico local para apoio à pesquisa científica, agnóstico ao tema.
Modelo local via Ollama (`qwen3:8b`, GPU local); busca científica no OpenAlex.
O pesquisador decide nos pontos-chave (human-in-the-loop); o sistema faz o trabalho repetitivo.

## Status atual (29/10/2026)

- `agent_intake`: concluído (V1) — coleta e confirma o contexto da pesquisa.
- `agent_research`: concluído (V1) — plano de busca, busca no OpenAlex, triagem,
  refino por loop e snowballing, com modo automático e tratamento de falhas (Ollama/OpenAlex).
- Camada de modelos (`config/modelos.json`, `src/core/modelos.py`): modelo por tarefa, local
  (Ollama) ou de API, com custo por chamada em `custos.csv` e teto de gasto por execução.
  Hoje o juiz da triagem usa `qwen3:8b`.
- Camada de trechos (RAG): acervo de PDFs (menu "Textos completos"), índice de trechos com
  página (`bge-m3`) e busca híbrida local BM25 + semântica, sem custo. O PaperQA2 foi testado
  e não adotado (ver "Teste da camada de trechos", parte B). A busca é usada pelo agente de escrita e
  pelo `scripts\teste_trechos.py`.
- `agent_writer`: V1 pronto — escreve uma seção por vez, só com trechos da busca local, cada frase
  ligada a um trecho, com verificação determinística do rascunho (ver README da pasta). Modelo de
  escrita padrão: `deepseek-flash` (API, cerca de US$ 0,003 por seção).
- Ainda não existe: juiz de suporte do escritor, agente de código/ML, orquestrador.
  A pasta de um agente só é criada quando ele começa a ser construído.

## Como rodar

Requer Ollama com `qwen3:8b` e `OPENALEX_API_KEY` no `.env`. O agente de escrita usa por padrão a API
do DeepSeek (`DEEPSEEK_API_KEY` no `.env`); o `qwen3:8b` continua selecionável.

    python src\main.py

Menu inicial (pesquisa ativa): [1] Manter · [2] Ajustar (um campo por vez; se tema, objetivo ou foco mudam, pergunta se reavalia a triagem agora ou depois) ·
[3] Começar pesquisa nova (apaga tudo em `data/active_research/`; antes, oferece backup em zip em `data/backups/`).

Ao manter a pesquisa:
- [1] Pesquisar (automático) — busca, triagem e snowballing até parar;
- [2] Revisar resultados — relevantes e "talvez" em `revisao.csv`;
- [3] Textos completos — importa os PDFs de `entrada/`, baixa do OpenAlex os que ele tem
  (US$ 0,01 cada; a chave grátis cobre US$ 1 por dia) e lista os que faltam em `faltantes.csv`;
- [4] Opções avançadas — etapas manuais, uma por vez (plano, triagem, loop, snowballing);
- [5] Escrever uma seção — definir seção (título e perguntas-guia), buscar evidências e escrever o
  rascunho, uma etapa por vez;
- [6] Sair.

Testes (sem Ollama, API ou dados; rodam também no GitHub Actions a cada push). Precisam de
`python -m pip install pytest==9.2.0`:

    python -m pytest

Calibração do juiz:

    python -c "import sys; sys.path.insert(0, 'src'); from agent_research.screening.calibracao import calibrar; calibrar()"

Avaliação do aprendizado (só leitura; precisa de `python -m pip install scikit-learn==1.7.2` e do `bge-m3` no Ollama):

    python scripts\avaliar_aprendizado.py

Comparação de juízes no gabarito (só leitura; não altera o `screening.csv`). Modelos de API
precisam de `python -m pip install langchain-openai==1.6.7` e da chave no `.env`
(`DEEPSEEK_API_KEY`, `GEMINI_API_KEY`); as respostas vão para `comparacao_juizes/` e o custo
de cada chamada paga para `custos.csv`:

    python scripts\comparar_juizes.py

Teste da camada de trechos (etapa 2), parte A: indexa os PDFs de `textos/` em trechos com a
página (`bge-m3` no Ollama; só os PDFs novos) e roda a busca local, sem LLM, nas perguntas de
`teste_trechos/perguntas.csv`. O resultado fica em `teste_trechos/nao_abrir_metodo_a.csv`, que
só deve ser aberto depois da avaliação às cegas:

    python scripts\teste_trechos.py

Parte B: comparação com o PaperQA2 via DeepSeek, em ambiente separado (`.venv-paperqa`), com os
scripts de `scripts/teste_paperqa/` (01 confere a chave, 02 roda o método B, 03 gera a avaliação
às cegas `teste_trechos/avaliacao_cega.html` e o mapa dos métodos). Resultado (21/10/2026): o
PaperQA2 **não foi adotado** — 45 de 50 trechos úteis contra 50 de 50 da busca local (o critério
exigia +15), com 45 de 45 citações conferíveis e US$ 0,0035 por pergunta. Ressalva: os 95
trechos foram marcados como "serve", então o teste não separou os métodos; refazer com
perguntas mais específicas quando existir o agente escritor.

    .venv-paperqa\Scripts\python.exe scripts\teste_paperqa\02_metodo_b.py
    python scripts\teste_paperqa\03_gerar_avaliacao_cega.py

## Estrutura

    src/main.py             ponto de entrada (menus)
    src/core/               código compartilhado (pasta da pesquisa ativa, textos)
    src/agent_intake/       coleta do contexto        -> ver README da pasta
    src/agent_research/     busca, triagem e refino   -> ver README da pasta
    src/agent_writer/       escrita de seções         -> ver README da pasta
    data/active_research/   dados da pesquisa ativa (fora do git)
    tests/                  testes (pytest)
    scripts/                avaliações e experimentos (só leitura)
    config/                 modelo de cada tarefa, preços e teto de gasto (modelos.json)
    docs/                   regras, decisões e fluxo de git (RECOMENDACOES_PROJETO.md)
    CLAUDE.md               manda ler docs/RECOMENDACOES_PROJETO.md

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
| `trechos/` | índice de trechos: `<ID>.jsonl` (trechos com a página do PDF) e `<ID>.npy` (vetores `bge-m3`) |
| `escrita/<seção>/` | uma pasta por seção: `secao.json`, `evidencias.csv` (`;`), `rascunho_<modelo>.md` e `revisao_<modelo>.csv` (`;`) |
| `teste_trechos/` | teste da etapa 2: `perguntas.csv` (`;`) e o resultado de cada método (não abrir antes da avaliação) |

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
- O escritor não detecta trecho que fala de outro contexto nem afirmação que o trecho não sustenta;
  isso depende de um juiz de suporte, que ainda não existe.
- Um conceito do tema pode não virar termo-base, sem aviso.
- Testado com um único tema; teste em outro tema pendente.

## Pendências

1. Ampliar o gabarito com papers sem resumo, recalibrar e manter backup fora de `data/active_research/`.
2. Decidir sobre `screening_v31.csv` (sem uso no código).
