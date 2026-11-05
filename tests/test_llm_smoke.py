"""Testes sem rede para os caminhos de sucesso e falha da integração Groq."""

from __future__ import annotations

import unittest

import httpx
from groq import APITimeoutError, AuthenticationError, RateLimitError
from langchain_core.messages import AIMessage

from instituto_horizonte.config import Configuracao
from instituto_horizonte.llm_smoke import FalhaSmoke, executar_smoke


class RunnableFalso:
    def __init__(self, respostas: list[object]) -> None:
        self.respostas = respostas

    def invoke(self, entrada: object) -> object:
        del entrada
        return self.respostas.pop(0)


class ModeloFalsoSucesso:
    def __init__(self, saida_estruturada: object | None = None) -> None:
        self.forcado = RunnableFalso(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "somar_inteiros",
                            "args": {"parcela_a": 19, "parcela_b": 23},
                            "id": "call_teste",
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        )
        self.auto = RunnableFalso([AIMessage(content="A soma calculada pela Tool é 42.")])
        self.saida_estruturada = saida_estruturada or {
            "integracao": "groq_langchain_pydantic",
            "modelo_respondeu": True,
            "resumo": "Resposta estruturada validada.",
        }

    def bind_tools(self, tools: list[object], **kwargs: object) -> RunnableFalso:
        del tools
        return self.forcado if kwargs["tool_choice"] == "somar_inteiros" else self.auto

    def with_structured_output(self, schema: object, **kwargs: object) -> RunnableFalso:
        del schema, kwargs
        return RunnableFalso([self.saida_estruturada])


def config_com_chave(chave: str = "chave-falsa-que-nao-deve-vazar") -> Configuracao:
    return Configuracao.from_env({"GROQ_API_KEY": chave})


class SmokeTestTests(unittest.TestCase):
    def test_fluxo_mock_executa_tool_local_e_valida_schema(self) -> None:
        resultado = executar_smoke(config_com_chave(), lambda config: ModeloFalsoSucesso())

        self.assertTrue(resultado.tool_call_detectado)
        self.assertEqual(resultado.tool_resultado_local, 42)
        self.assertTrue(resultado.structured_output.modelo_respondeu)

    def test_ausencia_de_chave_falha_antes_da_fabrica(self) -> None:
        fabrica_chamada = False

        def fabrica(config: Configuracao) -> ModeloFalsoSucesso:
            nonlocal fabrica_chamada
            fabrica_chamada = True
            return ModeloFalsoSucesso()

        with self.assertRaises(FalhaSmoke) as context:
            executar_smoke(Configuracao.from_env({}), fabrica)

        self.assertEqual(context.exception.categoria, "configuracao")
        self.assertFalse(fabrica_chamada)

    def test_autenticacao_invalida_e_sanitizada(self) -> None:
        chave = "chave-falsa-que-nao-deve-vazar"
        request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        response = httpx.Response(401, request=request)

        def fabrica(config: Configuracao) -> ModeloFalsoSucesso:
            del config
            raise AuthenticationError(chave, response=response, body=None)

        with self.assertRaises(FalhaSmoke) as context:
            executar_smoke(config_com_chave(chave), fabrica)

        self.assertEqual(context.exception.categoria, "autenticacao")
        self.assertNotIn(chave, str(context.exception))

    def test_timeout_e_sanitizado(self) -> None:
        request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")

        def fabrica(config: Configuracao) -> ModeloFalsoSucesso:
            del config
            raise APITimeoutError(request=request)

        with self.assertRaises(FalhaSmoke) as context:
            executar_smoke(config_com_chave(), fabrica)

        self.assertEqual(context.exception.categoria, "timeout")

    def test_http_429_e_sanitizado(self) -> None:
        request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        response = httpx.Response(429, request=request)

        def fabrica(config: Configuracao) -> ModeloFalsoSucesso:
            del config
            raise RateLimitError("limite", response=response, body=None)

        with self.assertRaises(FalhaSmoke) as context:
            executar_smoke(config_com_chave(), fabrica)

        self.assertEqual(context.exception.categoria, "limite")

    def test_saida_estruturada_invalida(self) -> None:
        modelo = ModeloFalsoSucesso(
            saida_estruturada={
                "integracao": "valor_invalido",
                "modelo_respondeu": True,
                "resumo": "",
            }
        )

        with self.assertRaises(FalhaSmoke) as context:
            executar_smoke(config_com_chave(), lambda config: modelo)

        self.assertEqual(context.exception.categoria, "saida_invalida")


if __name__ == "__main__":
    unittest.main()
