"""Experimento: cruza cobertura de texto completo (OpenAlex) com veredito do juiz e resumo."""

import csv
from pathlib import Path

from teste_conteudo_openalex import ids_com

PASTA = Path(__file__).resolve().parent.parent / "data" / "active_research"


def ler(nome):
    with open(PASTA / nome, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    resultados = ler("results.csv")
    veredito = {x["openalex_id"]: x["veredito"] for x in ler("screening.csv")}
    ids = [x["openalex_id"] for x in resultados]

    com_xml = set(ids_com("has_content.grobid_xml:true", ids))
    com_pdf = set(ids_com("has_content.pdf:true", ids))

    linhas = []
    for x in resultados:
        i = x["openalex_id"]
        linhas.append({
            "openalex_id": i,
            "veredito": veredito.get(i, "?"),
            "tem_resumo": bool(x["abstract"].strip()),
            "tem_xml": i in com_xml,
            "tem_pdf": i in com_pdf,
        })

    with open(PASTA / "cobertura_conteudo.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)

    print(f"{'veredito':11}{'total':>6}{'c/ XML':>8}{'c/ PDF':>8}{'c/ resumo':>11}{'sem resumo e sem XML':>22}")
    for v in ["relevante", "talvez", "lixo", "descartado", "?"]:
        g = [x for x in linhas if x["veredito"] == v]
        if not g:
            continue
        cego = sum(1 for x in g if not x["tem_resumo"] and not x["tem_xml"])
        print(f"{v:11}{len(g):>6}{sum(x['tem_xml'] for x in g):>8}{sum(x['tem_pdf'] for x in g):>8}"
              f"{sum(x['tem_resumo'] for x in g):>11}{cego:>22}")

    sem_resumo = [x for x in linhas if not x["tem_resumo"]]
    print(f"\nSem resumo: {len(sem_resumo)}; desses, com XML: {sum(x['tem_xml'] for x in sem_resumo)}")
    util = [x for x in linhas if x["tem_resumo"] or x["tem_xml"]]
    print(f"Com algum texto (resumo ou XML): {len(util)} de {len(linhas)} ({len(util) / len(linhas):.0%})")
    print("Detalhe em data\\active_research\\cobertura_conteudo.csv")


if __name__ == "__main__":
    main()
