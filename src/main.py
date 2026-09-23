import json
import unicodedata
from pathlib import Path

from langchain_ollama import ChatOllama


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ACTIVE_RESEARCH_DIR = PROJECT_ROOT / "data" / "active_research"
CONTEXT_FILE = ACTIVE_RESEARCH_DIR / "context.json"

# Um termo-base deve ser um conceito curto,
# não a frase inteira do tema ou do objetivo.
MAX_PALAVRAS_ORIGEM = 4


FOCOS = {
    "1": "panorama",
    "2": "metodos",
    "3": "dados",
    "4": "nao_sei",
}

ROTULOS_FOCO = {
    "panorama": "Panorama geral / estado da arte",
    "metodos": "Métodos e técnicas",
    "dados": "Dados e datasets",
    "nao_sei": "Ainda não sei",
}


def existe_pesquisa_ativa() -> bool:
    return CONTEXT_FILE.exists()


def normalizar_texto(texto: str) -> str:
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto)

    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )

    return " ".join(texto.split())


def criar_modelo() -> ChatOllama:
    return ChatOllama(
        model="qwen3:8b",
        temperature=0,
        reasoning=False,
        format="json",
    )


def perguntar_foco() -> str:
    while True:
        print("\n3. Qual é o foco desta busca?")
        print("[1] Panorama geral / estado da arte")
        print("[2] Métodos e técnicas")
        print("[3] Dados e datasets")
        print("[4] Ainda não sei")

        escolha = input("> ").strip()

        if escolha in FOCOS:
            return FOCOS[escolha]

        print("\nOpção inválida. Escolha 1, 2, 3 ou 4.")


def executar_intake() -> dict:
    print("\nVamos iniciar uma nova pesquisa.\n")

    tema = input(
        "1. Qual é o tema da tese?\n> "
    ).strip()

    objetivo = input(
        "\n2. Qual é o objetivo da pesquisa?\n> "
    ).strip()

    foco = perguntar_foco()

    restricao = input(
        "\n4. Existe alguma restrição importante?\n"
        "Se não houver, escreva 'Nenhuma'.\n> "
    ).strip()

    return {
        "tema": tema,
        "objetivo": objetivo,
        "foco": foco,
        "restricao": restricao,
    }


def mostrar_respostas(respostas: dict) -> None:
    print("\n=== Intake coletado ===\n")

    print(f"Tema: {respostas['tema']}")
    print(f"Objetivo: {respostas['objetivo']}")
    print(
        f"Foco: "
        f"{ROTULOS_FOCO.get(respostas['foco'], respostas['foco'])}"
    )
    print(f"Restrição: {respostas['restricao']}")


# ==================================================
# ETAPA A — CHAMADA 1: reformulação de Tema/Objetivo
# ==================================================


def sugerir_reformulacoes(
    tema: str,
    objetivo: str,
) -> dict:

    modelo = criar_modelo()

    dados = json.dumps(
        {
            "tema": tema,
            "objetivo": objetivo,
        },
        ensure_ascii=False,
        indent=2,
    )

    prompt = f"""
Você apoia a redação do Research Intake
de um sistema de pesquisa científica.

Textos do pesquisador:

{dados}

Tarefa:

"tema_formulado":
apenas melhore a redação do tema, sem mudar o sentido.

"objetivo_formulado":
apenas melhore a redação do objetivo, sem mudar o sentido.

Não acrescente conceitos que não estejam nos textos.

Retorne SOMENTE JSON válido:

{{
  "tema_formulado": "texto",
  "objetivo_formulado": "texto"
}}
"""

    resposta = modelo.invoke(prompt)

    sugestoes = json.loads(resposta.content)

    return {
        "tema_formulado": sugestoes.get("tema_formulado"),
        "objetivo_formulado": sugestoes.get("objetivo_formulado"),
    }


# ==================================================
# ETAPA A — DECISÃO HUMANA
# ==================================================


