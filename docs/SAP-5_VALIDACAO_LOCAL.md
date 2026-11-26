# Evidências locais — 26/11/2026

Branch mantida: `sap-5-fechamento`; base local
`eddc90101f6deb4650eb29ef941476ce9cd96738`. Sem fetch, troca de branch, push,
merge ou rebase. Nenhum dado interno da CELEO ou SSO foi usado.

Antes das alterações: lidos post Crosswalk `kp20ry`, comentário Jira `10589`,
`CLAUDE.md` e `docs/RECOMENDACOES_PROJETO.md`.

| Verificação | Resultado |
|---|---|
| `python -B scripts/validar_local.py` | 9 testes novos passaram com Python 3.14.5, biblioteca padrão |
| `python -B scripts/validar_local.py --base-deterministica` | 27 passaram (inclui os 9 novos), 4 Docker pulados por bloqueio local |
| `node --test tests/test_n8n_relatorio.cjs` | 8 testes com Node 24.17.0 passaram; HTTP em memória |
| Suíte completa `--suite-existente` | Bloqueada na coleta de 6 módulos: dependências do `.venv` Python 3.12 não compatíveis com Python 3.14 (`pydantic_core._pydantic_core` indisponível) |
| Python do `.venv` | Executável-base Python312 não localizado no caminho registrado |
| Teste legado `test_pesquisa_ativa.py` isolado na seleção inicial | Falhou com WinError 6 no subprocesso sob captura do pytest; não integra a seleção final compatível, não declarado aprovado |
| Git add/commit local | Ambos bloqueados ao criar `.git/index.lock`: Permission denied. Nenhum commit criado |
| Seção 9 | Comparação com `git show HEAD:docs/RECOMENDACOES_PROJETO.md`: conteúdo integralmente preservado |
| CLI manual com origem ausente sintética | JSON válido, 7 avisos de cobertura; nenhuma pasta de dados criada |
| Sintaxe/diff | AST dos quatro arquivos Python novos válida; `git diff --check` sem erros nos arquivos rastreados |

O validador desabilita dotenv antes de importar os módulos existentes; bloqueia
abertura de `.env`/extensões de chave, conexões de rede, Docker e outros executáveis;
direciona temporários, dados isolados e log para `.validacao-local/`. Não é um sandbox
para código hostil: as restrições são verificações adicionais ao ambiente gerenciado.
Os testes novos usam somente fixtures sintéticas; o teste CLI não importa os módulos
existentes. Não houve leitura de `.env`/chaves, execução de agentes/modelos, instalação,
consulta dos dados de pesquisa reais, envio ao Drive ou execução de instância n8n.

## PENDENTE DE APROVAÇÃO / ação do Vinicius

- Restabelecer um Python/dependências locais compatíveis e executar a suíte completa.
  Nenhuma instalação local ou global foi realizada.
- Permitir gravação Git para realizar os commits locais autorizados (sem push).
  A permissão de escrita do ambiente exclui `.git`; não houve tentativa de contorno.
- Revisar e executar a configuração operacional n8n/Drive conforme
  `RELATORIO_SEMANAL.md`: acesso pessoal, caminhos, mounts, horário, OAuth,
  importação, eventual instalação/habilitação de nós e serialização.
- Demonstrar os aceites reais: publicação/link/conteúdo e contagens, agendamento,
  reexecução, falha e recuperação, ciclo semanal. Nada disso foi executado.
- Vinicius revisar/aplicar `SAP-5_MARCOS_PROPOSTA.md` na seção 9.

Divisão sugerida de commits, ainda **não realizados**:

1. `SAP-5: gerar relatorio semanal somente leitura e validar offline`
   — gerador, CLI, testes Python, validador e ignore dos temporários.
2. `SAP-5: preparar workflow n8n inativo e simulacoes de publicacao`
   — export n8n e testes Node.
3. `SAP-5: documentar entrega local estado e proposta de marcos`
   — README, seção 3, contrato, evidências e proposta separada.

O status do Jira não foi alterado. A entrega local não comprova conclusão operacional
do SAP-5 nem os aceites de SAP-1 a SAP-4.

## Registros externos autorizados

- Jira: [comentário 10590](https://vinibrum10.atlassian.net/browse/SAP-5?focusedCommentId=10590),
  criado com o resumo por passo, resultados, impedimento dos commits e pendências.
- Crosswalk: post `qf0tzr`, agente `Codex (CLI)`, seção
  `grokclaudevinibrum10/agents`, resposta a `kp20ry`, mesma síntese com link Jira.
  Chave de idempotência: `codex-sap5-exec-20261126`.
