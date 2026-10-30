import shutil
import subprocess

import pytest

from agent_experiment.executor import IMAGEM_BASE, docker_disponivel, executar, ler_metrica, preparar_imagem

sem_docker = pytest.mark.skipif(not docker_disponivel(), reason="Docker indisponível")


def test_ler_metrica_pega_a_ultima_linha_do_nome():
    saida = "treinando\nMETRICA acc=0.5\nMETRICA outra=9\nMETRICA acc=0.75  \n"
    assert ler_metrica(saida, "acc") == 0.75
    assert ler_metrica(saida, "outra") == 9.0


def test_ler_metrica_sem_linha_ou_invalida():
    assert ler_metrica("sem nada", "acc") is None
    assert ler_metrica("METRICA acc=abc", "acc") is None
    assert ler_metrica("METRICA acc=nan", "acc") is None
    assert ler_metrica("meu METRICA acc=1", "acc") is None  # tem que começar a linha


@pytest.fixture(scope="module")
def imagem(tmp_path_factory):
    return preparar_imagem(tmp_path_factory.mktemp("base"))


def rodar(tmp_path, imagem, codigo, tempo=60, dados=None):
    (tmp_path / "main.py").write_text(codigo, encoding="utf-8")
    return executar(imagem, tmp_path, dados, "python main.py", tempo, "m")


@sem_docker
def test_le_a_metrica_e_grava_na_pasta_da_rodada(tmp_path, imagem):
    res = rodar(tmp_path, imagem, "open('out.txt', 'w').write('oi')\nprint('METRICA m=0.5')\n")
    assert (res["codigo"], res["metrica"], res["estourou_tempo"]) == (0, 0.5, False)
    assert (tmp_path / "out.txt").read_text() == "oi"


@sem_docker
def test_erro_do_codigo_e_capturado(tmp_path, imagem):
    res = rodar(tmp_path, imagem, "raise ValueError('quebrou')\n")
    assert res["codigo"] != 0 and res["metrica"] is None
    assert "ValueError: quebrou" in res["erro"]


@sem_docker
def test_estouro_de_tempo_mata_o_container(tmp_path, imagem):
    res = rodar(tmp_path, imagem, "import time\ntime.sleep(60)\n", tempo=4)
    assert res["estourou_tempo"] and res["codigo"] is None
    sobrou = subprocess.run(["docker", "ps", "-a", "-q", "--filter", "name=exp-"], capture_output=True, text=True).stdout.strip()
    assert sobrou == ""


@sem_docker
def test_isolamento_sem_rede_dados_somente_leitura_e_sistema_protegido(tmp_path, imagem):
    dados = tmp_path / "dados"
    dados.mkdir()
    (dados / "a.txt").write_text("abc", encoding="utf-8")
    codigo = """
import socket

def tenta(f):
    try:
        f()
        return 1
    except OSError:
        return 0

print('METRICA leu=%d' % len(open('/dados/a.txt').read()))
print('METRICA rede=%d' % tenta(lambda: socket.create_connection(('1.1.1.1', 53), 3)))
print('METRICA escreve_dados=%d' % tenta(lambda: open('/dados/b.txt', 'w')))
print('METRICA escreve_sistema=%d' % tenta(lambda: open('/etc/x', 'w')))
print('METRICA m=1')
"""
    (tmp_path / "rodada").mkdir()
    res = rodar(tmp_path / "rodada", imagem, codigo, dados=dados)
    assert res["metrica"] == 1.0, res["erro"]
    assert [ler_metrica(res["saida"], n) for n in ("leu", "rede", "escreve_dados", "escreve_sistema")] == [3.0, 0.0, 0.0, 0.0]
    assert not (dados / "b.txt").exists()
