"""Escritor, etapa 2: busca os trechos de cada pergunta-guia da seção e grava evidencias.csv."""

import csv
import json

from agent_research.trechos.busca import BuscaLocal
from agent_research.trechos.indice import atualizar_indice
from agent_writer.secao import ESCRITA_DIR


TRECHOS_POR_PERGUNTA = 5  # configuração medida no teste da camada de trechos
COLUNAS = ["ref", "pergunta", "posicao", "trecho_id", "paper", "pagina", "escore", "texto"]


def escolher_secao():
    pastas = sorted(p.parent for p in ESCRITA_DIR.glob("*/secao.json"))
    if not pastas:
        print("\nNenhuma seção salva. Defina uma seção antes de buscar evidências.")
        return None

    print("\nSeções salvas:")
    for i, pasta in enumerate(pastas, start=1):
        secao = json.loads((pasta / "secao.json").read_text(encoding="utf-8"))
        print(f"  {i}. {secao['titulo']} ({len(secao['perguntas'])} perguntas)")

    while True:
        escolha = input("\nNúmero da seção:\n> ").strip()
        if escolha.isdigit() and 1 <= int(escolha) <= len(pastas):
            return pastas[int(escolha) - 1]
        print("\nNúmero inválido.")


def montar_evidencias(perguntas: list, busca) -> list[dict]:
    """5 trechos por pergunta (versão EN); o mesmo trecho mantém a mesma referência T em todas."""
    refs = {}
    linhas = []

    for n, pergunta in enumerate(perguntas, start=1):
        for posicao, trecho in enumerate(busca.buscar(pergunta["en"], TRECHOS_POR_PERGUNTA), start=1):
            ref = refs.setdefault(trecho["id"], f"T{len(refs) + 1}")
            linhas.append(
                {
                    "ref": ref,
                    "pergunta": n,
                    "posicao": posicao,
                    "trecho_id": trecho["id"],
                    "paper": trecho["paper"],
                    "pagina": trecho["pagina"],
                    "escore": trecho["escore"],
                    "texto": trecho["texto"].replace("\x00", ""),  # PDFs às vezes trazem caracteres nulos
                }
            )

    return linhas


def buscar_evidencias():
    pasta = escolher_secao()
    if pasta is None:
        return None

    secao = json.loads((pasta / "secao.json").read_text(encoding="utf-8"))
    atualizar_indice()
    linhas = montar_evidencias(secao["perguntas"], BuscaLocal())

    arquivo = pasta / "evidencias.csv"
    with open(arquivo, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)

    print(f"\nEvidências de '{secao['titulo']}':")
    for n, pergunta in enumerate(secao["perguntas"], start=1):
        da_pergunta = [linha for linha in linhas if linha["pergunta"] == n]
        papers = len({linha["paper"] for linha in da_pergunta})
        print(f"  {n}. {len(da_pergunta)} trechos de {papers} paper(s) — {pergunta['pt']}")

    unicos = len({linha["ref"] for linha in linhas})
    papers = len({linha["paper"] for linha in linhas})
    print(f"\nTotal: {unicos} trechos únicos de {papers} papers.")
    print(f"Salvo em: {arquivo}")
    return arquivo
