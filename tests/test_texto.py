from core.texto import ler_indices, ler_lista, normalizar_texto, sem_duplicados


def test_normalizar_texto_tira_acento_caixa_e_espacos():
    assert normalizar_texto("  Ação   CIENTÍFICA ") == "acao cientifica"


def test_ler_lista_ignora_itens_vazios():
    assert ler_lista("a, b,, c ,") == ["a", "b", "c"]


def test_ler_indices_ordena_e_tira_repetidos():
    assert ler_indices("3, 1, 3", total=3) == [1, 3]


def test_ler_indices_recusa_entrada_invalida():
    for texto in ["", "0", "4", "x", "1, x"]:
        assert ler_indices(texto, total=3) is None


def test_sem_duplicados_compara_texto_normalizado():
    assert sem_duplicados(["Ação", "acao", " B ", ""]) == ["Ação", "B"]
