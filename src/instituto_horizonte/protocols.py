"""Consulta tipada e somente leitura de protocolos acadêmicos."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Annotated, Any

from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, StringConstraints

from instituto_horizonte.config import Configuracao
from instituto_horizonte.database import protocolo_para_id, resolver_caminho_sqlite


NumeroProtocolo = Annotated[
    str,
    StringConstraints(pattern=r"^SOL-\d{4,}$", strict=True),
]


class ErroConsultaProtocolo(RuntimeError):
    """Falha controlada de acesso ao banco de protocolos."""


class ConsultaProtocolo(BaseModel):
    """Entrada estrita da Tool ``consultar_protocolo``."""

    model_config = ConfigDict(extra="forbid", strict=True)

    numero: NumeroProtocolo


class RespostaConsultaProtocolo(BaseModel):
    """Resultado estruturado obtido exclusivamente do SQLite."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    encontrado: bool
    protocolo: NumeroProtocolo
    status: str | None
    tipo: str | None
    criado_em: str | None
    atualizado_em: str | None


def _uri_somente_leitura(caminho: Path) -> str:
    return f"{caminho.as_uri()}?mode=ro"


def consultar_protocolo_servico(
    numero: str,
    *,
    config: Configuracao | None = None,
) -> RespostaConsultaProtocolo:
    """Consulta protocolo existente sem criar ou modificar o banco SQLite."""

    entrada = ConsultaProtocolo(numero=numero)
    config = Configuracao.from_env() if config is None else config
    caminho = resolver_caminho_sqlite(config.sqlite_path)
    if not caminho.is_file():
        raise ErroConsultaProtocolo(
            "Banco de protocolos não inicializado; execute scripts/init_db.py."
        )

    conexao: sqlite3.Connection | None = None
    try:
        conexao = sqlite3.connect(_uri_somente_leitura(caminho), uri=True)
        registro = conexao.execute(
            """
            SELECT id, status, tipo, criado_em, atualizado_em
            FROM solicitacoes
            WHERE id = ?
            """,
            (protocolo_para_id(entrada.numero),),
        ).fetchone()
    except sqlite3.Error as error:
        raise ErroConsultaProtocolo(
            f"Falha ao consultar banco de protocolos ({type(error).__name__})."
        ) from None
    finally:
        if conexao is not None:
            conexao.close()

    if registro is None:
        return RespostaConsultaProtocolo(
            encontrado=False,
            protocolo=entrada.numero,
            status=None,
            tipo=None,
            criado_em=None,
            atualizado_em=None,
        )
    return RespostaConsultaProtocolo(
        encontrado=True,
        protocolo=entrada.numero,
        status=str(registro[1]),
        tipo=str(registro[2]),
        criado_em=str(registro[3]),
        atualizado_em=str(registro[4]),
    )


@tool("consultar_protocolo", args_schema=ConsultaProtocolo)
def consultar_protocolo(numero: str) -> dict[str, Any]:
    """Verifica o andamento de um protocolo acadêmico existente.

    Use quando o usuário fornecer um número de protocolo ou pedir seu status.
    Esta Tool não cria, altera, resolve ou cancela solicitações e nunca deve
    ser usada para inventar um protocolo ausente.
    """

    return consultar_protocolo_servico(numero).model_dump(mode="json")
