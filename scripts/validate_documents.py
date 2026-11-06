"""Valida e resume a base acadêmica oficial sem rede ou API externa."""

from __future__ import annotations

import json

from instituto_horizonte.ingest import (
    CAMINHO_BASE_OFICIAL,
    ErroIngestao,
    carregar_documentos,
    preparar_documentos,
)


def main() -> int:
    try:
        documentos = carregar_documentos()
        preparados = preparar_documentos(documentos)
    except ErroIngestao as error:
        print(f"Validação falhou: {error}")
        return 1

    resumo = {
        "arquivo": str(CAMINHO_BASE_OFICIAL),
        "quantidade": len(documentos),
        "ids": [documento.id for documento in documentos],
        "categorias": sorted({documento.categoria for documento in documentos}),
        "hashes_conteudo": {
            documento.id_estavel: documento.hash_conteudo for documento in preparados
        },
        "um_documento_por_registro": len(documentos) == len(preparados),
    }
    print("Base acadêmica válida.")
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
