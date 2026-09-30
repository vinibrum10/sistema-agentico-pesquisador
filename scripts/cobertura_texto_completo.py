"""Experimento: quantos papers de results.csv têm texto completo acessível (acesso aberto).

Nível 1: o OpenAlex informa um link de PDF.
Nível 2: em uma amostra, o link realmente devolve um PDF.
Não altera o pipeline; grava data/active_research/cobertura_texto.csv.
"""

import csv
import os
import random
from pathlib import Path

import pyalex
import requests
from dotenv import load_dotenv
from pyalex import Works

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "data" / "active_research"
AMOSTRA_DOWNLOAD = 20

load_dotenv(RAIZ / ".env")
pyalex.config.api_key = os.getenv("OPENALEX_API_KEY")


def ler_ids():
    with open(PASTA / "results.csv", encoding="utf-8-sig", newline="") as f:
        return [linha["openalex_id"] for linha in csv.DictReader(f)]


def buscar_lote(ids):
    curtos = "|".join(i.rsplit("/", 1)[-1] for i in ids)
    return Works().filter(openalex_id=curtos).get(per_page=len(ids))


def extrair(w):
    melhor = w.get("best_oa_location") or {}
    principal = w.get("primary_location") or {}
    pdf = melhor.get("pdf_url") or principal.get("pdf_url") or ""
    if not pdf:
        for loc in w.get("locations") or []:
            if loc.get("pdf_url"):
                pdf = loc["pdf_url"]
                break
    oa = w.get("open_access") or {}
    return {
        "openalex_id": w["id"],
        "titulo": w.get("title") or "",
        "is_oa": bool(oa.get("is_oa")),
        "oa_status": oa.get("oa_status") or "",
        "pdf_url": pdf,
        "landing_url": melhor.get("landing_page_url") or "",
        "baixou_pdf": "",
    }


def testar_pdf(url):
    try:
        r = requests.get(
            url, timeout=20, stream=True,
            headers={"User-Agent": "Mozilla/5.0 (pesquisa academica)"},
        )
        cabecalho = next(r.iter_content(chunk_size=5), b"")
        r.close()
        return r.status_code == 200 and cabecalho.startswith(b"%PDF")
    except requests.RequestException:
        return False


def main():
    ids = ler_ids()
    linhas = []
    for i in range(0, len(ids), 50):
        for w in buscar_lote(ids[i:i + 50]):
            linhas.append(extrair(w))
    print(f"Papers consultados: {len(linhas)} de {len(ids)}")

    com_pdf = [x for x in linhas if x["pdf_url"]]
    print(f"is_oa = True:            {sum(x['is_oa'] for x in linhas)}")
    print(f"com link de PDF:         {len(com_pdf)} ({len(com_pdf) / len(linhas):.0%})")

    contagem = {}
    for x in linhas:
        contagem[x["oa_status"] or "(vazio)"] = contagem.get(x["oa_status"] or "(vazio)", 0) + 1
    print("por oa_status:", contagem)

    random.seed(42)
    amostra = random.sample(com_pdf, min(AMOSTRA_DOWNLOAD, len(com_pdf)))
    ok = 0
    for x in amostra:
        x["baixou_pdf"] = testar_pdf(x["pdf_url"])
        ok += x["baixou_pdf"]
    if amostra:
        print(f"PDF realmente baixável (amostra de {len(amostra)}): {ok} ({ok / len(amostra):.0%})")

    with open(PASTA / "cobertura_texto.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)
    print("Detalhe em data\\active_research\\cobertura_texto.csv")


if __name__ == "__main__":
    main()
