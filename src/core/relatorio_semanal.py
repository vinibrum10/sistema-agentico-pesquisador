"""Relatório agregado, sem imports de agentes, configuração, modelos ou dotenv."""

import csv
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

FUSO = timezone(timedelta(hours=-3), "America/Sao_Paulo")
PENDENCIAS = [
    "SAP-1: revisão humana de seção real e rastreabilidade frase→trecho.",
    "SAP-2: juiz de suporte semântico das afirmações.",
    "SAP-3: orquestrador LangGraph.",
    "SAP-4: experimento e correção de falha reais.",
    "SAP-5: aprovação e validação operacional n8n/Drive; Marcos pelo Vinicius.",
]


def semana_anterior(hoje: date) -> date:
    return hoje - timedelta(days=hoje.weekday() + 7)


def gerar(dados: Path, inicio: date, sha: str) -> dict:
    """Lê somente CSVs conhecidos e metadados. Não cria nem altera arquivos.

    O offset -03 é válido para o contrato em datas >= 2020, sem depender de tzdata.
    Não reconstrói eventos apagados nem usa mtime como data de atividade científica.
    """
    if inicio.weekday() != 0 or inicio.year < 2020:
        raise ValueError("inicio deve ser uma segunda-feira a partir de 2020")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        raise ValueError("sha-origem deve conter os 40 caracteres hexadecimais do commit")
    dados = dados.resolve()
    fim = inicio + timedelta(days=7)
    avisos = set()
    if not dados.is_dir():
        avisos.add("Pasta de dados ausente; cobertura indisponível.")

    def seguro(p: Path) -> bool:
        # Impede que links/junctions na origem conduzam a outros diretórios.
        if not p.resolve().is_relative_to(dados) or p.is_symlink():
            avisos.add("Link fora da origem ou simbólico ignorado.")
            return False
        return True

    def linhas(p: Path, colunas: set, delimitador=",") -> list[dict]:
        rotulo = p.name if p.parent == dados else "experimentos.csv"
        if not seguro(p):
            return []
        try:
            with p.open(encoding="utf-8-sig", newline="") as f:
                leitor = csv.DictReader(f, delimiter=delimitador, strict=True)
                if not colunas.issubset(leitor.fieldnames or []):
                    avisos.add(f"{rotulo}: cabeçalho ausente/incompatível.")
                    return []
                resultado = []
                for linha in leitor:
                    if None in linha or any(v is None for v in linha.values()):
                        avisos.add(f"{rotulo}: linha incompleta/incompatível ignorada.")
                    else:
                        resultado.append(linha)
                return resultado
        except FileNotFoundError:
            avisos.add(f"{rotulo}: ausente; não equivale a zero atividade.")
        except (OSError, UnicodeError, csv.Error):
            avisos.add(f"{rotulo}: leitura inválida/indisponível.")
        return []

    def no_periodo(valor: str, fonte: str) -> bool:
        try:
            instante = datetime.fromisoformat(valor)
            if instante.tzinfo is None:
                instante = instante.replace(tzinfo=FUSO)
            return inicio <= instante.astimezone(FUSO).date() < fim
        except (ValueError, TypeError):
            avisos.add(f"{fonte}: data ausente/inválida; registro excluído do período.")
            return False

    def inteiro(valor: str, fonte: str) -> int:
        try:
            n = int(valor)
            if n < 0:
                raise ValueError
            return n
        except (ValueError, TypeError):
            avisos.add(f"{fonte}: contagem inválida ignorada.")
            return 0

    resultados = linhas(dados / "results.csv", {"openalex_id", "data_run"})
    triagem = linhas(dados / "screening.csv", {"openalex_id", "veredito"})
    loops = linhas(dados / "loop_log.csv", {"data_hora", "total", "erro"})
    custos = linhas(dados / "custos.csv", {"quando", "custo_usd"})
    loops_semana = [l for l in loops if no_periodo(l["data_hora"], "loop_log.csv")]
    custo = Decimal(0)
    chamadas = 0
    for linha in custos:
        if no_periodo(linha["quando"], "custos.csv"):
            try:
                valor = Decimal(linha["custo_usd"])
                if not valor.is_finite() or valor < 0:
                    raise InvalidOperation
                custo += valor
                chamadas += 1
            except InvalidOperation:
                avisos.add("custos.csv: custo inválido ignorado; soma parcial.")

    def arquivos(padrao: str) -> list[Path]:
        return [p for p in sorted(dados.glob(padrao)) if seguro(p) and p.is_file()]

    escrita = arquivos("escrita/*/texto_*.md")
    revisoes = arquivos("escrita/*/revisao_*.csv")
    execucoes = arquivos("experimentos/*/execucao_*/experimentos.csv")
    for pasta in ("escrita", "experimentos"):
        if not (dados / pasta).is_dir():
            avisos.add(f"{pasta}/: ausente; inventário indisponível.")
    tentativas, erros = 0, 0
    for p in execucoes:
        try:
            dt = datetime.strptime(p.parent.name, "execucao_%Y-%m-%d_%H-%M-%S")
        except ValueError:
            avisos.add("Experimento com data de início inválida; excluído do período.")
            continue
        if no_periodo(dt.isoformat(), "experimentos.csv"):
            registros = linhas(p, {"rodada", "tentativa", "status"}, ";")
            tentativas += len(registros)
            erros += sum(l["status"] == "erro" for l in registros)

    # Somente rótulos conhecidos saem no relatório: não retransmitir texto arbitrário.
    vereditos = Counter(l["veredito"] for l in triagem)
    conhecidos = ("relevante", "talvez", "lixo", "descartado", "erro")
    if set(vereditos) - set(conhecidos):
        avisos.add("screening.csv: vereditos desconhecidos omitidos da distribuição.")
    metricas = {
        "papers_inventario": len({l["openalex_id"] for l in resultados}),
        "papers_data_run_na_semana": len({l["openalex_id"] for l in resultados if no_periodo(l["data_run"], "results.csv")}),
        "rodadas_registradas_na_semana": len(loops_semana),
        "avaliacoes_em_rodadas": sum(inteiro(l["total"], "loop_log.csv") for l in loops_semana),
        "erros_triagem_em_rodadas": sum(inteiro(l["erro"], "loop_log.csv") for l in loops_semana),
        "chamadas_pagas_validas": chamadas,
        "custo_usd_registrado": format(custo, ".6f"),
        "textos_inventario": len(escrita),
        "revisoes_inventario": len(revisoes),
        "execucoes_inventario": len(execucoes),
        "tentativas_de_execucoes_iniciadas_na_semana": tentativas,
        "erros_de_execucoes_iniciadas_na_semana": erros,
    }
    atividade = any(metricas[k] for k in (
        "papers_data_run_na_semana", "rodadas_registradas_na_semana", "chamadas_pagas_validas",
        "tentativas_de_execucoes_iniciadas_na_semana",
    ))
    nome = f"sap-semanal_{inicio}_{fim}.md"
    md = ["# SAP — relatório semanal", "", f"Período: {inicio} (inclusive) → {fim} (exclusive).",
          "Fuso: America/Sao_Paulo (UTC−03, contrato desde 2020).", f"SHA de origem informado: `{sha.lower()}`.", "",
          "Atividade datada encontrada." if atividade else "Sem atividade datada observada no período; conferir cobertura abaixo.",
          "", "| Medida | Valor |", "|---|---:|"]
    md += [f"| {k} | {v} |" for k, v in metricas.items()]
    md += ["", "Triagem atual (inventário, sem data de evento):"]
    md += [f"- {v}: {vereditos[v]}" for v in conhecidos]
    md += ["", "## Cobertura e limites", "",
           "- Inventário reflete o estado atual, inclusive em reexecuções de semanas antigas.",
           "- data_run é a data mantida no upsert de results.csv; não mede descobertas únicas históricas.",
           "- Avaliações/erros em rodadas podem repetir papers; custos são só os registrados, não faturamento.",
           "- Escrita sem log temporal: somente inventário; mtime não é usado como atividade.",
           "- Tentativas de experimentos são agrupadas pela data de início da execução, não de cada rodada.",
           "- Ausência de erro registrado não comprova ausência de falha; não há log global de erros."]
    md += [f"- {a}" for a in sorted(avisos)]
    md += ["", "## Pendências conhecidas (lista documental, não consulta ao Jira)", ""]
    md += [f"- {p}" for p in PENDENCIAS]
    return {"schema_version": 1, "nome": nome, "inicio": str(inicio), "fim_exclusivo": str(fim),
            "fuso": "America/Sao_Paulo", "sha_origem": sha.lower(), "metricas": metricas,
            "avisos": sorted(avisos), "markdown": "\n".join(md) + "\n"}
