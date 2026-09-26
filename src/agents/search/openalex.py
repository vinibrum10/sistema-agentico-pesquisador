"""Search V1 — busca no OpenAlex a partir do plano confirmado pelo Planner."""

import csv
import os
from datetime import date

import pyalex
from dotenv import load_dotenv
from pyalex import Works

from core.pesquisa_ativa import ACTIVE_RESEARCH_DIR

load_dotenv()
pyalex.config.api_key = os.getenv("OPENALEX_API_KEY")

RESULTS_FILE = ACTIVE_RESEARCH_DIR / "results.csv"
COLUNAS = ["openalex_id", "doi", "titulo", "ano", "venue", "citacoes", "abstract", "consulta_origem", "data_run"]


def _formatar_termo(termo):
    termo = termo.strip()
    return f'"{termo}"' if " " in termo else termo


def montar_consulta(plano):
    """String booleana: OR dentro do grupo (todos os idiomas do plano), AND entre grupos marcados."""
    partes = []
    for grupo in plano["grupos"]:
        if not grupo["incluido"]:
            continue
        termos = []
        vistos = set()
        for idioma in plano["idiomas"]:
            for termo in grupo["variantes"].get(idioma, []):
                chave = termo.strip().lower()
                if chave and chave not in vistos:
                    vistos.add(chave)
                    termos.append(_formatar_termo(termo))
        if not termos:
            continue
        bloco = " OR ".join(termos)
        partes.append(f"({bloco})" if len(termos) > 1 else bloco)
    return " AND ".join(partes)


def buscar(consulta, n=25):
    """Uma consulta, n resultados, sem paginação. Zero resultados = lista vazia (válido)."""
    return Works().search(consulta).get(per_page=n)


def _linha(w, consulta, data_run):
    fonte = (w.get("primary_location") or {}).get("source") or {}
    return {
        "openalex_id": w["id"],
        "doi": w.get("doi") or "",
        "titulo": w.get("title") or "",
        "ano": w.get("publication_year") or "",
        "venue": fonte.get("display_name") or "",
        "citacoes": w.get("cited_by_count", 0),
        "abstract": w["abstract"] or "",
        "consulta_origem": consulta,
        "data_run": data_run,
    }


def salvar_resultados(resultados, consulta):
    """Upsert por openalex_id no results.csv da pesquisa ativa. Retorna o total de linhas."""
    linhas = {}
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE, encoding="utf-8-sig", newline="") as f:
            linhas = {l["openalex_id"]: l for l in csv.DictReader(f)}
    hoje = date.today().isoformat()
    for w in resultados:
        l = _linha(w, consulta, hoje)
        linhas[l["openalex_id"]] = l
    with open(RESULTS_FILE, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(linhas.values())
    return len(linhas)
