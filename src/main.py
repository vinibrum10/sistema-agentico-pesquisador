from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ACTIVE_RESEARCH_DIR = PROJECT_ROOT / "data" / "active_research"
CONTEXT_FILE = ACTIVE_RESEARCH_DIR / "context.json"


FOCOS = {
    "1": "panorama",
    "2": "metodos",
    "3": "dados",
    "4": "nao_sei",
}


def existe_pesquisa_ativa() -> bool:
    return CONTEXT_FILE.exists()


def perguntar_foco() -> str:
    while True:
        print("\n3. Qual é o foco desta busca?")
        print("[1] Panorama geral / estado da arte")
        print("[2] Métodos e técnicas")
        print("[3] Dados e datasets")
        print("[4] Ainda não sei")

        escolha = input("> ").strip()

        if escolha in FOCOS:
            return FOCOS[escolha]

        print("\nOpção inválida. Escolha 1, 2, 3 ou 4.")


def executar_intake() -> dict:
    print("\nVamos iniciar uma nova pesquisa.\n")

    tema = input("1. Qual é o tema da tese?\n> ").strip()

    objetivo = input("\n2. Qual é o objetivo da pesquisa?\n> ").strip()

    foco = perguntar_foco()

    restricao = input(
        "\n4. Existe alguma restrição importante?\n"
        "Se não houver, escreva 'Nenhuma'.\n> "
    ).strip()

    return {
        "tema": tema,
        "objetivo": objetivo,
        "foco": foco,
        "restricao": restricao,
    }


def mostrar_respostas(respostas: dict) -> None:
    print("\n=== Intake coletado ===\n")
    print(f"Tema: {respostas['tema']}")
    print(f"Objetivo: {respostas['objetivo']}")
    print(f"Foco: {respostas['foco']}")
    print(f"Restrição: {respostas['restricao']}")

    print("\nEssas informações ainda não foram salvas.")


def main() -> None:
    print("\n=== Sistema Agêntico Pesquisador ===\n")

    if existe_pesquisa_ativa():
        print("Pesquisa ativa encontrada.")
        return

    print("Nenhuma pesquisa ativa encontrada.")

    respostas = executar_intake()
    mostrar_respostas(respostas)


if __name__ == "__main__":
    main()