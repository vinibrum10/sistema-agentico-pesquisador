"""Escritor, etapa 3: escreve o rascunho da seção usando só os trechos de evidencias.csv."""

import csv
import json
import re

from agent_writer.evidencias import escolher_secao
from core.modelos import CONFIG_FILE, criar_modelo


TAREFA = "escrita_secao"
# Os trechos de uma seção somam uns 7 mil tokens; a janela padrão do Ollama
# é menor e cortaria o começo do prompt sem avisar.
CONTEXTO_OLLAMA = 12288
SEM_EVIDENCIA = "[sem evidência]"
MARCADOR = re.compile(r"\[(T\d+(?:\s*,\s*T\d+)*)\]")


def carregar_trechos(pasta) -> dict:
    """Trechos únicos de evidencias.csv por referência (T1, T2, ...), na ordem do arquivo."""
    with open(pasta / "evidencias.csv", encoding="utf-8-sig", newline="") as f:
        return {linha["ref"]: linha for linha in csv.DictReader(f, delimiter=";")}


def montar_prompt(secao: dict, trechos: dict) -> str:
    perguntas = "\n".join(
        f"{n}. {p['pt']}" for n, p in enumerate(secao["perguntas"], start=1)
    )
    evidencias = "\n\n".join(
        f"[{ref}] (paper {t['paper']}, p. {t['pagina']})\n{t['texto']}"
        for ref, t in trechos.items()
    )
    return f"""Trechos de artigos científicos (em inglês; cada um tem uma referência entre colchetes):

{evidencias}

---

Você escreve uma seção de um texto científico em português, usando SOMENTE os trechos acima.

Título da seção: {secao["titulo"]}

Perguntas-guia, na ordem em que a seção deve tratá-las:
{perguntas}

Regras:
- escreva um parágrafo por pergunta-guia, na mesma ordem, sem títulos nem numeração;
- toda frase termina com a referência do trecho que a sustenta, por exemplo [T3] ou [T3, T7] (exceto as frases {SEM_EVIDENCIA}, abaixo);
- cada frase diz só o que o trecho citado diz; não acrescente conhecimento próprio, números, lugares ou nomes que não estejam no trecho;
- escreva com suas palavras, em português; não copie frases inteiras dos trechos;
- uma pergunta-guia pode pedir algo específico (um lugar, período, método, material ou população). Se os trechos não mencionam esse aspecto, não responda como se mencionassem: escreva só o que os trechos dizem, citando-os, e acrescente uma frase dizendo qual parte da pergunta eles não cobrem, terminada com {SEM_EVIDENCIA} no lugar da referência. Se os trechos não cobrem nada da pergunta, escreva apenas essa frase;
- não escreva introdução, conclusão nem lista de referências.

Retorne SOMENTE o texto da seção."""


def refs_citadas(texto: str) -> list[str]:
    """Referências T citadas no texto, na ordem, com repetições."""
    return [ref.strip() for grupo in MARCADOR.findall(texto) for ref in grupo.split(",")]


def escolher_modelo() -> str:
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    nomes = list(config["modelos"])
    padrao = config["tarefas"][TAREFA]

    print("\nModelos disponíveis:")
    for i, nome in enumerate(nomes, start=1):
        print(f"  {i}. {nome}{' (padrão)' if nome == padrao else ''}")

    while True:
        escolha = input("\nNúmero do modelo [Enter = padrão]:\n> ").strip()
        if not escolha:
            return padrao
        if escolha.isdigit() and 1 <= int(escolha) <= len(nomes):
            return nomes[int(escolha) - 1]
        print("\nNúmero inválido.")


def escrever_rascunho():
    pasta = escolher_secao()
    if pasta is None:
        return None
    if not (pasta / "evidencias.csv").exists():
        print("\nEsta seção ainda não tem evidências. Busque as evidências antes de escrever.")
        return None

    secao = json.loads((pasta / "secao.json").read_text(encoding="utf-8"))
    trechos = carregar_trechos(pasta)
    nome = escolher_modelo()

    print(f"\nEscrevendo '{secao['titulo']}' com {nome} ({len(trechos)} trechos)...")
    modelo = criar_modelo(TAREFA, nome=nome, contexto=CONTEXTO_OLLAMA)
    texto = modelo.invoke(montar_prompt(secao, trechos)).content.strip()

    arquivo = pasta / f"rascunho_{nome.replace(':', '_')}.md"
    arquivo.write_text(f"# {secao['titulo']}\n\n{texto}\n", encoding="utf-8")

    citadas = refs_citadas(texto)
    inexistentes = sorted(set(citadas) - set(trechos), key=lambda ref: int(ref[1:]))
    print(f"\n{len(citadas)} citações de {len(set(citadas))} trechos diferentes (de {len(trechos)} disponíveis).")
    print(f"Frases marcadas {SEM_EVIDENCIA}: {texto.count(SEM_EVIDENCIA)}")
    if inexistentes:
        print(f"ATENÇÃO: referências que não existem em evidencias.csv: {', '.join(inexistentes)}")
    print(f"Salvo em: {arquivo}")
    return arquivo
