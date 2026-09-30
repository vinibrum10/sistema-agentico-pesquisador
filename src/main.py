"""Ponto de entrada: pesquisa ativa (Manter / Ajustar / Mudar tema) e novo Intake."""

import json

from agent_intake.ajuste import (
    ajustar_pesquisa,
)
from agent_intake.intake import (
    analisar_contexto_oficial,
    confirmar_contexto_final,
    definir_texto_oficial,
    executar_intake,
    montar_contexto_confirmado,
    mostrar_contexto_final,
    mostrar_contexto_oficial,
    mostrar_respostas,
    mostrar_termos_rejeitados,
    validar_sugestoes,
)
from agent_research.planner.planner import (
    executar_planner,
)
from agent_research.search.openalex import (
    buscar,
    montar_consulta,
    salvar_resultados,
)
from agent_research.screening.juiz import (
    executar_triagem,
)
from agent_research.refino.loop import (
    executar_loop,
)
from agent_research.refino.snowball import (
    executar_snowball,
)
from agent_research.refino.automatico import (
    executar_pesquisa_automatica,
)
from agent_research.screening.revisao import (
    gerar_revisao,
)
from core.pesquisa_ativa import (
    CONTEXT_FILE,
    ETAPA_INTAKE_CONCLUIDO,
    apagar_pesquisa_ativa,
    carregar_contexto,
    contexto_para_exibicao,
    existe_pesquisa_ativa,
    salvar_contexto,
)


def menu_pesquisa_ativa(dados: dict) -> str:
    while True:
        print("\n=== Pesquisa ativa ===\n")
        print(f"Tema oficial: {dados['oficial']['tema']}")
        print(f"Etapa: {dados.get('etapa')}")

        print("\n[1] Manter pesquisa atual")
        print("[2] Ajustar pesquisa atual")
        print("[3] Mudar tema da tese")

        escolha = input("> ").strip()

        if escolha == "1":
            return "manter"

        if escolha == "2":
            return "ajustar"

        if escolha == "3":
            if confirmar_mudanca_de_tema(dados):
                return "mudar"
            continue

        print("\nOpção inválida. Escolha 1, 2 ou 3.")


# ==================================================
# AJUSTAR PESQUISA ATUAL
# ==================================================


def confirmar_mudanca_de_tema(dados: dict) -> bool:
    print("\n=== Mudar tema da tese ===\n")
    print(f"Tema atual: {dados['oficial']['tema']}")
    print(
        "\nATENÇÃO: o contexto científico e os resultados "
        "desta pesquisa serão apagados."
    )
    print("Não será mantido nenhum histórico.")

    while True:
        print("\n[1] Confirmar mudança")
        print("[2] Cancelar")

        escolha = input("> ").strip()

        if escolha == "1":
            return True

        if escolha == "2":
            print("\nMudança cancelada. Nada foi alterado.")
            return False

        print("\nOpção inválida.")


def executar_busca(plano: dict) -> None:
    while True:
        escolha = input("\nExecutar busca no OpenAlex? [s/n] ").strip().lower()

        if escolha == "n":
            print("\nBusca não executada.")
            return

        if escolha == "s":
            break

        print("\nOpção inválida.")

    consulta = montar_consulta(plano)

    try:
        resultados = buscar(consulta)
        total = salvar_resultados(resultados, consulta)

    except Exception as erro:
        print("\nNão foi possível buscar no OpenAlex.")
        print(f"Erro: {erro}")
        print("Nada foi salvo.")
        return

    print(f"\n{len(resultados)} resultado(s) nesta busca.")
    print(f"Total acumulado em results.csv: {total}")


def manter_pesquisa(dados: dict) -> None:
    mostrar_contexto_final(
        contexto_para_exibicao(dados),
        titulo="Pesquisa atual",
    )

    print(f"\nEtapa concluída: {dados.get('etapa')}")
    print(f"Confirmado em: {dados.get('confirmado_em')}")

    if dados.get("etapa") != ETAPA_INTAKE_CONCLUIDO:
        return

    while True:
        print("\n[1] Pesquisar (automático) — busca, triagem e snowballing")
        print("[2] Revisar resultados — relevantes e talvez em revisao.csv")
        print("[3] Opções avançadas — etapas manuais, uma por vez")
        print("[4] Sair")

        escolha = input("> ").strip()

        if escolha == "1":
            executar_pesquisa_automatica(dados)
            return

        if escolha == "2":
            gerar_revisao()
            return

        if escolha == "3":
            opcoes_avancadas(dados)
            continue

        if escolha == "4":
            return

        print("\nOpção inválida.")


