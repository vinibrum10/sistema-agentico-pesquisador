"""Avaliação (só leitura): um modelo treinado nos seus rótulos supera o juiz atual?

Compara, em validação cruzada repetida sobre o gabarito:
  A  juiz atual (veredito como está)
  B  regressão logística nos campos que o juiz grava
  C  B + similaridade bge-m3 entre o paper e o tema/objetivo da pesquisa
  D  só a similaridade bge-m3

Não grava nada e não altera a triagem. Uso:

    python scripts/avaliar_aprendizado.py
"""

import csv
import re
import sys
from math import ceil
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

try:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
except ImportError:
    sys.exit("Falta o scikit-learn. Instale com: python -m pip install scikit-learn==1.7.2")

from agent_research.screening.calibracao import GABARITO_FILE, intervalo_wilson
from agent_research.screening.juiz import SCREENING_FILE
from agent_research.search.openalex import RESULTS_FILE
from core.pesquisa_ativa import carregar_contexto


MAX_RESUMO = 2500
REPETICOES = 20
REAMOSTRAGENS = 2000
NIVEL = {"lixo": 0, "talvez": 1, "relevante": 2}


def ler(caminho, delimitador=","):
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimitador))


def carregar_itens():
    """Papers do gabarito com os campos que o juiz gravou; ignora descartados e erros."""
    triados = {linha["openalex_id"]: linha for linha in ler(SCREENING_FILE)}
    resultados = {linha["openalex_id"]: linha for linha in ler(RESULTS_FILE)}
    itens = []
    ignorados = 0

    for linha in ler(GABARITO_FILE, ";"):
        pid = linha["openalex_id"]
        rotulo = linha["rotulo"].strip().lower()
        triado = triados.get(pid)
        resultado = resultados.get(pid)

        if (
            rotulo not in ("r", "t", "l")
            or not triado
            or not resultado
            or triado["veredito"] in ("descartado", "erro")
        ):
            ignorados += 1
            continue

        dominio = re.search(r"mesmo_dominio=(True|False)", triado["justificativa"])
        problema = re.search(r"mesmo_problema=(True|False)", triado["justificativa"])

        if not dominio or not problema:
            ignorados += 1
            continue

        resumo = resultado["abstract"].strip()
        itens.append(
            {
                "rotulo": rotulo,
                "veredito": triado["veredito"],
                "dominio": dominio.group(1) == "True",
                "problema": problema.group(1) == "True",
                "tem_resumo": bool(resumo),
                "confianca_baixa": triado["confianca"] == "baixa",
                "tema_antigo": triado.get("tema_confirmado") == "não",
                "texto": f"{triado['titulo']}. {resumo[:MAX_RESUMO]}",
            }
        )

    return itens, ignorados


def similaridades(itens):
    """Cosseno bge-m3 entre cada paper e o tema+objetivo da pesquisa; None se o Ollama falhar."""
    oficial = carregar_contexto()["oficial"]

    try:
        from langchain_ollama import OllamaEmbeddings

        vetores = np.array(
            OllamaEmbeddings(model="bge-m3").embed_documents(
                [item["texto"] for item in itens]
                + [f"{oficial['tema']} {oficial['objetivo']}"]
            )
        )
    except Exception as erro:
        print(f"\nSem embeddings ({erro}). Rodando só A e B.")
        return None

    vetores = vetores / np.linalg.norm(vetores, axis=1, keepdims=True)
    return vetores[:-1] @ vetores[-1]


def escores_cv(X, y):
    """Escore fora da amostra: média de REPETICOES validações cruzadas de 5 partes."""
    soma = np.zeros(len(y))

    for semente in range(REPETICOES):
        particoes = StratifiedKFold(5, shuffle=True, random_state=semente)

        for treino, teste in particoes.split(X, y):
            modelo = make_pipeline(
                StandardScaler(),
                LogisticRegression(class_weight="balanced"),
            )
            modelo.fit(X[treino], y[treino])
            soma[teste] += modelo.decision_function(X[teste])

    return soma / REPETICOES


def economia(y, escore, meta=0.9):
    """Fração dos papers que dá para pôr de lado (menores escores) mantendo >= meta dos positivos."""
    exigidos = ceil(meta * y.sum())

    for corte in sorted(set(escore), reverse=True):
        mantidos = escore >= corte

        if y[mantidos].sum() >= exigidos:
            return 1 - mantidos.mean()

    return 0.0


