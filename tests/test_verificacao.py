import csv

from agent_writer.verificacao import COPIA_MIN_PALAVRAS, gravar_revisao, verificar

COPIAVEL = (
    "the random forest algorithm was applied after optimization and tuning of the "
    "hyperparameters in the study area"
).split()

TRECHOS = {
    "T1": {"texto": "The model reached 92% accuracy in the test area with 100,388 grid values."},
    "T2": {"texto": "Another passage about a different subject entirely."},
    "T3": {"texto": " ".join(COPIAVEL)},
}


def problemas(texto, n_perguntas=1):
    return [p for linha in verificar(texto, TRECHOS, n_perguntas) for p in linha["problemas"]]


def test_texto_correto_nao_tem_problemas():
    texto = "O modelo alcançou 92% de acurácia com 100.388 valores [T1]. Outro assunto [T2, T1]."
    assert problemas(texto) == []


def test_sem_evidencia_vale_como_fonte():
    assert problemas("Os trechos não cobrem esse aspecto [sem evidência].") == []


def test_marcador_inexistente():
    assert problemas("Uma afirmação qualquer [T9].") == ["marcador inexistente: T9"]


def test_frase_sem_fonte_depois_do_ultimo_marcador():
    (problema,) = problemas("Uma afirmação [T2]. Sobrou texto sem referência.")
    assert problema.startswith("frase sem fonte")


def test_duas_frases_para_um_marcador():
    (problema,) = problemas("Uma frase solta. Outra frase [T2].")
    assert problema.startswith("duas frases")


def test_numero_fora_do_trecho_citado():
    assert problemas("Alcançou 95% de acurácia [T1].") == ["número fora do trecho citado: 95"]


def test_copia_literal_a_partir_do_limite():
    copia = " ".join(COPIAVEL[:COPIA_MIN_PALAVRAS])
    assert problemas(f"{copia} [T3].") == [f"cópia literal: {COPIA_MIN_PALAVRAS} palavras seguidas iguais ao trecho"]
    assert problemas(f"{' '.join(COPIAVEL[:COPIA_MIN_PALAVRAS - 1])} [T3].") == []


def test_frase_repetida():
    texto = "Uma afirmação [T2].\n\nUma afirmação [T2]."
    assert problemas(texto, n_perguntas=2) == ["frase repetida (já no parágrafo 1)"]


def test_numeracao_no_inicio_do_paragrafo():
    assert problemas("1. Uma afirmação [T2].") == ["numeração ou título no início do parágrafo"]


def test_paragrafos_diferentes_do_numero_de_perguntas():
    assert problemas("Uma afirmação [T2].", n_perguntas=2) == ["1 parágrafo(s) para 2 pergunta(s)"]


def test_gravar_revisao_marca_status_e_conta_problemas(tmp_path):
    linhas = verificar("Certa [T2]. Errada [T9].", TRECHOS, 1)
    arquivo = tmp_path / "revisao.csv"
    assert gravar_revisao(arquivo, linhas) == 1
    with open(arquivo, encoding="utf-8-sig", newline="") as f:
        status = [linha["status"] for linha in csv.DictReader(f, delimiter=";")]
    assert status == ["ok", "revisar"]
