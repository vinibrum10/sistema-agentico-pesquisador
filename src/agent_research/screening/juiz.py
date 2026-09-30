"""Triagem: juiz LLM local, um paper por vez, a partir de título e resumo."""

import csv
import json

from langchain_ollama import ChatOllama

from agent_research.screening.filtros import carregar_resultados, filtrar
from core.pesquisa_ativa import ACTIVE_RESEARCH_DIR, ROTULOS_FOCO
from core.texto import normalizar_texto


SCREENING_FILE = ACTIVE_RESEARCH_DIR / "screening.csv"
CONTEXTO_TRIAGEM_FILE = ACTIVE_RESEARCH_DIR / "triagem_contexto.json"

COLUNAS = [
    "openalex_id",
    "titulo",
    "veredito",
    "justificativa",
    "trecho",
    "confianca",
]

MAX_RESUMO = 2500

# Saída estruturada: tipos obrigatórios, sem exemplo de valores para copiar.
ESQUEMA = {
    "type": "object",
    "properties": {
        "objeto": {"type": "string"},
        "mesmo_dominio": {"type": "boolean"},
        "mesmo_problema": {"type": "boolean"},
        "trecho": {"type": "string"},
    },
    "required": ["objeto", "mesmo_dominio", "mesmo_problema", "trecho"],
}


def criar_juiz() -> ChatOllama:
    return ChatOllama(
        model="qwen3:8b",
        temperature=0,
        reasoning=False,
        format=ESQUEMA,
    )


def linha_sem_llm(linha: dict, veredito: str, justificativa: str) -> dict:
    return {
        "openalex_id": linha["openalex_id"],
        "titulo": linha["titulo"],
        "veredito": veredito,
        "justificativa": justificativa,
        "trecho": "",
        "confianca": "",
    }


def sim(valor) -> bool:
    return str(valor).strip().lower() in {"true", "sim", "yes"}


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

Ao comparar o artigo com a pesquisa, IGNORE as técnicas usadas
(por exemplo: aprendizado de máquina, estatística, simulação).
Compare apenas O QUE é estudado.

Campos da resposta:
- objeto: em poucas palavras, o que o artigo estuda ou analisa.
- mesmo_dominio: o artigo estuda o mesmo tipo de coisa que a pesquisa,
  na mesma área de aplicação, mesmo que em outro local ou exemplar?
- mesmo_problema: o artigo tenta resolver o mesmo problema da pesquisa
  ou um problema análogo direto?
- trecho: uma frase curta copiada LITERALMENTE do resumo que sustente
  as respostas; vazio se não houver resumo.

Responda em JSON.
"""

    resposta = json.loads(modelo.invoke(prompt).content)

    dominio = sim(resposta.get("mesmo_dominio"))
    problema = sim(resposta.get("mesmo_problema"))

    if not dominio:
        veredito = "lixo"
    elif problema:
        veredito = "relevante"
    else:
        veredito = "talvez"

    # Sem resumo, o titulo nao basta para descartar: vai para revisao humana.
    if not resumo and veredito == "lixo":
        veredito = "talvez"

    trecho = str(resposta.get("trecho", "")).strip()

    trecho_valido = bool(trecho) and (
        normalizar_texto(trecho) in normalizar_texto(resumo)
    )

    return {
        "openalex_id": linha["openalex_id"],
        "titulo": linha["titulo"],
        "veredito": veredito,
        "justificativa": (
            f"objeto: {str(resposta.get('objeto', '')).strip()}; "
            f"mesmo_dominio={dominio}; mesmo_problema={problema}"
        ),
        "trecho": trecho,
        "confianca": "normal" if trecho_valido else "baixa",
    }


def carregar_triagem() -> dict:
    """Vereditos ja gravados; "erro" nao conta e sera julgado de novo."""

    if not SCREENING_FILE.exists():
        return {}

    with open(SCREENING_FILE, encoding="utf-8-sig", newline="") as f:
        return {
            linha["openalex_id"]: linha
            for linha in csv.DictReader(f)
            if linha["veredito"] != "erro"
        }


def contexto_do_juiz(oficial: dict) -> dict:
    """O que o juiz usa do contexto: se mudar, os vereditos antigos deixam de valer."""
    return {
        "tema": oficial["tema"],
        "objetivo": oficial["objetivo"],
        "foco": oficial["foco"],
    }


def triagem_desatualizada(oficial: dict) -> bool:
    """True se a triagem gravada foi feita com outro tema, objetivo ou foco."""
    if not SCREENING_FILE.exists() or not CONTEXTO_TRIAGEM_FILE.exists():
        return False

    try:
        gravado = json.loads(CONTEXTO_TRIAGEM_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True

    return gravado != contexto_do_juiz(oficial)


def gravar_triagem(linhas: list, por_id: dict, oficial: dict) -> list:
    """Grava screening.csv (por troca de arquivo) e o contexto usado; devolve as linhas gravadas."""
    saida = [
        por_id[linha["openalex_id"]]
        for linha in linhas
        if linha["openalex_id"] in por_id
    ]

    temporario = SCREENING_FILE.with_name(SCREENING_FILE.name + ".tmp")

    with open(temporario, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(saida)

    temporario.replace(SCREENING_FILE)

    CONTEXTO_TRIAGEM_FILE.write_text(
        json.dumps(contexto_do_juiz(oficial), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return saida


def executar_triagem(dados: dict):
    linhas = carregar_resultados()
    descartes = filtrar(linhas)
    modelo = criar_juiz()
    anteriores = carregar_triagem()

    if anteriores and triagem_desatualizada(dados["oficial"]):
        print("\nO tema, o objetivo ou o foco mudaram desde a última triagem.")
        print(f"Os {len(anteriores)} vereditos anteriores serão refeitos.")
        anteriores = {}

    # Quem nao precisa do LLM ja entra: a gravacao parcial nao perde vereditos.
    por_id = {}

    for linha in linhas:
        pid = linha["openalex_id"]

        # Descartes sao recalculados sempre: valem tambem para papers ja triados.
        if pid in descartes:
            por_id[pid] = linha_sem_llm(linha, "descartado", descartes[pid])
        elif pid in anteriores:
            por_id[pid] = anteriores[pid]

    novos = 0

    for numero, linha in enumerate(linhas, start=1):
        pid = linha["openalex_id"]

        if pid in por_id:
            continue

        novos += 1
        print(f"[{numero}/{len(linhas)}] {linha['titulo'][:70]}")

        try:
            por_id[pid] = julgar(modelo, dados["oficial"], linha)

        except json.JSONDecodeError:
            por_id[pid] = linha_sem_llm(
                linha,
                "erro",
                "modelo não retornou JSON válido",
            )

        except Exception as erro:
            raise RuntimeError(
                f"falha ao chamar o modelo local ({erro}). "
                f"Confirme que o Ollama está em execução e que o modelo "
                f"{modelo.model} está instalado. "
                "Os vereditos já gravados foram mantidos."
            ) from erro

        gravar_triagem(linhas, por_id, dados["oficial"])

    saida = gravar_triagem(linhas, por_id, dados["oficial"])

    resumo = {}
    for linha in saida:
        resumo[linha["veredito"]] = resumo.get(linha["veredito"], 0) + 1

    print("\n=== Resumo da triagem ===")
    print(f"Papers novos triados: {novos}")
    for veredito, total in sorted(resumo.items()):
        print(f"{veredito}: {total}")

    return SCREENING_FILE
