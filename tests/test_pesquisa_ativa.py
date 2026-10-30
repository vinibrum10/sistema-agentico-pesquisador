import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def test_pasta_dados_vem_do_ambiente():
    # Processo separado: a variável vale para ele, sem mexer nos módulos já importados.
    env = {**os.environ, "PASTA_DADOS": "pasta_teste", "PYTHONPATH": str(RAIZ / "src")}
    codigo = (
        "from core.pesquisa_ativa import ACTIVE_RESEARCH_DIR, PROJECT_ROOT; "
        "print(ACTIVE_RESEARCH_DIR.relative_to(PROJECT_ROOT).as_posix())"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo], env=env, capture_output=True, text=True, check=True
    )
    assert saida.stdout.strip() == "pasta_teste/active_research"
