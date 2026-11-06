"""Testes dos entrypoints de retrieval, sem rede, Groq ou modelo real."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, call, patch

from scripts import evaluate_retrieval, index_documents


class RetrievalScriptsTests(unittest.TestCase):
    def test_indexador_carrega_dotenv_antes_da_configuracao(self) -> None:
        ordem = Mock()
        resultado = Mock()
        resultado.model_dump.return_value = {"quantidade": 12}

        with (
            patch.object(
                index_documents,
                "carregar_dotenv_projeto",
                side_effect=lambda: ordem("dotenv"),
            ),
            patch.object(
                index_documents,
                "configuracao_rag_do_ambiente",
                side_effect=lambda: ordem("config") or Mock(),
            ),
            patch.object(index_documents, "indexar_documentos", return_value=resultado),
        ):
            self.assertEqual(index_documents.main(), 0)

        self.assertEqual(ordem.call_args_list, [call("dotenv"), call("config")])

    def test_avaliador_carrega_dotenv_antes_da_configuracao(self) -> None:
        ordem = Mock()
        config = Mock(rag_top_k=3)

        with (
            patch.object(
                evaluate_retrieval,
                "carregar_dotenv_projeto",
                side_effect=lambda: ordem("dotenv"),
            ),
            patch.object(evaluate_retrieval, "carregar_perguntas", return_value={}),
            patch.object(
                evaluate_retrieval,
                "configuracao_rag_do_ambiente",
                side_effect=lambda: ordem("config") or config,
            ),
            patch.object(evaluate_retrieval, "CASOS_ESPERADOS", {}),
        ):
            self.assertEqual(evaluate_retrieval.main(), 0)

        self.assertEqual(ordem.call_args_list, [call("dotenv"), call("config")])


if __name__ == "__main__":
    unittest.main()
