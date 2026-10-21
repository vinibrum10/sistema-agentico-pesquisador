r"""Passo 3 do teste PaperQA2: método B (PaperQA2 + DeepSeek) nas perguntas do teste às cegas.

Roda no ambiente .venv-paperqa. Indexa os PDFs do acervo (embeddings locais bge-m3 pelo
Ollama), faz cada pergunta e guarda os 5 trechos que o PaperQA2 escolheu em
data/active_research/teste_trechos/nao_abrir_metodo_b.csv. Não abra esse arquivo antes da
avaliação às cegas. Uso:

    .venv-paperqa/Scripts/python.exe scripts/teste_paperqa/02_metodo_b.py       (as 10 perguntas)
    .venv-paperqa/Scripts/python.exe scripts/teste_paperqa/02_metodo_b.py 1     (só a pergunta 1)
"""

import asyncio
import csv
import json
import logging
import os
import pickle
import re
import sys
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import litellm
from dotenv import load_dotenv
from paperqa import Docs, Settings
from pypdf import PdfReader


RAIZ = Path(__file__).resolve().parent.parent.parent
ACTIVE_DIR = RAIZ / "data" / "active_research"
TEXTOS_DIR = ACTIVE_DIR / "textos"
TESTE_DIR = ACTIVE_DIR / "teste_trechos"
PERGUNTAS_FILE = TESTE_DIR / "perguntas.csv"
CUSTOS_FILE = ACTIVE_DIR / "custos.csv"
CONFIG_FILE = RAIZ / "config" / "modelos.json"

MODELO = "deepseek-flash"
TRECHOS_POR_PERGUNTA = 5
LIMITE_POR_PERGUNTA_USD = 0.02
COLUNAS = ["pergunta_id", "posicao", "trecho_id", "paper", "pagina", "escore", "texto", "resumo_llm", "verificado"]
COLUNAS_CUSTO = ["quando", "tarefa", "modelo", "tokens_entrada", "tokens_saida", "custo_usd"]

load_dotenv(RAIZ / ".env")
litellm.suppress_debug_info = True
logging.disable(logging.WARNING)  # o leitor de PDF avisa de fontes; não afeta o texto


def construir_settings() -> tuple[Settings, dict, float]:
    """PaperQA2 com o DeepSeek (mesma configuração do modelos.json) e embeddings locais."""
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    info = config["modelos"][MODELO]
    chave = os.getenv(info["chave_env"])

    if not chave:
        sys.exit(f"falta {info['chave_env']} no .env")

    rota = {
        "model_list": [
            {
                "model_name": MODELO,
                "litellm_params": {
                    "model": f"openai/{info['modelo']}",
                    "api_base": info["base_url"],
                    "api_key": chave,
                    "extra_body": info["extra_body"],
                },
            }
        ]
    }
    settings = Settings(
        llm=MODELO,
        summary_llm=MODELO,
        llm_config=rota,
        summary_llm_config=rota,
        embedding="ollama/bge-m3",
    )
    settings.parsing.use_doc_details = False  # sem consulta de metadados na internet
    settings.parsing.multimodal = False  # só texto: sem imagens e sem LLM descrevendo figuras
    settings.parsing.reader_config = {"chunk_chars": 1500, "overlap": 150}  # mesmo tamanho do método A

    return settings, info, config["teto_por_execucao_usd"]


async def indexar(settings: Settings) -> Docs:
    """Lê os PDFs do acervo e gera os embeddings (a primeira vez demora; depois usa o cache)."""
    pdfs = sorted(TEXTOS_DIR.glob("*.pdf"))
    cache = TESTE_DIR / f"paperqa_indice_{len(pdfs)}.pkl"

    if cache.exists():
        print(f"Índice em cache: {cache.name}")
        return pickle.loads(cache.read_bytes())

    docs = Docs()

    for i, pdf in enumerate(pdfs, start=1):
        await docs.aadd(pdf, citation=pdf.stem, docname=pdf.stem, dockey=pdf.stem, settings=settings)
        print(f"  indexando {i}/{len(pdfs)}", end="\r")

    print(f"Índice: {len(docs.docs)} papers, {len(docs.texts)} trechos.      ")
    cache.write_bytes(pickle.dumps(docs))
    return docs


def escolher(sessao, corte: int) -> list:
    """Os trechos que o PaperQA2 mandaria para a resposta: nota do LLM (maior primeiro), depois nome."""
    escolhidos, vistos = [], set()

    for contexto in sorted(sessao.contexts, key=lambda c: (-c.score, c.text.name)):
        if contexto.score < corte or contexto.text.text in vistos:
            continue
        vistos.add(contexto.text.text)
        escolhidos.append(contexto)
        if len(escolhidos) == TRECHOS_POR_PERGUNTA:
            break

    return escolhidos


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


