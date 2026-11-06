"""Inicializa o schema SQLite e a fixture fictícia SOL-1001."""

from __future__ import annotations

import json
from dataclasses import asdict

from instituto_horizonte.config import Configuracao, carregar_dotenv_projeto
from instituto_horizonte.database import ErroBanco, inicializar_banco


def main() -> int:
    carregar_dotenv_projeto()
    config = Configuracao.from_env()
    try:
        resumo = inicializar_banco(config.sqlite_path)
    except ErroBanco as error:
        print(f"Inicialização do banco falhou: {error}")
        return 1
    print("Banco SQLite inicializado.")
    print(json.dumps(asdict(resumo), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
