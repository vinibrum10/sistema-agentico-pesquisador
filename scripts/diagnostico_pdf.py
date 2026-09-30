"""Diagnóstico: por que os links de PDF da amostra não baixam."""

import csv
import random
from pathlib import Path
from urllib.parse import urlparse

import requests

PASTA = Path(__file__).resolve().parent.parent / "data" / "active_research"

with open(PASTA / "cobertura_texto.csv", encoding="utf-8-sig", newline="") as f:
    com_pdf = [x for x in csv.DictReader(f) if x["pdf_url"]]

random.seed(42)
amostra = random.sample(com_pdf, min(20, len(com_pdf)))

for x in amostra:
    url = x["pdf_url"]
    dominio = urlparse(url).netloc
    try:
        r = requests.get(
            url, timeout=20, stream=True,
            headers={"User-Agent": "Mozilla/5.0 (pesquisa academica)"},
        )
        inicio = next(r.iter_content(chunk_size=5), b"")
        tipo = r.headers.get("Content-Type", "?").split(";")[0]
        r.close()
        print(f"{r.status_code} | {tipo:28} | pdf={inicio.startswith(b'%PDF')!s:5} | {x['oa_status']:8} | {dominio}")
    except requests.RequestException as e:
        print(f"ERRO | {type(e).__name__:26} | {'':9} | {x['oa_status']:8} | {dominio}")
