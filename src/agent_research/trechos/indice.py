"""Índice de trechos: o texto de cada PDF do acervo em trechos curtos, com a página, e o vetor bge-m3 de cada um.

Fica em data/active_research/trechos/: <ID>.jsonl (os trechos) e <ID>.npy (os vetores, na mesma
ordem). Só indexa os PDFs novos; apagar os dois arquivos de um paper faz ele ser indexado de novo.
A página é a do arquivo PDF (1 = primeira folha), não a numeração impressa na revista.
"""

import json
import logging
import re
import time

import numpy as np
from langchain_ollama import OllamaEmbeddings
from pypdf import PdfReader

from agent_research.acervo.textos import TEXTOS_DIR
from core.pesquisa_ativa import ACTIVE_RESEARCH_DIR


TRECHOS_DIR = ACTIVE_RESEARCH_DIR / "trechos"
MODELO_EMBEDDING = "bge-m3"
TAMANHO = 1500  # caracteres por trecho, cerca de um parágrafo longo
MINIMO = 200  # sobras menores que isto (cabeçalho, rodapé, legenda solta) não viram trecho
REFERENCIAS = re.compile(
    r"^\s*(references|bibliography|literature cited|referências|referencias)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

logging.getLogger("pypdf").setLevel(logging.ERROR)  # PDFs mal formados geram avisos sem importância


def paginas(arquivo) -> list[str]:
    """Texto de cada página, parando no título das referências quando ele está na segunda metade."""
    leitor = PdfReader(arquivo)
    textos = []

    for numero, pagina in enumerate(leitor.pages):
        texto = pagina.extract_text() or ""
        referencias = REFERENCIAS.search(texto)

        if referencias and numero >= len(leitor.pages) / 2:
            textos.append(texto[: referencias.start()])
            break

        textos.append(texto)

    return textos


def cortar(texto: str) -> list[str]:
    """Trechos de até TAMANHO caracteres, cortados no fim de uma frase quando possível."""
    texto = re.sub(r"-\n(?=[a-z])", "", texto)  # junta palavra hifenizada na quebra de linha
    texto = re.sub(r"\s+", " ", texto).strip()
    trechos = []

    while len(texto) > TAMANHO:
        ponto = texto.rfind(". ", 0, TAMANHO)
        corte = ponto + 1 if ponto > TAMANHO // 2 else TAMANHO
        trechos.append(texto[:corte].strip())
        texto = texto[corte:].strip()

    if trechos and len(texto) < MINIMO:
        trechos[-1] += " " + texto
    else:
        trechos.append(texto)

    return [trecho for trecho in trechos if len(trecho) >= MINIMO]


def atualizar_indice() -> None:
    """Indexa os PDFs de textos/ que ainda não têm trechos. Grava paper a paper."""
    TRECHOS_DIR.mkdir(parents=True, exist_ok=True)
    novos = [
        arquivo
        for arquivo in sorted(TEXTOS_DIR.glob("*.pdf"))
        if not (TRECHOS_DIR / f"{arquivo.stem}.npy").exists()
    ]

    if not novos:
        print("\nÍndice de trechos: nenhum PDF novo para indexar.")
        return

    modelo = OllamaEmbeddings(model=MODELO_EMBEDDING)
    sem_texto = []
    inicio = time.time()

    for numero, arquivo in enumerate(novos, start=1):
        print(f"\r  indexando {numero}/{len(novos)}: {arquivo.stem}   ", end="", flush=True)

        try:
            textos = paginas(arquivo)
        except Exception:
            textos = []

        trechos = [
            {"id": f"{arquivo.stem}_p{pagina}_{n}", "paper": arquivo.stem, "pagina": pagina, "texto": trecho}
            for pagina, texto in enumerate(textos, start=1)
            for n, trecho in enumerate(cortar(texto), start=1)
        ]

        if not trechos:
            sem_texto.append(arquivo.stem)
            continue

        vetores = np.array(modelo.embed_documents([t["texto"] for t in trechos]), dtype=np.float32)
        linhas = [json.dumps(trecho, ensure_ascii=False) for trecho in trechos]
        (TRECHOS_DIR / f"{arquivo.stem}.jsonl").write_text("\n".join(linhas), encoding="utf-8")
        np.save(TRECHOS_DIR / f"{arquivo.stem}.npy", vetores)

    print(
        f"\nÍndice de trechos: {len(novos) - len(sem_texto)} PDF(s) indexados agora "
        f"em {(time.time() - inicio) / 60:.1f} min."
    )

    if sem_texto:
        print(f"Sem texto extraível (provável digitalização): {', '.join(sem_texto)}")


def carregar_indice() -> tuple[list[dict], np.ndarray]:
    """Todos os trechos e vetores dos PDFs que ainda estão no acervo."""
    trechos = []
    vetores = []

    for arquivo in sorted(TRECHOS_DIR.glob("*.npy")):
        if not (TEXTOS_DIR / f"{arquivo.stem}.pdf").exists():
            continue

        linhas = (TRECHOS_DIR / f"{arquivo.stem}.jsonl").read_text(encoding="utf-8").splitlines()
        trechos += [json.loads(linha) for linha in linhas]
        vetores.append(np.load(arquivo))

    if not vetores:
        return [], np.zeros((0, 0), dtype=np.float32)

    return trechos, np.vstack(vetores)
