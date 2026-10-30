"""Escritor, etapa 3: verificação determinística do rascunho (sem modelo, API ou dados)."""

import csv
import re

from core.texto import normalizar_texto


# Provisório: o maior trecho de texto legítimo medido nos rascunhos de teste tinha 9 palavras.
COPIA_MIN_PALAVRAS = 12

COLUNAS = ["paragrafo", "frase", "refs", "problemas", "status"]
MARCADOR = re.compile(r"\[(T\d+(?:\s*,\s*T\d+)*|sem evidência)\]\.?")
NUMERACAO = re.compile(r"^\s*(?:\d+[.)]|#+|[-*•])\s+")
DUAS_FRASES = re.compile(r"[.!?]\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ]")


def _palavras(texto: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalizar_texto(texto))


def _numeros(texto: str) -> set[str]:
    # Um separador antes de 3 dígitos vale como milhar nos dois lados (0,710 = 0.710 e
    # 100.388 = 100,388): o que importa é igualar português e inglês.
    return {
        re.sub(r"[.,](?=\d{3}\b)", "", n).replace(",", ".")
        for n in re.findall(r"\d+(?:[.,]\d+)*", texto)
    }


def _maior_sequencia(a: list[str], b: list[str]) -> int:
    """Maior número de palavras seguidas que aparecem iguais em a e em b."""
    posicoes = {}
    for j, palavra in enumerate(b):
        posicoes.setdefault(palavra, []).append(j)

    melhor = 0
    for i in range(len(a)):
        for j in posicoes.get(a[i], []):
            k = 0
            while i + k < len(a) and j + k < len(b) and a[i + k] == b[j + k]:
                k += 1
            melhor = max(melhor, k)
    return melhor


def verificar(texto: str, trechos: dict, n_perguntas: int) -> list[dict]:
    """Uma linha por frase: paragrafo, frase, refs e problemas (lista vazia = ok)."""
    paragrafos = [p.strip() for p in re.split(r"\n\s*\n", texto.strip()) if p.strip()]
    linhas = []
    vistas = {}

    for n, paragrafo in enumerate(paragrafos, start=1):
        numerada = NUMERACAO.match(paragrafo)
        if numerada:
            paragrafo = paragrafo[numerada.end():]

        itens = []  # (frase, texto do marcador; None = texto sem marcador)
        pos = 0
        for m in MARCADOR.finditer(paragrafo):
            itens.append((paragrafo[pos:m.start()].strip(), m.group(1)))
            pos = m.end()
        if paragrafo[pos:].strip():
            itens.append((paragrafo[pos:].strip(), None))

        for i, (frase, grupo) in enumerate(itens):
            if not frase:
                continue
            refs = re.findall(r"T\d+", grupo or "")
            problemas = []

            if i == 0 and numerada:
                problemas.append("numeração ou título no início do parágrafo")
            if grupo is None:
                problemas.append("frase sem fonte: texto depois do último marcador")
            elif DUAS_FRASES.search(frase):
                problemas.append("duas frases para um só marcador: a primeira está sem fonte")

            for ref in refs:
                if ref not in trechos:
                    problemas.append(f"marcador inexistente: {ref}")
            citados = [trechos[ref]["texto"] for ref in refs if ref in trechos]
            if citados:
                fora = sorted(_numeros(frase) - _numeros(" ".join(citados)))
                if fora:
                    problemas.append("número fora do trecho citado: " + ", ".join(fora))
                copia = max(_maior_sequencia(_palavras(frase), _palavras(t)) for t in citados)
                if copia >= COPIA_MIN_PALAVRAS:
                    problemas.append(f"cópia literal: {copia} palavras seguidas iguais ao trecho")

            chave = " ".join(_palavras(frase))
            if chave in vistas:
                problemas.append(f"frase repetida (já no parágrafo {vistas[chave]})")
            else:
                vistas[chave] = n

            linhas.append({
                "paragrafo": n,
                "frase": frase + (f" [{grupo}]" if grupo else ""),
                "refs": ", ".join(refs),
                "problemas": problemas,
            })

    if len(paragrafos) != n_perguntas:
        linhas.append({
            "paragrafo": "",
            "frase": "(texto inteiro)",
            "refs": "",
            "problemas": [f"{len(paragrafos)} parágrafo(s) para {n_perguntas} pergunta(s)"],
        })
    return linhas


def gravar_revisao(arquivo, linhas: list[dict]) -> int:
    """Grava o CSV de revisão e devolve quantas linhas têm problema."""
    with open(arquivo, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow({
                **linha,
                "problemas": "; ".join(linha["problemas"]),
                "status": "revisar" if linha["problemas"] else "ok",
            })
    return sum(1 for linha in linhas if linha["problemas"])
