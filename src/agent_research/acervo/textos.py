"""Acervo: texto completo (PDF) dos papers mantidos na triagem (relevantes e talvez).

Importa os PDFs que o pesquisador coloca em entrada/ (identificados pelo DOI ou pelo
título nas duas primeiras páginas), baixa do OpenAlex os que ele tem e lista em
faltantes.csv os que ainda faltam. Os textos ficam em textos/<ID do OpenAlex>.pdf.
"""

import csv
import io
import logging
import re

import pyalex
import requests
from pyalex import Works
from pypdf import PdfReader

from agent_research.screening.juiz import SCREENING_FILE
from agent_research.search.openalex import RESULTS_FILE
from core.pesquisa_ativa import ACTIVE_RESEARCH_DIR
from core.texto import normalizar_texto


TEXTOS_DIR = ACTIVE_RESEARCH_DIR / "textos"
ENTRADA_DIR = ACTIVE_RESEARCH_DIR / "entrada"
FALTANTES_FILE = ACTIVE_RESEARCH_DIR / "faltantes.csv"

COLUNAS_FALTANTES = ["veredito", "titulo", "ano", "citacoes", "venue", "link", "openalex_id"]
URL_PDF = "https://content.openalex.org/works/{}.pdf"
CUSTO_PDF_USD = 0.01  # preço do OpenAlex por arquivo; a chave grátis cobre US$ 1 por dia

logging.getLogger("pypdf").setLevel(logging.ERROR)  # PDFs mal formados geram avisos sem importância


def _id(openalex_id: str) -> str:
    return openalex_id.rsplit("/", 1)[-1]


def _caminho(pid: str):
    return TEXTOS_DIR / f"{pid}.pdf"


def _defeituoso(pid: str):
    """Marca de PDF que o OpenAlex entregou com defeito (ex.: cortado): não é baixado de novo."""
    return TEXTOS_DIR / f"{pid}.defeituoso"


def _abre(conteudo: bytes) -> bool:
    try:
        return len(PdfReader(io.BytesIO(conteudo)).pages) > 0
    except Exception:
        return False


def _compacto(texto: str) -> str:
    """Só letras e números, sem acento: resiste a quebras de linha e hifenização do PDF."""
    return re.sub(r"[^a-z0-9]", "", normalizar_texto(texto))


def _doi(doi: str) -> str:
    return doi.lower().replace("https://doi.org/", "").strip()


def carregar_mantidos() -> dict:
    """Relevantes e talvez de screening.csv, com os dados de results.csv, por ID curto (W...)."""
    with open(RESULTS_FILE, encoding="utf-8-sig", newline="") as f:
        resultados = {linha["openalex_id"]: linha for linha in csv.DictReader(f)}

    with open(SCREENING_FILE, encoding="utf-8-sig", newline="") as f:
        triados = [
            linha
            for linha in csv.DictReader(f)
            if linha["veredito"] in ("relevante", "talvez")
        ]

    return {
        _id(linha["openalex_id"]): {
            **resultados.get(linha["openalex_id"], {}),
            "openalex_id": linha["openalex_id"],
            "titulo": linha["titulo"],
            "veredito": linha["veredito"],
        }
        for linha in triados
    }


def identificar(arquivo, mantidos: dict) -> str | None:
    """ID do paper mantido a que o PDF corresponde, pelo DOI ou pelo título; None se não houver um único."""
    try:
        leitor = PdfReader(arquivo)
        texto = " ".join((pagina.extract_text() or "") for pagina in leitor.pages[:2])
    except Exception:
        return None

    sem_espacos = re.sub(r"\s+", "", texto.lower())
    por_doi = [
        pid
        for pid, paper in mantidos.items()
        if paper.get("doi") and _doi(paper["doi"]) in sem_espacos
    ]

    if len(por_doi) == 1:
        return por_doi[0]

    if por_doi:
        return None

    compacto = _compacto(texto)
    por_titulo = [
        pid
        for pid, paper in mantidos.items()
        if len(_compacto(paper["titulo"])) >= 20 and _compacto(paper["titulo"]) in compacto
    ]

    return por_titulo[0] if len(por_titulo) == 1 else None


def importar_entrada(mantidos: dict) -> None:
    """Move cada PDF de entrada/ (qualquer nome) para textos/<ID>.pdf; os não identificados ficam."""
    ENTRADA_DIR.mkdir(parents=True, exist_ok=True)
    arquivos = sorted(ENTRADA_DIR.glob("*.pdf"))

    if not arquivos:
        return

    TEXTOS_DIR.mkdir(parents=True, exist_ok=True)
    ficaram = []

    for arquivo in arquivos:
        pid = identificar(arquivo, mantidos)

        if pid is None:
            ficaram.append(f"{arquivo.name}: DOI e título não reconhecidos entre os relevantes e talvez")
        elif _caminho(pid).exists():
            ficaram.append(f"{arquivo.name}: o texto de {pid} já está no acervo")
        else:
            arquivo.replace(_caminho(pid))
            _defeituoso(pid).unlink(missing_ok=True)

    print(f"\nPasta entrada/: {len(arquivos) - len(ficaram)} de {len(arquivos)} PDF(s) identificados e movidos para textos/.")

    for linha in ficaram:
        print(f"  ficou em entrada/ -> {linha}")


