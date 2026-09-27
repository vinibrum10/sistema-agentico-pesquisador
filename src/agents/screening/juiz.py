"""Triagem: juiz LLM local, um paper por vez, a partir de título e resumo."""

import csv
import json

from agents.intake.intake import criar_modelo
from agents.screening.filtros import carregar_resultados, filtrar
from core.pesquisa_ativa import ACTIVE_RESEARCH_DIR, ROTULOS_FOCO
from core.texto import normalizar_texto


SCREENING_FILE = ACTIVE_RESEARCH_DIR / "screening.csv"

COLUNAS = [
    "openalex_id",
    "titulo",
    "veredito",
    "justificativa",
    "trecho",
    "confianca",
]

VEREDITOS = {"relevante", "talvez", "lixo"}

MAX_RESUMO = 2500


def linha_sem_llm(linha: dict, veredito: str, justificativa: str) -> dict:
    return {
        "openalex_id": linha["openalex_id"],
        "titulo": linha["titulo"],
        "veredito": veredito,
        "justificativa": justificativa,
        "trecho": "",
        "confianca": "",
    }


def julgar(modelo, oficial: dict, linha: dict) -> dict:
    resumo = linha["abstract"][:MAX_RESUMO]

    prompt = f"""
Você faz a triagem de artigos científicos para uma pesquisa.

Pesquisa:
- Tema: {oficial["tema"]}
- Objetivo: {oficial["objetivo"]}
- Foco da busca: {ROTULOS_FOCO[oficial["foco"]]}

Artigo:
- Título: {linha["titulo"]}
- Resumo: {resumo or "(sem resumo)"}

Classifique o artigo em relação ao OBJETIVO da pesquisa:
- "relevante": contribui diretamente para o objetivo, considerando o foco;
- "talvez": relacionado, mas com contribuição indireta ou parcial;
- "lixo": não contribui para o objetivo.

"justificativa": uma frase curta explicando o veredito.
"trecho": copie LITERALMENTE uma frase curta do resumo que sustente
o veredito. Se não houver resumo, use "".

Retorne SOMENTE JSON válido:

{{"veredito": "relevante", "justificativa": "texto", "trecho": "texto"}}
"""

    resposta = json.loads(modelo.invoke(prompt).content)

    veredito = str(resposta.get("veredito", "")).strip().lower()
    trecho = str(resposta.get("trecho", "")).strip()

    trecho_valido = bool(trecho) and (
        normalizar_texto(trecho) in normalizar_texto(resumo)
    )

    return {
        "openalex_id": linha["openalex_id"],
        "titulo": linha["titulo"],
        "veredito": veredito if veredito in VEREDITOS else "erro",
        "justificativa": str(resposta.get("justificativa", "")).strip(),
        "trecho": trecho,
        "confianca": "normal" if trecho_valido else "baixa",
    }


def executar_triagem(dados: dict):
    linhas = carregar_resultados()
    descartes = filtrar(linhas)
    modelo = criar_modelo()
    saida = []

    for numero, linha in enumerate(linhas, start=1):
        print(f"[{numero}/{len(linhas)}] {linha['titulo'][:70]}")

        if linha["openalex_id"] in descartes:
            saida.append(
                linha_sem_llm(
                    linha,
                    "descartado",
                    descartes[linha["openalex_id"]],
                )
            )
            continue

        try:
            saida.append(julgar(modelo, dados["oficial"], linha))

        except json.JSONDecodeError:
            saida.append(
                linha_sem_llm(
                    linha,
                    "erro",
                    "modelo não retornou JSON válido",
                )
            )

    with open(SCREENING_FILE, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(saida)

    return SCREENING_FILE
