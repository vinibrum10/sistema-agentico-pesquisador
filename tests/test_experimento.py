import json

import pytest

from agent_experiment import experimento


@pytest.fixture(autouse=True)
def pasta_de_experimentos(tmp_path, monkeypatch):
    monkeypatch.setattr(experimento, "EXPERIMENTOS_DIR", tmp_path / "experimentos")
    return tmp_path / "experimentos"


@pytest.fixture
def base(tmp_path):
    pasta = tmp_path / "meu_codigo"
    (pasta / ".venv").mkdir(parents=True)
    (pasta / ".venv" / "lixo.py").write_text("x", encoding="utf-8")
    (pasta / "__pycache__").mkdir()
    (pasta / "main.py").write_text("print('METRICA acc=1')\n", encoding="utf-8")
    return pasta


def digitar(monkeypatch, *respostas):
    fila = iter(respostas)
    monkeypatch.setattr("builtins.input", lambda *_: next(fila))


def test_define_e_salva_o_experimento_com_copia_so_do_codigo(monkeypatch, base, pasta_de_experimentos):
    digitar(monkeypatch, "Meu Teste", "melhorar a acurácia", str(base), "python main.py", "", "acc", "2", "", "", "s")
    pasta = experimento.definir_experimento()
    config = json.loads((pasta / "experimento.json").read_text(encoding="utf-8"))
    assert pasta == pasta_de_experimentos / "meu-teste"
    assert (config["direcao"], config["max_rodadas"], config["tempo_max_s"], config["dados"]) == ("menor", 3, 600, "")
    assert config["metrica"] == "acc" and config["comando"] == "python main.py"
    assert (pasta / "base" / "main.py").exists()
    assert not (pasta / "base" / ".venv").exists() and not (pasta / "base" / "__pycache__").exists()


def test_valor_invalido_pergunta_de_novo(monkeypatch, base, tmp_path):
    dados = tmp_path / "dados"
    dados.mkdir()
    digitar(monkeypatch, "", "T", "obj", "/nao/existe", str(base), "cmd", "/nao/existe", str(dados), "nome com espaco", "acc", "9", "1", "0", "11", "4", "x", "30", "s")
    pasta = experimento.definir_experimento()
    config = json.loads((pasta / "experimento.json").read_text(encoding="utf-8"))
    assert (config["dados"], config["metrica"], config["direcao"], config["max_rodadas"], config["tempo_max_s"]) == (str(dados), "acc", "maior", 4, 1800)


def test_recusa_pasta_sem_py_e_pasta_grande_demais(monkeypatch, base, tmp_path, capsys):
    vazia = tmp_path / "vazia"
    vazia.mkdir()
    (vazia / "leia.txt").write_text("x", encoding="utf-8")
    grande = tmp_path / "grande"
    grande.mkdir()
    (grande / "a.py").write_text("x" * (experimento.LIMITE_CODIGO + 1), encoding="utf-8")
    digitar(monkeypatch, "T", "obj", str(vazia), str(grande), str(base), "cmd", "", "acc", "1", "", "", "n")
    assert experimento.definir_experimento() is None
    saida = capsys.readouterr().out
    assert "não tem arquivo .py" in saida and "o limite é" in saida and "Nada foi salvo" in saida


def test_nome_repetido_e_recusado(monkeypatch, base, pasta_de_experimentos, capsys):
    (pasta_de_experimentos / "meu-teste").mkdir(parents=True)
    digitar(monkeypatch, "Meu Teste", "Outro", "obj", str(base), "cmd", "", "acc", "1", "", "", "n")
    assert experimento.definir_experimento() is None
    assert "Já existe um experimento 'meu-teste'" in capsys.readouterr().out


def definido(monkeypatch, base):
    digitar(monkeypatch, "T", "obj", str(base), "python main.py", "", "acc", "1", "2", "5", "s")
    return experimento.definir_experimento()


def test_rodar_sem_docker_avisa(monkeypatch, base):
    definido(monkeypatch, base)
    digitar(monkeypatch, "1")
    monkeypatch.setattr(experimento, "docker_disponivel", lambda: False)
    with pytest.raises(RuntimeError, match="Docker"):
        experimento.rodar_experimento()


def test_rodar_chama_o_laco_com_a_base_e_uma_pasta_de_execucao_nova(monkeypatch, base):
    pasta = definido(monkeypatch, base)
    digitar(monkeypatch, "1")
    chamadas = []
    monkeypatch.setattr(experimento, "docker_disponivel", lambda: True)
    monkeypatch.setattr(experimento, "preparar_imagem", lambda b: "img")
    monkeypatch.setattr(experimento, "rodar_rodadas", lambda *args: chamadas.append(args) or {"baseline": 0.5, "melhor": {"rodada": 0}, "parada": "limite de rodadas"})
    saida = experimento.rodar_experimento()
    config, base_copia, dados, pasta_saida, imagem = chamadas[0]
    assert (config["max_rodadas"], config["tempo_max_s"], dados, imagem) == (2, 300, None, "img")
    assert base_copia == pasta / "base" and pasta_saida == saida and saida.name.startswith("execucao_")
