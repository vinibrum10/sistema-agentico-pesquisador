# Recomendações do Projeto — Sistema Agêntico Pesquisador

Documento de referência para o Vinicius e para o Claude. O Claude lê este arquivo no
início de toda sessão, antes de propor ou alterar qualquer coisa.
Última atualização: 29/10/2026.

## 1. Regras para o Claude

1. **Ordem de verdade:** código e git > este documento > conversa. Se este documento
   divergir do git, vale o git, e o Claude avisa.
2. **Nada sem sinal verde.** Concordar com um desenho não autoriza implementar.
3. **Sem chute.** Ler o arquivo antes de afirmar que algo existe e citar o caminho.
   Pesquisa externa sempre com fonte. Se não souber, dizer que não sabe.
4. **Diretrizes Karpathy:** pensar antes de codar (explicitar suposições), código mínimo,
   mudanças cirúrgicas (cada linha vem do pedido), plano curto "etapa → verificação".
5. **Uma etapa por vez.** Testar e fechar antes de avançar; não nomear etapas futuras.
6. **Sistema agnóstico ao tema.** O tema no `context.json` é só entrada de teste,
   não é a tese. Nada de tema escrito no código ou nos prompts.
7. **Dados:** trabalhar sempre na homologação. Nunca rodar "[3] Começar pesquisa nova"
   nem apagar dados sem pedir antes.
8. **Decisões registradas (seção 4) não são revertidas pelo Claude.** Se discordar,
   propõe uma nova decisão com evidência.
9. **Ao entregar código:** dar o comando exato para rodar no terminal do VS Code.
10. **Fim de sessão:** propor a atualização da seção 3 (Estado atual).

## 2. Visão e princípios (só o Vinicius altera)

- Equipe de agentes reutilizável para **qualquer tese**; o pesquisador decide nos
  pontos-chave e revisa tudo o que a IA produz.
- Agentes de código/ML são **opcionais** (nem toda tese tem programação).
- **Custo baixo:** modelo local (Ollama) por padrão; API barata (ex.: DeepSeek) só
  onde um teste provar ganho.
- Nada inferido pela IA entra no contexto sem aprovação do pesquisador.
- **Rastreabilidade:** cada frase escrita pelo sistema aponta para um trecho com fonte.
- Agentes não importam um ao outro: conversam por arquivos em `data/` e usam `core/`.

## 3. Estado atual (29/10/2026 — main em `9f86df8`, igual a origin/main)

| Parte | Situação |
|---|---|
| `agent_intake` | Concluído (V1) |
| `agent_research` | Concluído (V1): plano, OpenAlex, triagem, loop, snowballing |
| Camada de modelos | Concluída: `config/modelos.json`, custo em `custos.csv` |
| Camada de trechos (RAG) | Concluída: índice `bge-m3` + busca híbrida BM25 local |
| `agent_writer` | Etapas 1 (`secao.py`) e 2 (`evidencias.py`) na main. **Etapa 3 iniciada em 23/10, guardada na branch `feat/escritor-etapa3` (`d5dda51`, sem merge):** `src/agent_writer/rascunho.py` (novo), tarefa `escrita_secao` em `config/modelos.json` e parâmetro `contexto` em `src/core/modelos.py`. Já gerou `rascunho_qwen3_8b.md` e `rascunho_deepseek-flash.md` na seção de teste; a comparação não foi avaliada; não está ligado ao menu |
| Ambiente (seção 8) | Worktree criada em `.claude\worktrees\trabalho`; `CLAUDE.md` na main; bloqueios na branch `feat/ambiente-bloqueios`; faltam homologação, testes e Actions |
| `tests/` | Vazio |

**Divergência a resolver:** `rascunho.py` ainda não segue a decisão 5.1 (CAG): no
prompt, os trechos vêm depois do título e das perguntas-guia, e não no início.

**Próximo passo:** testar os bloqueios da 8.3 e seguir para a 8.4.

## 4. Decisões registradas

| Data | Decisão | Motivo |
|---|---|---|
| 26/09 | Sistema agnóstico ao tema | Servir a qualquer tese |
| 27/09 | Triagem medida por evidência perdida (recall), não acurácia | LLM4SCREENLIT 2025 |
| 27/09 | Paper sem resumo nunca vira "lixo"; vai para "talvez" | Não perder evidência |
| 06/10 | API barata aceita (~US$ 5/mês) onde provar ganho | Custo-benefício |
| 21/10 | PaperQA2 não adotado; busca híbrida local | 50/50 trechos úteis contra 45/50 |
| 21/10 | Escritor V1: uma seção por vez, frase ligada a trecho, verificação determinística + juiz que só marca, saída Markdown + CSV, texto em português | Rastreabilidade |
| 29/10 | **RAG para buscar, CAG para escrever** (ver 5.1) | Corpus grande e crescente; cache barato na escrita |
| 29/10 | Uma worktree fixa; Claude faz commit na branch; Vinicius faz merge e push | Isolamento sem várias pastas |
| 29/10 | Produção e homologação separadas, escolhidas pelo `.env`; sem banco por ora | Testes não tocam a pesquisa real |
| 29/10 | GitHub Actions só para rodar testes antes do merge | Verificação automática |
| 29/10 | Orquestrador em LangGraph; n8n só como camada operacional (agendar, Drive, avisos) | O n8n não alcança os agentes Python |

## 5. Arquitetura

### 5.1 RAG e CAG

- **RAG (corpus):** busca híbrida local encontra os trechos, cada um com ID (T1, T2...).
  O CAG do corpus inteiro não serve: modelos de 8B têm contexto efetivo na faixa de 32K, o corpus
  cresce a cada snowballing e a citação exige trechos identificados.
