"""Snowballing: candidatos a partir das referências e dos trabalhos relacionados dos papers relevantes."""

import csv
from collections import Counter

from pyalex import Works

from agent_research.refino.loop import registrar_rodada
from agent_research.screening.juiz import SCREENING_FILE, executar_triagem
from agent_research.search.openalex import RESULTS_FILE, salvar_resultados


LOTE = 50  # IDs por filtro OR (limite da API: 100)


def curto(openalex_id: str) -> str:
    return openalex_id.rsplit("/", 1)[-1]


def buscar_por_ids(ids: list, campos: list | None = None) -> list:
    works = []

    for inicio in range(0, len(ids), LOTE):
        lote = "|".join(curto(pid) for pid in ids[inicio:inicio + LOTE])
        consulta = Works().filter(openalex_id=lote)

        if campos:
            consulta = consulta.select(campos)

        works += consulta.get(per_page=LOTE)

    return works


def sementes() -> list:
    with open(SCREENING_FILE, encoding="utf-8-sig", newline="") as f:
        return [
            linha["openalex_id"]
            for linha in csv.DictReader(f)
            if linha["veredito"] == "relevante"
        ]


def ids_conhecidos() -> set:
    with open(RESULTS_FILE, encoding="utf-8-sig", newline="") as f:
        return {linha["openalex_id"] for linha in csv.DictReader(f)}


def coletar_candidatos(min_ligacoes: int = 2, maximo: int = 50) -> list:
    """
    Retorna [(openalex_id, ligacoes)] em ordem decrescente de ligações.
    Ligação = uma semente cita o candidato ou o aponta como relacionado.
    Papers já presentes no results.csv ficam de fora.
    """

    seeds = sementes()
    conhecidos = ids_conhecidos()
    ligacoes = Counter()

    for work in buscar_por_ids(seeds, ["id", "referenced_works", "related_works"]):
        vizinhos = set(work.get("referenced_works") or []) | set(
            work.get("related_works") or []
        )
        ligacoes.update(v for v in vizinhos if v not in conhecidos)

    fortes = [
        (pid, n) for pid, n in ligacoes.most_common() if n >= min_ligacoes
    ]

    print(
        f"Sementes: {len(seeds)} | vizinhos novos: {len(ligacoes)} | "
        f"com >= {min_ligacoes} ligações: {len(fortes)}"
    )

    return fortes[:maximo]


def executar_snowball(dados: dict, min_ligacoes: int = 2, maximo: int = 50) -> dict:
    """Uma rodada: candidatos por citação → results.csv → triagem → loop_log.csv."""

    candidatos = coletar_candidatos(min_ligacoes, maximo)

    if not candidatos:
        print("\nNenhum candidato novo com ligações suficientes.")
        return {}

    works = buscar_por_ids([pid for pid, _ in candidatos])
    salvar_resultados(works, "snowball")
    executar_triagem(dados)

    return registrar_rodada(
        [work["id"] for work in works],
        "snowball",
        "snowball",
        motivo=f"{len(works)} candidatos com >= {min_ligacoes} ligações",
    )
