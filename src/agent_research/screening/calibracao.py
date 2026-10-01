"""Triagem: calibração, concordância entre o juiz e o gabarito."""

import csv
from collections import Counter
from math import sqrt

from agent_research.screening.juiz import SCREENING_FILE, triagem_desatualizada
from core.pesquisa_ativa import ACTIVE_RESEARCH_DIR, carregar_contexto


GABARITO_FILE = ACTIVE_RESEARCH_DIR / "gabarito.csv"

ROTULOS = {"r": "relevante", "t": "talvez", "l": "lixo"}


def intervalo_wilson(k: int, n: int, z: float = 1.96) -> tuple:
    """Intervalo de confiança de 95% (Wilson) para k em n; serve para n pequeno."""
    p = k / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    meia = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centro - meia, centro + meia


def calibrar() -> None:
    with open(GABARITO_FILE, encoding="utf-8-sig", newline="") as f:
        gabarito = {
            linha["openalex_id"]: ROTULOS[linha["rotulo"].strip().lower()]
            for linha in csv.DictReader(f, delimiter=";")
        }

    with open(SCREENING_FILE, encoding="utf-8-sig", newline="") as f:
        triados = list(csv.DictReader(f))

    juiz = {linha["openalex_id"]: linha["veredito"] for linha in triados}

    de_outro_tema = sum(
        linha.get("tema_confirmado") == "não" and linha["veredito"] != "erro"
        for linha in triados
    )

    if de_outro_tema or triagem_desatualizada(carregar_contexto()["oficial"]):
        print(
            "\nAVISO: a triagem é de outro tema, objetivo ou foco "
            f"({de_outro_tema} vereditos com tema_confirmado = não). "
            "A concordância abaixo não vale para o contexto atual; "
            "reavalie a triagem antes."
        )

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

    # Métricas de triagem: perder um relevante é o erro mais caro.
    relevantes = sum(n for (g, j), n in pares.items() if g == "relevante")
    perdidos = pares[("relevante", "lixo")]
    excluidos = sum(
        n for (g, j), n in pares.items() if j in ("lixo", "descartado")
    )

    if relevantes:
        print(
            f"\nEvidência perdida (relevante -> lixo): "
            f"{perdidos}/{relevantes} ({perdidos / relevantes:.0%})"
        )
        baixo, alto = intervalo_wilson(relevantes - perdidos, relevantes)
        print(
            f"Recall (relevante mantido como relevante ou talvez): "
            f"{(relevantes - perdidos) / relevantes:.0%} "
            f"(IC 95%: {baixo:.0%} a {alto:.0%}; {relevantes} relevantes no gabarito)"
        )

    print(
        f"Redução de trabalho (lixo + descartado): "
        f"{excluidos}/{total} ({excluidos / total:.0%})"
    )
