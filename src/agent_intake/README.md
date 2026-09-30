# agent_intake

Primeiro agente: transforma as respostas do pesquisador em um **contexto confirmado**
(`data/active_research/context.json`), que alimenta o `agent_research`.
Nada entra no contexto sem confirmação humana.

## Etapas

| # | Etapa | Quem decide | Onde |
|---|---|---|---|
| 1 | 4 perguntas curtas: tema, objetivo, foco, restrição | pesquisador | `intake.py` (`executar_intake`) |
| 2 | LLM (chamada 1) sugere reformulações de tema, objetivo e restrição; o pesquisador escolhe original ou sugestão | pesquisador | `intake.py` |
| 3 | LLM (chamada 2) propõe termos-base, idiomas e expansões; o código valida (termo curto, ligado ao contexto) e mostra os rejeitados | código + pesquisador | `intake.py` |
| 4 | Pesquisador confirma foco, idiomas, termos-base (remover, adicionar, editar) e expansões | pesquisador | `intake.py` |
| 5 | Contexto final exibido e gravado só após confirmação | pesquisador | `intake.py` |

O foco tem 4 opções: panorama geral, métodos e técnicas, dados e datasets, ainda não sei.

## Ajuste de pesquisa existente

`ajuste.py` (menu principal → [2] Ajustar): altera **um campo por vez** entre tema,
objetivo, foco, restrição, idiomas e termos-base. Mostra antes/depois e só grava
depois da confirmação final; cancelar não altera nada.

## Regras

- Modelo local `qwen3:8b` via Ollama, temperatura 0, saída JSON (`criar_modelo`).
- O LLM só sugere; validação e decisão ficam no código e no pesquisador.
- Um termo-base é um conceito curto (até 4 palavras), não a frase do tema.
- Lê e grava só via `core/pesquisa_ativa.py`; não importa outros agentes.

## Saída

`data/active_research/context.json` — respostas do intake, texto oficial confirmado,
foco, idiomas e termos-base com variantes/expansões.

## Limitações

- Um conceito do tema pode não virar termo-base, sem aviso.
- Termos-base descritivos (não pesquisáveis) passam na validação e podem zerar a busca.
- Nome do modelo repetido em `intake.py` e em `agent_research/screening/juiz.py`.
