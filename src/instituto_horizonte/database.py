"""Infraestrutura SQLite e seed idempotente de protocolos acadêmicos."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from instituto_horizonte.config import RAIZ_PROJETO


ID_FIXTURE = 1001
PROTOCOLO_FIXTURE = "SOL-1001"
TIPO_FIXTURE = "solicitacao_academica_demonstracao"
STATUS_FIXTURE = "em_analise"
ORIGEM_FIXTURE = "seed"
CHAVE_FIXTURE = "seed:SOL-1001"

SCHEMA_SOLICITACOES = """
CREATE TABLE IF NOT EXISTS solicitacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    turma TEXT,
    justificativa TEXT,
    status TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    idempotency_key TEXT UNIQUE,
    origem TEXT NOT NULL DEFAULT 'agente'
)
"""


class ErroBanco(RuntimeError):
    """Falha controlada de inicialização ou verificação do SQLite."""


class ConflitoFixture(ErroBanco):
    """O ID reservado da fixture já contém dados incompatíveis."""


@dataclass(frozen=True, slots=True)
class ResumoBanco:
    caminho: str
    schema_existe: bool
    quantidade_registros: int
    protocolo_fixture: str
    status_fixture: str


def resolver_caminho_sqlite(caminho: Path) -> Path:
    """Resolve caminho relativo pela raiz do projeto e aceita absoluto em testes."""

    if caminho.is_absolute():
        return caminho.resolve()
    resolvido = (RAIZ_PROJETO / caminho).resolve()
    try:
        resolvido.relative_to(RAIZ_PROJETO.resolve())
    except ValueError:
        raise ErroBanco(
            "SQLITE_PATH relativo deve permanecer dentro da raiz do projeto."
        ) from None
    return resolvido


def id_para_protocolo(identificador: int) -> str:
    if identificador < 1:
        raise ValueError("identificador de protocolo deve ser positivo")
    return f"SOL-{identificador}"


def protocolo_para_id(protocolo: str) -> int:
    if not re.fullmatch(r"SOL-\d{4,}", protocolo):
        raise ValueError("protocolo deve seguir o formato SOL-nnnn")
    return int(protocolo.removeprefix("SOL-"))


def _agora_utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def _inserir_ou_validar_fixture(conexao: sqlite3.Connection) -> None:
    existente = conexao.execute(
        """
        SELECT tipo, turma, justificativa, idempotency_key, origem
        FROM solicitacoes
        WHERE id = ?
        """,
        (ID_FIXTURE,),
    ).fetchone()
    if existente is not None:
        identidade_esperada = (
            TIPO_FIXTURE,
            None,
            None,
            CHAVE_FIXTURE,
            ORIGEM_FIXTURE,
        )
        if tuple(existente) != identidade_esperada:
            raise ConflitoFixture(
                "O ID 1001 já está ocupado por registro incompatível; "
                "o dado existente foi preservado."
            )
        return

    timestamp = _agora_utc_iso()
    conexao.execute(
        """
        INSERT INTO solicitacoes (
            id, tipo, turma, justificativa, status,
            criado_em, atualizado_em, idempotency_key, origem
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ID_FIXTURE,
            TIPO_FIXTURE,
            None,
            None,
            STATUS_FIXTURE,
            timestamp,
            timestamp,
            CHAVE_FIXTURE,
            ORIGEM_FIXTURE,
        ),
    )


def _obter_resumo(conexao: sqlite3.Connection, caminho: Path) -> ResumoBanco:
    schema_existe = conexao.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("solicitacoes",),
    ).fetchone() is not None
    quantidade = conexao.execute("SELECT COUNT(*) FROM solicitacoes").fetchone()[0]
    fixture = conexao.execute(
        "SELECT id, status FROM solicitacoes WHERE id = ?",
        (ID_FIXTURE,),
    ).fetchone()
    if fixture is None:
        raise ErroBanco("Fixture SOL-1001 não foi encontrada após a inicialização.")
    return ResumoBanco(
        caminho=str(caminho),
        schema_existe=schema_existe,
        quantidade_registros=int(quantidade),
        protocolo_fixture=id_para_protocolo(int(fixture[0])),
        status_fixture=str(fixture[1]),
    )


def inicializar_banco(caminho_configurado: Path) -> ResumoBanco:
    """Cria schema e fixture em uma transação, sem atualizar dados existentes."""

    caminho = resolver_caminho_sqlite(caminho_configurado)
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ErroBanco(
            f"Falha ao preparar diretório do SQLite ({type(error).__name__})."
        ) from None
    conexao: sqlite3.Connection | None = None
    try:
        conexao = sqlite3.connect(caminho, isolation_level=None)
        conexao.execute("BEGIN IMMEDIATE")
        conexao.execute(SCHEMA_SOLICITACOES)
        _inserir_ou_validar_fixture(conexao)
        resumo = _obter_resumo(conexao, caminho)
        conexao.commit()
        return resumo
    except ConflitoFixture:
        if conexao is not None:
            conexao.rollback()
        raise
    except sqlite3.Error as error:
        if conexao is not None:
            conexao.rollback()
        raise ErroBanco(
            f"Falha transacional ao inicializar SQLite ({type(error).__name__})."
        ) from None
    finally:
        if conexao is not None:
            conexao.close()