- **CAG (escrita):** o pacote de evidências da seção vai **no início do prompt, sempre
  igual** (mesmo texto, mesma ordem); as instruções variáveis vêm depois. Rascunho,
  juiz e revisões reaproveitam esse prefixo, e o cache automático do DeepSeek reduz o
  custo de entrada.

### 5.2 Stack

- **Em uso:** LangChain (`langchain_ollama`, `langchain_openai`, `langchain_core`),
  Ollama `qwen3:8b` e `bge-m3`, pyalex.
- **Declarado e ainda não usado:** `langgraph` (entra no orquestrador) e o pacote
  `langchain` (só os subpacotes são importados). Revisar quando o orquestrador entrar.

## 6. Fluxo de trabalho

```
7-sistema_agentico_pesquisador\            ← main (Vinicius roda e faz merge)
└── .claude\worktrees\trabalho\            ← única worktree do Claude (fora do git)
```

1. Uma etapa = uma branch, aberta **dentro da worktree** (`git switch -c feat/<etapa> main`).
2. O Claude codifica e testa na worktree, usando a homologação.
3. O Claude faz commit na branch → o GitHub Actions roda os testes.
4. Com os testes passando, o Vinicius faz o merge na main e o push.
5. A próxima etapa abre uma branch nova a partir da main atualizada (as duas pastas
   usam o mesmo repositório, então a main local já aparece na worktree).
6. O Claude nunca faz merge, push, nem troca para a main dentro da worktree.
7. O Claude Code é iniciado **dentro da worktree** (`cd .claude\worktrees\trabalho`;
   `claude`). O `.claude/settings.json` só é lido da pasta onde a sessão começa, sem
   procurar nas pastas acima; por isso ele é versionado (exceção no `.gitignore`) e
   existe nas duas pastas.

## 7. Produção e homologação

- **Produção:** `data/` da pasta principal (`data/active_research/`, ~462 MB em 29/10).
  É a pesquisa real; só o Vinicius roda nela.
- **Homologação:** cópia da produção numa pasta separada, fora do git. É onde o Claude
  roda e testa.
- **Escolha pelo `.env`:** uma variável (`PASTA_DADOS`) diz qual pasta usar; sem a
  variável, vale `data/` (comportamento de hoje). O `.env` da pasta principal não tem a
  variável; o `.env` da worktree aponta para a homologação.
- O caminho dos dados é montado em um só lugar: `src/core/pesquisa_ativa.py`
  (`ACTIVE_RESEARCH_DIR` e `BACKUPS_DIR`). Hoje esse arquivo não carrega o `.env`
  (quem carrega é `src/core/modelos.py`, que importa o `pesquisa_ativa`); a mudança
  precisa tratar isso. Os scripts antigos de `scripts/teste_paperqa/` montam o caminho
  por conta própria e ficam de fora.
- A homologação é recopiada da produção quando o Vinicius pedir; nunca o contrário.

## 8. Preparar o ambiente

Uma etapa por vez, cada uma com verificação. Situação em 29/10: 8.0 feita (`d5dda51`); 8.1 feita (worktree em `9f86df8`, HEAD destacado); 8.2 feita (`7afea9e`, na main); 8.3 com commit na branch `feat/ambiente-bloqueios`, teste ao vivo pendente.

| # | Etapa | Verificação |
|---|---|---|
| 8.0 | Guardar a etapa 3 do escritor: branch `feat/escritor-etapa3` com `rascunho.py`, `config/modelos.json` e `src/core/modelos.py` | main limpa no `git status`; branch 1 commit à frente da main |
| 8.1 | Criar a worktree `.claude\worktrees\trabalho` a partir da main | `git worktree list` mostra as duas pastas; a pasta principal não acusa arquivos novos (`.claude/` já está no `.gitignore`) |
| 8.2 | `CLAUDE.md` na raiz (versionado), curto, mandando ler este documento | o arquivo aparece na worktree depois do merge |
| 8.3 | Bloqueios do Claude Code em `.claude/settings.json`: negar `git push`, `git merge`, troca para a main, escrita em `data/` de produção e leitura do `.env` | tentar cada ação proibida e ver o bloqueio |
| 8.4 | Homologação (seção 7): variável `PASTA_DADOS` + cópia dos dados | na worktree o caminho de dados aponta para a homologação; na pasta principal, para `data/` |
| 8.5 | Testes com `pytest` em `tests/`, só de funções determinísticas (sem Ollama, sem API, sem dados) | `pytest` passa local |
| 8.6 | GitHub Actions (`.github/workflows/testes.yml`) rodando o `pytest` a cada push de branch `feat/**` | commit aparece verde no GitHub |

Observações:
- Bloqueios da 8.3 (`.claude/settings.json`): negam `git push`, `git merge`, troca
  para a main (no Bash e no PowerShell), edição em `data/` da pasta principal, leitura
  de `.env` e edição do próprio `settings.json`. Limite: segundo a documentação do
  Claude Code, as regras valem para o comando como o Claude o escreve e para as
  ferramentas internas; não seguram variações (`git -C . push`) nem um script Python
  que grave arquivos por conta própria. São trava de segurança, não muralha.
- `pytest` não está nas dependências do `pyproject.toml`; entra como dependência de
  desenvolvimento na 8.5.
- Comandos de git que gravam caminhos (ex.: `git worktree add`) rodam no git do
  Windows (Desktop Commander), não no git do Linux da ponte, para não gravar caminhos
  `/sessions/...`.
- Quando o Claude trabalha pela ponte do app (pasta conectada), apagar arquivos vem
  bloqueado por padrão e o git precisa apagar os próprios arquivos de trava; o
  Vinicius autoriza a exclusão na pasta antes do primeiro commit.

## 9. Marcos (só o Vinicius altera)

_A preencher._
