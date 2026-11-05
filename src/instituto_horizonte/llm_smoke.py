"""Smoke test isolado da integração LangChain/Groq da TSK-002."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, Protocol

from groq import APITimeoutError, AuthenticationError, RateLimitError
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from instituto_horizonte.config import Configuracao


class SomaInteirosEntrada(BaseModel):
    """Argumentos tipados da Tool local de demonstração."""

    model_config = ConfigDict(extra="forbid")

    parcela_a: int = Field(description="Primeiro número inteiro")
    parcela_b: int = Field(description="Segundo número inteiro")


@tool("somar_inteiros", args_schema=SomaInteirosEntrada)
def somar_inteiros(parcela_a: int, parcela_b: int) -> int:
    """Soma dois inteiros localmente, sem leitura ou escrita externa."""

    return parcela_a + parcela_b


class SaidaEstruturadaSmoke(BaseModel):
    """Contrato Pydantic solicitado ao modelo no segundo teste real."""

    model_config = ConfigDict(extra="forbid")

    integracao: Literal["groq_langchain_pydantic"]
    modelo_respondeu: bool
    resumo: str = Field(min_length=1, max_length=200)


class ResultadoSmoke(BaseModel):
    """Evidência segura produzida pelo script, sem credenciais."""

    model_config = ConfigDict(extra="forbid")

    modelo: str
    tool_call_detectado: bool
    tool_nome: str
    tool_argumentos: SomaInteirosEntrada
    tool_resultado_local: int
    resposta_final_llm: str
    structured_output: SaidaEstruturadaSmoke


class FalhaSmoke(RuntimeError):
    """Erro sanitizado, categorizado sem incluir conteúdo da exceção original."""

    def __init__(self, categoria: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.categoria = categoria


class ModeloChat(Protocol):
    def bind_tools(self, tools: list[Any], **kwargs: Any) -> Any: ...

    def with_structured_output(self, schema: type[BaseModel], **kwargs: Any) -> Any: ...


FabricaModelo = Callable[[Configuracao], ModeloChat]


def _criar_chat_groq(config: Configuracao) -> ChatGroq:
    if config.groq_api_key is None:
        raise FalhaSmoke("configuracao", "GROQ_API_KEY não está configurada.")
    return ChatGroq(
        api_key=config.groq_api_key,
        model=config.groq_model,
        temperature=0,
        timeout=30,
        max_retries=0,
    )


def _falha_sanitizada(error: Exception) -> FalhaSmoke:
    if isinstance(error, FalhaSmoke):
        return error
    if isinstance(error, AuthenticationError):
        return FalhaSmoke("autenticacao", "A autenticação Groq foi recusada (HTTP 401).")
    if isinstance(error, RateLimitError):
        return FalhaSmoke("limite", "O limite de requisições Groq foi atingido (HTTP 429).")
    if isinstance(error, APITimeoutError) or isinstance(error, TimeoutError):
        return FalhaSmoke("timeout", "A chamada Groq excedeu o tempo limite.")
    if isinstance(error, ValidationError):
        return FalhaSmoke("saida_invalida", "A saída do modelo não satisfez o schema Pydantic.")
    return FalhaSmoke("integracao", "A integração Groq falhou; consulte o tipo no diagnóstico local.")


def _conteudo_textual(message: AIMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content.strip()
    return str(content).strip()


def executar_smoke(
    config: Configuracao,
    fabrica_modelo: FabricaModelo = _criar_chat_groq,
) -> ResultadoSmoke:
    """Executa Tool Calling local e Structured Output em chamadas separadas."""

    if config.groq_api_key is None:
        raise FalhaSmoke("configuracao", "GROQ_API_KEY não está configurada.")

    try:
        modelo = fabrica_modelo(config)
        prompt_tool = HumanMessage(
            content=(
                "Use obrigatoriamente a ferramenta somar_inteiros para calcular "
                "19 + 23. Não faça a soma sem a ferramenta."
            )
        )
        modelo_forcado = modelo.bind_tools([somar_inteiros], tool_choice="somar_inteiros")
        solicitacao = modelo_forcado.invoke([prompt_tool])
        if not isinstance(solicitacao, AIMessage) or not solicitacao.tool_calls:
            raise FalhaSmoke("tool_call_ausente", "O modelo não solicitou a Tool esperada.")

        chamada = solicitacao.tool_calls[0]
        if chamada["name"] != somar_inteiros.name:
            raise FalhaSmoke("tool_incorreta", "O modelo solicitou uma Tool inesperada.")
        argumentos = SomaInteirosEntrada.model_validate(chamada["args"])

        # Esta é a execução Python real e local; o LLM apenas forneceu os argumentos.
        resultado_local = somar_inteiros.invoke(argumentos.model_dump())
        if not isinstance(resultado_local, int):
            raise FalhaSmoke("tool_resultado_invalido", "A Tool local retornou tipo inesperado.")

        retorno_tool = ToolMessage(
            content=str(resultado_local),
            tool_call_id=chamada["id"],
            name=somar_inteiros.name,
        )
        modelo_auto = modelo.bind_tools([somar_inteiros], tool_choice="auto")
        resposta_final = modelo_auto.invoke([prompt_tool, solicitacao, retorno_tool])
        if not isinstance(resposta_final, AIMessage):
            raise FalhaSmoke("resposta_invalida", "O modelo não retornou uma mensagem final válida.")
        texto_final = _conteudo_textual(resposta_final)
        if not texto_final:
            raise FalhaSmoke("resposta_vazia", "O modelo retornou resposta final vazia.")

        modelo_estruturado = modelo.with_structured_output(
            SaidaEstruturadaSmoke,
            method="json_schema",
            strict=True,
        )
        saida_bruta = modelo_estruturado.invoke(
            "Confirme em português que esta é uma resposta estruturada do smoke test."
        )
        saida_validada = SaidaEstruturadaSmoke.model_validate(saida_bruta)

        return ResultadoSmoke(
            modelo=config.groq_model,
            tool_call_detectado=True,
            tool_nome=chamada["name"],
            tool_argumentos=argumentos,
            tool_resultado_local=resultado_local,
            resposta_final_llm=texto_final,
            structured_output=saida_validada,
        )
    except Exception as error:
        raise _falha_sanitizada(error) from None
