"""Revisão: relevantes e talvez num arquivo legível (abre no Excel), com link para cada paper."""

import csv
from collections import Counter

from agents.screening.juiz import SCREENING_FILE
from agents.search.openalex import RESULTS_FILE
from core.pesquisa_ativa import ACTIVE_RESEARCH_DIR


REVIEW_FILE = ACTIVE_RESEARCH_DIR / "revisao.csv"

COLUNAS = [
    "veredito",
    "titulo",
    "ano",
    "citacoes",
    "venue",
    "link",
    "justificativa",
    "trecho",
]

ORDEM = {"relevante": 0, "talvez": 1}


def gerar_revisao():
    """Relevantes primeiro, depois talvez; em cada grupo, os mais citados primeiro."""

    if not SCREENING_FILE.exists():
        print("\nNenhuma triagem ainda: rode a pesquisa primeiro.")
        return None

    with open(RESULTS_FILE, encoding="utf-8-sig", newline="") as f:
        resultados = {linha["openalex_id"]: linha for linha in csv.DictReader(f)}

    with open(SCREENING_FILE, encoding="utf-8-sig", newline="") as f:
        triados = [
            linha
            for linha in csv.DictReader(f)
            if linha["veredito"] in ORDEM
        ]

    linhas = []

    for triado in triados:
        paper = resultados.get(triado["openalex_id"], {})

        linhas.append(
            {
                "veredito": triado["veredito"],
                "titulo": triado["titulo"],
                "ano": paper.get("ano", ""),
                "citacoes": paper.get("citacoes", ""),
                "venue": paper.get("venue", ""),
                "link": paper.get("doi") or triado["openalex_id"],
                "justificativa": triado["justificativa"],
                "trecho": triado["trecho"],
            }
        )

    linhas.sort(
        key=lambda linha: (
            ORDEM[linha["veredito"]],
            -int(linha["citacoes"] or 0),
        )
    )

    try:
        with open(REVIEW_FILE, "w", encoding="utf-8-sig", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
            escritor.writeheader()
            escritor.writerows(linhas)

    except PermissionError:
        print(
            f"\nNão foi possível gravar {REVIEW_FILE.name}: "
            "feche o arquivo no Excel e tente de novo."
        )
        return None

    contagem = Counter(linha["veredito"] for linha in linhas)

    print(
        f"\nRevisão: {contagem['relevante']} relevantes "
        f"e {contagem['talvez']} talvez"
    )
    print(f"Arquivo: {REVIEW_FILE}")

    return REVIEW_FILE
