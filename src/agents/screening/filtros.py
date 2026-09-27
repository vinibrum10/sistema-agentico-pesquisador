"""Triagem: filtros determinísticos (retratados e duplicatas), sem LLM."""

import csv

from agents.search.openalex import RESULTS_FILE
from core.texto import normalizar_texto


def carregar_resultados() -> list:
    with open(RESULTS_FILE, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def filtrar(linhas: list) -> dict:
    """
    Retorna {openalex_id: motivo} dos papers descartados antes do LLM.
    Motivos: "retratado" ou "duplicata de <openalex_id>".
    Na duplicata, fica o primeiro que aparece no arquivo.
    """

    descartes = {}
    vistos = {}

    for linha in linhas:
        pid = linha["openalex_id"]

        if linha.get("retratado") == "True":
            descartes[pid] = "retratado"
            continue

        chaves = [
            chave
            for chave in (
                normalizar_texto(linha["titulo"]),
                linha["doi"].lower(),
            )
            if chave
        ]

        original = next(
            (vistos[chave] for chave in chaves if chave in vistos),
            None,
        )

        if original:
            descartes[pid] = f"duplicata de {original}"
            continue

        for chave in chaves:
            vistos[chave] = pid

    return descartes
