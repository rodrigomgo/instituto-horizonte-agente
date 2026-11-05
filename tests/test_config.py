"""Testes locais da configuração inicial, sem integração externa."""

from __future__ import annotations

import os
from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from instituto_horizonte.config import (
    Configuracao,
    caminho_dotenv,
    carregar_dotenv_projeto,
    formatar_erros_configuracao,
)


class ConfiguracaoTests(unittest.TestCase):
    def test_valores_padrao_sao_validos(self) -> None:
        config = Configuracao.from_env({})

        self.assertEqual(config.rag_top_k, 3)
        self.assertEqual(config.max_agent_rounds, 6)
        self.assertIsNone(config.groq_api_key)

    def test_variaveis_do_ambiente_sao_convertidas(self) -> None:
        config = Configuracao.from_env(
            {
                "GROQ_API_KEY": "segredo-de-teste",
                "RAG_TOP_K": "5",
                "MAX_AGENT_ROUNDS": "8",
            }
        )

        self.assertEqual(config.rag_top_k, 5)
        self.assertEqual(config.max_agent_rounds, 8)
        self.assertTrue(config.resumo_seguro()["groq_api_key_configurada"])
        self.assertNotIn("segredo-de-teste", str(config.resumo_seguro()))

    def test_top_k_fora_do_intervalo_e_rejeitado(self) -> None:
        with self.assertRaises(ValidationError) as context:
            Configuracao.from_env({"RAG_TOP_K": "0"})

        mensagem = formatar_erros_configuracao(context.exception)
        self.assertIn("rag_top_k", mensagem)
        self.assertNotIn("input", mensagem)

    def test_modelo_em_branco_e_rejeitado(self) -> None:
        with self.assertRaises(ValidationError):
            Configuracao.from_env({"GROQ_MODEL": "   "})

    def test_resumo_e_repr_nao_exibem_chave(self) -> None:
        chave = "chave-local-que-nao-pode-aparecer"
        config = Configuracao.from_env({"GROQ_API_KEY": chave})

        self.assertNotIn(chave, str(config.resumo_seguro()))
        self.assertNotIn(chave, repr(config))


class DotenvTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_carrega_dotenv_somente_quando_solicitado(self) -> None:
        with TemporaryDirectory() as diretorio:
            raiz = Path(diretorio)
            caminho_dotenv(raiz).write_text(
                "GROQ_API_KEY=chave-do-arquivo\nRAG_TOP_K=4\n",
                encoding="utf-8",
            )

            self.assertNotIn("GROQ_API_KEY", os.environ)
            self.assertTrue(carregar_dotenv_projeto(raiz))
            config = Configuracao.from_env()

        self.assertTrue(config.resumo_seguro()["groq_api_key_configurada"])
        self.assertEqual(config.rag_top_k, 4)

    @patch.dict(os.environ, {"GROQ_API_KEY": "chave-do-ambiente"}, clear=True)
    def test_ambiente_tem_prioridade_sobre_dotenv(self) -> None:
        with TemporaryDirectory() as diretorio:
            raiz = Path(diretorio)
            caminho_dotenv(raiz).write_text(
                "GROQ_API_KEY=chave-do-arquivo\n",
                encoding="utf-8",
            )
            carregar_dotenv_projeto(raiz)
            config = Configuracao.from_env()

        self.assertEqual(config.groq_api_key.get_secret_value(), "chave-do-ambiente")

    @patch.dict(os.environ, {}, clear=True)
    def test_ausencia_de_dotenv_nao_falha(self) -> None:
        with TemporaryDirectory() as diretorio:
            carregado = carregar_dotenv_projeto(Path(diretorio))
            config = Configuracao.from_env()

        self.assertFalse(carregado)
        self.assertIsNone(config.groq_api_key)

    @patch.dict(os.environ, {}, clear=True)
    def test_carregamento_independe_do_diretorio_atual(self) -> None:
        with TemporaryDirectory() as raiz_temp, TemporaryDirectory() as cwd_temp:
            raiz = Path(raiz_temp)
            caminho_dotenv(raiz).write_text("RAG_TOP_K=5\n", encoding="utf-8")

            with chdir(cwd_temp):
                carregado = carregar_dotenv_projeto(raiz)
                config = Configuracao.from_env()

        self.assertTrue(carregado)
        self.assertEqual(config.rag_top_k, 5)

    @patch.dict(
        os.environ,
        {"GROQ_API_KEY": "chave-que-nao-deve-vazar", "GROQ_MODEL": "   "},
        clear=True,
    )
    def test_erro_de_configuracao_nao_exibe_chave(self) -> None:
        with self.assertRaises(ValidationError) as context:
            Configuracao.from_env()

        mensagem = formatar_erros_configuracao(context.exception)
        self.assertNotIn("chave-que-nao-deve-vazar", mensagem)


if __name__ == "__main__":
    unittest.main()
