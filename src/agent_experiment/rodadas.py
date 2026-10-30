"""Experimentos: laço de rodadas — o modelo propõe uma mudança, o código roda, mede e decide."""

import csv
import difflib
import json
import shutil
from functools import partial
from pathlib import Path, PurePosixPath

from agent_experiment.executor import executar
from core.modelos import criar_modelo


TAREFA = "codigo_experimento"
CONTEXTO_OLLAMA = 16384  # a janela padrão do Ollama cortaria o começo do prompt (código + histórico)
MAX_CORRECOES = 2  # tentativas de corrigir um erro dentro da mesma rodada
SEM_MELHORA_PARA_PARAR = 2
COLUNAS = ["rodada", "tentativa", "mudanca", "metrica", "status", "tempo_s"]

ESQUEMA = {
    "type": "object",
    "properties": {
        "motivo": {"type": "string"},
        "arquivos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"caminho": {"type": "string"}, "conteudo": {"type": "string"}},
                "required": ["caminho", "conteudo"],
            },
        },
    },
    "required": ["motivo", "arquivos"],
}


def melhor_que(nova: float, atual: float, direcao: str) -> bool:
    return nova > atual if direcao == "maior" else nova < atual


def ler_codigo(pasta: Path) -> dict[str, str]:
    """Arquivos .py da pasta: caminho relativo -> conteúdo."""
    return {
        arquivo.relative_to(pasta).as_posix(): arquivo.read_text(encoding="utf-8")
        for arquivo in sorted(pasta.rglob("*.py"))
        if "__pycache__" not in arquivo.parts
    }


def validar_proposta(dados, codigo: dict[str, str]) -> tuple[str, dict[str, str]] | None:
    """Motivo e arquivos .py (caminho relativo -> conteúdo completo) que mudam algo; senão None."""
    if not isinstance(dados, dict) or not isinstance(dados.get("arquivos"), list):
        return None

    motivo = str(dados.get("motivo", "")).strip()
    arquivos = {}
    for item in dados["arquivos"]:
        if not isinstance(item, dict):
            return None
        caminho, conteudo = str(item.get("caminho", "")).strip(), item.get("conteudo")
        parte = PurePosixPath(caminho)
        if (
            not caminho or "\\" in caminho or ":" in caminho or parte.is_absolute() or ".." in parte.parts
            or parte.suffix != ".py" or not isinstance(conteudo, str) or not conteudo.strip()
        ):
            return None
        arquivos[parte.as_posix()] = conteudo

    if not motivo or not arquivos or all(codigo.get(c) == t for c, t in arquivos.items()):
        return None
    return motivo, arquivos


def montar_prompt(config: dict, historico: list[dict], codigo: dict[str, str], erro: str | None) -> str:
    historia = "\n".join(
        f"- rodada {l['rodada']}: {l['mudanca']} -> {config['metrica']} = "
        f"{'sem valor' if l['metrica'] is None else l['metrica']} ({l['status']})"
        for l in historico
    ) or "(nenhum)"
    arquivos = "\n\n".join(f"=== {caminho} ===\n{texto}" for caminho, texto in codigo.items())
    falha = f"\nA versão anterior desta rodada falhou:\n{erro}\nCorrija o erro.\n" if erro else ""

    return f"""Você melhora, uma mudança por vez, o código de um experimento para otimizar uma métrica.

Objetivo do experimento: {config["objetivo"]}
Métrica: {config["metrica"]} ({config["direcao"]} é melhor)
Comando de execução: {config["comando"]}
O código roda num container sem rede, com os dados somente leitura em /dados, e imprime uma linha
METRICA {config["metrica"]}=<número>. Mantenha essa linha.

Histórico (rodada: mudança -> métrica):
{historia}

Arquivos atuais:
{arquivos}
{falha}
Regras:
- proponha UMA mudança que possa melhorar a métrica e que ainda não foi tentada;
- devolva o conteúdo COMPLETO de cada arquivo .py que você alterar ou criar; não devolva arquivos sem mudança;
- não use rede; leia dados só de /dados; grave arquivos só no diretório atual;
- "motivo" é uma frase dizendo o que mudou e por quê.

Retorne SOMENTE JSON no formato:
{{"motivo": "...", "arquivos": [{{"caminho": "...", "conteudo": "..."}}]}}
"""


def propor(config: dict, historico: list[dict], codigo: dict[str, str], erro: str | None = None, modelo: str | None = None):
    """Pede uma mudança ao modelo; tenta duas vezes e devolve None se nenhuma resposta servir."""
    prompt = montar_prompt(config, historico, codigo, erro)
    llm = criar_modelo(TAREFA, esquema=ESQUEMA, nome=modelo, contexto=CONTEXTO_OLLAMA)

    for _ in (1, 2):
        try:
            proposta = validar_proposta(json.loads(llm.invoke(prompt).content), codigo)
        except json.JSONDecodeError:
            proposta = None
        if proposta:
            return proposta
    return None


def aplicar(pasta: Path, arquivos: dict[str, str]) -> None:
    for caminho, conteudo in arquivos.items():
        destino = pasta / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo, encoding="utf-8")


