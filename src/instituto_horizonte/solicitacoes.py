"""Registro autorizado e idempotente de solicitações acadêmicas."""

from __future__ import annotations

import secrets
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from langchain_core.tools import tool
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from instituto_horizonte.config import Configuracao
from instituto_horizonte.database import id_para_protocolo, resolver_caminho_sqlite


TextoTurma = Annotated[str, StringConstraints(min_length=1, max_length=100, strict=True)]
TextoJustificativa = Annotated[
    str,
    StringConstraints(min_length=1, max_length=500, strict=True),
]


class ErroAutorizacao(RuntimeError):
    """Tentativa de escrita sem autorização confiável do backend."""


class ErroRascunho(RuntimeError):
    """Transição inválida no estado de um rascunho."""


class DadosSolicitacao(BaseModel):
    """Dados lógicos aceitos pela Tool de registro."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    tipo: Literal["segunda_via_certificado"]
    turma: TextoTurma
    justificativa: TextoJustificativa

    @field_validator("turma", "justificativa", mode="before")
    @classmethod
    def remover_espacos_externos(cls, valor: object) -> object:
        return valor.strip() if isinstance(valor, str) else valor


class RespostaRegistro(BaseModel):
    """Resultado estrito de uma tentativa de registro."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    sucesso: bool
    protocolo: str | None
    status: Literal["aberto"] | None
    erro: str | None

    @model_validator(mode="after")
    def validar_coerencia(self) -> RespostaRegistro:
        if self.sucesso:
            if self.protocolo is None or self.status != "aberto" or self.erro is not None:
                raise ValueError("sucesso exige protocolo e status aberto, sem erro")
        elif self.protocolo is not None or self.status is not None or self.erro is None:
            raise ValueError("falha exige erro e não pode declarar protocolo ou status")
        return self


class ResumoRascunho(BaseModel):
    """Resumo exibível sem expor a chave opaca de idempotência."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    tipo: Literal["segunda_via_certificado"]
    turma: str
    justificativa: str
    instrucao: str = Field(
        default="Digite CONFIRMAR para registrar ou CANCELAR para desistir."
    )


@dataclass(frozen=True, slots=True)
class _AutorizacaoConfiavel:
    chave: str
    dados: DadosSolicitacao
    resumo_apresentado: bool
    confirmada: bool
    config: Configuracao


@dataclass(slots=True)
class _EstadoRascunho:
    dados: DadosSolicitacao
    chave: str
    resumo_apresentado: bool = False
    resultado: RespostaRegistro | None = None


_AUTORIZACAO_ATUAL: ContextVar[_AutorizacaoConfiavel | None] = ContextVar(
    "autorizacao_registro_solicitacao",
    default=None,
)


def _falha(mensagem: str) -> RespostaRegistro:
    return RespostaRegistro(
        sucesso=False,
        protocolo=None,
        status=None,
        erro=mensagem,
    )


@contextmanager
def _contexto_autorizado(autorizacao: _AutorizacaoConfiavel) -> Iterator[None]:
    token = _AUTORIZACAO_ATUAL.set(autorizacao)
    try:
        yield
    finally:
        _AUTORIZACAO_ATUAL.reset(token)


def registrar_solicitacao_servico(
    dados: DadosSolicitacao,
    *,
    autorizacao: _AutorizacaoConfiavel | None,
    config: Configuracao | None = None,
) -> RespostaRegistro:
    """Persiste somente quando a autorização confiável corresponde aos dados."""

    if (
        autorizacao is None
        or not autorizacao.confirmada
        or not autorizacao.resumo_apresentado
        or autorizacao.dados != dados
    ):
        raise ErroAutorizacao(
            "Registro recusado: confirmação confiável do backend ausente ou inválida."
        )

    config = autorizacao.config if config is None else config
    caminho = resolver_caminho_sqlite(config.sqlite_path)
    if not caminho.is_file():
        return _falha("Banco não inicializado; execute scripts/init_db.py.")

    conexao: sqlite3.Connection | None = None
    try:
        conexao = sqlite3.connect(caminho, isolation_level=None)
        conexao.execute("BEGIN IMMEDIATE")
        existente = conexao.execute(
            """
            SELECT id, tipo, turma, justificativa, status, origem
            FROM solicitacoes WHERE idempotency_key = ?
            """,
            (autorizacao.chave,),
        ).fetchone()
        if existente is not None:
            esperado = (
                dados.tipo,
                dados.turma,
                dados.justificativa,
                "aberto",
                "agente",
            )
            if tuple(existente[1:]) != esperado:
                conexao.rollback()
                return _falha(
                    "Conflito de idempotência: chave já associada a dados diferentes."
                )
            conexao.commit()
            return RespostaRegistro(
                sucesso=True,
                protocolo=id_para_protocolo(int(existente[0])),
                status="aberto",
                erro=None,
            )

        timestamp = datetime.now(UTC).isoformat()
        cursor = conexao.execute(
            """
            INSERT INTO solicitacoes (
                tipo, turma, justificativa, status, criado_em,
                atualizado_em, idempotency_key, origem
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dados.tipo,
                dados.turma,
                dados.justificativa,
                "aberto",
                timestamp,
                timestamp,
                autorizacao.chave,
                "agente",
            ),
        )
        identificador = cursor.lastrowid
        if identificador is None:
            raise sqlite3.DatabaseError("SQLite não retornou lastrowid")
        conexao.commit()
        return RespostaRegistro(
            sucesso=True,
            protocolo=id_para_protocolo(int(identificador)),
            status="aberto",
            erro=None,
        )
    except sqlite3.Error as error:
        if conexao is not None:
            conexao.rollback()
        return _falha(f"Falha ao registrar solicitação ({type(error).__name__}).")
    finally:
        if conexao is not None:
            conexao.close()


