import pytest

import main

ETAPAS = ["definir_experimento", "rodar_experimento"]


def rodar_menu(monkeypatch, respostas):
    chamadas = []
    for nome in ETAPAS:
        monkeypatch.setattr(main, nome, lambda nome=nome: chamadas.append(nome))
    entradas = iter(respostas)
    monkeypatch.setattr("builtins.input", lambda *_: next(entradas))
    main.menu_experimento()
    return chamadas


@pytest.mark.parametrize("escolha, etapa", [("1", "definir_experimento"), ("2", "rodar_experimento")])
def test_cada_opcao_chama_a_etapa_certa(monkeypatch, escolha, etapa):
    assert rodar_menu(monkeypatch, [escolha]) == [etapa]


def test_voltar_nao_chama_nenhuma_etapa(monkeypatch):
    assert rodar_menu(monkeypatch, ["3"]) == []


def test_opcao_invalida_pergunta_de_novo(monkeypatch):
    assert rodar_menu(monkeypatch, ["9", "", "2"]) == ["rodar_experimento"]
