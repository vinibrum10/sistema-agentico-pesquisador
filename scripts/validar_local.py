"""Validação offline: temporários no repo, dotenv desabilitado, rede/Docker bloqueados."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TMP = RAIZ / ".validacao-local"
TMP.mkdir(exist_ok=True)
sys.dont_write_bytecode = True
sys.path.insert(0, str(RAIZ / "src"))
os.environ.update(PYTHONDONTWRITEBYTECODE="1", PYTHON_DOTENV_DISABLED="1",
                  PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", TMP=str(TMP), TEMP=str(TMP),
                  PASTA_DADOS=str(TMP / "dados-isolados"))
tempfile.tempdir = str(TMP)


def caminho(valor):
    texto = os.fsdecode(valor)
    if texto.startswith("\\\\?\\UNC\\"):
        texto = "\\\\" + texto[8:]
    elif texto.startswith("\\\\?\\"):
        texto = texto[4:]
    return Path(texto).resolve()


def auditar(evento, args):
    if evento == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        p = caminho(args[0])
        if p.name == ".env" or p.name.startswith(".env.") or p.suffix.lower() in {".pem", ".key", ".pfx"}:
            raise OSError("Leitura de credenciais proibida na validação")
        modo, flags = args[1:3]
        escrita = (isinstance(modo, str) and any(c in modo for c in "wax+")) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))
        if escrita and not p.is_relative_to(RAIZ):
            raise OSError("Escrita fora do repositório proibida")
    if evento in {"os.mkdir", "os.remove", "os.rmdir", "os.rename"}:
        for valor in args[:2] if evento == "os.rename" else args[:1]:
            if isinstance(valor, (str, bytes, os.PathLike)) and not caminho(valor).is_relative_to(RAIZ):
                raise OSError("Mutação fora do repositório proibida")
    if evento in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
        raise OSError("Rede proibida na validação")
    if evento == "subprocess.Popen":
        executavel = args[0]
        comando = args[1]
        permitido = (Path(executavel).resolve() == Path(sys.executable).resolve()) if executavel else (
            isinstance(comando, str) and comando.startswith(subprocess.list2cmdline([sys.executable]) + " ")
        )
        if not permitido:
            raise OSError("Somente subprocessos do Python da validação são permitidos")


sys.addaudithook(auditar)
if "--suite-existente" in sys.argv or "--base-deterministica" in sys.argv:
    # Reutiliza dependências locais; nenhuma instalação. Pode falhar por ABI do Python.
    sys.path.append(str(RAIZ / ".venv/Lib/site-packages"))
    import pytest
    alvos = [str(RAIZ / "tests")]
    if "--base-deterministica" in sys.argv:
        alvos = [str(RAIZ / "tests" / n) for n in (
            "test_texto.py", "test_verificacao.py", "test_executor.py", "test_relatorio_semanal.py")]
    base = tempfile.mkdtemp(prefix="pytest-", dir=TMP)
    raise SystemExit(pytest.main([*alvos, "-q", "-p", "no:cacheprovider", "--basetemp", base,
                                 "--log-file", str(TMP / "pytest.log")]))

suite = unittest.defaultTestLoader.discover(str(RAIZ / "tests"), pattern="test_relatorio_semanal.py")
raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