@lru_cache(maxsize=None)
def _paginas(paper: str) -> tuple[str, ...]:
    return tuple(p.extract_text() or "" for p in PdfReader(TEXTOS_DIR / f"{paper}.pdf").pages)


def conferir(contexto) -> str:
    """O texto do trecho existe, palavra por palavra, no PDF?

    "exato": está nas páginas citadas. "adjacente": só aparece com mais uma página de cada lado
    (a sobreposição entre trechos pode começar na página anterior à citada). "nao": não achado.
    O PaperQA2 junta as páginas sem espaço entre elas, por isso o join é "".
    """
    paper, intervalo = contexto.text.name.rsplit(" pages ", 1)
    inicio, fim = (int(n) for n in intervalo.split("-"))
    paginas = _paginas(paper)
    alvo = _normalizar(contexto.text.text)

    if alvo in _normalizar("".join(paginas[inicio - 1 : fim])):
        return "exato"

    if alvo in _normalizar("".join(paginas[max(inicio - 2, 0) : fim + 1])):
        return "adjacente"

    return "nao"


def registrar_custo(tarefa: str, entrada: int, saida: int, usd: float) -> None:
    novo = not CUSTOS_FILE.exists()

    with open(CUSTOS_FILE, "a", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS_CUSTO)
        if novo:
            escritor.writeheader()
        escritor.writerow(
            {
                "quando": datetime.now().isoformat(timespec="seconds"),
                "tarefa": tarefa,
                "modelo": MODELO,
                "tokens_entrada": entrada,
                "tokens_saida": saida,
                "custo_usd": f"{usd:.6f}",
            }
        )


async def main(ids: list[str]) -> None:
    settings, info, teto = construir_settings()

    with open(PERGUNTAS_FILE, encoding="utf-8-sig", newline="") as f:
        perguntas = [p for p in csv.DictReader(f, delimiter=";") if not ids or p["id"] in ids]

    docs = await indexar(settings)
    corte = settings.answer.evidence_relevance_score_cutoff
    linhas, custos, gasto = [], [], 0.0

    for pergunta in perguntas:
        if gasto >= teto:
            print(f"Teto de US$ {teto:.2f} atingido: parei antes da pergunta {pergunta['id']}.")
            break

        inicio = time.time()
        sessao = await docs.aquery(pergunta["pergunta_en"], settings=settings)
        entrada = sum(c[0] for c in sessao.token_counts.values())
        saida = sum(c[1] for c in sessao.token_counts.values())
        usd = (entrada * info["entrada_usd_1m"] + saida * info["saida_usd_1m"]) / 1_000_000
        gasto += usd
        custos.append(usd)
        registrar_custo(f"teste_paperqa_p{pergunta['id']}", entrada, saida, usd)

        escolhidos = escolher(sessao, corte)
        resultados = []

        for posicao, contexto in enumerate(escolhidos, start=1):
            paper, pagina = contexto.text.name.rsplit(" pages ", 1)
            verificado = conferir(contexto)
            resultados.append(verificado)
            linhas.append(
                {
                    "pergunta_id": pergunta["id"],
                    "posicao": posicao,
                    "trecho_id": f"{paper}_{pagina}_{posicao}",
                    "paper": paper,
                    "pagina": pagina,
                    "escore": contexto.score,
                    "texto": contexto.text.text,
                    "resumo_llm": contexto.context,
                    "verificado": verificado,
                }
            )

        print(
            f"Pergunta {pergunta['id']}: {len(escolhidos)} trechos ({resultados.count('exato')} exatos, "
            f"{resultados.count('adjacente')} adjacentes, {resultados.count('nao')} não achados), "
            f"{entrada}/{saida} tokens, US$ {usd:.4f}, {time.time() - inicio:.0f} s"
        )

    saida_csv = TESTE_DIR / ("teste_parcial_metodo_b.csv" if ids else "nao_abrir_metodo_b.csv")

    with open(saida_csv, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)

    achados = [linha["verificado"] for linha in linhas]
    print(f"\nConferência no PDF, de {len(achados)} trechos: {achados.count('exato')} na página citada, "
          f"{achados.count('adjacente')} em página adjacente, {achados.count('nao')} não achados")
    print(f"Custo: total US$ {gasto:.4f} | médio US$ {gasto / max(len(custos), 1):.4f} por pergunta | "
          f"máximo US$ {max(custos, default=0):.4f} (limite US$ {LIMITE_POR_PERGUNTA_USD:.2f})")
    print(f"Resultado: {saida_csv.name}. Não abra esse arquivo: ele é a metade B do teste às cegas.")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
