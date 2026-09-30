"""Experimento: cobertura e qualidade do texto completo via OpenAlex Content API."""

import csv
import os
import random
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "data" / "active_research"
SAIDA = PASTA / "teste_texto"
load_dotenv(RAIZ / ".env")
CHAVE = os.getenv("OPENALEX_API_KEY")
TEI = {"t": "http://www.tei-c.org/ns/1.0"}


def curto(id_):
    return id_.rsplit("/", 1)[-1]


def ids_com(filtro, ids):
    achados = []
    for i in range(0, len(ids), 50):
        lote = "|".join(curto(x) for x in ids[i:i + 50])
        r = requests.get(
            "https://api.openalex.org/works",
            params={"filter": f"openalex:{lote},{filtro}", "select": "id",
                    "per-page": 50, "api_key": CHAVE},
            timeout=30,
        )
        r.raise_for_status()
        achados += [w["id"] for w in r.json()["results"]]
    return achados


def baixar(id_, ext):
    r = requests.get(
        f"https://content.openalex.org/works/{curto(id_)}.{ext}",
        params={"api_key": CHAVE}, timeout=60,
    )
    return r


def resumo_tei(conteudo):
    raiz = ET.fromstring(conteudo)
    divs = raiz.findall(".//t:body//t:div", TEI)
    heads = [(d.find("t:head", TEI).text or "").strip() for d in divs if d.find("t:head", TEI) is not None]
    texto = " ".join("".join(p.itertext()) for p in raiz.findall(".//t:body//t:p", TEI))
    return len(divs), len(texto), heads[:6]


def main():
    with open(PASTA / "results.csv", encoding="utf-8-sig", newline="") as f:
        ids = [x["openalex_id"] for x in csv.DictReader(f)]
    print(f"Papers no corpus: {len(ids)}")

    com_xml = ids_com("has_content.grobid_xml:true", ids)
    com_pdf = ids_com("has_content.pdf:true", ids)
    print(f"com TEI XML (Grobid): {len(com_xml)} ({len(com_xml) / len(ids):.0%})")
    print(f"com PDF em cache:     {len(com_pdf)} ({len(com_pdf) / len(ids):.0%})")

    SAIDA.mkdir(exist_ok=True)
    random.seed(42)
    for id_ in random.sample(com_xml, min(5, len(com_xml))):
        r = baixar(id_, "grobid-xml")
        if r.status_code != 200:
            print(f"XML {curto(id_)}: HTTP {r.status_code}")
            continue
        (SAIDA / f"{curto(id_)}.xml").write_bytes(r.content)
        try:
            secoes, chars, heads = resumo_tei(r.content)
            print(f"XML {curto(id_)}: {secoes} seções, {chars} caracteres de corpo; {heads}")
        except ET.ParseError as e:
            print(f"XML {curto(id_)}: erro de parsing ({e})")
    for id_ in random.sample(com_pdf, min(2, len(com_pdf))):
        r = baixar(id_, "pdf")
        ok = r.status_code == 200 and r.content.startswith(b"%PDF")
        print(f"PDF {curto(id_)}: HTTP {r.status_code}, PDF válido={ok}, {len(r.content) // 1024} KB")
        if ok:
            (SAIDA / f"{curto(id_)}.pdf").write_bytes(r.content)


if __name__ == "__main__":
    main()
