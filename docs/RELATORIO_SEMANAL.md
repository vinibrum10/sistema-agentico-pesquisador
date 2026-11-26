# Relatório semanal — SAP-5

Entrega local de 26/11/2026, autorizada pelo Vinicius, com base no post Crosswalk
`kp20ry` e no [comentário 10589](https://vinibrum10.atlassian.net/browse/SAP-5?focusedCommentId=10589).
Automação operacional e aceite no Drive continuam **PENDENTES DE APROVAÇÃO**.

## Contrato

- Semana fechada de segunda 00:00 (inclusive) até segunda seguinte 00:00 (exclusive).
  Por padrão, última semana completa. `--inicio` permite reprocessar uma segunda específica.
- Fuso `America/Sao_Paulo`, UTC−03. O gerador usa offset explícito para não exigir
  pacote tzdata no Windows; aceita apenas períodos desde 2020. Rever o contrato se a
  regra do fuso mudar; datas históricas com horário de verão ficam fora do contrato.
- Horário operacional proposto no export: segunda, 08:00 no mesmo fuso.
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
node --test tests/test_n8n_relatorio.cjs
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

## n8n: export preparado, sem importação nem execução real

Arquivo: [n8n/relatorio_semanal.json](n8n/relatorio_semanal.json).

Grafo: Schedule/Manual → Gerar → Preparar → Buscar no Drive → Decidir → Existe?
Se existir, reutiliza ID; se não existir, cria metadados. Ambos seguem para
PATCH do conteúdo pelo ID → Confirmar ID e link. A busca limita por pasta pessoal,
nome exato e `trashed=false`; mais de um resultado, paginação, busca incompleta
ou MIME incompatível interrompem a publicação. O arquivo é Markdown comum.

O export está `active=false`, não contém credenciais e tem placeholders bloqueantes
para SHA e pasta. Os nós HTTP não têm retry automático e interrompem o workflow
na falha. O histórico salva execuções e erros; um registro de metadados criado antes
de uma falha de upload é reutilizado pela próxima execução. Conferir sucesso pelo
nó Confirmar e pelo conteúdo, pois metadados vazios ainda não são um relatório pronto.

Reexecução sequencial usa o mesmo arquivo. **Exige execução serializada**, inclusive
entre disparos manuais, agendados e outros workflows que publiquem na mesma pasta.
Nome no Drive não é chave única: busca + criação não são uma operação atômica.
O export não implementa bloqueio distribuído. Configurar e testar exclusão mútua
no ambiente operacional antes de ativar; concorrência pode produzir duplicatas,
detectadas na busca posterior. Não prometer idempotência concorrente.

### Preparação operacional — PENDENTE DE APROVAÇÃO

1. Confirmar dia/horário/fuso, pasta pessoal exclusiva de relatórios e política de
   retenção do histórico. Não usar dados internos da CELEO ou SSO.
2. Confirmar n8n self-hosted, versão dos nós do export e acesso local controlado.
   O Execute Command não existe no n8n Cloud; em Docker executa no container e
   precisa de Python e mounts próprios. Desde n8n 2.0 vem desabilitado por padrão;
   eventual habilitação/instalação depende de aprovação, não foi feita aqui.
3. Importar inativo; conferir parâmetros no editor. Substituir caminhos e SHA no
   comando Gerar por caminhos estáticos revisados; não interpolar texto de posts
   ou entradas externas em shell. Para reprocessar semana antiga, informar
   `--inicio AAAA-MM-DD` no comando. Trocar o placeholder de pasta no nó Preparar.
4. Selecionar OAuth pessoal Google Drive nos três nós HTTP. Credenciais ficam no
   n8n, nunca no export/repo. Montar código e dados pessoais para leitura; o
   gerador não precisa de permissão de escrita. Não configurar `.env` para ele.
5. Configurar serialização/exclusão mútua e validar com fixtures numa pasta de teste.
   Executar manualmente, conferir contagens e conteúdo; repetir e conferir o mesmo
   ID; simular falha de publicação e confirmar erro no histórico e recuperação sem
   duplicação. Testar disparo agendado, fuso e ciclo semanal completo.
6. Só depois de aprovados os testes operacionais, ativar/publicar e registrar os
   links/evidências no Jira. Aplicar Marcos é atribuição exclusiva do Vinicius.

Os testes Node executam o grafo e os nós Code exportados com HTTP simulado em memória.
Não validam importabilidade em uma versão específica do n8n, OAuth, permissões,
conectividade, serialização real nem o agendador. Esses aceites permanecem abertos.

Fontes oficiais consultadas em 26/11/2026:
[Execute Command](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executecommand/),
[Schedule Trigger](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.scheduletrigger/),
[busca de arquivos Drive](https://developers.google.com/workspace/drive/api/guides/search-files),
[upload/atualização Drive](https://developers.google.com/workspace/drive/api/guides/manage-uploads).
