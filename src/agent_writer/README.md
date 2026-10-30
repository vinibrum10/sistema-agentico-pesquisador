# agent_writer

Terceiro agente: escreve **uma seção por vez** de um texto científico, em português, usando só os
trechos da busca local (`agent_research/trechos`). Cada frase aponta para o trecho que a sustenta; o
pesquisador revisa tudo. Acesso: menu principal → [5] Escrever uma seção.

## Etapas

| # | Etapa | Quem decide | Onde | Saída |
|---|---|---|---|---|
| 1 | Define a seção: título; o LLM (`qwen3:8b`, tarefa `perguntas_secao`) sugere de 3 a 6 perguntas-guia em português e inglês; o pesquisador confirma, remove, adiciona ou edita (a seção fica com 1 a 6) | pesquisador | `secao.py` (`definir_secao`) | `secao.json` |
| 2 | Busca 5 trechos por pergunta (versão em inglês) na busca local; o mesmo trecho mantém a mesma referência (T1, T2...) em todas as perguntas | código | `evidencias.py` (`buscar_evidencias`) | `evidencias.csv` |
| 3 | Escreve o rascunho: um parágrafo por pergunta, só com os trechos; pergunta qual modelo usar (Enter = padrão da tarefa `escrita_secao`, hoje `deepseek-flash`) | modelo + pesquisador | `rascunho.py` (`escrever_rascunho`) | `rascunho_<modelo>.md` |
| 4 | Verifica o rascunho, sem modelo, e lista o que o pesquisador deve olhar. Roda sozinha no fim da etapa 3 | código | `verificacao.py` (`verificar`) | `revisao_<modelo>.csv` |

Tudo fica em `data/active_research/escrita/<título da seção>/` (nome da pasta com até 60 caracteres).

## Regras do rascunho

- O prompt começa pelos trechos, sempre iguais (CAG), e só depois vêm título, perguntas e regras.
- Toda frase termina com a referência do trecho (`[T3]` ou `[T3, T7]`) ou com `[sem evidência]`.
- O que os trechos não cobrem vira uma frase "Os trechos não mencionam X" com `[sem evidência]`; o
  modelo não completa com conhecimento próprio.
- Sem títulos, numeração, introdução nem lista de referências.
- Modelo local: janela de 12.288 tokens (`CONTEXTO_OLLAMA`); os trechos de uma seção somam cerca de
  7 mil tokens.

## Verificação (`revisao_<modelo>.csv`)

Uma linha por frase, com `paragrafo;frase;refs;problemas;status` (`ok` ou `revisar`). Sete checagens:

1. marcador inexistente (referência que não está em `evidencias.csv`);
2. frase sem fonte (texto depois do último marcador, ou duas frases para um só marcador);
3. número da frase que não aparece no trecho citado (0,710 = 0.710; 100.388 = 100,388);
4. cópia literal: 12 ou mais palavras seguidas iguais ao trecho (`COPIA_MIN_PALAVRAS`, provisório: o
   maior trecho legítimo medido tinha 9 palavras);
5. frase repetida;
6. numeração ou título no início do parágrafo;
7. número de parágrafos diferente do número de perguntas.

A verificação **não** detecta trecho que fala de outro contexto (por exemplo, a pergunta pede um
lugar que nenhum trecho cita) nem afirmação que o trecho não sustenta.

## Regras

- Lê e grava só em `data/active_research/escrita/` e usa `core/`.
- Exceção à regra de agentes não se importarem: `evidencias.py` usa `BuscaLocal` e
  `atualizar_indice` de `agent_research.trechos` (a camada de trechos).
