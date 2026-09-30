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
    "tema_confirmado",
    "veredito_anterior",
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
        "tema_confirmado": "sim",
        "veredito_anterior": "",
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
        "tema_confirmado": "sim",
        "veredito_anterior": "",
    }


def carregar_triagem(incluir_erros: bool = False) -> dict:
    """Vereditos ja gravados; "erro" nao conta e sera julgado de novo."""

    if not SCREENING_FILE.exists():
        return {}

    with open(SCREENING_FILE, encoding="utf-8-sig", newline="") as f:
        return {
            linha["openalex_id"]: linha
            for linha in csv.DictReader(f)
            if incluir_erros or linha["veredito"] != "erro"
        }


def veredito_anterior_de(antiga: dict | None) -> str:
    """Veredito que o paper tinha antes de ser julgado de novo ("" se nao tinha)."""
    if not antiga:
        return ""

    if antiga["veredito"] == "erro":
        return antiga.get("veredito_anterior") or ""

    return antiga["veredito"]


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


def marcar_triagem_desatualizada() -> int:
    """Reavaliar depois: marca os vereditos como de outro tema, sem chamar o modelo.

    Devolve quantos vereditos foram marcados. O contexto gravado em
    triagem_contexto.json nao muda, entao a proxima triagem refaz tudo.
    """
    gravadas = carregar_triagem(incluir_erros=True)

    if not gravadas:
        return 0

    marcados = 0

    for linha in gravadas.values():
        if linha["veredito"] != "descartado":
            linha["tema_confirmado"] = "não"
            marcados += 1

        linha.setdefault("veredito_anterior", "")

    temporario = SCREENING_FILE.with_name(SCREENING_FILE.name + ".tmp")

    with open(temporario, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(gravadas.values())

    temporario.replace(SCREENING_FILE)

    return marcados


def mostrar_transicoes(saida: list) -> None:
    """Resumo "anterior -> atual" dos papers refeitos (le o veredito_anterior gravado)."""
    mudancas = {}
    iguais = 0
    caiu = []

    for linha in saida:
        antes = linha.get("veredito_anterior") or ""

        if linha.get("tema_confirmado") != "sim" or not antes:
            continue

        if antes == linha["veredito"]:
            iguais += 1
            continue

        mudancas[(antes, linha["veredito"])] = mudancas.get((antes, linha["veredito"]), 0) + 1

        if antes == "relevante" and linha["veredito"] == "lixo":
            caiu.append(linha["titulo"])

    print("\n=== Mudanças de veredito (anterior → atual) ===")
    print(f"Sem mudança: {iguais}")

    for (antes, agora), total in sorted(mudancas.items(), key=lambda m: -m[1]):
        destaque = "   <-- revise" if (antes, agora) == ("relevante", "lixo") else ""
        print(f"{antes} → {agora}: {total}{destaque}")

    for titulo in caiu[:10]:
        print(f"  relevante → lixo: {titulo[:80]}")

    if len(caiu) > 10:
        print(f"  ... e mais {len(caiu) - 10}")

    print("Para ver só os que mudaram, filtre `veredito_anterior` no screening.csv.")


def executar_triagem(dados: dict):
    linhas = carregar_resultados()
    descartes = filtrar(linhas)
    modelo = criar_juiz()
    gravadas = carregar_triagem(incluir_erros=True)
    anteriores = {
        pid: antiga
        for pid, antiga in gravadas.items()
        if antiga["veredito"] != "erro"
    }
    desatualizada = bool(anteriores) and triagem_desatualizada(dados["oficial"])
    # Tambem vale para a retomada de uma reavaliacao interrompida (restam vereditos "não").
    refazendo = desatualizada or any(
        antiga.get("tema_confirmado") == "não" for antiga in anteriores.values()
    )

    if desatualizada:
        print("\nO tema, o objetivo ou o foco mudaram desde a última triagem.")
        print(f"Os {len(anteriores)} vereditos anteriores serão refeitos.")

    # Quem nao precisa do LLM ja entra: a gravacao parcial nao perde vereditos.
    # Veredito de outro tema continua gravado, marcado "não", ate ser refeito.
    por_id = {}
    prontos = set()

    for pid, antiga in anteriores.items():
        if not desatualizada and antiga.get("tema_confirmado") in (None, "", "sim"):
            por_id[pid] = {**antiga, "tema_confirmado": "sim"}
            prontos.add(pid)
        else:
            por_id[pid] = {**antiga, "tema_confirmado": "não"}

    for linha in linhas:
        pid = linha["openalex_id"]

        # Descartes sao recalculados sempre: valem tambem para papers ja triados.
        if pid in descartes:
            por_id[pid] = linha_sem_llm(linha, "descartado", descartes[pid])
            prontos.add(pid)

    novos = 0

    for numero, linha in enumerate(linhas, start=1):
        pid = linha["openalex_id"]

        if pid in prontos:
            continue

        novos += 1
        print(f"[{numero}/{len(linhas)}] {linha['titulo'][:70]}")

        try:
            nova = julgar(modelo, dados["oficial"], linha)

        except json.JSONDecodeError:
            nova = linha_sem_llm(
                linha,
                "erro",
                "modelo não retornou JSON válido",
            )
            nova["tema_confirmado"] = "não"

        except Exception as erro:
            raise RuntimeError(
                f"falha ao chamar o modelo local ({erro}). "
                f"Confirme que o Ollama está em execução e que o modelo "
                f"{modelo.model} está instalado. "
                "Os vereditos já gravados foram mantidos."
            ) from erro

        nova["veredito_anterior"] = veredito_anterior_de(gravadas.get(pid))
        por_id[pid] = nova

        gravar_triagem(linhas, por_id, dados["oficial"])

    saida = gravar_triagem(linhas, por_id, dados["oficial"])

    resumo = {}
    for linha in saida:
        resumo[linha["veredito"]] = resumo.get(linha["veredito"], 0) + 1

    print("\n=== Resumo da triagem ===")
    print(f"Papers novos triados: {novos}")
    for veredito, total in sorted(resumo.items()):
        print(f"{veredito}: {total}")

    if refazendo:
        mostrar_transicoes(saida)

    return SCREENING_FILE
