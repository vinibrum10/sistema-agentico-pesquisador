"""Pesquisa automática: busca + triagem, limpeza pelo loop e rodadas de snowballing com regras de parada."""

from collections import Counter

from agent_research.refino.loop import executar_loop, ler_vereditos
from agent_research.refino.snowball import executar_snowball
from agent_research.screening.revisao import gerar_revisao


PISO = 0.3                # precisão mínima de uma rodada (relevantes / válidos)
MAX_SNOWBALL = 3          # rodadas de snowballing por execução
MIN_RELEVANTES_NOVOS = 5  # abaixo disso, uma nova rodada não compensa


def snowball_com_parada(dados: dict) -> str:
    """Roda até MAX_SNOWBALL rodadas e devolve o motivo da parada."""

    for rodada in range(1, MAX_SNOWBALL + 1):
        print(f"\n=== Snowballing {rodada}/{MAX_SNOWBALL} ===")

        linha = executar_snowball(dados)

        if not linha:
            return "acabaram os candidatos do snowballing"

        if linha["relevante"] < MIN_RELEVANTES_NOVOS:
            return (
                f"snowballing {rodada} trouxe menos de "
                f"{MIN_RELEVANTES_NOVOS} relevantes novos"
            )

        if float(linha["precisao"]) < PISO:
            return f"snowballing {rodada} ficou abaixo do piso de {PISO:.0%}"

    return f"limite de {MAX_SNOWBALL} rodadas de snowballing"


def executar_pesquisa_automatica(dados: dict) -> dict:
    print("\n=== Busca e triagem ===")

    melhor = executar_loop(dados, piso=PISO)
    decisao = melhor["precisao"] < PISO

    if decisao:
        parada = (
            f"a busca não atingiu o piso de {PISO:.0%}; "
            "snowballing não executado"
        )
    else:
        parada = snowball_com_parada(dados)

    contagem = Counter(ler_vereditos().values())

    print("\n=== Resumo da pesquisa automática ===")
    print(f"Relevantes: {contagem['relevante']}")
    print(f"Talvez (para revisar): {contagem['talvez']}")
    print(
        f"Lixo: {contagem['lixo']} | "
        f"Descartados: {contagem['descartado']} | "
        f"Erros: {contagem['erro']}"
    )
    print(f"Parada: {parada}")

    if decisao:
        print("\nATENÇÃO: decisão do pesquisador necessária (ver loop_log.csv).")

    gerar_revisao()

    return {"parada": parada, "decisao": decisao, **contagem}
