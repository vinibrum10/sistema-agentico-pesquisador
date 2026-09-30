"""Loop de refinamento: rodadas de busca + triagem com ajustes determinísticos, registradas em loop_log.csv."""

import copy
import csv
from datetime import datetime

from agent_research.planner.planner import montar_plano
from agent_research.screening.juiz import SCREENING_FILE, executar_triagem
from agent_research.search.openalex import (
    RESULTS_FILE,
    buscar,
    montar_consulta,
    salvar_resultados,
)
from core.pesquisa_ativa import ACTIVE_RESEARCH_DIR
from core.texto import normalizar_texto


LOOP_LOG_FILE = ACTIVE_RESEARCH_DIR / "loop_log.csv"

VEREDITOS = ["relevante", "talvez", "lixo", "descartado", "erro"]

COLUNAS = [
    "data_hora",
    "rodada",
    "consulta",
    "total",
    *VEREDITOS,
    "precisao",
    "ajuste",
    "motivo",
]


def ler_vereditos() -> dict:
    with open(SCREENING_FILE, encoding="utf-8-sig", newline="") as f:
        return {
            linha["openalex_id"]: linha["veredito"]
            for linha in csv.DictReader(f)
        }


def registrar_rodada(
    ids: list,
    rodada,
    consulta: str,
    ajuste: str = "",
    motivo: str = "",
) -> dict:
    """Mede os vereditos dos papers da rodada e grava uma linha no loop_log.csv."""

    vereditos = ler_vereditos()
    contagem = {veredito: 0 for veredito in VEREDITOS}

    for pid in ids:
        contagem[vereditos[pid]] += 1

    validos = len(ids) - contagem["descartado"] - contagem["erro"]
    precisao = contagem["relevante"] / validos if validos else 0.0

    linha = {
        "data_hora": datetime.now().isoformat(timespec="seconds"),
        "rodada": rodada,
        "consulta": consulta,
        "total": len(ids),
        **contagem,
        "precisao": f"{precisao:.2f}",
        "ajuste": ajuste,
        "motivo": motivo,
    }

    novo = not LOOP_LOG_FILE.exists()

    with open(LOOP_LOG_FILE, "a", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS)
        if novo:
            escritor.writeheader()
        escritor.writerow(linha)

    print(
        f"\nRodada {rodada}: precisão {precisao:.0%} "
        f"({contagem['relevante']}/{validos} relevantes)"
    )

    return linha


def executar_rodada(
    dados: dict,
    plano: dict,
    rodada: int,
    ajuste: str = "",
    motivo: str = "",
) -> dict:
    consulta = montar_consulta(plano)
    resultados = buscar(consulta)
    salvar_resultados(resultados, consulta)
    executar_triagem(dados)

    return registrar_rodada(
        [work["id"] for work in resultados],
        rodada,
        consulta,
        ajuste,
        motivo,
    )


def papers_da_rodada(consulta: str) -> list:
    vereditos = ler_vereditos()

    with open(RESULTS_FILE, encoding="utf-8-sig", newline="") as f:
        return [
            {
                "texto": normalizar_texto(
                    linha["titulo"] + " " + linha["abstract"]
                ),
                "veredito": vereditos.get(linha["openalex_id"], ""),
            }
            for linha in csv.DictReader(f)
            if linha["consulta_origem"] == consulta
        ]


def escolher_ajuste(dados: dict, plano: dict, consulta: str) -> tuple:
    """
    Um ajuste por rodada, aplicado na cópia do plano.
    Nunca remove termos-base; só expansões ou o grupo de foco.
    """

    derivados = dados["derivados_aprovados"]

    expansoes = {
        normalizar_texto(termo)
        for expansao in derivados["expansoes"]
        for idioma in derivados["idiomas"]
        for termo in expansao.get(idioma, [])
    }

    papers = papers_da_rodada(consulta)
    pior = None

    for grupo in plano["grupos"]:
        if not (grupo["incluido"] and grupo["tipo"] == "conceito"):
            continue

        for termos in grupo["variantes"].values():
            for termo in termos:
                chave = normalizar_texto(termo)

                if chave not in expansoes:
                    continue

                lixo = sum(
                    p["veredito"] == "lixo" and chave in p["texto"]
                    for p in papers
                )
                relevantes = sum(
                    p["veredito"] == "relevante" and chave in p["texto"]
                    for p in papers
                )

                if lixo >= 2 and lixo > relevantes and (
                    pior is None or relevantes - lixo < pior[0]
                ):
                    pior = (relevantes - lixo, lixo, relevantes, grupo, termo)

    if pior:
        _, lixo, relevantes, grupo, termo = pior

        for idioma, termos in grupo["variantes"].items():
            grupo["variantes"][idioma] = [t for t in termos if t != termo]

        return (
            f"remover expansão '{termo}'",
            f"{lixo} lixo e {relevantes} relevante(s) da rodada contêm o termo",
        )

    for grupo in plano["grupos"]:
        if grupo["tipo"] == "foco" and grupo["incluido"]:
            grupo["incluido"] = False
            return (
                "desmarcar grupo de foco",
                "grupo genérico, não filtra por conteúdo",
            )

    return ("", "")


def executar_loop(
    dados: dict,
    piso: float = 0.3,
    max_rodadas: int = 3,
) -> dict:
    """
    Objetivo: o máximo de relevantes com precisão >= piso.
    Abaixo do piso, aplica um ajuste (remoção) por rodada.
    Trabalha numa cópia do plano; o context.json não é alterado.
    """

    plano = montar_plano(dados)
    ajuste = motivo = ""
    rodadas = []

    for rodada in range(1, max_rodadas + 1):
        linha = executar_rodada(dados, plano, rodada, ajuste, motivo)

        rodadas.append(
            {
                "rodada": rodada,
                "precisao": float(linha["precisao"]),
                "relevantes": linha["relevante"],
                "consulta": linha["consulta"],
                "plano": copy.deepcopy(plano),
            }
        )

        if rodadas[-1]["precisao"] >= piso:
            print(f"\nPrecisão acima do piso de {piso:.0%} na rodada {rodada}.")
            break

        if rodada == max_rodadas:
            break

        ajuste, motivo = escolher_ajuste(dados, plano, linha["consulta"])

        if not ajuste:
            print("\nNenhum ajuste determinístico disponível.")
            break

        print(f"Ajuste para a rodada {rodada + 1}: {ajuste} ({motivo})")

    validas = [r for r in rodadas if r["precisao"] >= piso]

    if validas:
        melhor = max(validas, key=lambda r: (r["relevantes"], r["precisao"]))
    else:
        melhor = max(rodadas, key=lambda r: r["precisao"])
        print(
            f"\nATENÇÃO: nenhuma rodada atingiu o piso de {piso:.0%}. "
            "Decisão do pesquisador necessária."
        )

    print(
        f"\nMelhor rodada: {melhor['rodada']} "
        f"({melhor['relevantes']} relevantes, precisão {melhor['precisao']:.0%})"
    )
    print(f"Consulta: {melhor['consulta']}")
    print(f"Registro: {LOOP_LOG_FILE}")

    return melhor
