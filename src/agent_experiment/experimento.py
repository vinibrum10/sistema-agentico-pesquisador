"""Experimentos: definir o experimento (perguntas curtas, confirmadas) e rodá-lo."""

import json
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path

from agent_experiment.executor import docker_disponivel, preparar_imagem
from agent_experiment.rodadas import rodar_rodadas
from core.pesquisa_ativa import ACTIVE_RESEARCH_DIR


EXPERIMENTOS_DIR = ACTIVE_RESEARCH_DIR / "experimentos"
LIMITE_CODIGO = 24_000  # bytes de .py que cabem no prompt do modelo
LIMITE_BASE = 5_000_000  # bytes copiados para base/: a base é só código
PASTAS_IGNORADAS = {"__pycache__", ".git", ".venv"}
IGNORAR = shutil.ignore_patterns(*PASTAS_IGNORADAS, "*.pyc")


def _ler(rotulo: str, validar, padrao=None):
    """Repete a pergunta até `validar(texto)` devolver um valor (None = inválido); Enter usa `padrao`."""
    while True:
        texto = input(f"\n{rotulo}\n> ").strip()
        if not texto and padrao is not None:
            return padrao
        valor = validar(texto)
        if valor is not None:
            return valor
        print("\nValor inválido.")


def _nome(texto: str) -> str | None:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")[:60]
    if slug and (EXPERIMENTOS_DIR / slug).exists():
        print(f"\nJá existe um experimento '{slug}'; escolha outro nome.")
        return None
    return slug or None


def _pasta_base(texto: str) -> Path | None:
    pasta = Path(texto)
    if not pasta.is_dir():
        return None
    arquivos = [a for a in pasta.rglob("*") if a.is_file() and not set(a.relative_to(pasta).parts) & PASTAS_IGNORADAS]
    codigo = sum(a.stat().st_size for a in arquivos if a.suffix == ".py")
    if not codigo:
        print("\nA pasta não tem arquivo .py.")
        return None
    if codigo > LIMITE_CODIGO:
        print(f"\nOs arquivos .py somam {codigo} bytes; o limite é {LIMITE_CODIGO} (precisam caber no prompt do modelo).")
        return None
    if sum(a.stat().st_size for a in arquivos) > LIMITE_BASE:
        print(f"\nA pasta passa de {LIMITE_BASE // 1_000_000} MB; a base deve ter só o código (os dados vão em 'Pasta de dados').")
        return None
    return pasta


def _inteiro(minimo: int, maximo: int):
    return lambda texto: int(texto) if texto.isdigit() and minimo <= int(texto) <= maximo else None


def definir_experimento():
    print("\n=== Definir experimento ===")
    nome = _ler("Nome do experimento:", _nome)
    objetivo = _ler("Objetivo do experimento (uma frase):", lambda t: t or None)
    origem = _ler("Pasta do código base (caminho completo; o experimento usa uma cópia):", _pasta_base)
    comando = _ler("Comando que roda o código, a partir da pasta do código (ex.: python main.py):", lambda t: t or None)
    dados = _ler("Pasta de dados, somente leitura (Enter = nenhuma):", lambda t: t if Path(t).is_dir() else None, padrao="")
    metrica = _ler("Nome da métrica (o código imprime uma linha METRICA nome=valor):", lambda t: t if re.fullmatch(r"[A-Za-z0-9_.-]+", t) else None)
    direcao = _ler("Na métrica, o que é melhor? [1] maior  [2] menor", {"1": "maior", "2": "menor"}.get)
    max_rodadas = _ler("Máximo de rodadas de mudança (Enter = 3; de 1 a 10):", _inteiro(1, 10), padrao=3)
    minutos = _ler("Tempo máximo por rodada, em minutos (Enter = 10):", _inteiro(1, 240), padrao=10)

    config = {
        "nome": nome, "objetivo": objetivo, "comando": comando, "metrica": metrica, "direcao": direcao,
        "max_rodadas": max_rodadas, "tempo_max_s": minutos * 60, "dados": dados, "origem": str(origem),
        "criado_em": datetime.now().isoformat(timespec="seconds"),
    }
    print(f"\nExperimento '{nome}'")
    print(f"  Objetivo: {objetivo}")
    print(f"  Código base: {origem}  ->  comando: {comando}")
    print(f"  Dados: {dados or '(nenhum)'}")
    print(f"  Métrica: {metrica} ({direcao} é melhor)")
    print(f"  Limites: {max_rodadas} rodadas de mudança, {minutos} min por rodada")

    if input("\nConfirmar? [s/n]\n> ").strip().lower() != "s":
        print("\nNada foi salvo.")
        return None

    pasta = EXPERIMENTOS_DIR / nome
    shutil.copytree(origem, pasta / "base", ignore=IGNORAR)
    (pasta / "experimento.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nExperimento salvo em: {pasta}")
    return pasta


def escolher_experimento():
    pastas = sorted(p.parent for p in EXPERIMENTOS_DIR.glob("*/experimento.json"))
    if not pastas:
        print("\nNenhum experimento definido. Defina um experimento antes.")
        return None

    print("\nExperimentos:")
    for i, pasta in enumerate(pastas, start=1):
        objetivo = json.loads((pasta / "experimento.json").read_text(encoding="utf-8"))["objetivo"]
        print(f"  {i}. {pasta.name} — {objetivo}")

    while True:
        escolha = input("\nNúmero do experimento:\n> ").strip()
        if escolha.isdigit() and 1 <= int(escolha) <= len(pastas):
            return pastas[int(escolha) - 1]
        print("\nNúmero inválido.")


def rodar_experimento():
    pasta = escolher_experimento()
    if pasta is None:
        return None
    if not docker_disponivel():
        raise RuntimeError("o Docker não está respondendo: abra o Docker Desktop e rode a etapa de novo")

    config = json.loads((pasta / "experimento.json").read_text(encoding="utf-8"))
    dados = Path(config["dados"]) if config["dados"] else None
    if dados and not dados.is_dir():
        raise RuntimeError(f"a pasta de dados não existe mais: {dados}")

    saida = pasta / f"execucao_{datetime.now():%Y-%m-%d_%H-%M-%S}"
    print("\nMontando o ambiente (a primeira vez pode levar alguns minutos)...")
    imagem = preparar_imagem(pasta / "base")
    print(f"Rodando o código base e até {config['max_rodadas']} rodadas de mudança...")
    resultado = rodar_rodadas(config, pasta / "base", dados, saida, imagem)

    melhor = resultado["melhor"]
    print(f"\nCódigo base: {config['metrica']} = {resultado['baseline']}")
    if melhor["rodada"] == 0:
        print("Nenhuma mudança melhorou a métrica.")
    else:
        print(f"Melhor: rodada {melhor['rodada']}, {config['metrica']} = {melhor['metrica']}")
    print(f"Parou por: {resultado['parada']}")
    print(f"Relatório: {saida / 'relatorio.md'}")
    return saida
