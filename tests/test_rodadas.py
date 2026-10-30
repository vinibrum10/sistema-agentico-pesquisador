import csv

import pytest

from agent_experiment.rodadas import MAX_CORRECOES, ler_codigo, montar_prompt, rodar_rodadas, validar_proposta

CONFIG = {"nome": "t", "objetivo": "melhorar o resultado", "comando": "python main.py", "metrica": "acc",
          "direcao": "maior", "max_rodadas": 5, "tempo_max_s": 10, "dados": ""}


def res(metrica=None, codigo=0, estourou=False, erro=""):
    return {"codigo": codigo, "estourou_tempo": estourou, "tempo_s": 0.1, "metrica": metrica, "saida": "", "erro": erro}


class ExecutorFalso:
    def __init__(self, *resultados):
        self.resultados = iter(resultados)

    def __call__(self, imagem, pasta, dados, comando, tempo, metrica):
        return next(self.resultados)


def propor_falso(config, historico, codigo, erro=None):
    n = len(historico)
    return f"mudança {n}", {"main.py": f"x = {n}\n"}


def rodar(tmp_path, *resultados, config=None, propor_fn=propor_falso):
    base = tmp_path / "base"
    base.mkdir(exist_ok=True)
    (base / "main.py").write_text("x = base\n", encoding="utf-8")
    saida = tmp_path / "execucao"
    try:
        resultado = rodar_rodadas({**CONFIG, **(config or {})}, base, None, saida, "img", propor_fn=propor_fn, executar_fn=ExecutorFalso(*resultados))
    finally:
        linhas = list(csv.DictReader(open(saida / "experimentos.csv", encoding="utf-8-sig", newline=""), delimiter=";"))
    return resultado, linhas, saida


def test_guarda_a_melhor_e_para_depois_de_duas_rodadas_sem_melhora(tmp_path):
    resultado, linhas, saida = rodar(tmp_path, res(0.5), res(0.6), res(0.55), res(0.58))
    assert resultado["melhor"]["rodada"] == 1 and resultado["melhor"]["metrica"] == 0.6
    assert resultado["baseline"] == 0.5 and "sem melhora" in resultado["parada"]
    assert [l["status"] for l in linhas] == ["base", "melhorou", "não melhorou", "não melhorou"]
    assert (saida / "rodada_03").exists() and not (saida / "rodada_04").exists()
    assert "rodada 1" in (saida / "relatorio.md").read_text(encoding="utf-8")


def test_cada_rodada_parte_da_melhor_versao_e_nao_da_anterior(tmp_path):
    def cria_arquivo_novo(config, historico, codigo, erro=None):
        n = len(historico)
        return f"mudança {n}", {f"m{n}.py": "y = 1\n"}

    _, _, saida = rodar(tmp_path, res(0.5), res(0.6), res(0.55), res(0.58), propor_fn=cria_arquivo_novo)
    assert set(ler_codigo(saida / "rodada_02")) == {"main.py", "m1.py", "m2.py"}  # parte da rodada 1, que melhorou
    assert set(ler_codigo(saida / "rodada_03")) == {"main.py", "m1.py", "m3.py"}  # a rodada 2 não melhorou: seu arquivo não vem junto


def test_menor_e_melhor(tmp_path):
    resultado, _, _ = rodar(tmp_path, res(10), res(8), res(9), res(9), config={"direcao": "menor"})
    assert resultado["melhor"]["rodada"] == 1 and resultado["melhor"]["metrica"] == 8


def test_erro_recebe_correcao_na_mesma_rodada(tmp_path):
    erros = []

    def propor_registrando(config, historico, codigo, erro=None):
        erros.append(erro)
        return propor_falso(config, historico, codigo, erro)

    resultado, linhas, _ = rodar(tmp_path, res(0.5), res(codigo=1, erro="boom"), res(0.7), config={"max_rodadas": 1}, propor_fn=propor_registrando)
    assert [l["status"] for l in linhas] == ["base", "erro", "melhorou"]
    assert [l["rodada"] for l in linhas] == ["0", "1", "1"]
    assert erros[0] is None and "boom" in erros[1]
    assert resultado["melhor"]["rodada"] == 1