def escolher_original_ou_sugestao(
    titulo: str,
    original: str,
    sugestao: str | None,
) -> str:

    print(f"\n=== Confirmação: {titulo} ===\n")

    print("Texto informado:")
    print(original)

    tem_sugestao = bool(sugestao and sugestao.strip())

    print("\nSugestão do LLM:")
    if tem_sugestao:
        print(sugestao)
    else:
        print("(o modelo não gerou sugestão)")

    while True:
        if tem_sugestao:
            print("\n[1] Usar sugestão")
        print("[2] Manter texto original")
        print("[3] Escrever uma versão própria")

        escolha = input("> ").strip()

        if escolha == "1" and tem_sugestao:
            return sugestao.strip()

        if escolha == "2":
            return original

        if escolha == "3":
            while True:
                texto_proprio = input(
                    f"\nDigite o {titulo.lower()} que deseja usar:\n> "
                ).strip()

                if texto_proprio:
                    return texto_proprio

                print("\nO texto não pode ficar vazio.")

        print("\nOpção inválida.")


def confirmar_tema_oficial(tema: str) -> str:
    while True:
        print("\n=== Tema oficial da pesquisa ===\n")

        print(tema)

        print("\n[1] Confirmar tema oficial")
        print("[2] Ajustar texto")

        escolha = input("> ").strip()

        if escolha == "1":
            print("\nTema oficial confirmado.")
            return tema

        if escolha == "2":
            novo_tema = input(
                "\nDigite o tema oficial da pesquisa:\n> "
            ).strip()

            if novo_tema:
                tema = novo_tema
            else:
                print("\nO tema não pode ficar vazio.")

        else:
            print("\nOpção inválida. Escolha 1 ou 2.")


def definir_texto_oficial(respostas: dict) -> dict:
    """
    Etapa A completa: chamada 1 ao LLM + decisões do pesquisador.

    Retorna o contexto OFICIAL. A partir daqui, o tema e o
    objetivo originais do Intake não são mais usados.
    """

    print(
        "\nGerando sugestões de redação "
        "para Tema e Objetivo..."
    )

    reformulacoes = sugerir_reformulacoes(
        respostas["tema"],
        respostas["objetivo"],
    )

    tema_escolhido = escolher_original_ou_sugestao(
        "Tema",
        respostas["tema"],
        reformulacoes["tema_formulado"],
    )

    tema_oficial = confirmar_tema_oficial(
        tema_escolhido
    )

    objetivo_oficial = escolher_original_ou_sugestao(
        "Objetivo",
        respostas["objetivo"],
        reformulacoes["objetivo_formulado"],
    )

    return {
        "tema": tema_oficial,
        "objetivo": objetivo_oficial,
        "foco": respostas["foco"],
        "restricao": respostas["restricao"],
    }


def mostrar_contexto_oficial(oficial: dict) -> None:
    print("\n=== Contexto oficial enviado para análise ===\n")

    print(f"Tema oficial: {oficial['tema']}")
    print(f"Objetivo oficial: {oficial['objetivo']}")
    print(
        f"Foco: "
        f"{ROTULOS_FOCO.get(oficial['foco'], oficial['foco'])}"
    )
    print(f"Restrição: {oficial['restricao']}")


# ==================================================
# ETAPA B — CHAMADA 2: análise do contexto oficial
# ==================================================


