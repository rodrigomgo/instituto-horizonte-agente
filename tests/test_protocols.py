"""Testes da Tool consultar_protocolo, sem LLM, Groq ou rede."""

from __future__ import annotations

import os
import socket
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pydantic import ValidationError

from instituto_horizonte.config import Configuracao
from instituto_horizonte.database import ID_FIXTURE, inicializar_banco
from instituto_horizonte.protocols import (
    ConsultaProtocolo,
    ErroConsultaProtocolo,
    RespostaConsultaProtocolo,
    consultar_protocolo,
    consultar_protocolo_servico,
)


class ProxyConexao:
    def __init__(self, conexao: sqlite3.Connection) -> None:
        self.conexao = conexao
        self.fechada = False

    def execute(self, sql: str, parametros: tuple[int, ...]):
        return self.conexao.execute(sql, parametros)

    def close(self) -> None:
        self.fechada = True
        self.conexao.close()


class ProtocolosTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.caminho = Path(self.temp.name) / "protocolos.sqlite3"
        self.config = Configuracao.from_env({"SQLITE_PATH": str(self.caminho)})

    def tearDown(self) -> None:
        self.temp.cleanup()

    def inicializar(self) -> None:
        inicializar_banco(self.caminho)

    def consultar(self, numero: str) -> RespostaConsultaProtocolo:
        return consultar_protocolo_servico(numero, config=self.config)

    def test_consulta_sol_1001_preserva_dados_persistidos(self) -> None:
        self.inicializar()
        conexao = sqlite3.connect(self.caminho)
        try:
            esperado = conexao.execute(
                "SELECT status, tipo, criado_em, atualizado_em FROM solicitacoes WHERE id = ?",
                (ID_FIXTURE,),
            ).fetchone()
        finally:
            conexao.close()

        resposta = self.consultar("SOL-1001")

        self.assertTrue(resposta.encontrado)
        self.assertEqual(resposta.protocolo, "SOL-1001")
        self.assertEqual(
            (resposta.status, resposta.tipo, resposta.criado_em, resposta.atualizado_em),
            esperado,
        )
        self.assertEqual(resposta.status, "em_analise")

    def test_protocolo_inexistente_retorna_campos_nulos(self) -> None:
        self.inicializar()

        resposta = self.consultar("SOL-9999")

        self.assertFalse(resposta.encontrado)
        self.assertEqual(resposta.protocolo, "SOL-9999")
        self.assertIsNone(resposta.status)
        self.assertIsNone(resposta.tipo)
        self.assertIsNone(resposta.criado_em)
        self.assertIsNone(resposta.atualizado_em)

    def test_rejeita_protocolo_malformado_sem_consultar_banco(self) -> None:
        for numero in ("SOL-ABC", ""):
            with (
                self.subTest(numero=numero),
                patch("instituto_horizonte.protocols.sqlite3.connect") as conectar,
                self.assertRaises(ValidationError),
            ):
                self.consultar(numero)
            conectar.assert_not_called()

    def test_contratos_pydantic_sao_estritos(self) -> None:
        with self.assertRaises(ValidationError):
            ConsultaProtocolo.model_validate({"numero": 1001})
        with self.assertRaises(ValidationError):
            ConsultaProtocolo.model_validate({"numero": "SOL-1001", "extra": True})
        with self.assertRaises(ValidationError):
            RespostaConsultaProtocolo.model_validate(
                {
                    "encontrado": 1,
                    "protocolo": "SOL-1001",
                    "status": "em_analise",
                    "tipo": "teste",
                    "criado_em": "agora",
                    "atualizado_em": "agora",
                }
            )

    def test_banco_inexistente_nao_e_criado(self) -> None:
        with self.assertRaisesRegex(ErroConsultaProtocolo, "scripts/init_db.py"):
            self.consultar("SOL-1001")
        self.assertFalse(self.caminho.exists())

    def test_retorna_status_real_apos_alteracao_controlada(self) -> None:
        self.inicializar()
        conexao = sqlite3.connect(self.caminho)
        try:
            conexao.execute(
                "UPDATE solicitacoes SET status = ? WHERE id = ?",
                ("concluido_no_teste", ID_FIXTURE),
            )
            conexao.commit()
        finally:
            conexao.close()

        resposta = self.consultar("SOL-1001")
        self.assertEqual(resposta.status, "concluido_no_teste")

    def test_tool_langchain_e_invocada_sem_llm(self) -> None:
        self.inicializar()
        with patch.dict(os.environ, {"SQLITE_PATH": str(self.caminho)}, clear=True):
            saida = consultar_protocolo.invoke({"numero": "SOL-1001"})

        self.assertTrue(saida["encontrado"])
        self.assertEqual(saida["protocolo"], "SOL-1001")
        self.assertEqual(consultar_protocolo.name, "consultar_protocolo")

    def test_abre_em_modo_somente_leitura_e_fecha_conexao(self) -> None:
        self.inicializar()
        conectar_real = sqlite3.connect
        proxy: ProxyConexao | None = None

        def conectar_proxy(database: str, *, uri: bool = False) -> ProxyConexao:
            nonlocal proxy
            self.assertTrue(uri)
            self.assertIn("mode=ro", database)
            proxy = ProxyConexao(conectar_real(database, uri=uri))
            return proxy

        with patch(
            "instituto_horizonte.protocols.sqlite3.connect",
            side_effect=conectar_proxy,
        ):
            resposta = self.consultar("SOL-1001")

        self.assertTrue(resposta.encontrado)
        self.assertIsNotNone(proxy)
        self.assertTrue(proxy.fechada)

    def test_falha_sqlite_e_controlada_e_sanitizada(self) -> None:
        self.inicializar()
        detalhe = "detalhe privado do sistema"
        with (
            patch(
                "instituto_horizonte.protocols.sqlite3.connect",
                side_effect=sqlite3.OperationalError(detalhe),
            ),
            self.assertRaises(ErroConsultaProtocolo) as contexto,
        ):
            self.consultar("SOL-1001")

        self.assertIn("OperationalError", str(contexto.exception))
        self.assertNotIn(detalhe, str(contexto.exception))

    def test_fluxo_nao_requer_groq_nem_rede(self) -> None:
        self.inicializar()
        ambiente = {chave: valor for chave, valor in os.environ.items() if chave != "GROQ_API_KEY"}
        with (
            patch.dict(os.environ, ambiente, clear=True),
            patch.object(socket, "create_connection", side_effect=AssertionError("rede usada")),
        ):
            resposta = self.consultar("SOL-1001")
        self.assertTrue(resposta.encontrado)


if __name__ == "__main__":
    unittest.main()
