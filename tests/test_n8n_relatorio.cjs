// Simulação local dos nós Code e do contrato HTTP. Nenhum serviço ou n8n é iniciado.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {test} = require('node:test');
const w = JSON.parse(fs.readFileSync(path.join(__dirname, '../docs/n8n/relatorio_semanal.json'), 'utf8'));
const nodes = Object.fromEntries(w.nodes.map(n => [n.name, n]));
const report = {schema_version: 1, nome: 'sap-semanal_2026-11-16_2026-11-23.md', markdown: '# SAP\n', sha_origem: 'a'.repeat(40)};

function code(name, input, prepared, configure = true) {
  let source = nodes[name].parameters.jsCode;
  if (configure) source = source.replace('PREENCHER_ID_PASTA_PESSOAL', 'pasta_pessoal');
  return new Function('$input', '$', source)(
    {first: () => ({json: input})}, () => ({first: () => ({json: prepared})})
  )[0].json;
}

// Pequeno executor do grafo exportado. HTTP é substituído por um Drive em memória.
function run(files, {failure, reportOverride, responseOverride} = {}) {
  const calls = [], context = {};
  let current = 'Manual', data = {};
  while (current) {
    const n = nodes[current];
    let branch = 0;
    if (n.type.endsWith('executeCommand')) {
      data = {exitCode: 0, stdout: JSON.stringify(reportOverride || report)};
    } else if (n.type.endsWith('.code')) {
      data = code(current, data, context.Preparar);
    } else if (n.type.endsWith('.if')) {
      assert.equal(n.parameters.conditions.conditions[0].leftValue, '={{ $json.existe }}');
      branch = data.existe ? 0 : 1;
    } else if (n.type.endsWith('.httpRequest')) {
      calls.push(current);
      if (failure === current) throw new Error('HTTP simulado indisponível');
      if (current === 'Buscar') {
        data = responseOverride || {files: files.map(f => ({id: f.id, mimeType: f.mimeType}))};
      } else if (current === 'Criar metadados') {
        const f = {id: 'file_1', name: data.nome, mimeType: 'text/markdown'};
        files.push(f);
        data = {id: f.id};
      } else if (current === 'Atualizar conteudo') {
        files.find(f => f.id === data.id).content = context.Preparar.markdown;
        data = {id: data.id};
      }
    }
    context[current] = data;
    current = w.connections[current]?.main[branch]?.[0]?.node;
  }
  return {data, calls};
}

test('export inativo, sem credenciais, fuso e horario explícitos', () => {
  assert.equal(w.active, false);
  assert.equal(w.settings.timezone, 'America/Sao_Paulo');
  assert.equal(nodes['Segunda 08h'].parameters.rule.interval[0].expression, '0 8 * * 1');
  assert.equal(w.settings.saveDataErrorExecution, 'all');
  assert.ok(w.nodes.every(n => !n.credentials));
  assert.ok(w.nodes.filter(n => n.type.endsWith('httpRequest')).every(n => n.onError === 'stopWorkflow' && n.retryOnFail === false));
});

test('preparação bloqueia placeholders, falha e JSON inválido antes de qualquer HTTP', () => {
  assert.throws(() => code('Preparar', {exitCode: 0, stdout: JSON.stringify(report)}, null, false), /Pasta pessoal/);
  assert.throws(() => code('Preparar', {exitCode: 1, stdout: ''}), /Falha do gerador/);
  assert.throws(() => code('Preparar', {exitCode: 0, stdout: 'invalido'}), SyntaxError);
  assert.throws(() => run([], {reportOverride: {...report, nome: "nome' injetado"}}), /Contrato inválido/);
});

test('busca restrita a pasta, nome e arquivos não excluídos; contratos HTTP', () => {
  const r = code('Preparar', {exitCode: 0, stdout: JSON.stringify(report)});
  assert.equal(r.query, "'pasta_pessoal' in parents and trashed = false and name = '" + report.nome + "'");
  assert.equal(nodes.Buscar.parameters.queryParameters.parameters.find(p => p.name === 'pageSize').value, '2');
  assert.equal(nodes['Criar metadados'].parameters.method, 'POST');
  assert.equal(nodes['Atualizar conteudo'].parameters.method, 'PATCH');
  assert.equal(nodes['Atualizar conteudo'].parameters.rawContentType, 'text/markdown; charset=utf-8');
});

test('primeira publicação e reexecução usam o mesmo ID sem duplicar', () => {
  const files = [];
  const a = run(files), b = run(files);
  assert.equal(files.length, 1);
  assert.equal(files[0].content, report.markdown);
  assert.equal(a.data.id, b.data.id);
  assert.ok(a.calls.includes('Criar metadados'));
  assert.ok(!b.calls.includes('Criar metadados'));
  assert.equal(b.data.link, 'https://drive.google.com/file/d/file_1/view');
});

test('falha no upload fica observável e reexecução reutiliza metadados', () => {
  const files = [];
  assert.throws(() => run(files, {failure: 'Atualizar conteudo'}), /HTTP simulado/);
  assert.equal(files.length, 1);
  assert.equal(files[0].content, undefined);
  const r = run(files);
  assert.equal(files.length, 1);
  assert.ok(!r.calls.includes('Criar metadados'));
  assert.equal(r.data.status, 'publicado');
});

test('falha de busca não cria arquivo', () => {
  const files = [];
  assert.throws(() => run(files, {failure: 'Buscar'}), /HTTP simulado/);
  assert.equal(files.length, 0);
});

test('duplicatas, paginação, busca incompleta e MIME incompatível interrompem', () => {
  for (const responseOverride of [
    {files: [{id: '1'}, {id: '2'}]}, {files: [], nextPageToken: 'next'},
    {files: [], incompleteSearch: true}, {}, {files: [{id: '1', mimeType: 'application/vnd.google-apps.document'}]},
  ]) assert.throws(() => run([], {responseOverride}));
});

test('publicação exige confirmação de ID', () => {
  assert.throws(() => code('Confirmar', {}, report), /sem confirmação/);
});