def auc_reamostrado(y, escore, amostras):
    return np.array(
        [
            roc_auc_score(y[i], escore[i]) if 0 < y[i].sum() < len(i) else np.nan
            for i in amostras
        ]
    )


def avaliar(nome, y, nivel, metodos, amostras):
    print(f"\n=== Alvo: {nome} ({y.sum()} de {len(y)}) ===")

    mantidos = nivel >= 1
    k = int(y[mantidos].sum())
    baixo, alto = intervalo_wilson(k, int(y.sum()))
    print(
        f"Juiz atual como está: recall {k}/{int(y.sum())} ({k / y.sum():.0%}; "
        f"IC 95%: {baixo:.0%} a {alto:.0%}), "
        f"{1 - mantidos.mean():.0%} dos papers postos de lado"
    )

    aucs = {nome_m: auc_reamostrado(y, e, amostras) for nome_m, e in metodos.items()}
    base = "A juiz atual"

    print("\nmétodo                AUC (IC 95%)        economia mantendo >=90% dos positivos")

    for nome_m, escore in metodos.items():
        b, a = np.nanpercentile(aucs[nome_m], [2.5, 97.5])
        print(
            f"{nome_m:<21} {roc_auc_score(y, escore):.2f} ({b:.2f} a {a:.2f})"
            f"      {economia(y, escore):.0%}"
        )

    for nome_m, escore in metodos.items():
        if nome_m == base:
            continue

        dif = roc_auc_score(y, escore) - roc_auc_score(y, metodos[base])
        b, a = np.nanpercentile(aucs[nome_m] - aucs[base], [2.5, 97.5])
        veredito = "sem evidência de ganho" if b <= 0 <= a else (
            "ganho" if dif > 0 else "perda"
        )
        print(f"{nome_m} menos A: AUC {dif:+.2f} (IC 95%: {b:+.2f} a {a:+.2f}) → {veredito}")


def main():
    itens, ignorados = carregar_itens()

    if not itens:
        sys.exit("Nenhum paper do gabarito com veredito do juiz. Nada a avaliar.")

    print(f"Gabarito: {len(itens) + ignorados} papers; usados {len(itens)} "
          f"({ignorados} ignorados: descartados pelo filtro, erro ou sem veredito).")

    if any(item["tema_antigo"] for item in itens):
        print(
            "\nAVISO: há vereditos de outro tema (tema_confirmado = não). "
            "Reavalie a triagem antes de confiar nesta avaliação."
        )

    rotulos = np.array([item["rotulo"] for item in itens])
    nivel = np.array([NIVEL[item["veredito"]] for item in itens], float)
    campos = np.array(
        [
            [item["dominio"], item["problema"], item["tem_resumo"], item["confianca_baixa"]]
            for item in itens
        ],
        float,
    )
    sim = similaridades(itens)

    gerador = np.random.default_rng(0)
    amostras = [gerador.integers(0, len(itens), len(itens)) for _ in range(REAMOSTRAGENS)]

    alvos = {
        "relevante": rotulos == "r",
        "relevante ou talvez": np.isin(rotulos, ["r", "t"]),
    }

    for nome, alvo in alvos.items():
        y = alvo.astype(int)

        if min(y.sum(), len(y) - y.sum()) < 5:
            print(f"\nAlvo {nome}: menos de 5 exemplos em uma das classes; ignorado.")
            continue

        metodos = {"A juiz atual": nivel, "B campos do juiz": escores_cv(campos, y)}

        if sim is not None:
            metodos["C campos + bge-m3"] = escores_cv(np.column_stack([campos, sim]), y)
            metodos["D só bge-m3"] = escores_cv(sim.reshape(-1, 1), y)

        avaliar(nome, y, nivel, metodos, amostras)

    print(
        "\nComo ler: só vale adotar B, C ou D se o IC da diferença para A "
        "não incluir zero. O IC vem de reamostrar os papers; não inclui o ruído "
        "dos próprios rótulos. Com poucos positivos, o esperado é 'sem evidência'."
    )


if __name__ == "__main__":
    main()
