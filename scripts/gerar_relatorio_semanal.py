"""CLI sem escrita em disco. Redirecionamento/publicação pertencem ao chamador."""

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core.relatorio_semanal import FUSO, gerar, semana_anterior


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dados", type=Path, required=True, help="pasta active_research explícita")
    parser.add_argument("--inicio", type=date.fromisoformat, help="segunda-feira; padrão: semana anterior")
    parser.add_argument("--sha-origem", required=True, help="git rev-parse HEAD, informado pelo chamador")
    parser.add_argument("--formato", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()
    try:
        relatorio = gerar(args.dados, args.inicio or semana_anterior(datetime.now(FUSO).date()), args.sha_origem)
    except (ValueError, OSError):
        parser.error("argumentos ou origem inválidos; confira --dados, --inicio e --sha-origem")
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(relatorio, ensure_ascii=False) if args.formato == "json" else relatorio["markdown"], end="\n" if args.formato == "json" else "")


if __name__ == "__main__":
    main()
