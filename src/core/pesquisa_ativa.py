"""Pesquisa ativa: caminhos, leitura, gravação, backup e remoção do context.json."""

import json
import re
import shutil
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path


# src/core/pesquisa_ativa.py -> raiz do projeto
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


ACTIVE_RESEARCH_DIR = PROJECT_ROOT / "data" / "active_research"


BACKUPS_DIR = PROJECT_ROOT / "data" / "backups"


CONTEXT_FILE = ACTIVE_RESEARCH_DIR / "context.json"


# Etapa do workflow em que a pesquisa ativa parou.
ETAPA_INTAKE_CONCLUIDO = "intake_concluido"


FOCOS = {
    "1": "panorama",
    "2": "metodos",
    "3": "dados",
    "4": "nao_sei",
}


ROTULOS_FOCO = {
    "panorama": "Panorama geral / estado da arte",
    "metodos": "Métodos e técnicas",
    "dados": "Dados e datasets",
    "nao_sei": "Ainda não sei",
}


def existe_pesquisa_ativa() -> bool:
    return CONTEXT_FILE.exists()


def salvar_contexto(
    respostas: dict,
    contexto: dict,
) -> Path:

    ACTIVE_RESEARCH_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Separação: o que o pesquisador respondeu,
    # o que ele definiu como oficial e o que ele aprovou.
    dados = {
        "etapa": ETAPA_INTAKE_CONCLUIDO,
        "confirmado_em": datetime.now().isoformat(
            timespec="seconds"
        ),
        "respostas_intake": {
            "tema": respostas["tema"],
            "objetivo": respostas["objetivo"],
            "foco": respostas["foco"],
            "restricao": respostas["restricao"],
        },
        "oficial": {
            "tema": contexto["tema"],
            "objetivo": contexto["objetivo"],
            "foco": contexto["foco"],
            "restricao": contexto["restricao"],
        },
        "derivados_aprovados": {
            "idiomas": contexto["idiomas"],
            "termos_base": contexto["termos_base"],
            "restricao_geografica": contexto[
                "restricao_geografica"
            ],
            "expansoes": contexto["expansoes_aprovadas"],
        },
    }

    CONTEXT_FILE.write_text(
        json.dumps(
            dados,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return CONTEXT_FILE


# ==================================================
# PESQUISA ATIVA — Manter / Ajustar / Começar pesquisa nova
# ==================================================


def carregar_contexto() -> dict:
    return json.loads(
        CONTEXT_FILE.read_text(encoding="utf-8")
    )


def contexto_para_exibicao(dados: dict) -> dict:
    oficial = dados["oficial"]
    derivados = dados["derivados_aprovados"]

    return {
        "tema": oficial["tema"],
        "objetivo": oficial["objetivo"],
        "foco": oficial["foco"],
        "restricao": oficial["restricao"],
        "idiomas": derivados["idiomas"],
        "termos_base": derivados["termos_base"],
        "restricao_geografica": derivados[
            "restricao_geografica"
        ],
        "expansoes_aprovadas": derivados["expansoes"],
    }


def apagar_pesquisa_ativa() -> None:
    if ACTIVE_RESEARCH_DIR.exists():
        shutil.rmtree(ACTIVE_RESEARCH_DIR)


def criar_backup_pesquisa_ativa(tema: str) -> Path:
    """Compacta data/active_research/ em data/backups/ e confere o zip."""
    arquivos = [a for a in sorted(ACTIVE_RESEARCH_DIR.rglob("*")) if a.is_file()]
    if not arquivos:
        raise RuntimeError("não há arquivos para incluir no backup")

    slug = unicodedata.normalize("NFKD", tema).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")[:40] or "pesquisa"
    agora = datetime.now().strftime("%Y-%m-%d_%H%M")

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    destino = BACKUPS_DIR / f"pesquisa_{slug}_{agora}.zip"

    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
        for arquivo in arquivos:
            zf.write(arquivo, arquivo.relative_to(ACTIVE_RESEARCH_DIR))

    with zipfile.ZipFile(destino) as zf:
        if zf.testzip() is not None or len(zf.namelist()) != len(arquivos):
            destino.unlink()
            raise RuntimeError("o zip gerado não passou na conferência")

    return destino