def analisar_contexto_oficial(oficial: dict) -> dict:
    modelo = criar_modelo()

    dados = json.dumps(
        oficial,
        ensure_ascii=False,
        indent=2,
    )

    prompt = f"""
Você é o componente de apoio ao Research Intake
de um sistema de pesquisa científica.

Contexto oficial confirmado pelo pesquisador:

{dados}

Sua tarefa possui DUAS PARTES DIFERENTES.

==================================================
PARTE 1 — TERMOS-BASE
==================================================

Identifique somente conceitos que estejam explicitamente
presentes nas respostas do pesquisador.

Para cada conceito-base:

1. "origem" deve ser uma expressão copiada LITERALMENTE
   de alguma resposta do pesquisador.
   Deve ser um conceito curto (1 a 4 palavras),
   nunca a frase inteira do tema ou do objetivo.

2. Não invente uma origem.

3. Não transforme um conceito em outro conceito.

4. Você pode fornecer:
   - o termo original em português;
   - uma tradução direta para inglês.

5. Não acrescente como termo-base:
   - métodos relacionados;
   - disciplinas relacionadas;
   - técnicas relacionadas;
   - tipos de dados;
   - conceitos mais amplos;
   - conceitos mais específicos.

Exemplo:

Se o pesquisador escreveu:

"inteligência artificial"

termo-base permitido:

origem: "inteligência artificial"
pt: ["inteligência artificial"]
en: ["artificial intelligence"]

NÃO são termos-base permitidos:

- machine learning
- deep learning
- neural networks

Se o pesquisador escreveu:

"prospecção de urânio"

termo-base permitido:

origem: "prospecção de urânio"
pt: ["prospecção de urânio"]
en: ["uranium prospecting"]

NÃO são termos-base permitidos:

- mineração
- geologia
- prospecção mineral
- prospecção geológica


==================================================
PARTE 2 — EXPANSÕES SUGERIDAS
==================================================

Separadamente, você pode sugerir termos que POSSAM ser
úteis para ampliar futuras buscas.

Essas expansões:

- NÃO fazem parte do contexto confirmado;
- NÃO devem ser misturadas com os termos-base;
- podem incluir sinônimos ou conceitos relacionados;
- devem informar a qual conceito-base estão relacionadas.


==================================================
RESTRIÇÃO GEOGRÁFICA
==================================================

Se existir uma restrição geográfica explícita,
como Brasil ou Brazil, coloque-a separadamente.

A origem também deve ser copiada literalmente
da resposta do pesquisador.


==================================================
FOCO
==================================================

Se foco for diferente de "nao_sei":

"foco_sugerido": null

Se foco for "nao_sei":

sugira somente um destes valores:

- panorama
- metodos
- dados


==================================================
FORMATO DE SAÍDA
==================================================

Retorne SOMENTE JSON válido:

{{
  "foco_sugerido": null,
  "idiomas": ["pt", "en"],

  "termos_base": [
    {{
      "codigo": "conceito_1",
      "origem": "expressão literal presente nas respostas",
      "pt": ["termo"],
      "en": ["term"]
    }}
  ],

  "restricao_geografica": {{
    "origem": "expressão literal presente nas respostas",
    "pt": ["Brasil"],
    "en": ["Brazil"]
  }},

  "expansoes_sugeridas": [
    {{
      "codigo_base": "conceito_1",
      "origem_base": "expressão literal do conceito-base",
      "pt": ["sugestão"],
      "en": ["suggestion"]
    }}
  ]
}}

Se não existir restrição geográfica explícita:

"restricao_geografica": null

Se não houver expansões úteis:

"expansoes_sugeridas": []
"""

    resposta = modelo.invoke(prompt)

    return json.loads(resposta.content)


def validar_origem(origem: str, oficial: dict) -> bool:
    if not origem or not isinstance(origem, str):
        return False

    texto_oficial = " ".join(
        [
            oficial["tema"],
            oficial["objetivo"],
            oficial["restricao"],
        ]
    )

    return (
        normalizar_texto(origem)
        in normalizar_texto(texto_oficial)
    )


def origem_e_conceito_curto(
    origem: str,
    oficial: dict,
) -> bool:

    origem_normalizada = normalizar_texto(origem)

    campos_inteiros = {
        normalizar_texto(oficial["tema"]),
        normalizar_texto(oficial["objetivo"]),
        normalizar_texto(oficial["restricao"]),
    }

    if origem_normalizada in campos_inteiros:
        return False

    return (
        len(origem_normalizada.split())
        <= MAX_PALAVRAS_ORIGEM
    )