def opcoes_avancadas(dados: dict) -> None:
    while True:
        print("\n=== Opções avançadas ===")
        print("[1] Montar plano de busca (manual)")
        print("[2] Triar resultados")
        print("[3] Refinar busca (loop)")
        print("[4] Snowballing (uma rodada)")
        print("[5] Voltar")

        escolha = input("> ").strip()

        if escolha == "1":
            plano = executar_planner(dados)

            if plano is not None:
                executar_busca(plano)

            return

        if escolha == "2":
            executar_triagem(dados)
            return

        if escolha == "3":
            executar_loop(dados)
            return

        if escolha == "4":
            executar_snowball(dados)
            return

        if escolha == "5":
            return

        print("\nOpção inválida.")


# ==================================================
# PLANNER V1 — determinístico, sem LLM
# ==================================================


def main() -> None:
    print(
        "\n=== Sistema Agêntico Pesquisador ===\n"
    )

    if existe_pesquisa_ativa():
        try:
            dados = carregar_contexto()
            contexto_para_exibicao(dados)

        except (json.JSONDecodeError, KeyError) as erro:
            print(
                "Pesquisa ativa encontrada, mas o arquivo "
                "context.json não pôde ser lido."
            )
            print(f"Erro: {erro}")
            print(f"Arquivo: {CONTEXT_FILE}")
            return

        acao = menu_pesquisa_ativa(dados)

        if acao == "manter":
            manter_pesquisa(dados)
            return

        if acao == "ajustar":
            try:
                ajustar_pesquisa(dados)

            except json.JSONDecodeError as erro:
                print(
                    "\nO modelo respondeu, "
                    "mas não retornou JSON válido."
                )
                print(f"Erro: {erro}")
                print("Nada foi alterado.")

            except Exception as erro:
                print("\nNão foi possível ajustar a pesquisa.")
                print(f"Erro: {erro}")
                print("Nada foi alterado.")

            return

        apagar_pesquisa_ativa()

        print(
            "\nPesquisa anterior apagada. "
            "Iniciando novo Intake."
        )

    else:
        print(
            "Nenhuma pesquisa ativa encontrada."
        )

    respostas = executar_intake()

    mostrar_respostas(respostas)

    try:
        # Etapa A: chamada 1 + decisão humana
        oficial = definir_texto_oficial(
            respostas
        )

        # A partir daqui, somente o contexto oficial é usado.
        mostrar_contexto_oficial(oficial)

        print(
            "\nAnalisando o contexto oficial "
            "com o modelo local..."
        )

        # Etapa B: chamada 2 sobre o contexto oficial
        sugestoes = analisar_contexto_oficial(
            oficial
        )

        resultado = validar_sugestoes(
            sugestoes,
            oficial,
        )

        mostrar_termos_rejeitados(
            resultado["termos_base_rejeitados"]
        )

        contexto = montar_contexto_confirmado(
            oficial,
            resultado,
        )

        mostrar_contexto_final(
            contexto
        )

        confirmado = confirmar_contexto_final()

        if confirmado:
            print(
                "\nContexto confirmado pelo pesquisador."
            )

            caminho = salvar_contexto(
                respostas,
                contexto,
            )

            print(
                f"Contexto salvo em: {caminho}"
            )
        else:
            print(
                "\nConfirmação cancelada."
            )
            print(
                "Nada foi salvo."
            )

    except json.JSONDecodeError as erro:
        print(
            "\nO modelo respondeu, "
            "mas não retornou JSON válido."
        )
        print(f"Erro: {erro}")

    except Exception as erro:
        print(
            "\nNão foi possível processar "
            "o Intake."
        )
        print(f"Erro: {erro}")


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print("\n\nInterrompido pelo usuário.")
        print(
            "Etapas concluídas ficam salvas; "
            "a triagem em andamento é refeita na próxima execução."
        )
