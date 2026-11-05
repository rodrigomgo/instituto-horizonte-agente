"""Executa o smoke test real da TSK-002; requer GROQ_API_KEY no ambiente."""

from __future__ import annotations

import json

from pydantic import ValidationError

from instituto_horizonte.config import (
    Configuracao,
    carregar_dotenv_projeto,
    formatar_erros_configuracao,
)
from instituto_horizonte.llm_smoke import FalhaSmoke, executar_smoke


def main() -> int:
    carregar_dotenv_projeto()
    try:
        config = Configuracao.from_env()
    except ValidationError as error:
        print(f"Configuração inválida: {formatar_erros_configuracao(error)}")
        return 2

    try:
        resultado = executar_smoke(config)
    except FalhaSmoke as error:
        print(f"Smoke test falhou [{error.categoria}]: {error}")
        return 1

    print("Smoke test Groq concluído com integração real.")
    print(json.dumps(resultado.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
