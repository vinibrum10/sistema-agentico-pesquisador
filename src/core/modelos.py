"""Modelos: qual LLM atende cada tarefa, custo de cada chamada e teto por execução."""

import csv
import json
import os
from datetime import datetime

from dotenv import load_dotenv
from langchain_core.callbacks import BaseCallbackHandler

from core.pesquisa_ativa import ACTIVE_RESEARCH_DIR, PROJECT_ROOT


CONFIG_FILE = PROJECT_ROOT / "config" / "modelos.json"
CUSTOS_FILE = ACTIVE_RESEARCH_DIR / "custos.csv"
COLUNAS_CUSTO = ["quando", "tarefa", "modelo", "tokens_entrada", "tokens_saida", "custo_usd"]

load_dotenv(PROJECT_ROOT / ".env")

# Quanto esta execução (este processo) já gastou com modelos pagos, em US$.
gasto_execucao = 0.0


class TetoAtingido(RuntimeError):
    """A execução chegou ao teto de gasto de config/modelos.json."""


class RegistroCusto(BaseCallbackHandler):
    """Modelos pagos: antes da chamada confere o teto; depois grava tokens e custo em custos.csv."""

    raise_error = True  # sem isto o LangChain engoliria o TetoAtingido

    def __init__(self, tarefa: str, nome: str, info: dict, teto: float):
        self.tarefa = tarefa
        self.nome = nome
        self.info = info
        self.teto = teto

    def on_chat_model_start(self, serialized, messages, **kwargs):
        if gasto_execucao >= self.teto:
            raise TetoAtingido(
                f"teto de US$ {self.teto:.2f} por execução atingido "
                f"(gasto: US$ {gasto_execucao:.4f}). O que já foi gravado foi mantido."
            )

    def on_llm_end(self, response, **kwargs):
        global gasto_execucao

        uso = response.generations[0][0].message.usage_metadata or {}
        entrada = uso.get("input_tokens", 0)
        saida = uso.get("output_tokens", 0)
        custo = (
            entrada * self.info["entrada_usd_1m"] + saida * self.info["saida_usd_1m"]
        ) / 1_000_000
        gasto_execucao += custo

        novo = not CUSTOS_FILE.exists()
        CUSTOS_FILE.parent.mkdir(parents=True, exist_ok=True)

        with open(CUSTOS_FILE, "a", encoding="utf-8-sig", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=COLUNAS_CUSTO)
            if novo:
                escritor.writeheader()
            escritor.writerow(
                {
                    "quando": datetime.now().isoformat(timespec="seconds"),
                    "tarefa": self.tarefa,
                    "modelo": self.nome,
                    "tokens_entrada": entrada,
                    "tokens_saida": saida,
                    "custo_usd": f"{custo:.6f}",
                }
            )


def criar_modelo(tarefa: str, esquema: dict | None = None, nome: str | None = None):
    """Modelo da tarefa em config/modelos.json (ou o modelo `nome`), pronto para .invoke().

    `esquema` pede a resposta em JSON: no Ollama, com o esquema imposto; nas APIs,
    em modo JSON (os campos vêm do prompt).
    """
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    nome = nome or config["tarefas"][tarefa]
    info = config["modelos"][nome]

    if info["provedor"] == "ollama":
        from langchain_ollama import ChatOllama

        extras = {"format": esquema} if esquema else {}
        return ChatOllama(model=info["modelo"], temperature=0, reasoning=False, **extras)

    from langchain_openai import ChatOpenAI

    chave = os.getenv(info["chave_env"])
    if not chave:
        raise RuntimeError(f"falta {info['chave_env']} no .env para usar {nome}")

    extras = {campo: info[campo] for campo in ("extra_body", "reasoning_effort") if campo in info}
    if esquema:
        extras["model_kwargs"] = {"response_format": {"type": "json_object"}}

    return ChatOpenAI(
        model=info["modelo"],
        base_url=info["base_url"],
        api_key=chave,
        temperature=0,
        callbacks=[RegistroCusto(tarefa, nome, info, config["teto_por_execucao_usd"])],
        **extras,
    )
