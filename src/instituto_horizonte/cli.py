"""Comando mínimo da TSK-001 para validar a configuração local."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from pydantic import ValidationError

from instituto_horizonte.config import Configuracao, formatar_erros_configuracao


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="instituto-horizonte",
        description="Valida a configuração local do Instituto Horizonte.",
    )
    parser.add_argument(
        "--require-api-key",
        action="store_true",
        help="falha se GROQ_API_KEY não estiver configurada",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = criar_parser().parse_args(argv)
    try:
        config = Configuracao.from_env()
    except ValidationError as error:
        print(f"Configuração inválida: {formatar_erros_configuracao(error)}")
        return 2

    if args.require_api_key and config.groq_api_key is None:
        print("Configuração inválida: GROQ_API_KEY não está configurada.")
        return 2

    print("Configuração válida (TSK-001).")
    print(json.dumps(config.resumo_seguro(), ensure_ascii=False, indent=2))
    return 0
