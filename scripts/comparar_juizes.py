"""Comparação de juízes (só leitura): o mesmo juiz com cada modelo, no gabarito.

Roda o juiz da triagem nos papers do gabarito com cada modelo de
config/modelos.json e compara com os seus rótulos. Não altera o
screening.csv: as respostas de cada modelo vão para
data/active_research/comparacao_juizes/. Uso:

    python scripts/comparar_juizes.py                      (todos os modelos)
    python scripts/comparar_juizes.py qwen3:8b deepseek-flash
"""

import csv
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import core.modelos as modelos
from agent_research.screening.calibracao import GABARITO_FILE, ROTULOS, intervalo_wilson
from agent_research.screening.filtros import carregar_resultados, filtrar
from agent_research.screening.juiz import COLUNAS, ESQUEMA, SCREENING_FILE, julgar, linha_sem_llm
from core.pesquisa_ativa import ACTIVE_RESEARCH_DIR, carregar_contexto


SAIDA_DIR = ACTIVE_RESEARCH_DIR / "comparacao_juizes"


def ler(caminho, delimitador=","):
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimitador))


def julgar_com(nome: str, oficial: dict, papers: list) -> list:
    """Vereditos de um modelo para os papers; grava em comparacao_juizes/<modelo>.csv."""
    modelo = modelos.criar_modelo("juiz", esquema=ESQUEMA, nome=nome)
    saida = []

    for numero, linha in enumerate(papers, start=1):
        print(f"\r  {nome}: {numero}/{len(papers)}", end="", flush=True)

        try:
            saida.append(julgar(modelo, oficial, linha))
        except json.JSONDecodeError:
            saida.append(linha_sem_llm(linha, "erro", "modelo não retornou JSON válido"))

    print()
    SAIDA_DIR.mkdir(parents=True, exist_ok=True)
    arquivo = SAIDA_DIR / f"{nome.replace(':', '_')}.csv"

    with open(arquivo, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(saida)

    return saida


def resumo(nome: str, saida: list, gabarito: dict, atual: dict, custo: float, segundos: float) -> str:
    juiz = {linha["openalex_id"]: linha["veredito"] for linha in saida}
    relevantes = [pid for pid in juiz if gabarito[pid] == "relevante"]
    r_ou_t = [pid for pid in juiz if gabarito[pid] in ("relevante", "talvez")]
    mantido = {pid for pid, v in juiz.items() if v in ("relevante", "talvez")}

    k = len(mantido.intersection(relevantes))
    baixo, alto = intervalo_wilson(k, len(relevantes))
    k_rt = len(mantido.intersection(r_ou_t))
    iguais_gabarito = sum(juiz[pid] == gabarito[pid] for pid in juiz)
    comparaveis = [pid for pid in juiz if atual.get(pid, "erro") != "erro"]
    iguais_atual = sum(juiz[pid] == atual[pid] for pid in comparaveis)
    erros = sum(v == "erro" for v in juiz.values())

    return (
        f"\n=== {nome} ===\n"
        f"Relevantes mantidos (recall): {k}/{len(relevantes)} ({k / len(relevantes):.0%}; "
        f"IC 95%: {baixo:.0%} a {alto:.0%})\n"
        f"Relevantes ou talvez mantidos: {k_rt}/{len(r_ou_t)} ({k_rt / len(r_ou_t):.0%})\n"
        f"Concordância com o gabarito: {iguais_gabarito}/{len(juiz)} ({iguais_gabarito / len(juiz):.0%})\n"
        f"Igual ao screening.csv atual: {iguais_atual}/{len(comparaveis)}\n"
        f"Erros de JSON: {erros}\n"
        f"Custo estimado: US$ {custo:.4f} (preços de config/modelos.json) · tempo: {segundos / 60:.1f} min"
    )


def main():
    config = json.loads(modelos.CONFIG_FILE.read_text(encoding="utf-8"))
    nomes = sys.argv[1:] or list(config["modelos"])

    gabarito = {
        linha["openalex_id"]: ROTULOS[linha["rotulo"].strip().lower()]
        for linha in ler(GABARITO_FILE, ";")
    }

    if "relevante" not in gabarito.values():
        sys.exit("O gabarito não tem papers marcados como relevantes. Nada a comparar.")

    linhas = carregar_resultados()
    descartes = filtrar(linhas)
    papers = [
        linha
        for linha in linhas
        if linha["openalex_id"] in gabarito and linha["openalex_id"] not in descartes
    ]
    atual = (
        {linha["openalex_id"]: linha["veredito"] for linha in ler(SCREENING_FILE)}
        if SCREENING_FILE.exists()
        else {}
    )
    oficial = carregar_contexto()["oficial"]

    print(f"{len(papers)} papers do gabarito (fora os descartados pelos filtros).")
    resumos = []

    for nome in nomes:
        gasto_antes = modelos.gasto_execucao
        inicio = time.time()

        try:
            saida = julgar_com(nome, oficial, papers)

        except modelos.TetoAtingido as erro:
            print(f"\nParado: {erro}")
            break

        except RuntimeError as erro:
            print(f"\n{nome}: pulado ({erro})")
            continue

        resumos.append(
            resumo(nome, saida, gabarito, atual, modelos.gasto_execucao - gasto_antes, time.time() - inicio)
        )

    for texto in resumos:
        print(texto)

    print(
        "\nComo ler: o que mais importa é o recall (relevantes mantidos). "
        "Com poucos relevantes no gabarito, intervalos que se sobrepõem "
        "não mostram diferença real entre os modelos."
    )


if __name__ == "__main__":
    main()
