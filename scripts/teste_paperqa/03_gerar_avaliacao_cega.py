r"""Passo 4 do teste PaperQA2: gera a avaliação às cegas (página HTML) e o mapa dos métodos.

Junta os trechos do método A (busca local) e do método B (PaperQA2), embaralha dentro de cada
pergunta e escreve, em data/active_research/teste_trechos/:

    avaliacao_cega.html           abra no navegador: marque S (serve) ou N (não serve) em cada trecho
    mapa_metodos_NAO_ABRIR.csv    qual trecho veio de qual método: só abra depois de avaliar

Só usa a biblioteca padrão, então roda em qualquer ambiente do projeto. Uso:

    python scripts/teste_paperqa/03_gerar_avaliacao_cega.py
"""

import csv
import hashlib
import json
import random
import re
from pathlib import Path


RAIZ = Path(__file__).resolve().parent.parent.parent
TESTE_DIR = RAIZ / "data" / "active_research" / "teste_trechos"
PERGUNTAS_FILE = TESTE_DIR / "perguntas.csv"
ARQUIVO_A = TESTE_DIR / "nao_abrir_metodo_a.csv"
ARQUIVO_B = TESTE_DIR / "nao_abrir_metodo_b.csv"
SAIDA_HTML = TESTE_DIR / "avaliacao_cega.html"
SAIDA_MAPA = TESTE_DIR / "mapa_metodos_NAO_ABRIR.csv"
SEMENTE = 2026  # a mesma ordem sempre que o script rodar com os mesmos arquivos
COLUNAS_MAPA = ["id", "pergunta_id", "metodo", "trecho_id_original", "paper", "pagina_original", "escore"]

