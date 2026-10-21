"""Passo 1 do teste PaperQA2: confere a chave do DeepSeek com uma chamada mínima.

Usa a camada de modelos do projeto (custo registrado em custos.csv). Uso:

    python scripts/teste_paperqa/01_testar_chave.py
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import core.modelos as modelos

modelo = modelos.criar_modelo("teste_chave", nome="deepseek-flash")
resposta = modelo.invoke("Responda apenas com a palavra: ok")

uso = resposta.usage_metadata or {}
raciocinio = resposta.additional_kwargs.get("reasoning_content")

print("modelo servido:", resposta.response_metadata.get("model_name"))
print("resposta:", resposta.content)
print("tokens entrada/saída:", uso.get("input_tokens"), "/", uso.get("output_tokens"))
print("raciocínio ligado:", bool(raciocinio))
print(f"custo desta execução: US$ {modelos.gasto_execucao:.6f}")
print("última linha do custos.csv:", modelos.CUSTOS_FILE.read_text(encoding="utf-8-sig").splitlines()[-1])
