from agent_writer.rascunho import montar_prompt

TRECHOS = {
    "T1": {"paper": "W1", "pagina": "3", "texto": "texto do primeiro trecho"},
    "T2": {"paper": "W2", "pagina": "7", "texto": "texto do segundo trecho"},
}


def secao(titulo, perguntas):
    return {"titulo": titulo, "perguntas": [{"pt": p} for p in perguntas]}


def test_trechos_vem_antes_das_instrucoes():
    prompt = montar_prompt(secao("Titulo A", ["Pergunta A?"]), TRECHOS)
    assert prompt.index("[T1]") < prompt.index("[T2]") < prompt.index("Titulo A") < prompt.index("Regras:")


def test_prefixo_de_evidencias_e_igual_entre_secoes():
    # CAG: o prefixo (os trechos) não muda, mesmo que o título e as perguntas mudem.
    a = montar_prompt(secao("Titulo A", ["Pergunta A?"]), TRECHOS)
    b = montar_prompt(secao("Titulo B", ["Outra?", "Mais uma?"]), TRECHOS)
    prefixo_a = a[: a.index("Você escreve")]
    assert "texto do segundo trecho" in prefixo_a
    assert prefixo_a == b[: b.index("Você escreve")]