def validar_sugestoes(
    sugestoes: dict,
    oficial: dict,
) -> dict:

    termos_validos = []
    termos_rejeitados = []

    termos_base = sugestoes.get("termos_base", [])

    if not isinstance(termos_base, list):
        raise ValueError(
            "O modelo não retornou termos_base como lista."
        )

    for termo in termos_base:
        if not isinstance(termo, dict):
            termos_rejeitados.append(
                {
                    "motivo": "formato inválido",
                    "conteudo": termo,
                }
            )
            continue

        codigo = termo.get("codigo")
        origem = termo.get("origem")
        termos_pt = termo.get("pt")
        termos_en = termo.get("en")

        if not codigo:
            termos_rejeitados.append(
                {
                    "motivo": "conceito sem código",
                    "conteudo": termo,
                }
            )
            continue

        if not validar_origem(origem, oficial):
            termos_rejeitados.append(
                {
                    "motivo": (
                        "origem não encontrada no contexto oficial"
                    ),
                    "conteudo": termo,
                }
            )
            continue

        if not origem_e_conceito_curto(origem, oficial):
            termos_rejeitados.append(
                {
                    "motivo": (
                        "origem longa demais, não é um conceito"
                    ),
                    "conteudo": termo,
                }
            )
            continue

        if not isinstance(termos_pt, list):
            termos_rejeitados.append(
                {
                    "motivo": "campo PT inválido",
                    "conteudo": termo,
                }
            )
            continue

        if not isinstance(termos_en, list):
            termos_rejeitados.append(
                {
                    "motivo": "campo EN inválido",
                    "conteudo": termo,
                }
            )
            continue

        termos_validos.append(termo)

    restricao = sugestoes.get(
        "restricao_geografica"
    )

    restricao_valida = None

    if isinstance(restricao, dict):
        origem_restricao = restricao.get("origem")

        if validar_origem(
            origem_restricao,
            oficial,
        ):
            restricao_valida = restricao

    # Expansões só são oferecidas se estiverem ligadas
    # a um termo-base que passou na validação.
    codigos_validos = {
        termo["codigo"] for termo in termos_validos
    }

    expansoes = sugestoes.get(
        "expansoes_sugeridas",
        [],
    )

    if not isinstance(expansoes, list):
        expansoes = []

    expansoes_validas = [
        expansao
        for expansao in expansoes
        if isinstance(expansao, dict)
        and expansao.get("codigo_base") in codigos_validos
    ]

    return {
        "foco_sugerido": sugestoes.get(
            "foco_sugerido"
        ),
        "idiomas": sugestoes.get(
            "idiomas",
            [],
        ),
        "termos_base_validos": termos_validos,
        "termos_base_rejeitados": termos_rejeitados,
        "restricao_geografica_valida": restricao_valida,
        "expansoes_sugeridas": expansoes_validas,
    }


def mostrar_termos_rejeitados(
    rejeitados: list,
) -> None:

    if not rejeitados:
        return

    print("\n=== Termos descartados pelo programa ===")

    for item in rejeitados:
        conteudo = item["conteudo"]

        if isinstance(conteudo, dict):
            descricao = conteudo.get("origem")
        else:
            descricao = conteudo

        print(f"- {descricao} ({item['motivo']})")


# ==================================================
# ETAPA B — DECISÃO HUMANA
# ==================================================


def confirmar_foco(
    foco_original: str,
    resultado: dict,
) -> str:

    if foco_original != "nao_sei":
        return foco_original

    foco_sugerido = resultado.get(
        "foco_sugerido"
    )

    if foco_sugerido not in {
        "panorama",
        "metodos",
        "dados",
    }:
        print(
            "\nO modelo não gerou um foco válido."
        )
        return perguntar_foco()

    print("\n=== Foco sugerido ===\n")
    print(
        ROTULOS_FOCO[foco_sugerido]
    )

    while True:
        print("\n[1] Aceitar sugestão")
        print("[2] Escolher manualmente")

        escolha = input("> ").strip()

        if escolha == "1":
            return foco_sugerido

        if escolha == "2":
            return perguntar_foco()

        print("\nOpção inválida.")