PAGINA = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Avaliação às cegas</title>
<style>
  :root { --fundo:#f6f5f1; --cartao:#fff; --texto:#1d1d1b; --suave:#6b6a64; --linha:#d9d7cf;
          --sim:#1f7a4d; --nao:#a63d2f; --barra:#2b5fa8; }
  @media (prefers-color-scheme: dark) {
    :root { --fundo:#171715; --cartao:#222220; --texto:#ecebe5; --suave:#9a998f; --linha:#3a3a36;
            --sim:#4fbf86; --nao:#e5806f; --barra:#6aa0ea; } }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--fundo); color:var(--texto);
         font:17px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
  main { max-width: 820px; margin: 0 auto; padding: 24px 16px 64px; }
  header { display:flex; justify-content:space-between; align-items:baseline; gap:12px; flex-wrap:wrap; }
  .progresso { height:6px; background:var(--linha); border-radius:3px; margin:8px 0 24px; overflow:hidden; }
  .progresso div { height:100%; background:var(--barra); width:0; }
  .suave { color:var(--suave); font-size:14px; }
  h1 { font-size:20px; margin:0 0 4px; }
  .cartao { background:var(--cartao); border:1px solid var(--linha); border-radius:10px; padding:20px; margin:16px 0; }
  #trecho { white-space:pre-wrap; font-family: Georgia, "Times New Roman", serif; font-size:18px; }
  .botoes { display:flex; gap:12px; flex-wrap:wrap; margin-top:10px; }
  button { font:inherit; padding:12px 20px; border-radius:8px; border:1px solid var(--linha);
           background:var(--cartao); color:var(--texto); cursor:pointer; }
  button:focus-visible { outline:3px solid var(--barra); outline-offset:2px; }
  .sim { border-color:var(--sim); color:var(--sim); font-weight:600; }
  .nao { border-color:var(--nao); color:var(--nao); font-weight:600; }
  kbd { font:12px monospace; border:1px solid var(--linha); border-radius:4px; padding:1px 5px; margin-left:6px; }
  .marca { font-size:14px; font-weight:600; }
</style>
</head>
<body>
<main>
  <header>
    <div class="suave" id="posicao"></div>
    <button id="exportar" type="button">Exportar CSV</button>
  </header>
  <div class="progresso"><div id="barra"></div></div>
  <div id="tela"></div>
</main>
<script type="application/json" id="dados">__DADOS__</script>
<script>
const itens = JSON.parse(document.getElementById('dados').textContent);
const CHAVE = 'avaliacao_cega:__HASH__';
let resp = {};
try { resp = JSON.parse(localStorage.getItem(CHAVE) || '{}'); } catch (e) {}
let i = itens.findIndex(x => !resp[x.id]);
if (i < 0) i = itens.length;

const el = id => document.getElementById(id);
function salvar() { try { localStorage.setItem(CHAVE, JSON.stringify(resp)); } catch (e) {} }
function marcar(v) { if (i >= itens.length) return; resp[itens[i].id] = v; salvar(); i++; mostrar(); }
function voltar() { if (i > 0) { i--; mostrar(); } }

function exportar() {
  const linhas = ['id;serve'];
  for (const x of itens) if (resp[x.id]) linhas.push(x.id + ';' + resp[x.id]);
  const blob = new Blob(['\ufeff' + linhas.join('\r\n') + '\r\n'], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'avaliacao_cega.csv';
  a.click();
}

function mostrar() {
  const feitos = Object.keys(resp).length;
  el('barra').style.width = (100 * feitos / itens.length) + '%';
  const tela = el('tela');
  tela.textContent = '';

  if (i >= itens.length) {
    el('posicao').textContent = 'Concluído';
    const pend = itens.filter(x => !resp[x.id]).length;
    const serve = Object.values(resp).filter(v => v === 's').length;
    const c = document.createElement('div'); c.className = 'cartao';
    c.textContent = pend === 0
      ? 'Todos os ' + itens.length + ' trechos avaliados (' + serve + ' marcados como "serve"). Clique em "Exportar CSV" e guarde o arquivo na pasta teste_trechos.'
      : 'Faltam ' + pend + ' trechos sem resposta. Use a tecla B para voltar.';
    tela.appendChild(c);
    return;
  }

  const x = itens[i];
  const n = itens.filter(y => y.pergunta_id === x.pergunta_id);
  el('posicao').textContent = 'Pergunta ' + x.pergunta_id + ' · trecho ' + (n.indexOf(x) + 1) + ' de ' + n.length +
                              ' · ' + (i + 1) + '/' + itens.length;

  const q = document.createElement('div'); q.className = 'cartao';
  const h = document.createElement('h1'); h.textContent = x.pergunta_pt;
  const en = document.createElement('div'); en.className = 'suave'; en.textContent = x.pergunta_en;
  q.append(h, en);

  const t = document.createElement('div'); t.className = 'cartao';
  const meta = document.createElement('div'); meta.className = 'suave';
  meta.textContent = x.paper + ' · p. ' + x.pagina;
  const corpo = document.createElement('div'); corpo.id = 'trecho'; corpo.textContent = x.texto;
  t.append(meta, corpo);

  const ask = document.createElement('div'); ask.className = 'suave';
  ask.textContent = 'Este trecho serve à sua leitura para responder a pergunta?';
  const b = document.createElement('div'); b.className = 'botoes';
  const bs = document.createElement('button'); bs.className = 'sim'; bs.type = 'button';
  bs.innerHTML = 'Serve <kbd>S</kbd>'; bs.onclick = () => marcar('s');
  const bn = document.createElement('button'); bn.className = 'nao'; bn.type = 'button';
  bn.innerHTML = 'Não serve <kbd>N</kbd>'; bn.onclick = () => marcar('n');
  const bv = document.createElement('button'); bv.type = 'button';
  bv.innerHTML = 'Voltar <kbd>B</kbd>'; bv.onclick = voltar;
  b.append(bs, bn, bv);
  tela.append(q, t, ask, b);

  if (resp[x.id]) {
    const m = document.createElement('div'); m.className = 'marca';
    m.textContent = 'Resposta atual: ' + (resp[x.id] === 's' ? 'serve' : 'não serve') + ' (marque de novo para trocar)';
    tela.appendChild(m);
  }
}

el('exportar').onclick = exportar;
document.addEventListener('keydown', e => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const k = e.key.toLowerCase();
  if (k === 's') marcar('s');
  else if (k === 'n') marcar('n');
  else if (k === 'b' || k === 'arrowleft') voltar();
});
mostrar();
</script>
</body>
</html>
"""


def ler(arquivo: Path) -> list[dict]:
    with open(arquivo, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def main() -> None:
    perguntas = ler(PERGUNTAS_FILE)
    trechos = [("A", linha) for linha in ler(ARQUIVO_A)] + [("B", linha) for linha in ler(ARQUIVO_B)]
    sorteio = random.Random(SEMENTE)
    itens, mapa = [], []

    for pergunta in perguntas:
        grupo = [(metodo, linha) for metodo, linha in trechos if linha["pergunta_id"] == pergunta["id"]]
        sorteio.shuffle(grupo)

        for n, (metodo, linha) in enumerate(grupo, start=1):
            id_trecho = f"P{int(pergunta['id']):02d}-{n:02d}"
            itens.append(
                {
                    "id": id_trecho,
                    "pergunta_id": pergunta["id"],
                    "pergunta_pt": pergunta["pergunta_pt"],
                    "pergunta_en": pergunta["pergunta_en"],
                    "paper": linha["paper"],
                    "pagina": int(re.match(r"\d+", linha["pagina"]).group()),  # B vem como "4-5": só a primeira
                    "texto": re.sub(r"\s+", " ", linha["texto"]).strip(),  # mesmo formato nos dois métodos
                }
            )
            mapa.append(
                {
                    "id": id_trecho,
                    "pergunta_id": pergunta["id"],
                    "metodo": metodo,
                    "trecho_id_original": linha["trecho_id"],
                    "paper": linha["paper"],
                    "pagina_original": linha["pagina"],
                    "escore": linha["escore"],
                }
            )

    dados = json.dumps(itens, ensure_ascii=False).replace("<", "\\u003c")
    impressao = hashlib.sha256(dados.encode("utf-8")).hexdigest()[:12]
    SAIDA_HTML.write_text(PAGINA.replace("__DADOS__", dados).replace("__HASH__", impressao), encoding="utf-8")

    with open(SAIDA_MAPA, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS_MAPA, delimiter=";")
        escritor.writeheader()
        escritor.writerows(mapa)

    por_metodo = {m: sum(1 for x in mapa if x["metodo"] == m) for m in "AB"}
    print(f"{len(itens)} trechos de {len(perguntas)} perguntas (método A: {por_metodo['A']}, método B: {por_metodo['B']}).")
    print(f"Avaliação: {SAIDA_HTML}")
    print(f"Mapa dos métodos: {SAIDA_MAPA.name} (não abra antes de avaliar).")


if __name__ == "__main__":
    main()
