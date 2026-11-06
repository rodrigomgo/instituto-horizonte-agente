"""Integração local opcional com FastEmbed real; separada dos mocks unitários."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from instituto_horizonte.config import Configuracao
from instituto_horizonte.retrieval import consultar_normas, indexar_documentos


pytestmark = pytest.mark.fastembed_real


@pytest.mark.skipif(
    os.environ.get("RUN_FASTEMBED_TESTS") != "1",
    reason="defina RUN_FASTEMBED_TESTS=1 para usar o modelo FastEmbed real",
)
def test_indexacao_e_consulta_com_fastembed_real() -> None:
    with TemporaryDirectory() as diretorio:
        config = Configuracao.from_env({"CHROMA_DIR": str(Path(diretorio) / "chroma")})
        primeira = indexar_documentos(config)
        segunda = indexar_documentos(config)
        resposta = consultar_normas(
            "Qual é o prazo para emitir a declaração de matrícula?",
            top_k=3,
            config=config,
        )

    assert primeira.quantidade == 12
    assert segunda.quantidade == 12
    assert resposta.total == 3
    assert "ACAD-001" in [resultado.id for resultado in resposta.resultados]