def confirmar_idiomas(
    idiomas_sugeridos: list,
) -> list:

    print("\n=== Idiomas sugeridos ===\n")

    for idioma in idiomas_sugeridos:
        print(f"- {idioma}")

    while True:
        print("\n[1] Confirmar")
        print("[2] Ajustar")

        escolha = input("> ").strip()

        if escolha == "1":
            return idiomas_sugeridos

        if escolha == "2":
            print(
                "\nEscolha os idiomas desejados:"
            )
            print("[1] Português")
            print("[2] Inglês")
            print("[3] Português e Inglês")

            opcao = input("> ").strip()

            if opcao == "1":
                return ["pt"]

            if opcao == "2":
                return ["en"]

            if opcao == "3":
                return ["pt", "en"]

            print("\nOpção inválida.")
            continue

        print("\nOpção inválida.")


def mostrar_termos_base(
    termos: list,
) -> None:

    print("\n=== Termos-base ===")

    if not termos:
        print("\nNenhum termo-base válido.")

    for termo in termos:
        print(
            f"\nOrigem: \"{termo['origem']}\""
        )

        print("PT:")
        for item in termo["pt"]:
            print(f"- {item}")

        print("EN:")
        for item in termo["en"]:
            print(f"- {item}")


def confirmar_termos_base(
    termos: list,
) -> list:

    mostrar_termos_base(termos)

    while True:
        print("\n[1] Confirmar")
        print("[2] Ajustar")

        escolha = input("> ").strip()

        if escolha == "1":
            return termos

        if escolha == "2":
            termos_ajustados = []

            for termo in termos:
                print(
                    f"\nOrigem: {termo['origem']}"
                )

                print(
                    "Termos PT atuais: "
                    + ", ".join(termo["pt"])
                )

                novo_pt = input(
                    "Novos termos PT "
                    "(separe por vírgula ou Enter para manter):\n> "
                ).strip()

                print(
                    "Termos EN atuais: "
                    + ", ".join(termo["en"])
                )

                novo_en = input(
                    "Novos termos EN "
                    "(separe por vírgula ou Enter para manter):\n> "
                ).strip()

                pt = termo["pt"]
                en = termo["en"]

                if novo_pt:
                    pt = [
                        item.strip()
                        for item in novo_pt.split(",")
                        if item.strip()
                    ]

                if novo_en:
                    en = [
                        item.strip()
                        for item in novo_en.split(",")
                        if item.strip()
                    ]

                termos_ajustados.append(
                    {
                        "codigo": termo["codigo"],
                        "origem": termo["origem"],
                        "pt": pt,
                        "en": en,
                    }
                )

            return termos_ajustados

        print("\nOpção inválida.")


def selecionar_expansoes(
    expansoes: list,
) -> list:

    print("\n=== Expansões opcionais ===")

    if not expansoes:
        print("\nNenhuma expansão foi sugerida.")
        return []

    for indice, expansao in enumerate(
        expansoes,
        start=1,
    ):
        print(f"\n[{indice}]")
        print(
            f"Relacionada a: "
            f"{expansao.get('origem_base')}"
        )

        print(
            "PT: "
            + ", ".join(
                expansao.get("pt", [])
            )
        )

        print(
            "EN: "
            + ", ".join(
                expansao.get("en", [])
            )
        )

    print(
        "\nDigite os números das expansões que deseja aceitar."
    )
    print("Exemplo: 1,2")
    print("Digite N para não aceitar nenhuma.")

    while True:
        escolha = input("> ").strip().lower()

        if escolha == "n":
            return []

        try:
            indices = {
                int(item.strip())
                for item in escolha.split(",")
                if item.strip()
            }

        except ValueError:
            print("\nEntrada inválida.")
            continue

        if not indices:
            print("\nEscolha pelo menos uma opção ou N.")
            continue

        if any(
            indice < 1
            or indice > len(expansoes)
            for indice in indices
        ):
            print("\nExiste um número inválido.")
            continue

        return [
            expansoes[indice - 1]
            for indice in sorted(indices)
        ]