def test_correcoes_esgotadas_contam_como_rodada_sem_melhora(tmp_path):
    falhas = [res(codigo=1, erro="x")] * (MAX_CORRECOES + 1)
    resultado, linhas, _ = rodar(tmp_path, res(0.5), *falhas, config={"max_rodadas": 1})
    assert [l["status"] for l in linhas] == ["base"] + ["erro"] * (MAX_CORRECOES + 1)
    assert resultado["melhor"]["rodada"] == 0 and resultado["parada"] == "limite de rodadas"


def test_estouro_de_tempo_e_saida_sem_metrica_sao_erros(tmp_path):
    _, linhas, _ = rodar(tmp_path, res(0.5), res(estourou=True), res(codigo=0, metrica=None), res(0.6), config={"max_rodadas": 1})
    assert [l["status"] for l in linhas] == ["base", "erro", "erro", "melhorou"]


def test_proposta_invalida_conta_como_sem_melhora(tmp_path):
    resultado, linhas, _ = rodar(tmp_path, res(0.5), config={"max_rodadas": 3}, propor_fn=lambda *a: None)
    assert [l["status"] for l in linhas] == ["base", "proposta inválida", "proposta inválida"]
    assert "sem melhora" in resultado["parada"]


def test_base_sem_metrica_interrompe_mas_gera_relatorio(tmp_path):
    with pytest.raises(RuntimeError, match="não gerou a métrica"):
        rodar(tmp_path, res(None))
    assert "não gerou a métrica" in (tmp_path / "execucao" / "relatorio.md").read_text(encoding="utf-8")


def test_relatorio_mostra_a_diferenca_para_o_codigo_base(tmp_path):
    _, _, saida = rodar(tmp_path, res(0.5), res(0.6), config={"max_rodadas": 1})
    texto = (saida / "relatorio.md").read_text(encoding="utf-8")
    assert "-x = base" in texto and "+x = 1" in texto


@pytest.mark.parametrize("dados", [
    {"motivo": "m", "arquivos": [{"caminho": "/etc/x.py", "conteudo": "x"}]},
    {"motivo": "m", "arquivos": [{"caminho": "../x.py", "conteudo": "x"}]},
    {"motivo": "m", "arquivos": [{"caminho": "C:/x.py", "conteudo": "x"}]},
    {"motivo": "m", "arquivos": [{"caminho": "a\\b.py", "conteudo": "x"}]},
    {"motivo": "m", "arquivos": [{"caminho": "run.sh", "conteudo": "x"}]},
    {"motivo": "m", "arquivos": [{"caminho": "a.py", "conteudo": "  "}]},
    {"motivo": "", "arquivos": [{"caminho": "a.py", "conteudo": "x"}]},
    {"motivo": "m", "arquivos": []},
    {"motivo": "m", "arquivos": [{"caminho": "a.py", "conteudo": "igual"}]},  # não muda nada
    {"arquivos": "texto"},
])
def test_proposta_invalida_e_recusada(dados):
    assert validar_proposta(dados, {"a.py": "igual"}) is None


def test_proposta_valida_aceita_arquivo_novo_em_subpasta():
    dados = {"motivo": " m ", "arquivos": [{"caminho": "pkg/novo.py", "conteudo": "y = 1"}]}
    assert validar_proposta(dados, {"a.py": "x"}) == ("m", {"pkg/novo.py": "y = 1"})


def test_ler_codigo_ignora_cache_e_outros_arquivos(tmp_path):
    (tmp_path / "a.py").write_text("a", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "b.py").write_text("b", encoding="utf-8")
    (tmp_path / "dados.csv").write_text("c", encoding="utf-8")
    assert ler_codigo(tmp_path) == {"a.py": "a"}


def test_prompt_traz_objetivo_metrica_historico_codigo_e_erro():
    historico = [{"rodada": 1, "tentativa": 0, "mudanca": "trocou X", "metrica": 0.6, "status": "melhorou", "tempo_s": 1}]
    prompt = montar_prompt(CONFIG, historico, {"main.py": "x = 1"}, "deu ruim")
    for trecho in ["melhorar o resultado", "acc (maior é melhor)", "rodada 1: trocou X -> acc = 0.6 (melhorou)", "=== main.py ===", "x = 1", "deu ruim"]:
        assert trecho in prompt
    assert "falhou" not in montar_prompt(CONFIG, [], {"main.py": "x"}, None)
