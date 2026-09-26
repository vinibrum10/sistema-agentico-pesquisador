# Sistema Agêntico Pesquisador

Workflow agêntico local para apoio à pesquisa científica, agnóstico ao tema.
Modelo local via Ollama (`qwen3:8b`); busca científica no OpenAlex.

## Status atual

Agente 1 V1 concluído: Intake → Planner → Search (OpenAlex) → `results.csv`.

## Fluxo do Agente 1

1. **Intake** — 4 perguntas curtas (tema, objetivo, foco, restrição). O LLM sugere
   redação e termos-base; nada entra no contexto sem confirmação do pesquisador.
2. **Pesquisa ativa** — menu Manter / Ajustar (um campo por vez) / Mudar tema
   (apaga tudo, sem histórico).
3. **Planner** — determinístico, sem LLM: um grupo por termo-base (OR entre
   variantes PT/EN e expansões), AND entre grupos; grupos marcáveis antes de confirmar.
4. **Search** — uma consulta booleana no OpenAlex (25 resultados), gravados com
   upsert por `openalex_id` em `data/active_research/results.csv`.

## Como rodar

Requer Ollama com `qwen3:8b` e `OPENALEX_API_KEY` no `.env`.

    python src\main.py

## Métrica de referência (26/09/2026)

Tema de teste com 3 termos-base (mineral, machine learning, prospecção) + foco em métodos:
56% de resultados relevantes, 36% talvez, 8% descartáveis (classificação manual de 25 títulos).
Sem o conceito central do tema como termo-base, o mesmo teste deu 4%.

## Limitações conhecidas (V1)

- Um conceito do tema pode não virar termo-base, sem aviso.
- Termos-base descritivos (não pesquisáveis) passam na validação e podem zerar a busca.
- Duplicatas da mesma obra com IDs diferentes no OpenAlex (ex.: preprint e publicado).
- Artigos retratados não são filtrados.
- A busca considera texto completo, não só título e resumo.