def montar_contexto_confirmado(
    oficial: dict,
    resultado: dict,
) -> dict:

    foco = confirmar_foco(
        oficial["foco"],
        resultado,
    )

    idiomas = confirmar_idiomas(
        resultado["idiomas"]
    )

    termos_base = confirmar_termos_base(
        resultado["termos_base_validos"]
    )

    expansoes = selecionar_expansoes(
        resultado["expansoes_sugeridas"]
    )

    return {
        "tema": oficial["tema"],
        "objetivo": oficial["objetivo"],
        "foco": foco,
        "restricao": oficial["restricao"],
        "idiomas": idiomas,
        "termos_base": termos_base,
        "restricao_geografica": resultado[
            "restricao_geografica_valida"
        ],
        "expansoes_aprovadas": expansoes,
    }


def mostrar_contexto_final(
    contexto: dict,
) -> None:

    print(
        "\n=== Contexto pronto para confirmação ===\n"
    )

    print(f"Tema:\n{contexto['tema']}")

    print(
        f"\nObjetivo:\n"
        f"{contexto['objetivo']}"
    )

    print(
        f"\nFoco:\n"
        f"{ROTULOS_FOCO[contexto['foco']]}"
    )

    print(
        "\nIdiomas:\n"
        + ", ".join(contexto["idiomas"])
    )

    print("\nTermos-base:")

    for termo in contexto["termos_base"]:
        print(
            f"\n- {termo['origem']}"
        )
        print(
            "  PT: "
            + ", ".join(termo["pt"])
        )
        print(
            "  EN: "
            + ", ".join(termo["en"])
        )

    restricao = contexto.get(
        "restricao_geografica"
    )

    if restricao:
        print("\nRestrição geográfica:")
        print(
            "PT: "
            + ", ".join(
                restricao.get("pt", [])
            )
        )
        print(
            "EN: "
            + ", ".join(
                restricao.get("en", [])
            )
        )

    expansoes = contexto.get(
        "expansoes_aprovadas",
        [],
    )

    print("\nExpansões aprovadas:")

    if not expansoes:
        print("- Nenhuma")

    for expansao in expansoes:
        print(
            f"- {expansao.get('origem_base')}"
        )
        print(
            "  PT: "
            + ", ".join(
                expansao.get("pt", [])
            )
        )
        print(
            "  EN: "
            + ", ".join(
                expansao.get("en", [])
            )
        )


def confirmar_contexto_final() -> bool:
    while True:
        print("\n[1] Confirmar contexto")
        print("[2] Cancelar")

        escolha = input("> ").strip()

        if escolha == "1":
            return True

        if escolha == "2":
            return False

        print("\nOpção inválida.")


def main() -> None:
    print(
        "\n=== Sistema Agêntico Pesquisador ===\n"
    )

    if existe_pesquisa_ativa():
        print("Pesquisa ativa encontrada.")
        return

    print(
        "Nenhuma pesquisa ativa encontrada."
    )

    respostas = executar_intake()

    mostrar_respostas(respostas)

    try:
        # Etapa A: chamada 1 + decisão humana
        oficial = definir_texto_oficial(
            respostas
        )

        # A partir daqui, somente o contexto oficial é usado.
        mostrar_contexto_oficial(oficial)

        print(
            "\nAnalisando o contexto oficial "
            "com o modelo local..."
        )

        # Etapa B: chamada 2 sobre o contexto oficial
        sugestoes = analisar_contexto_oficial(
            oficial
        )

        resultado = validar_sugestoes(
            sugestoes,
            oficial,
        )

        mostrar_termos_rejeitados(
            resultado["termos_base_rejeitados"]
        )

        contexto = montar_contexto_confirmado(
            oficial,
            resultado,
        )

        mostrar_contexto_final(
            contexto
        )

        confirmado = confirmar_contexto_final()

        if confirmado:
            print(
                "\nContexto confirmado pelo pesquisador."
            )
            print(
                "Nada foi salvo ainda."
            )
        else:
            print(
                "\nConfirmação cancelada."
            )
            print(
                "Nada foi salvo."
            )

    except json.JSONDecodeError as erro:
        print(
            "\nO modelo respondeu, "
            "mas não retornou JSON válido."
        )
        print(f"Erro: {erro}")

    except Exception as erro:
        print(
            "\nNão foi possível processar "
            "o Intake."
        )
        print(f"Erro: {erro}")


if __name__ == "__main__":
    main()
