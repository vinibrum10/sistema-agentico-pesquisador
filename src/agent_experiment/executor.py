"""Experimentos: roda o comando de uma rodada num container Docker isolado e lê a métrica."""

import hashlib
import math
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path


IMAGEM_BASE = "python:3.12-slim"
MEMORIA = "4g"
CPUS = "2"
SAIDA_MAX = 4000  # caracteres guardados de cada saída (stdout e stderr)


def docker_disponivel() -> bool:
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _existe(imagem: str) -> bool:
    return subprocess.run(["docker", "image", "inspect", imagem], capture_output=True).returncode == 0


def preparar_imagem(base: Path) -> str:
    """Imagem com as dependências de base/requirements.txt (a rede só é usada aqui); sem o arquivo, a imagem base."""
    if not _existe(IMAGEM_BASE):
        subprocess.run(["docker", "pull", IMAGEM_BASE], check=True)

    requisitos = base / "requirements.txt"
    if not requisitos.exists():
        return IMAGEM_BASE

    imagem = "agent-experiment:" + hashlib.sha256(requisitos.read_bytes()).hexdigest()[:12]
    if _existe(imagem):
        return imagem

    with tempfile.TemporaryDirectory() as contexto:
        shutil.copy(requisitos, Path(contexto) / "requirements.txt")
        (Path(contexto) / "Dockerfile").write_text(
            f"FROM {IMAGEM_BASE}\nWORKDIR /exp\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\n",
            encoding="utf-8",
        )
        montagem = subprocess.run(["docker", "build", "-t", imagem, contexto], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if montagem.returncode != 0:
        raise RuntimeError(f"não foi possível montar a imagem com o requirements.txt:\n{(montagem.stdout + montagem.stderr)[-1500:]}")
    return imagem


def ler_metrica(saida: str, nome: str) -> float | None:
    """Valor da última linha 'METRICA nome=valor' da saída; None se não houver ou não for um número."""
    achadas = re.findall(rf"^METRICA\s+{re.escape(nome)}\s*=\s*(\S+)\s*$", saida, re.M)
    try:
        valor = float(achadas[-1]) if achadas else None
    except ValueError:
        return None
    return valor if valor is not None and math.isfinite(valor) else None


def _texto(valor) -> str:
    return valor.decode("utf-8", errors="replace") if isinstance(valor, bytes) else (valor or "")


def executar(imagem: str, pasta_rodada: Path, pasta_dados: Path | None, comando: str, tempo_max_s: int, metrica: str) -> dict:
    """Roda `comando` em /exp (a pasta da rodada, gravável). Sem rede; dados em /dados, só leitura."""
    nome = f"exp-{uuid.uuid4().hex[:12]}"
    args = [
        "docker", "run", "--rm", "--name", nome,
        "--network", "none", "--memory", MEMORIA, "--cpus", CPUS, "--pids-limit", "256",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--read-only", "--tmpfs", "/tmp", "-e", "HOME=/tmp",
        "--mount", f"type=bind,source={Path(pasta_rodada).resolve()},target=/exp", "-w", "/exp",
    ]
    if pasta_dados:
        args += ["--mount", f"type=bind,source={Path(pasta_dados).resolve()},target=/dados,readonly"]
    args += [imagem, "sh", "-c", comando]

    inicio = time.time()
    try:
        r = subprocess.run(args, capture_output=True, timeout=tempo_max_s)
        codigo, saida, erro, estourou = r.returncode, _texto(r.stdout), _texto(r.stderr), False
    except subprocess.TimeoutExpired as e:
        subprocess.run(["docker", "kill", nome], capture_output=True)  # parar o docker CLI não pararia o container
        codigo, saida, erro, estourou = None, _texto(e.stdout), _texto(e.stderr), True

    return {
        "codigo": codigo,
        "estourou_tempo": estourou,
        "tempo_s": round(time.time() - inicio, 1),
        "metrica": ler_metrica(saida, metrica),
        "saida": saida[-SAIDA_MAX:],
        "erro": erro[-SAIDA_MAX:],
    }
