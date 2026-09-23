"""Utilitários de texto e de leitura de entradas do terminal."""

import unicodedata


def normalizar_texto(texto: str) -> str:
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto)

    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )

    return " ".join(texto.split())


def ler_lista(texto: str) -> list:
    return [
        item.strip()
        for item in texto.split(",")
        if item.strip()
    ]


def ler_indices(
    texto: str,
    total: int,
) -> list | None:

    try:
        indices = {
            int(item.strip())
            for item in texto.split(",")
            if item.strip()
        }

    except ValueError:
        return None

    if not indices or any(
        indice < 1 or indice > total
        for indice in indices
    ):
        return None

    return sorted(indices)


def sem_duplicados(itens: list) -> list:
    vistos = set()
    resultado = []

    for item in itens:
        chave = normalizar_texto(item)

        if item.strip() and chave not in vistos:
            vistos.add(chave)
            resultado.append(item.strip())

    return resultado
