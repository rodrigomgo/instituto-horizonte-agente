"""Indexa os 12 documentos oficiais no Chroma persistente."""

from __future__ import annotations

import json

from instituto_horizonte.retrieval import (
    ErroRecuperacao,
    configuracao_rag_do_ambiente,
    indexar_documentos,
)


def main() -> int:
    try:
        resultado = indexar_documentos(configuracao_rag_do_ambiente())
    except ErroRecuperacao as error:
        print(f"Indexação falhou: {error}")
        return 1
    print("Indexação concluída.")
    print(json.dumps(resultado.model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
