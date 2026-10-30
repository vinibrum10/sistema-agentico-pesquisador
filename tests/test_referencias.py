from agent_writer.referencias import chave, converter, dados_do_paper, entrada_bib

TRABALHO = {
    "id": "https://openalex.org/W111112222",
    "doi": "https://doi.org/10.1000/abc_1",
    "title": "Um & outro {título}",
    "publication_year": 2020,
    "authorships": [{"author": {"display_name": "José Álvares"}}, {"author": {"display_name": "Mary Smith"}}],
    "biblio": {"volume": "7", "issue": "2", "first_page": "10", "last_page": "20"},
    "primary_location": {"source": {"display_name": "Revista X"}},
}


def dados_a():
    return dados_do_paper("W111112222", TRABALHO, None)


def test_dados_do_openalex():
    dados = dados_a()
    assert dados["autores"] == ["José Álvares", "Mary Smith"]
    assert (dados["venue"], dados["ano"], dados["volume"], dados["numero"]) == ("Revista X", 2020, "7", "2")
    assert (dados["paginas"], dados["doi"]) == ("10--20", "10.1000/abc_1")


def test_pagina_unica_nao_vira_intervalo():
    trabalho = {**TRABALHO, "biblio": {"first_page": "128", "last_page": "128"}}
    assert dados_do_paper("W1", trabalho, None)["paginas"] == "128"


def test_sem_openalex_usa_o_results_csv():
    linha = {"titulo": "Titulo", "ano": "2019", "venue": "V", "doi": "https://doi.org/10.1/x"}
    dados = dados_do_paper("W9", None, linha)
    assert (dados["autores"], dados["titulo"], dados["ano"], dados["doi"]) == ([], "Titulo", "2019", "10.1/x")


def test_sem_nada_so_o_id():
    assert "W9" in dados_do_paper("W9", None, None)["titulo"]


def test_chave_usa_sobrenome_sem_acento_ano_e_fim_do_id():
    assert chave(dados_a(), "W111112222") == "alvares2020_2222"
    assert chave({"autores": [], "ano": 2020}, "W111112222") == "anon2020_2222"


def test_converter_troca_marcadores_sem_repetir_chave():
    outro = dados_do_paper("W333334444", {**TRABALHO, "authorships": [{"author": {"display_name": "Li Wei"}}], "publication_year": 2021}, None)
    dados = {"W111112222": dados_a(), "W333334444": outro}
    refs = {"T1": "W111112222", "T2": "W333334444"}
    texto = "A [T1]. B [T2, T1, T2]. C [T9]. D [sem evidência]."
    novo, sem_paper = converter(texto, refs, dados)
    assert novo == "A [@alvares2020_2222]. B [@wei2021_4444; @alvares2020_2222]. C [T9]. D [sem evidência]."
    assert sem_paper == ["T9"]


def test_entrada_bib_escapa_e_omite_campos_vazios():
    entrada = entrada_bib("W111112222", dados_a())
    assert entrada.startswith("@article{alvares2020_2222,")
    for linha in ["author = {José Álvares and Mary Smith}", r"title = {Um \& outro título}", "pages = {10--20}", r"doi = {10.1000/abc\_1}"]:
        assert linha in entrada


def test_sem_periodico_vira_misc_sem_journal():
    entrada = entrada_bib("W9", dados_do_paper("W9", None, {"titulo": "Titulo", "ano": "2019"}))
    assert entrada.startswith("@misc{anon2019_W9,")
    assert "journal" not in entrada and "author" not in entrada