def baixar_do_openalex(mantidos: dict) -> None:
    """Baixa os PDFs que o OpenAlex tem para os mantidos ainda sem texto. Grava um a um."""
    pendentes = [
        pid
        for pid in mantidos
        if not _caminho(pid).exists() and not _defeituoso(pid).exists()
    ]
    disponiveis = []

    for inicio in range(0, len(pendentes), 50):
        lote = pendentes[inicio:inicio + 50]
        resposta = (
            Works()
            .filter(openalex_id="|".join(lote), has_content={"pdf": True})
            .select(["id"])
            .get(per_page=100)
        )
        disponiveis += [_id(work["id"]) for work in resposta]

    if not disponiveis:
        print("\nOpenAlex: nenhum PDF novo disponível para os papers que faltam.")
        return

    TEXTOS_DIR.mkdir(parents=True, exist_ok=True)
    baixados = 0
    defeituosos = 0

    try:
        for numero, pid in enumerate(disponiveis, start=1):
            print(f"\r  OpenAlex: baixando {numero}/{len(disponiveis)}", end="", flush=True)

            resposta = requests.get(
                URL_PDF.format(pid),
                params={"api_key": pyalex.config.api_key},
                timeout=120,
            )

            if resposta.status_code == 404:
                continue

            if resposta.status_code != 200:
                raise RuntimeError(
                    f"o OpenAlex recusou o PDF de {pid} "
                    f"(HTTP {resposta.status_code}: {resposta.text[:150]}). "
                    "Se for o limite diário da chave (US$ 1, cerca de 100 PDFs), rode de novo "
                    "amanhã. Os PDFs já baixados foram mantidos."
                )

            if not _abre(resposta.content):
                _defeituoso(pid).touch()
                defeituosos += 1
                continue

            parcial = _caminho(pid).with_suffix(".parcial")
            parcial.write_bytes(resposta.content)
            parcial.replace(_caminho(pid))
            baixados += 1

    finally:
        print(
            f"\nOpenAlex: {baixados} PDF(s) baixados agora "
            f"(US$ {(baixados + defeituosos) * CUSTO_PDF_USD:.2f}; a chave grátis cobre US$ 1 por dia)."
        )

        if defeituosos:
            print(f"OpenAlex: {defeituosos} PDF(s) vieram com defeito e não abrem; ficam em faltantes.csv.")


def gravar_faltantes(mantidos: dict) -> None:
    """faltantes.csv (;): mantidos sem texto, relevantes primeiro e mais citados antes."""
    faltam = [paper for pid, paper in mantidos.items() if not _caminho(pid).exists()]
    faltam.sort(key=lambda p: (p["veredito"] != "relevante", -int(p.get("citacoes") or 0)))

    try:
        with open(FALTANTES_FILE, "w", encoding="utf-8-sig", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=COLUNAS_FALTANTES, delimiter=";", extrasaction="ignore")
            escritor.writeheader()
            escritor.writerows({**p, "link": p.get("doi") or p["openalex_id"]} for p in faltam)

    except PermissionError:
        print(f"\nNão foi possível gravar {FALTANTES_FILE.name}: feche o arquivo no Excel e tente de novo.")
        return

    com_texto = len(mantidos) - len(faltam)
    relevantes = [pid for pid, p in mantidos.items() if p["veredito"] == "relevante"]
    relevantes_com_texto = sum(_caminho(pid).exists() for pid in relevantes)

    print(
        f"\nAcervo: {com_texto} de {len(mantidos)} papers com texto completo "
        f"({relevantes_com_texto} de {len(relevantes)} relevantes)."
    )
    print(f"Faltam {len(faltam)}: {FALTANTES_FILE}")
    print(f"Para incluir um PDF que você obteve, coloque-o (com qualquer nome) em {ENTRADA_DIR} e rode esta opção de novo.")


def montar_acervo() -> None:
    """Importa entrada/, baixa do OpenAlex o que ainda falta e grava faltantes.csv."""
    if not SCREENING_FILE.exists():
        print("\nNenhuma triagem ainda: rode a pesquisa primeiro.")
        return

    mantidos = carregar_mantidos()
    importar_entrada(mantidos)

    try:
        baixar_do_openalex(mantidos)
    finally:
        gravar_faltantes(mantidos)
