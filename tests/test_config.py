"""Testes locais da configuração inicial, sem integração externa."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from instituto_horizonte.config import Configuracao, formatar_erros_configuracao


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


if __name__ == "__main__":
    unittest.main()