def _registrar(saida: Path, historico: list[dict], linha: dict) -> None:
    historico.append(linha)
    arquivo = saida / "experimentos.csv"
    novo = not arquivo.exists()
    with open(arquivo, "a", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
        if novo:
            escritor.writeheader()
        escritor.writerow({**linha, "metrica": "" if linha["metrica"] is None else linha["metrica"]})


def _guardar_saida(pasta: Path, res: dict) -> None:
    (pasta / "saida.txt").write_text(
        f"# código de saída: {res['codigo']} | estourou o tempo: {res['estourou_tempo']}\n"
        f"# stdout\n{res['saida']}\n# stderr\n{res['erro']}\n",
        encoding="utf-8",
    )


def _funcionou(res: dict) -> bool:
    return res["codigo"] == 0 and not res["estourou_tempo"] and res["metrica"] is not None


def _motivo_falha(res: dict) -> str:
    if res["estourou_tempo"]:
        return "o tempo máximo da rodada estourou"
    if res["codigo"] != 0:
        return f"código de saída {res['codigo']}:\n{res['erro'][-1500:]}"
    return "a saída não tem a linha METRICA"


def diferenca(base: Path, pasta: Path) -> str:
    antes, depois = ler_codigo(base), ler_codigo(pasta)
    partes = []
    for caminho in sorted(set(antes) | set(depois)):
        if antes.get(caminho) != depois.get(caminho):
            partes += difflib.unified_diff(
                (antes.get(caminho) or "").splitlines(), (depois.get(caminho) or "").splitlines(),
                f"base/{caminho}", f"{pasta.name}/{caminho}", lineterm="",
            )
    return "\n".join(partes)


def gerar_relatorio(config: dict, base: Path, saida: Path, historico: list[dict], melhor: dict | None, parada: str) -> None:
    linhas = [
        f"# Experimento: {config['nome']}", "",
        f"**Objetivo:** {config['objetivo']}", "",
        f"**Métrica:** {config['metrica']} ({config['direcao']} é melhor) · **Comando:** `{config['comando']}`", "",
        f"**Parou por:** {parada}", "",
        "| rodada | tentativa | mudança | métrica | resultado | tempo (s) |", "|---|---|---|---|---|---|",
    ]
    for l in historico:
        linhas.append(
            f"| {l['rodada']} | {l['tentativa']} | {l['mudanca'].replace('|', '/')} | "
            f"{'' if l['metrica'] is None else l['metrica']} | {l['status']} | {l['tempo_s']} |"
        )
    linhas.append("")

    if melhor is None:
        linhas.append("O código base não gerou a métrica; veja `rodada_00/saida.txt`.")
    elif melhor["rodada"] == 0:
        linhas.append("Nenhuma mudança melhorou a métrica: o código base continua sendo o melhor.")
    else:
        linhas += [
            f"**Melhor:** rodada {melhor['rodada']} ({config['metrica']} = {melhor['metrica']}; código base = {historico[0]['metrica']}). "
            f"Para usar, copie os arquivos de `{melhor['pasta'].name}/` para o seu projeto.",
            "", "## Diferença em relação ao código base", "",
            "```diff", diferenca(base, melhor["pasta"]), "```",
        ]
    (saida / "relatorio.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def rodar_rodadas(config, base, dados, saida, imagem, modelo=None, propor_fn=None, executar_fn=executar) -> dict:
    """Rodada 0 (código base) e até `max_rodadas` rodadas de mudança. O relatório sai mesmo se algo interromper."""
    propor_fn = propor_fn or partial(propor, modelo=modelo)
    saida.mkdir(parents=True)
    historico, melhor, parada = [], None, "limite de rodadas"

    def executar_rodada(pasta):
        res = executar_fn(imagem, pasta, dados, config["comando"], config["tempo_max_s"], config["metrica"])
        _guardar_saida(pasta, res)
        return res

    try:
        pasta0 = saida / "rodada_00"
        shutil.copytree(base, pasta0)
        res = executar_rodada(pasta0)
        _registrar(saida, historico, {"rodada": 0, "tentativa": 0, "mudanca": "código base", "metrica": res["metrica"], "status": "base", "tempo_s": res["tempo_s"]})
        if res["metrica"] is None:
            raise RuntimeError("o código base não gerou a métrica: confira o comando e a linha METRICA (rodada_00/saida.txt)")
        melhor = {"rodada": 0, "metrica": res["metrica"], "pasta": pasta0}

        sem_melhora = 0
        for n in range(1, config["max_rodadas"] + 1):
            if sem_melhora >= SEM_MELHORA_PARA_PARAR:
                parada = f"{SEM_MELHORA_PARA_PARAR} rodadas seguidas sem melhora"
                break

            pasta_n = saida / f"rodada_{n:02d}"
            shutil.copytree(melhor["pasta"], pasta_n)
            codigo, erro, melhorou = ler_codigo(pasta_n), None, False

            for tentativa in range(MAX_CORRECOES + 1):
                proposta = propor_fn(config, historico, codigo, erro)
                if proposta is None:
                    _registrar(saida, historico, {"rodada": n, "tentativa": tentativa, "mudanca": "(sem proposta válida)", "metrica": None, "status": "proposta inválida", "tempo_s": 0})
                    break

                motivo, arquivos = proposta
                aplicar(pasta_n, arquivos)
                res = executar_rodada(pasta_n)
                linha = {"rodada": n, "tentativa": tentativa, "mudanca": motivo, "metrica": res["metrica"], "tempo_s": res["tempo_s"]}
                if _funcionou(res):
                    melhorou = melhor_que(res["metrica"], melhor["metrica"], config["direcao"])
                    _registrar(saida, historico, {**linha, "status": "melhorou" if melhorou else "não melhorou"})
                    break
                _registrar(saida, historico, {**linha, "status": "erro"})
                erro, codigo = _motivo_falha(res), ler_codigo(pasta_n)

            if melhorou:
                melhor, sem_melhora = {"rodada": n, "metrica": res["metrica"], "pasta": pasta_n}, 0
            else:
                sem_melhora += 1
    except Exception as erro_final:
        parada = f"interrompido: {erro_final}"
        raise
    finally:
        gerar_relatorio(config, base, saida, historico, melhor, parada)

    return {"baseline": historico[0]["metrica"], "melhor": melhor, "parada": parada}
