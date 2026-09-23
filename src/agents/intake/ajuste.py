"""Ajustar pesquisa atual: altera um campo por vez do contexto salvo."""

from agents.intake.intake import (
    analisar_contexto_oficial,
    confirmar_contexto_final,
    confirmar_idiomas,
    confirmar_termos_base,
    montar_contexto_confirmado,
    mostrar_contexto_final,
    mostrar_contexto_oficial,
    mostrar_termos_rejeitados,
    perguntar_foco,
    validar_sugestoes,
)
from core.pesquisa_ativa import (
    ROTULOS_FOCO,
    contexto_para_exibicao,
    salvar_contexto,
)


CAMPOS_AJUSTE = {
    "1": "tema",
    "2": "objetivo",
    "3": "foco",
    "4": "restricao",
    "5": "idiomas",
    "6": "termos_base",
}


ROTULOS_CAMPO = {
    "tema": "Tema",
    "objetivo": "Objetivo",
    "foco": "Foco",
    "restricao": "Restrição",
    "idiomas": "Idiomas",
    "termos_base": "Termos-base",
}


def descrever_campo(contexto: dict, campo: str) -> str:
    if campo == "foco":
        return ROTULOS_FOCO.get(contexto["foco"], contexto["foco"])

    if campo == "idiomas":
        return ", ".join(contexto["idiomas"])

    if campo == "termos_base":
        return "; ".join(
            termo["origem"] for termo in contexto["termos_base"]
        ) or "(nenhum)"

    return contexto[campo]


def escolher_campo_ajuste(contexto: dict) -> str | None:
    while True:
        print("\n=== Ajustar pesquisa atual ===")

        for numero, campo in CAMPOS_AJUSTE.items():
            print(f"\n[{numero}] {ROTULOS_CAMPO[campo]}")
            print(f"    {descrever_campo(contexto, campo)}")

        print("\n[0] Voltar sem alterar")

        escolha = input("> ").strip()

        if escolha == "0":
            return None

        if escolha in CAMPOS_AJUSTE:
            return CAMPOS_AJUSTE[escolha]

        print("\nOpção inválida.")


def confirmar_antes_depois(
    rotulo: str,
    antes: str,
    depois: str,
) -> bool:

    print(f"\n=== {rotulo}: antes / depois ===\n")
    print(f"Antes:  {antes}")
    print(f"Depois: {depois}")

    while True:
        print("\n[1] Confirmar alteração")
        print("[2] Cancelar")

        escolha = input("> ").strip()

        if escolha == "1":
            return True

        if escolha == "2":
            return False

        print("\nOpção inválida.")


def ajustar_texto_oficial(
    contexto: dict,
    campo: str,
) -> dict | None:
    """
    Tema, Objetivo ou Restrição: os termos dependem
    desses textos, então a chamada 2 roda de novo
    sobre o novo contexto oficial.
    """

    rotulo = ROTULOS_CAMPO[campo]

    while True:
        novo = input(
            f"\nDigite o novo texto para {rotulo}:\n> "
        ).strip()

        if novo:
            break

        print("\nO texto não pode ficar vazio.")

    if not confirmar_antes_depois(rotulo, contexto[campo], novo):
        return None

    oficial = {
        "tema": contexto["tema"],
        "objetivo": contexto["objetivo"],
        "foco": contexto["foco"],
        "restricao": contexto["restricao"],
    }
    oficial[campo] = novo

    print(
        f"\n{rotulo} alterado. Os termos dependem desse texto,"
        " então o contexto oficial será analisado de novo."
    )

    mostrar_contexto_oficial(oficial)

    print(
        "\nAnalisando o contexto oficial "
        "com o modelo local..."
    )

    sugestoes = analisar_contexto_oficial(oficial)
    resultado = validar_sugestoes(sugestoes, oficial)

    mostrar_termos_rejeitados(
        resultado["termos_base_rejeitados"]
    )

    return montar_contexto_confirmado(oficial, resultado)


def ajustar_foco(contexto: dict) -> dict | None:
    while True:
        foco = perguntar_foco()

        if foco != "nao_sei":
            break

        print(
            "\nNo ajuste, escolha um foco definido (1, 2 ou 3)."
        )

    if not confirmar_antes_depois(
        "Foco",
        ROTULOS_FOCO[contexto["foco"]],
        ROTULOS_FOCO[foco],
    ):
        return None

    return {**contexto, "foco": foco}


def ajustar_termos(contexto: dict) -> dict:
    oficial = {
        "tema": contexto["tema"],
        "objetivo": contexto["objetivo"],
        "restricao": contexto["restricao"],
    }

    termos = confirmar_termos_base(
        contexto["termos_base"],
        oficial,
    )

    # Expansões de termos removidos saem junto.
    codigos = {termo["codigo"] for termo in termos}

    expansoes = [
        expansao
        for expansao in contexto["expansoes_aprovadas"]
        if expansao.get("codigo_base") in codigos
    ]

    removidas = (
        len(contexto["expansoes_aprovadas"]) - len(expansoes)
    )

    if removidas:
        print(
            f"\n{removidas} expansão(ões) removida(s) junto "
            "com os termos-base."
        )

    return {
        **contexto,
        "termos_base": termos,
        "expansoes_aprovadas": expansoes,
    }


def ajustar_pesquisa(dados: dict) -> bool:
    """
    Ajusta um campo por vez. Só grava depois da
    confirmação final. Retorna True se salvou.
    """

    contexto = contexto_para_exibicao(dados)

    campo = escolher_campo_ajuste(contexto)

    if campo is None:
        print("\nNada foi alterado.")
        return False

    if campo in {"tema", "objetivo", "restricao"}:
        novo = ajustar_texto_oficial(contexto, campo)

    elif campo == "foco":
        novo = ajustar_foco(contexto)

    elif campo == "idiomas":
        novo = {
            **contexto,
            "idiomas": confirmar_idiomas(contexto["idiomas"]),
        }

    else:
        novo = ajustar_termos(contexto)

    if novo is None:
        print("\nAjuste cancelado. Nada foi alterado.")
        return False

    mostrar_contexto_final(
        novo,
        titulo="Contexto ajustado",
    )

    if not confirmar_contexto_final():
        print("\nAjuste cancelado. Nada foi alterado.")
        return False

    caminho = salvar_contexto(
        dados["respostas_intake"],
        novo,
    )

    print(f"\nContexto ajustado salvo em: {caminho}")
    return True
