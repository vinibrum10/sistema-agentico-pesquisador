"""Escritor, etapa 1: define a seção (título e perguntas-guia PT/EN aprovadas pelo pesquisador)."""

import json
import re
import unicodedata
from datetime import datetime

from core.modelos import CONFIG_FILE, criar_modelo
from core.pesquisa_ativa import ACTIVE_RESEARCH_DIR, carregar_contexto, existe_pesquisa_ativa
from core.texto import ler_indices, normalizar_texto


ESCRITA_DIR = ACTIVE_RESEARCH_DIR / "escrita"
TAREFA = "perguntas_secao"

# O LLM sugere de 3 a 6; depois da revisão, a seção fica com 1 a 6.
MIN_SUGERIDAS = 3
MAX_PERGUNTAS = 6

ESQUEMA = {
    "type": "object",
    "properties": {
        "perguntas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"pt": {"type": "string"}, "en": {"type": "string"}},
                "required": ["pt", "en"],
            },
        }
    },
    "required": ["perguntas"],
}


def pasta_da_secao(titulo: str):
    slug = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")[:60] or "secao"
    return ESCRITA_DIR / slug


def validar_perguntas(dados) -> list | None:
    """Perguntas com PT e EN preenchidos, sem repetir, entre 3 e 6; senão None."""
    if not isinstance(dados, dict) or not isinstance(dados.get("perguntas"), list):
        return None

    perguntas, vistas = [], set()
    for item in dados["perguntas"]:
        if not isinstance(item, dict):
            return None
        pt = str(item.get("pt", "")).strip()
        en = str(item.get("en", "")).strip()
        if not pt or not en:
            return None
        if normalizar_texto(pt) not in vistas:
            vistas.add(normalizar_texto(pt))
            perguntas.append({"pt": pt, "en": en})

    if not MIN_SUGERIDAS <= len(perguntas) <= MAX_PERGUNTAS:
        return None
    return perguntas


def sugerir_perguntas(titulo: str, oficial: dict) -> list | None:
    """Pede as perguntas-guia ao LLM; tenta duas vezes e devolve None se nenhuma resposta servir."""
    prompt = f"""Você ajuda a planejar uma seção de um texto científico.

Tema da pesquisa: {oficial["tema"]}
Objetivo da pesquisa: {oficial["objetivo"]}
Título da seção: {titulo}

Sugira de {MIN_SUGERIDAS} a {MAX_PERGUNTAS} perguntas-guia que esta seção deve responder.

Regras:
- cada pergunta trata de um único ponto e pode ser respondida com evidências de artigos científicos;
- as perguntas não se repetem e seguem uma ordem lógica para a seção;
- "pt" é a pergunta em português; "en" é a mesma pergunta em inglês, usada para buscar trechos nos artigos;
- não inclua respostas, explicações nem numeração.

Retorne SOMENTE JSON no formato:
{{"perguntas": [{{"pt": "...", "en": "..."}}]}}
"""
    modelo = criar_modelo(TAREFA, esquema=ESQUEMA)

    for tentativa in (1, 2):
        try:
            perguntas = validar_perguntas(json.loads(modelo.invoke(prompt).content))
        except json.JSONDecodeError:
            perguntas = None
        if perguntas:
            return perguntas
        print(f"\nA sugestão {tentativa} veio fora do formato esperado.")

    return None


def digitar_pergunta() -> dict | None:
    pt = input("Pergunta em português:\n> ").strip()
    en = input("A mesma pergunta em inglês (usada na busca):\n> ").strip()
    if not pt or not en:
        print("\nAs duas versões são obrigatórias; nada foi alterado.")
        return None
    return {"pt": pt, "en": en}


def mostrar_perguntas(perguntas: list) -> None:
    print("\nPerguntas-guia da seção:")
    if not perguntas:
        print("  (nenhuma; use A para adicionar)")
    for i, p in enumerate(perguntas, start=1):
        print(f"  {i}. {p['pt']}")
        print(f"     EN: {p['en']}")


def confirmar_perguntas(perguntas: list) -> list:
    perguntas = list(perguntas)

    while True:
        mostrar_perguntas(perguntas)
        print("\n[C] Confirmar")
        print("[R] Remover perguntas (ex.: R 2  ou  R 1,2)")
        print("[A] Adicionar pergunta")
        print("[E] Editar uma pergunta (ex.: E 1)")

        entrada = input("> ").strip()
        comando = entrada[:1].lower()
        argumento = entrada[1:].strip()

        if comando == "c" and not argumento:
            if perguntas:
                return perguntas
            print("\nÉ preciso ter pelo menos uma pergunta.")

        elif comando == "r":
            indices = ler_indices(argumento, len(perguntas))
            if indices is None:
                print("\nÍndice inválido.")
            else:
                perguntas = [p for i, p in enumerate(perguntas, start=1) if i not in indices]

        elif comando == "a" and not argumento:
            if len(perguntas) >= MAX_PERGUNTAS:
                print(f"\nA seção já tem {MAX_PERGUNTAS} perguntas; remova uma antes de adicionar.")
            else:
                nova = digitar_pergunta()
                if nova:
                    perguntas.append(nova)

        elif comando == "e":
            indices = ler_indices(argumento, len(perguntas))
            if indices is None or len(indices) != 1:
                print("\nInforme um único índice (ex.: E 1).")
            else:
                nova = digitar_pergunta()
                if nova:
                    perguntas[indices[0] - 1] = nova

        else:
            print("\nOpção inválida. Use C, R, A ou E.")


def definir_secao() -> dict | None:
    if not existe_pesquisa_ativa():
        print("\nNão há pesquisa ativa. Rode o intake antes de definir uma seção.")
        return None

    oficial = carregar_contexto()["oficial"]
    print(f"\nTema: {oficial['tema']}")
    print(f"Objetivo: {oficial['objetivo']}")

    titulo = ""
    while not titulo:
        titulo = input("\nTítulo da seção:\n> ").strip()

    pasta = pasta_da_secao(titulo)
    arquivo = pasta / "secao.json"
    if arquivo.exists():
        resposta = input(f"\nA seção '{pasta.name}' já existe. Sobrescrever? [s/n]\n> ").strip().lower()
        if resposta != "s":
            print("\nNada foi alterado.")
            return None

    print("\nGerando sugestões de perguntas-guia...")
    sugeridas = sugerir_perguntas(titulo, oficial)
    if sugeridas is None:
        print("Sem sugestões válidas do LLM. Digite as perguntas com A.")

    perguntas = confirmar_perguntas(sugeridas or [])

    secao = {
        "titulo": titulo,
        "perguntas": perguntas,
        "modelo_sugestao": json.loads(CONFIG_FILE.read_text(encoding="utf-8"))["tarefas"][TAREFA],
        "sugestao_valida": sugeridas is not None,
        "confirmado_em": datetime.now().isoformat(timespec="seconds"),
    }
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(secao, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSeção salva em: {arquivo}")
    return secao
