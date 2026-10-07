"""Busca local de trechos (método A): palavras-chave (BM25) e significado (bge-m3), sem LLM.

As duas listas são combinadas pela posição de cada trecho em cada uma (reciprocal rank fusion):
um trecho bem colocado nas duas sobe; um que só aparece em uma também pode entrar.
"""

import math
import re
from collections import Counter

import numpy as np
from langchain_ollama import OllamaEmbeddings

from agent_research.trechos.indice import MODELO_EMBEDDING, carregar_indice
from core.texto import normalizar_texto


K_FUSAO = 60  # constante usual da fusão por posição
K1, B = 1.5, 0.75  # parâmetros usuais do BM25


def _palavras(texto: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalizar_texto(texto))


class BuscaLocal:
    """Carrega o índice uma vez; buscar() pode ser chamado várias vezes."""

    def __init__(self):
        self.trechos, vetores = carregar_indice()

        if not self.trechos:
            raise RuntimeError("o índice de trechos está vazio: rode a indexação antes de buscar")

        self.vetores = vetores / np.linalg.norm(vetores, axis=1, keepdims=True)
        self.modelo = OllamaEmbeddings(model=MODELO_EMBEDDING)

        documentos = [_palavras(trecho["texto"]) for trecho in self.trechos]
        self.frequencias = [Counter(documento) for documento in documentos]
        self.tamanhos = np.array([len(documento) for documento in documentos])
        presenca = Counter(palavra for documento in documentos for palavra in set(documento))
        total = len(documentos)
        self.idf = {
            palavra: math.log(1 + (total - n + 0.5) / (n + 0.5))
            for palavra, n in presenca.items()
        }

    def _bm25(self, pergunta: str) -> np.ndarray:
        termos = set(_palavras(pergunta)) & self.idf.keys()
        media = self.tamanhos.mean()
        escores = np.zeros(len(self.trechos))

        for i, frequencia in enumerate(self.frequencias):
            normalizacao = K1 * (1 - B + B * self.tamanhos[i] / media)
            escores[i] = sum(
                self.idf[termo] * frequencia[termo] * (K1 + 1) / (frequencia[termo] + normalizacao)
                for termo in termos
                if termo in frequencia
            )

        return escores

    def buscar(self, pergunta: str, k: int = 5) -> list[dict]:
        """Os k trechos mais bem colocados na combinação das duas buscas."""
        consulta = np.array(self.modelo.embed_query(pergunta), dtype=np.float32)
        semantico = self.vetores @ (consulta / np.linalg.norm(consulta))
        lexico = self._bm25(pergunta)

        fusao = np.zeros(len(self.trechos))

        for posicao, i in enumerate(np.argsort(-semantico), start=1):
            fusao[i] += 1 / (K_FUSAO + posicao)

        for posicao, i in enumerate(np.argsort(-lexico), start=1):
            if lexico[i] <= 0:
                break
            fusao[i] += 1 / (K_FUSAO + posicao)

        return [
            {**self.trechos[i], "escore": round(float(fusao[i]), 5)}
            for i in np.argsort(-fusao)[:k]
        ]
