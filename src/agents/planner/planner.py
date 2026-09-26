"""Planner V1: monta o plano de busca de forma determinística, sem LLM."""

from agents.search.openalex import (
    montar_consulta,
)
from core.pesquisa_ativa import (
    ROTULOS_FOCO,
)
from core.texto import (
    ler_indices,
    sem_duplicados,
)


# Grupos genéricos por foco (seção 17). Não dependem do tema.
GRUPOS_FOCO = {
    "metodos": {
        "pt": ["método", "metodologia", "técnica", "abordagem"],
        "en": ["method", "methodology", "technique", "approach"],
    },
    "dados": {
        "pt": ["conjunto de dados", "base de dados", "dados"],
        "en": ["dataset", "data set", "database"],
    },
}


def montar_plano(dados: dict) -> dict:
    """
    Monta a estrutura do plano a partir do contexto
    confirmado. Não usa LLM e não cria termos.
    """

    oficial = dados["oficial"]
    derivados = dados["derivados_aprovados"]
    idiomas = derivados["idiomas"]

    grupos = []

    # A: expansões entram no OR do termo-base ligado a elas.
    for termo in derivados["termos_base"]:
        variantes = {
            idioma: list(termo.get(idioma, []))
            for idioma in idiomas
        }

        for expansao in derivados["expansoes"]:
            if expansao.get("codigo_base") == termo["codigo"]:
                for idioma in idiomas:
                    variantes[idioma] += expansao.get(idioma, [])

        grupos.append(
            {
                "tipo": "conceito",
                "rotulo": termo["origem"],
                "variantes": {
                    idioma: sem_duplicados(lista)
                    for idioma, lista in variantes.items()
                },
                "incluido": True,
            }
        )

    # C: grupo genérico do foco.
    if oficial["foco"] in GRUPOS_FOCO:
        grupos.append(
            {
                "tipo": "foco",
                "rotulo": f"foco: {ROTULOS_FOCO[oficial['foco']]}",
                "variantes": {
                    idioma: list(
                        GRUPOS_FOCO[oficial["foco"]].get(idioma, [])
                    )
                    for idioma in idiomas
                },
                "incluido": True,
            }
        )

    # B: geografia aparece, mas começa desmarcada.
    geografia = derivados.get("restricao_geografica")

    if geografia:
        grupos.append(
            {
                "tipo": "geografia",
                "rotulo": f"geografia: {geografia.get('origem')}",
                "variantes": {
                    idioma: sem_duplicados(geografia.get(idioma, []))
                    for idioma in idiomas
                },
                "incluido": False,
            }
        )

    return {
        "idiomas": idiomas,
        "foco": oficial["foco"],
        "grupos": grupos,
    }


def mostrar_plano(plano: dict) -> None:
    print("\n=== Plano de busca ===")

    for numero, grupo in enumerate(plano["grupos"], start=1):
        marca = "x" if grupo["incluido"] else " "
        print(f"\n[{marca}] {numero}. {grupo['rotulo']}")

        for idioma in plano["idiomas"]:
            termos = grupo["variantes"].get(idioma, [])
            print(
                f"      {idioma.upper()}: "
                + (", ".join(termos) if termos else "(sem termos)")
            )

    print("\n--- Prévia da consulta ---")
    print(montar_consulta(plano) or "(vazia)")


def editar_plano(plano: dict) -> dict | None:
    while True:
        mostrar_plano(plano)

        print("\n[T n] Marcar/desmarcar grupo (ex.: T 3)")
        print("[C] Confirmar plano")
        print("[X] Cancelar")

        entrada = input("> ").strip()
        comando = entrada[:1].lower()
        argumento = entrada[1:].strip()

        if comando == "t":
            indices = ler_indices(argumento, len(plano["grupos"]))

            if indices is None or len(indices) != 1:
                print("\nInforme um único número válido.")
                continue

            grupo = plano["grupos"][indices[0] - 1]
            grupo["incluido"] = not grupo["incluido"]
            continue

        if comando == "c" and not argumento:
            tem_conceito = any(
                grupo["incluido"] and grupo["tipo"] == "conceito"
                for grupo in plano["grupos"]
            )

            if not tem_conceito:
                print(
                    "\nMarque pelo menos um grupo de termo-base."
                )
                continue

            return plano

        if comando == "x" and not argumento:
            return None

        print("\nOpção inválida. Use T n, C ou X.")


def executar_planner(dados: dict) -> dict | None:
    plano = montar_plano(dados)

    if not any(g["tipo"] == "conceito" for g in plano["grupos"]):
        print(
            "\nA pesquisa não tem termos-base. "
            "Use [2] Ajustar para adicioná-los."
        )
        return None

    plano = editar_plano(plano)

    if plano is None:
        print("\nPlano cancelado. Nada foi alterado.")
        return None

    print("\n=== Plano confirmado ===")
    print(montar_consulta(plano))

    return plano
