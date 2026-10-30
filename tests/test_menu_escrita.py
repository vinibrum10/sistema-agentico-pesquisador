import pytest

import main

ETAPAS = ["definir_secao", "buscar_evidencias", "escrever_rascunho", "gerar_referencias"]


def rodar_menu(monkeypatch, respostas):
    chamadas = []
    for nome in ETAPAS:
        monkeypatch.setattr(main, nome, lambda nome=nome: chamadas.append(nome))
    entradas = iter(respostas)
    monkeypatch.setattr("builtins.input", lambda *_: next(entradas))
    main.menu_escrita()
    return chamadas


@pytest.mark.parametrize("escolha, etapa", [("1", "definir_secao"), ("2", "buscar_evidencias"), ("3", "escrever_rascunho"), ("4", "gerar_referencias")])
def test_cada_opcao_chama_a_etapa_certa(monkeypatch, escolha, etapa):
    assert rodar_menu(monkeypatch, [escolha]) == [etapa]


def test_voltar_nao_chama_nenhuma_etapa(monkeypatch):
    assert rodar_menu(monkeypatch, ["5"]) == []


def test_opcao_invalida_pergunta_de_novo(monkeypatch):
    assert rodar_menu(monkeypatch, ["9", "", "2"]) == ["buscar_evidencias"]
