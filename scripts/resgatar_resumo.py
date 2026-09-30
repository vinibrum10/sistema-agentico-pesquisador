"""Experimento: resgatar resumos dos papers sem resumo e sem XML (Semantic Scholar e Crossref).

Não altera o pipeline. Lê cobertura_conteudo.csv e results.csv; grava resgate_resumo.csv.
"""

import csv
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "data" / "active_research"
MIN_CHARS = 150  # abaixo disso não conta como resumo
load_dotenv(RAIZ / ".env")


def ler(nome):
    with open(PASTA / nome, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def doi_curto(url):
    return url.replace("https://doi.org/", "").strip()


def com_retentativa(fazer):
    for espera in (0, 5, 15, 30):
        time.sleep(espera)
        r = fazer()
        if r.status_code != 429:
            return r
    return r


def semantic_scholar(dois):
    cab = {}
    if os.getenv("SEMANTIC_SCHOLAR_API_KEY"):
        cab["x-api-key"] = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    achados = {}
    for i in range(0, len(dois), 100):
        lote = dois[i:i + 100]
        r = com_retentativa(lambda: requests.post(
            "https://api.semanticscholar.org/graph/v1/paper/batch",
            params={"fields": "abstract"},
            json={"ids": [f"DOI:{d}" for d in lote]},
            headers=cab, timeout=60,
        ))
        if r.status_code != 200:
            print(f"Semantic Scholar: HTTP {r.status_code} no lote {i // 100 + 1}")
            continue
        for d, item in zip(lote, r.json()):
            if item and item.get("abstract"):
                achados[d] = item["abstract"].strip()
    return achados


def crossref(doi):
    r = com_retentativa(lambda: requests.get(
        f"https://api.crossref.org/works/{doi}", timeout=30))
    if r.status_code != 200:
        return ""
    bruto = r.json().get("message", {}).get("abstract") or ""
    limpo = re.sub(r"<[^>]+>", " ", bruto)
    limpo = re.sub(r"\s+", " ", limpo).strip()
    return re.sub(r"^Abstract[:.\s]*", "", limpo, flags=re.I)


def main():
    cobertura = {x["openalex_id"]: x for x in ler("cobertura_conteudo.csv")}
    cegos = []
    for x in ler("results.csv"):
        c = cobertura[x["openalex_id"]]
        if c["tem_resumo"] == "False" and c["tem_xml"] == "False":
            cegos.append({"openalex_id": x["openalex_id"], "doi": doi_curto(x["doi"]),
                          "veredito": c["veredito"]})
    sem_doi = [x for x in cegos if not x["doi"]]
    cegos_doi = [x for x in cegos if x["doi"]]
    print(f"Sem resumo e sem XML: {len(cegos)} (sem DOI: {len(sem_doi)})")

    ss = semantic_scholar([x["doi"] for x in cegos_doi])
    for x in cegos_doi:
        texto = ss.get(x["doi"], "")
        x["fonte"], x["resumo"] = ("semantic_scholar", texto) if len(texto) >= MIN_CHARS else ("", "")
    print(f"Semantic Scholar recuperou: {sum(1 for x in cegos_doi if x['fonte'])}")

    for x in cegos_doi:
        if not x["fonte"]:
            texto = crossref(x["doi"])
            if len(texto) >= MIN_CHARS:
                x["fonte"], x["resumo"] = "crossref", texto
            time.sleep(0.2)
    print(f"Crossref recuperou (dos restantes): {sum(1 for x in cegos_doi if x['fonte'] == 'crossref')}")

    print(f"\n{'veredito':11}{'cegos':>6}{'recuperados':>13}{'ainda cegos':>13}")
    for v in ["relevante", "talvez", "descartado"]:
        g = [x for x in cegos if x["veredito"] == v]
        rec = sum(1 for x in g if x.get("fonte"))
        print(f"{v:11}{len(g):>6}{rec:>13}{len(g) - rec:>13}")
    total = sum(1 for x in cegos if x.get("fonte"))
    print(f"\nTotal recuperado: {total} de {len(cegos)} ({total / len(cegos):.0%})")

    with open(PASTA / "resgate_resumo.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["openalex_id", "doi", "veredito", "fonte", "resumo"])
        w.writeheader()
        for x in cegos:
            w.writerow({k: x.get(k, "") for k in w.fieldnames})
    print("Detalhe em data\\active_research\\resgate_resumo.csv")


if __name__ == "__main__":
    main()
