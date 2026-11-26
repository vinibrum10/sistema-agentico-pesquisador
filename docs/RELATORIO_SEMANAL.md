# Relatório semanal — SAP-5

Entrega local de 26/11/2026, autorizada pelo Vinicius, com base no post Crosswalk
`kp20ry` e no [comentário 10589](https://vinibrum10.atlassian.net/browse/SAP-5?focusedCommentId=10589).
Automação pelo GitHub Actions (o n8n foi descontinuado em 26/11/2026). Envio ao Drive
continua **PENDENTE DE APROVAÇÃO**.

## Contrato

- Semana fechada de segunda 00:00 (inclusive) até segunda seguinte 00:00 (exclusive).
  Por padrão, última semana completa. `--inicio` permite reprocessar uma segunda específica.
- Fuso `America/Sao_Paulo`, UTC−03. O gerador usa offset explícito para não exigir
  pacote tzdata no Windows; aceita apenas períodos desde 2020. Rever o contrato se a
  regra do fuso mudar; datas históricas com horário de verão ficam fora do contrato.
- Horário operacional: segunda, 08:00 no mesmo fuso, pelo GitHub Actions (cron `0 11 * * 1` UTC).
- Nome estável: `sap-semanal_<inicio>_<fim-exclusivo>.md`.
- Origem obrigatória: pasta `active_research` explícita e SHA completo informado.
  O SHA identifica o código informado pelo chamador, não certifica os dados nem
  alterações ainda não commitadas. O operador deve conferir checkout limpo e SHA.
- Saída em stdout: Markdown ou JSON UTF-8 com `schema_version=1`, período, nome,
  fuso, SHA, métricas, avisos e Markdown. Não há argumento de destino nem escrita
  no gerador; redirecionamentos são responsabilidade do chamador.
- Apenas biblioteca padrão Python >=3.12. Não carrega `.env`, modelos, agentes,
  configurações de modelo, contexto, PDFs ou conteúdo dos textos escritos.

### Campos e limites de interpretação

| Grupo | Origem | Significado |
|---|---|---|
| Atividade | `results.csv`, `data_run` | IDs distintos com a data mantida no upsert dentro da semana; não é um histórico de descobertas |
| Rodadas | `loop_log.csv`, `data_hora` | Linhas da semana; soma de `total` e `erro` pode contar o mesmo paper várias vezes |
| Custos | `custos.csv`, `quando`, `custo_usd` | Soma decimal de registros válidos e número de chamadas pagas registradas; sem inferir faturamento nem custo local |
| Triagem | `screening.csv` | Distribuição atual por veredito conhecido; sem atribuição semanal |
| Escrita | metadados `escrita/*/texto_*.md` e `revisao_*.csv` | Inventário de arquivos, não seções aprovadas ou atividade semanal; conteúdo e mtime não são lidos como eventos |
| Experimentos | `experimentos/*/execucao_<data>/experimentos.csv` (`;`) | Inventário de execuções e contagem de tentativas/erros das execuções iniciadas na semana; sem data individual por tentativa |
| Erros | rodadas de triagem e tentativas de experimento | Somente erros explicitamente registrados; não há log global de falhas |
| Pendências | lista documental no gerador | SAP-1 a SAP-5; não consulta nem acompanha status vivo do Jira |

Datas sem offset são interpretadas como São Paulo; datas com offset são convertidas.
CSVs aceitam BOM UTF-8. Cabeçalho incompatível, data/custo inválidos, linha incompleta,
origem ausente ou leitura indisponível geram avisos sem retransmitir valores brutos.
Valores zero com aviso de ausência não comprovam ausência de atividade. Valores
inválidos são excluídos, tornando as somas parciais. Semana sem eventos produz
relatório explícito de ausência observada e cobertura. O gerador ignora links
simbólicos de arquivos e caminhos resolvidos fora da origem. A origem deve ser
uma cópia pessoal estável, sem edição concorrente; não há snapshot transacional.

Nenhum título, resumo, trecho, código experimental, pergunta ou justificativa é
incluído na saída. Inventários são atuais: reprocessar uma semana antiga depois
de alterar as fontes pode mudar os números. Fontes iguais + período + SHA iguais
produzem saída idêntica.

## Executar localmente com dados sintéticos

Na raiz do repo, PowerShell:

```powershell
python -B scripts/validar_local.py
python -B scripts/validar_local.py --base-deterministica
```

O primeiro comando executa os nove testes novos, inclusive o CLI em subprocesso,
criando seus temporários em `.validacao-local/` (fora do git). O terceiro reutiliza
os pacotes locais de `.venv/Lib/site-packages` para testar texto, verificação,
executor e relatório. Rede e subprocessos externos ao Python são bloqueados:
os quatro testes Docker são pulados sem consultar o serviço.

Exemplo de CLI somente leitura, usando uma origem inexistente de teste para
demonstrar os avisos sem ler a pesquisa real:

```powershell
$shaRelatorio = git rev-parse HEAD
python -B scripts/gerar_relatorio_semanal.py --dados .validacao-local/origem-ausente --inicio 2026-11-16 --sha-origem $shaRelatorio --formato json
```

Para dados efetivos, o operador deverá substituir `--dados` por uma cópia pessoal
de homologação aprovada. Esta entrega não executou o gerador contra `data/` real.

## GitHub Actions (substitui o n8n desde 26/11/2026)

O fluxo n8n foi **descontinuado** por decisão do Vinicius (26/11/2026). O export
`docs/n8n/relatorio_semanal.json` e o teste Node `tests/test_n8n_relatorio.cjs`
foram removidos; ficam no histórico do git (commit `6c8a8d2`).

Arquivo: [`.github/workflows/relatorio-semanal.yml`](../.github/workflows/relatorio-semanal.yml).

- **Quando:** toda segunda às 08:00 de São Paulo (cron `0 11 * * 1` em UTC; São Paulo
  está em UTC−03 sem horário de verão). Também roda manualmente (`workflow_dispatch`,
  com `inicio` opcional `AAAA-MM-DD` para reprocessar uma semana) e em pull requests
  que mudem o workflow ou o gerador.
- **O que faz:** roda `scripts/gerar_relatorio_semanal.py` com `--dados data/active_research`
  e `--sha-origem $GITHUB_SHA`, grava `sap-semanal_<inicio>_<fim>.md` e o JSON em `saida/`,
  mostra o relatório no resumo da execução e publica `saida/` como artifact
  `relatorio-semanal-<n>` (retenção de 90 dias).
- **Sem secrets:** permissão `contents: read`, sem credenciais e sem `.env`.
- **Limite conhecido — dados:** `data/active_research/` fica fora do git, então no Actions
  a origem não existe. O workflow avisa (`::warning` "Dados ausentes"), põe uma nota de
  atenção no topo do relatório e gera o relatório só com avisos e métricas zeradas.
  Para números reais: rodar o gerador localmente (comando acima) ou aprovar uma fonte de
  dados para o Actions (ex.: armazenamento privado acessado com secret).
- Execuções simultâneas são serializadas por `concurrency` (sem cancelar a anterior).

### Pendente de aprovação

1. **Envio ao Drive:** etapa futura do workflow, com credencial guardada em GitHub
   Secrets. Só com aprovação do Vinicius; não usar dados internos da CELEO ou SSO.
2. **Fonte de dados no Actions:** decidir se o relatório semanal deve ter números reais
   no Actions e de onde virão os dados.
3. **Marcos:** aplicar a proposta de `SAP-5_MARCOS_PROPOSTA.md` na seção 9 (só o Vinicius).
