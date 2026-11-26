"""Cenários locais com dados sintéticos; executáveis também pelo unittest."""

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

from core.relatorio_semanal import gerar, semana_anterior

RAIZ = Path(__file__).resolve().parents[1]
SHA = "a" * 40
INICIO = date(2026, 11, 16)


class RelatorioSemanalTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dados = Path(self.temp.name)

    def csv(self, nome, campos, linhas, delimitador=","):
        p = self.dados / nome
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, campos, delimiter=delimitador)
            w.writeheader()
            w.writerows(linhas)
        return p

    def gerar(self):
        return gerar(self.dados, INICIO, SHA)

    def test_semana_anterior_e_argumentos(self):
        self.assertEqual(semana_anterior(date(2026, 11, 26)), INICIO)
        self.assertEqual(semana_anterior(date(2026, 11, 23)), INICIO)
        for inicio, sha in [(date(2026, 11, 17), SHA), (INICIO, "HEAD"), (date(2019, 1, 7), SHA)]:
            with self.assertRaises(ValueError):
                gerar(self.dados, inicio, sha)

    def test_pasta_ausente_nao_e_criada(self):
        p = self.dados / "ausente"
        r = gerar(p, INICIO, SHA)
        self.assertFalse(p.exists())
        self.assertIn("Pasta de dados ausente", r["markdown"])
        self.assertIn("Sem atividade datada", r["markdown"])
        self.assertEqual(len(r["avisos"]), 7)

    def test_semana_vazia_com_fontes_presentes(self):
        (self.dados / "escrita").mkdir()
        (self.dados / "experimentos").mkdir()
        self.csv("results.csv", ["openalex_id", "data_run"], [])
        self.csv("screening.csv", ["openalex_id", "veredito"], [])
        self.csv("loop_log.csv", ["data_hora", "total", "erro"], [])
        self.csv("custos.csv", ["quando", "custo_usd"], [])
        r = self.gerar()
        self.assertEqual(r["avisos"], [])
        self.assertIn("Sem atividade datada", r["markdown"])

    def test_limites_fuso_bom_decimais_e_repeticao(self):
        self.csv("results.csv", ["openalex_id", "data_run"], [
            {"openalex_id": "W1", "data_run": "2026-11-16"},
            {"openalex_id": "W1", "data_run": "2026-11-16"},
            {"openalex_id": "W2", "data_run": "2026-11-23"},
        ])
        self.csv("loop_log.csv", ["data_hora", "total", "erro"], [
            {"data_hora": "2026-11-16T03:00:00Z", "total": "4", "erro": "1"},
            {"data_hora": "2026-11-23T02:59:59Z", "total": "5", "erro": "0"},
            {"data_hora": "2026-11-23T03:00:00Z", "total": "100", "erro": "100"},
            {"data_hora": "2026-11-16T02:59:59Z", "total": "100", "erro": "100"},
        ])
        self.csv("custos.csv", ["quando", "custo_usd"], [
            {"quando": "2026-11-16T00:00:00", "custo_usd": "0.001234"},
            {"quando": "2026-11-22T23:59:59-03:00", "custo_usd": "0.002345"},
        ])
        r = self.gerar()["metricas"]
        self.assertEqual(r["papers_data_run_na_semana"], 1)
        self.assertEqual(r["papers_inventario"], 2)
        self.assertEqual(r["rodadas_registradas_na_semana"], 2)
        self.assertEqual(r["avaliacoes_em_rodadas"], 9)
        self.assertEqual(r["erros_triagem_em_rodadas"], 1)
        self.assertEqual(r["custo_usd_registrado"], "0.003579")

    def test_dados_invalidos_nao_vazam_e_sao_observaveis(self):
        self.csv("results.csv", ["openalex_id", "data_run"], [{"openalex_id": "W", "data_run": "CONTEUDO_PRIVADO"}])
        self.csv("screening.csv", ["openalex_id", "veredito"], [{"openalex_id": "W", "veredito": "CONTEUDO_PRIVADO"}])
        self.csv("loop_log.csv", ["data_hora", "total", "erro"], [{"data_hora": "2026-11-17", "total": "-2", "erro": "abc"}])
        self.csv("custos.csv", ["quando", "custo_usd"], [{"quando": "2026-11-17", "custo_usd": v} for v in ["NaN", "Infinity", "-1", "abc"]])
        r = self.gerar()
        self.assertNotIn("CONTEUDO_PRIVADO", json.dumps(r))
        self.assertEqual(r["metricas"]["custo_usd_registrado"], "0.000000")
        self.assertTrue(any("soma parcial" in a for a in r["avisos"]))
        self.assertTrue(any("data ausente/inválida" in a for a in r["avisos"]))

    def test_cabecalho_linha_e_encoding_invalidos(self):
        (self.dados / "results.csv").write_bytes(b"\xff\xff")
        (self.dados / "screening.csv").write_text("errado\n1\n", encoding="utf-8")
        (self.dados / "loop_log.csv").write_text("data_hora,total,erro\n2026-11-17,1\n", encoding="utf-8")
        r = self.gerar()
        self.assertTrue(any("leitura inválida" in a for a in r["avisos"]))
        self.assertTrue(any("cabeçalho" in a for a in r["avisos"]))
        self.assertTrue(any("linha incompleta" in a for a in r["avisos"]))

    def test_escrita_inventario_e_experimento_por_inicio(self):
        escrita = self.dados / "escrita" / "secao"
        escrita.mkdir(parents=True)
        (escrita / "texto_modelo.md").write_text("NAO_LER_CONTEUDO", encoding="utf-8")
        (escrita / "revisao_modelo.csv").write_text("NAO_LER_CONTEUDO", encoding="utf-8")
        for dt in ["2026-11-17_12-00-00", "2026-11-23_00-00-00"]:
            self.csv(f"experimentos/teste/execucao_{dt}/experimentos.csv", ["rodada", "tentativa", "status"], [
                {"rodada": "0", "tentativa": "0", "status": "base"},
                {"rodada": "1", "tentativa": "0", "status": "erro"},
            ], ";")
        r = self.gerar()
        self.assertEqual(r["metricas"]["textos_inventario"], 1)
        self.assertEqual(r["metricas"]["revisoes_inventario"], 1)
        self.assertEqual(r["metricas"]["execucoes_inventario"], 2)
        self.assertEqual(r["metricas"]["tentativas_de_execucoes_iniciadas_na_semana"], 2)
        self.assertEqual(r["metricas"]["erros_de_execucoes_iniciadas_na_semana"], 1)
        self.assertNotIn("NAO_LER_CONTEUDO", r["markdown"])

    def test_reexecucao_identica_sem_modificar_fontes(self):
        self.csv("custos.csv", ["quando", "custo_usd"], [{"quando": "2026-11-17", "custo_usd": "1"}])
        def snapshot():
            return {p.name: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns) for p in self.dados.iterdir()}
        antes = snapshot()
        a, b = self.gerar(), self.gerar()
        self.assertEqual(a, b)
        self.assertEqual(antes, snapshot())
        self.assertEqual(a["nome"], "sap-semanal_2026-11-16_2026-11-23.md")

    def test_cli_json_sem_dependencias(self):
        res = subprocess.run([sys.executable, "-B", str(RAIZ / "scripts/gerar_relatorio_semanal.py"),
                              "--dados", str(self.dados), "--inicio", str(INICIO), "--sha-origem", SHA,
                              "--formato", "json"], input="", capture_output=True, check=True, encoding="utf-8")
        self.assertEqual(json.loads(res.stdout), self.gerar())
        self.assertEqual(list(self.dados.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
