"""Loop de refinamento: uma rodada de busca + triagem, registrada em loop_log.csv."""

import csv
from datetime import datetime

from agents.screening.juiz import SCREENING_FILE, executar_triagem
from agents.search.openalex import buscar, montar_consulta, salvar_resultados
from core.pesquisa_ativa import ACTIVE_RESEARCH_DIR


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

    with open(SCREENING_FILE, encoding="utf-8-sig", newline="") as f:
        vereditos = {
            linha["openalex_id"]: linha["veredito"]
            for linha in csv.DictReader(f)
        }

    contagem = {veredito: 0 for veredito in VEREDITOS}

    for work in resultados:
        contagem[vereditos[work["id"]]] += 1

    validos = len(resultados) - contagem["descartado"] - contagem["erro"]
    precisao = contagem["relevante"] / validos if validos else 0.0

    linha = {
        "data_hora": datetime.now().isoformat(timespec="seconds"),
        "rodada": rodada,
        "consulta": consulta,
        "total": len(resultados),
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
