"""Prova de conceito: recuperação de trechos por embeddings locais (bge-m3 via Ollama).

Uso: python scripts\\prova_recuperacao_trechos.py "sua pergunta de pesquisa"
Lê os XMLs (TEI/Grobid) de data/active_research/teste_texto/. Não altera o pipeline.
"""

import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

PASTA = Path(__file__).resolve().parent.parent / "data" / "active_research" / "teste_texto"
TEI = {"t": "http://www.tei-c.org/ns/1.0"}
MODELO = "bge-m3"
MIN_CHARS = 200
TOP = 10


def limpar(texto):
    return re.sub(r"\s+", " ", texto).strip()


def ler_trechos(caminho):
    raiz = ET.parse(caminho).getroot()
    titulo = raiz.find(".//t:titleStmt/t:title", TEI)
    titulo = limpar("".join(titulo.itertext())) if titulo is not None else caminho.stem
    trechos = []
    for div in raiz.findall(".//t:body//t:div", TEI):
        head = div.find("t:head", TEI)
        secao = limpar("".join(head.itertext())) if head is not None else "(sem título de seção)"
        for p in div.findall("t:p", TEI):
            texto = limpar("".join(p.itertext()))
            if len(texto) >= MIN_CHARS:
                trechos.append({"paper": titulo, "id": caminho.stem, "secao": secao, "texto": texto})
    return trechos


def embutir(textos):
    vetores = []
    for i in range(0, len(textos), 16):
        r = requests.post(
            "http://localhost:11434/api/embed",
            json={"model": MODELO, "input": textos[i:i + 16]}, timeout=300,
        )
        r.raise_for_status()
        vetores += r.json()["embeddings"]
    return vetores


def cosseno(a, b):
    return sum(x * y for x, y in zip(a, b)) / (
        math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def main():
    if len(sys.argv) < 2:
        sys.exit('Uso: python scripts\\prova_recuperacao_trechos.py "sua pergunta"')
    pergunta = sys.argv[1]

    trechos = []
    for xml in sorted(PASTA.glob("*.xml")):
        trechos += ler_trechos(xml)
    print(f"{len(trechos)} trechos (parágrafos com {MIN_CHARS}+ caracteres) de {len(set(t['id'] for t in trechos))} papers")

    vetores = embutir([t["texto"] for t in trechos])
    q = embutir([pergunta])[0]
    for t, v in zip(trechos, vetores):
        t["score"] = cosseno(q, v)

    print(f"\nPergunta: {pergunta}\n")
    for n, t in enumerate(sorted(trechos, key=lambda x: -x["score"])[:TOP], 1):
        print(f"[{n}] score {t['score']:.3f} | {t['id']} | {t['paper'][:70]}")
        print(f"    Seção: {t['secao']}")
        print(f"    {t['texto'][:450]}{'...' if len(t['texto']) > 450 else ''}\n")


if __name__ == "__main__":
    main()
