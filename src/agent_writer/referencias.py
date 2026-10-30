"""Escritor: troca as referências T do rascunho por chaves de citação e gera o .bib."""

import csv
import os
import re

import pyalex
from pyalex import Works

from agent_writer.evidencias import escolher_secao
from core.pesquisa_ativa import ACTIVE_RESEARCH_DIR
from core.texto import normalizar_texto


# Uma seção cita no máximo 30 papers (6 perguntas x 5 trechos): cabe em uma consulta (limite de 50).
CAMPOS_OPENALEX = ["id", "doi", "title", "publication_year", "authorships", "biblio", "primary_location"]
MARCADOR = re.compile(r"\[(T\d+(?:\s*,\s*T\d+)*)\]")


def _curto(openalex_id: str) -> str:
    return openalex_id.rsplit("/", 1)[-1]


def buscar_trabalhos(papers: list[str]) -> dict:
    """Metadados no OpenAlex, uma consulta em lote; devolve {ID curto: trabalho}."""
    pyalex.config.api_key = os.getenv("OPENALEX_API_KEY")
    pyalex.config.max_retries = 3  # novas tentativas em 429, 500 e 503
    pyalex.config.retry_backoff_factor = 0.5
    trabalhos = Works().filter(openalex="|".join(papers)).select(CAMPOS_OPENALEX).get(per_page=50)
    return {_curto(t["id"]): t for t in trabalhos}


def dados_do_paper(paper: str, trabalho: dict | None, linha: dict | None) -> dict:
    """Dados da referência: do OpenAlex; na falta dele, do results.csv; na falta dos dois, só o ID."""
    if trabalho:
        fonte = (trabalho.get("primary_location") or {}).get("source") or {}
        biblio = trabalho.get("biblio") or {}
        primeira, ultima = biblio.get("first_page"), biblio.get("last_page")
        return {
            "autores": [a["author"]["display_name"] for a in trabalho.get("authorships", []) if a["author"].get("display_name")],
            "titulo": trabalho.get("title") or f"(sem título: {paper})",
            "venue": fonte.get("display_name"),
            "ano": trabalho.get("publication_year"),
            "volume": biblio.get("volume"),
            "numero": biblio.get("issue"),
            "paginas": f"{primeira}--{ultima}" if primeira and ultima and primeira != ultima else primeira,
            "doi": (trabalho.get("doi") or "").removeprefix("https://doi.org/"),
        }
    linha = linha or {}
    return {
        "autores": [],
        "titulo": linha.get("titulo") or f"(sem metadados: {paper})",
        "venue": linha.get("venue"),
        "ano": linha.get("ano"),
        "volume": None,
        "numero": None,
        "paginas": None,
        "doi": (linha.get("doi") or "").removeprefix("https://doi.org/"),
    }


def chave(dados: dict, paper: str) -> str:
    """Sobrenome do primeiro autor + ano + 4 últimos dígitos do ID (mesmo paper, mesma chave em toda seção)."""
    partes = dados["autores"][0].split() if dados["autores"] else []
    sobrenome = re.sub(r"[^a-z]", "", normalizar_texto(partes[-1])) if partes else ""
    return f"{sobrenome or 'anon'}{dados['ano'] or ''}_{paper[-4:]}"


def _bib(valor) -> str:
    valor = str(valor).replace("{", "").replace("}", "")
    for caractere in "&%$#_":
        valor = valor.replace(caractere, "\\" + caractere)
    return valor


def entrada_bib(paper: str, dados: dict) -> str:
    tipo = "article" if dados["venue"] else "misc"
    campos = {
        "author": " and ".join(dados["autores"]),
        "title": dados["titulo"],
        "journal": dados["venue"],
        "year": dados["ano"],
        "volume": dados["volume"],
        "number": dados["numero"],
        "pages": dados["paginas"],
        "doi": dados["doi"],
    }
    linhas = [f"  {nome} = {{{_bib(valor)}}}," for nome, valor in campos.items() if valor]
    return "\n".join([f"@{tipo}{{{chave(dados, paper)},", *linhas, "}", ""])


def converter(texto: str, paper_da_ref: dict, dados: dict) -> tuple[str, list[str]]:
    """Troca [T3, T7] por [@chave1; @chave2]. Devolve o texto e as referências T sem paper."""
    sem_paper = []

    def trocar(m):
        chaves = []
        for ref in re.findall(r"T\d+", m.group(1)):
            paper = paper_da_ref.get(ref)
            if paper is None:
                sem_paper.append(ref)
                return m.group(0)
            if f"@{chave(dados[paper], paper)}" not in chaves:
                chaves.append(f"@{chave(dados[paper], paper)}")
        return "[" + "; ".join(chaves) + "]"

    return MARCADOR.sub(trocar, texto), sem_paper


def escolher_rascunho(pasta):
    rascunhos = sorted(pasta.glob("rascunho_*.md"))
    if not rascunhos:
        print("\nEsta seção ainda não tem rascunho. Escreva o rascunho antes.")
        return None
    if len(rascunhos) == 1:
        return rascunhos[0]

    print("\nRascunhos:")
    for i, rascunho in enumerate(rascunhos, start=1):
        print(f"  {i}. {rascunho.name}")

    while True:
        escolha = input("\nNúmero do rascunho:\n> ").strip()
        if escolha.isdigit() and 1 <= int(escolha) <= len(rascunhos):
            return rascunhos[int(escolha) - 1]
        print("\nNúmero inválido.")


def gerar_referencias():
    pasta = escolher_secao()
    if pasta is None:
        return None
    rascunho = escolher_rascunho(pasta)
    if rascunho is None:
        return None

    texto = rascunho.read_text(encoding="utf-8")
    with open(pasta / "evidencias.csv", encoding="utf-8-sig", newline="") as f:
        paper_da_ref = {linha["ref"]: linha["paper"] for linha in csv.DictReader(f, delimiter=";")}

    citadas = [ref for grupo in MARCADOR.findall(texto) for ref in re.findall(r"T\d+", grupo)]
    usados = sorted({paper_da_ref[ref] for ref in citadas if ref in paper_da_ref})
    if not usados:
        print("\nO rascunho não tem citações [T..] para converter.")
        return None

    resultados = ACTIVE_RESEARCH_DIR / "results.csv"
    linhas = {}
    if resultados.exists():
        with open(resultados, encoding="utf-8-sig", newline="") as f:
            linhas = {_curto(linha["openalex_id"]): linha for linha in csv.DictReader(f)}

    trabalhos = buscar_trabalhos(usados)
    dados = {paper: dados_do_paper(paper, trabalhos.get(paper), linhas.get(paper)) for paper in usados}
    novo, sem_paper = converter(texto, paper_da_ref, dados)

    nome = rascunho.stem.removeprefix("rascunho_")
    bib = pasta / f"referencias_{nome}.bib"
    final = pasta / f"texto_{nome}.md"
    bib.write_text("\n".join(entrada_bib(paper, dados[paper]) for paper in usados), encoding="utf-8")
    final.write_text(f"---\nbibliography: {bib.name}\n---\n\n{novo}", encoding="utf-8")

    print(f"\n{len(usados)} papers citados. Salvos em {pasta}:")
    print(f"  {final.name}")
    print(f"  {bib.name}")
    sem_autores = [paper for paper in usados if not dados[paper]["autores"]]
    if sem_autores:
        print(f"ATENÇÃO: sem autores (confira à mão): {', '.join(sem_autores)}")
    if sem_paper:
        print(f"ATENÇÃO: referências sem paper em evidencias.csv, mantidas como estão: {', '.join(sorted(set(sem_paper)))}")
    return final
