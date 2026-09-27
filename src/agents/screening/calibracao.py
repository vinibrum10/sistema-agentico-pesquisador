"""Triagem: calibração, concordância entre o juiz e o gabarito."""

import csv
from collections import Counter

from agents.screening.juiz import SCREENING_FILE
from core.pesquisa_ativa import ACTIVE_RESEARCH_DIR


GABARITO_FILE = ACTIVE_RESEARCH_DIR / "gabarito.csv"

ROTULOS = {"r": "relevante", "t": "talvez", "l": "lixo"}


def calibrar() -> None:
    with open(GABARITO_FILE, encoding="utf-8-sig", newline="") as f:
        gabarito = {
            linha["openalex_id"]: ROTULOS[linha["rotulo"].strip().lower()]
            for linha in csv.DictReader(f, delimiter=";")
        }

    with open(SCREENING_FILE, encoding="utf-8-sig", newline="") as f:
        juiz = {
            linha["openalex_id"]: linha["veredito"]
            for linha in csv.DictReader(f)
        }

    pares = Counter(
        (rotulo, juiz.get(pid, "ausente"))
        for pid, rotulo in gabarito.items()
    )

    total = sum(pares.values())
    acertos = sum(n for (g, j), n in pares.items() if g == j)

    print(f"\nConcordância: {acertos}/{total} ({acertos / total:.0%})")
    print("\nGabarito -> juiz:")

    for rotulo in ROTULOS.values():
        detalhe = ", ".join(
            f"{j}: {n}"
            for (g, j), n in sorted(pares.items())
            if g == rotulo
        )
        print(f"  {rotulo}: {detalhe}")
