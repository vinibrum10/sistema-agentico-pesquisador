"""Teste da camada de trechos (etapa 2), parte A: índice e busca local, sem LLM.

Indexa os PDFs novos do acervo e roda a busca local (método A) nas perguntas de
data/active_research/teste_trechos/perguntas.csv (separado por ;, colunas id, pergunta_pt,
pergunta_en). O resultado vai para teste_trechos/nao_abrir_metodo_a.csv: não abra antes da
avaliação às cegas, para não saber de qual método veio cada trecho. Uso:

    python scripts/teste_trechos.py
"""

import csv
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from agent_research.trechos.busca import BuscaLocal
from agent_research.trechos.indice import atualizar_indice
from core.pesquisa_ativa import ACTIVE_RESEARCH_DIR


TESTE_DIR = ACTIVE_RESEARCH_DIR / "teste_trechos"
PERGUNTAS_FILE = TESTE_DIR / "perguntas.csv"
SAIDA_A = TESTE_DIR / "nao_abrir_metodo_a.csv"
COLUNAS = ["pergunta_id", "posicao", "trecho_id", "paper", "pagina", "escore", "texto"]
TRECHOS_POR_PERGUNTA = 5


def main():
    atualizar_indice()

    if not PERGUNTAS_FILE.exists():
        sys.exit(f"\nFalta {PERGUNTAS_FILE} (separado por ;, colunas id, pergunta_pt, pergunta_en).")

    with open(PERGUNTAS_FILE, encoding="utf-8-sig", newline="") as f:
        perguntas = list(csv.DictReader(f, delimiter=";"))

    busca = BuscaLocal()
    papers = len({trecho["paper"] for trecho in busca.trechos})
    print(f"\nÍndice: {len(busca.trechos)} trechos de {papers} papers.")

    inicio = time.time()
    linhas = []

    for pergunta in perguntas:
        consulta = pergunta.get("pergunta_en") or pergunta["pergunta_pt"]

        for posicao, trecho in enumerate(busca.buscar(consulta, TRECHOS_POR_PERGUNTA), start=1):
            linhas.append({**trecho, "pergunta_id": pergunta["id"], "posicao": posicao, "trecho_id": trecho["id"]})

    segundos = (time.time() - inicio) / max(len(perguntas), 1)

    with open(SAIDA_A, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";", extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(linhas)

    print(f"Método A: {len(perguntas)} perguntas, {len(linhas)} trechos, {segundos:.1f} s por pergunta.")
    print(f"Resultado: {SAIDA_A}")
    print("Não abra esse arquivo: ele é a metade A do teste às cegas.")


if __name__ == "__main__":
    main()
