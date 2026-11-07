"""Consulta um protocolo acadêmico existente pelo terminal."""

from __future__ import annotations

import argparse
import json

from pydantic import ValidationError

from instituto_horizonte.config import Configuracao, carregar_dotenv_projeto
from instituto_horizonte.protocols import ErroConsultaProtocolo, consultar_protocolo_servico


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Consulta protocolo acadêmico existente.")
    parser.add_argument("numero", help="Número no formato SOL-nnnn")
    return parser


def main(argv: list[str] | None = None) -> int:
    argumentos = criar_parser().parse_args(argv)
    carregar_dotenv_projeto()
    config = Configuracao.from_env()
    try:
        resposta = consultar_protocolo_servico(argumentos.numero, config=config)
    except ValidationError:
        print("Consulta falhou: protocolo deve seguir o formato SOL-nnnn.")
        return 2
    except ErroConsultaProtocolo as error:
        print(f"Consulta falhou: {error}")
        return 1
    print(json.dumps(resposta.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
