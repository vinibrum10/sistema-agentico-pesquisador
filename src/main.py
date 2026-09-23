from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ACTIVE_RESEARCH_DIR = PROJECT_ROOT / "data" / "active_research"
CONTEXT_FILE = ACTIVE_RESEARCH_DIR / "context.json"


def existe_pesquisa_ativa() -> bool:
    return CONTEXT_FILE.exists()


def main() -> None:
    print("\n=== Sistema Agêntico Pesquisador ===\n")

    if existe_pesquisa_ativa():
        print("Pesquisa ativa encontrada.")
    else:
        print("Nenhuma pesquisa ativa encontrada.")
        print("Um novo Intake deverá ser iniciado.")


if __name__ == "__main__":
    main()