@tool("registrar_solicitacao", args_schema=DadosSolicitacao)
def registrar_solicitacao(
    tipo: Literal["segunda_via_certificado"],
    turma: str,
    justificativa: str,
) -> dict[str, Any]:
    """Registra somente segunda via de certificado previamente autorizada.

    A gravação exige confirmação validada pelo backend em mensagem posterior;
    o pedido inicial do usuário não autoriza a Tool. Não altera notas nem
    protocolos existentes.
    """

    dados = DadosSolicitacao(tipo=tipo, turma=turma, justificativa=justificativa)
    resposta = registrar_solicitacao_servico(
        dados,
        autorizacao=_AUTORIZACAO_ATUAL.get(),
    )
    return resposta.model_dump(mode="json")


class GestorRascunhos:
    """Estado confiável em memória, reutilizável pela futura orquestração."""

    def __init__(self, chave_factory: Callable[[], str] | None = None) -> None:
        self._rascunhos: dict[str, _EstadoRascunho] = {}
        self._chave_factory = chave_factory or (lambda: secrets.token_urlsafe(32))

    def preparar(self, sessao: str, dados: DadosSolicitacao) -> None:
        self._rascunhos[sessao] = _EstadoRascunho(
            dados=dados,
            chave=self._chave_factory(),
        )

    def apresentar_resumo(self, sessao: str) -> ResumoRascunho:
        estado = self._rascunhos.get(sessao)
        if estado is None:
            raise ErroRascunho("Não existe rascunho pendente para esta sessão.")
        estado.resumo_apresentado = True
        return ResumoRascunho(**estado.dados.model_dump())

    def processar_comando(
        self,
        sessao: str,
        comando: str,
        *,
        config: Configuracao,
    ) -> RespostaRegistro:
        estado = self._rascunhos.get(sessao)
        normalizado = comando.strip().upper()
        if normalizado == "CANCELAR":
            if estado is not None:
                del self._rascunhos[sessao]
            return _falha("Solicitação cancelada; nenhum registro foi criado.")
        if normalizado != "CONFIRMAR":
            return _falha("Comando inválido; use CONFIRMAR ou CANCELAR.")
        if estado is None:
            return _falha("Não existe rascunho pendente para confirmar.")
        if not estado.resumo_apresentado:
            return _falha("O resumo deve ser apresentado antes da confirmação.")
        if estado.resultado is not None:
            return estado.resultado

        autorizacao = _AutorizacaoConfiavel(
            chave=estado.chave,
            dados=estado.dados,
            resumo_apresentado=True,
            confirmada=True,
            config=config,
        )
        with _contexto_autorizado(autorizacao):
            resultado_tool = registrar_solicitacao.invoke(estado.dados.model_dump())
        resultado = RespostaRegistro.model_validate(resultado_tool)
        if resultado.sucesso:
            estado.resultado = resultado
        return resultado
