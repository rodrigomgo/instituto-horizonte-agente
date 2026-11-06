"""Testes da infraestrutura SQLite da TSK-005, sem Tools ou Groq."""

from __future__ import annotations

import os
import socket
import sqlite3
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from instituto_horizonte.config import RAIZ_PROJETO
from instituto_horizonte.database import (
    CHAVE_FIXTURE,
    ID_FIXTURE,
    ORIGEM_FIXTURE,
    PROTOCOLO_FIXTURE,
    STATUS_FIXTURE,
    TIPO_FIXTURE,
    ConflitoFixture,
    ErroBanco,
    id_para_protocolo,
    inicializar_banco,
    protocolo_para_id,
    resolver_caminho_sqlite,
)


COLUNAS_ESPERADAS = [
    "id",
    "tipo",
    "turma",
    "justificativa",
    "status",
    "criado_em",
    "atualizado_em",
    "idempotency_key",
    "origem",
]


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.caminho = Path(self.temp.name) / "isolado" / "protocolos.sqlite3"

    def tearDown(self) -> None:
        self.temp.cleanup()

    @contextmanager
    def conectar(self) -> Iterator[sqlite3.Connection]:
        conexao = sqlite3.connect(self.caminho)
        try:
            yield conexao
            conexao.commit()
        except Exception:
            conexao.rollback()
            raise
        finally:
            conexao.close()

    def test_cria_banco_schema_e_colunas_em_diretorio_temporario(self) -> None:
        resumo = inicializar_banco(self.caminho)

        self.assertTrue(self.caminho.is_file())
        self.assertTrue(resumo.schema_existe)
        with self.conectar() as conexao:
            colunas = [linha[1] for linha in conexao.execute("PRAGMA table_info(solicitacoes)")]
        self.assertEqual(colunas, COLUNAS_ESPERADAS)

    def test_insere_fixture_com_status_e_timestamps_utc(self) -> None:
        inicializar_banco(self.caminho)

        with self.conectar() as conexao:
            registro = conexao.execute(
                """
                SELECT id, tipo, turma, justificativa, status, criado_em,
                       atualizado_em, idempotency_key, origem
                FROM solicitacoes WHERE id = ?
                """,
                (ID_FIXTURE,),
            ).fetchone()
        self.assertEqual(
            registro[:5],
            (ID_FIXTURE, TIPO_FIXTURE, None, None, STATUS_FIXTURE),
        )
        self.assertEqual(registro[7:], (CHAVE_FIXTURE, ORIGEM_FIXTURE))
        for timestamp in registro[5:7]:
            instante = datetime.fromisoformat(timestamp)
            self.assertIsNotNone(instante.tzinfo)
            self.assertEqual(instante.utcoffset().total_seconds(), 0)

    def test_converte_id_e_protocolo(self) -> None:
        self.assertEqual(id_para_protocolo(1001), PROTOCOLO_FIXTURE)
        self.assertEqual(protocolo_para_id(PROTOCOLO_FIXTURE), 1001)
        with self.assertRaises(ValueError):
            protocolo_para_id("SOL-ABC")

    def test_segunda_inicializacao_nao_duplica(self) -> None:
        primeira = inicializar_banco(self.caminho)
        segunda = inicializar_banco(self.caminho)

        self.assertEqual(primeira.quantidade_registros, 1)
        self.assertEqual(segunda.quantidade_registros, 1)

    def test_preserva_status_e_timestamps_existentes(self) -> None:
        inicializar_banco(self.caminho)
        timestamps = ("2025-01-01T10:00:00+00:00", "2025-01-02T11:00:00+00:00")
        with self.conectar() as conexao:
            conexao.execute(
                """
                UPDATE solicitacoes
                SET status = ?, criado_em = ?, atualizado_em = ?
                WHERE id = ?
                """,
                ("resolvido", *timestamps, ID_FIXTURE),
            )

        resumo = inicializar_banco(self.caminho)
        with self.conectar() as conexao:
            persistido = conexao.execute(
                "SELECT status, criado_em, atualizado_em FROM solicitacoes WHERE id = ?",
                (ID_FIXTURE,),
            ).fetchone()
        self.assertEqual(persistido, ("resolvido", *timestamps))
        self.assertEqual(resumo.status_fixture, "resolvido")

    def test_preserva_registro_adicional_e_proximo_id_e_1002(self) -> None:
        inicializar_banco(self.caminho)
        with self.conectar() as conexao:
            cursor = conexao.execute(
                """
                INSERT INTO solicitacoes (
                    tipo, status, criado_em, atualizado_em, idempotency_key, origem
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("teste", "aberto", "2025-01-01T00:00:00+00:00",
                 "2025-01-01T00:00:00+00:00", "teste-1002", "teste"),
            )
            novo_id = cursor.lastrowid

        resumo = inicializar_banco(self.caminho)
        self.assertEqual(novo_id, 1002)
        self.assertEqual(resumo.quantidade_registros, 2)

    def test_conflito_id_1001_preserva_registro_incompativel(self) -> None:
        inicializar_banco(self.caminho)
        with self.conectar() as conexao:
            conexao.execute(
                "UPDATE solicitacoes SET tipo = ?, status = ? WHERE id = ?",
                ("registro_preexistente", "intacto", ID_FIXTURE),
            )

        with self.assertRaisesRegex(ConflitoFixture, "preservado"):
            inicializar_banco(self.caminho)

        with self.conectar() as conexao:
            persistido = conexao.execute(
                "SELECT tipo, status FROM solicitacoes WHERE id = ?",
                (ID_FIXTURE,),
            ).fetchone()
        self.assertEqual(persistido, ("registro_preexistente", "intacto"))

    def test_idempotency_key_e_unica(self) -> None:
        inicializar_banco(self.caminho)
        with self.conectar() as conexao:
            with self.assertRaises(sqlite3.IntegrityError):
                conexao.execute(
                    """
                    INSERT INTO solicitacoes (
                        tipo, status, criado_em, atualizado_em, idempotency_key
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    ("teste", "aberto", "2025-01-01T00:00:00+00:00",
                     "2025-01-01T00:00:00+00:00", CHAVE_FIXTURE),
                )

    def test_falha_transacional_faz_rollback_do_schema(self) -> None:
        with (
            patch(
                "instituto_horizonte.database._inserir_ou_validar_fixture",
                side_effect=sqlite3.OperationalError("falha injetada"),
            ),
            self.assertRaisesRegex(ErroBanco, "Falha transacional"),
        ):
            inicializar_banco(self.caminho)

        with self.conectar() as conexao:
            tabela = conexao.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='solicitacoes'"
            ).fetchone()
        self.assertIsNone(tabela)

    def test_falha_ao_criar_diretorio_retorna_erro_sanitizado(self) -> None:
        mensagem_sensivel = "caminho privado e conteudo sensivel"
        with (
            patch.object(Path, "mkdir", side_effect=PermissionError(mensagem_sensivel)),
            self.assertRaises(ErroBanco) as contexto,
        ):
            inicializar_banco(self.caminho)

        mensagem = str(contexto.exception)
        self.assertIn("Falha ao preparar diretório do SQLite", mensagem)
        self.assertIn("PermissionError", mensagem)
        self.assertNotIn(mensagem_sensivel, mensagem)
        self.assertFalse(self.caminho.exists())

    def test_resolve_caminho_relativo_independente_do_cwd(self) -> None:
        outro_cwd = Path(self.temp.name)
        cwd_original = Path.cwd()
        try:
            os.chdir(outro_cwd)
            resolvido = resolver_caminho_sqlite(Path(".local/teste.sqlite3"))
        finally:
            os.chdir(cwd_original)
        self.assertEqual(resolvido, (RAIZ_PROJETO / ".local/teste.sqlite3").resolve())

    def test_caminho_absoluto_e_preservado(self) -> None:
        self.assertEqual(resolver_caminho_sqlite(self.caminho), self.caminho.resolve())

    def test_nao_requer_groq_nem_rede(self) -> None:
        ambiente = {chave: valor for chave, valor in os.environ.items() if chave != "GROQ_API_KEY"}
        with (
            patch.dict(os.environ, ambiente, clear=True),
            patch.object(socket, "create_connection", side_effect=AssertionError("rede usada")),
        ):
            resumo = inicializar_banco(self.caminho)
        self.assertEqual(resumo.protocolo_fixture, PROTOCOLO_FIXTURE)


if __name__ == "__main__":
    unittest.main()
