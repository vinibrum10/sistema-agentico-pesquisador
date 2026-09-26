"""Search V1 — busca no OpenAlex a partir do plano confirmado pelo Planner."""

import os

import pyalex
from dotenv import load_dotenv
from pyalex import Works

load_dotenv()
pyalex.config.api_key = os.getenv("OPENALEX_API_KEY")


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
