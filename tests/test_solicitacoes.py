"""Testes de autorização e idempotência da TSK-007, sem LLM ou rede."""

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
from instituto_horizonte.database import inicializar_banco
from instituto_horizonte.protocols import consultar_protocolo_servico
from instituto_horizonte.solicitacoes import (
    DadosSolicitacao,
    ErroAutorizacao,
    GestorRascunhos,
    registrar_solicitacao,
)


class SolicitacoesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.caminho = Path(self.temp.name) / "protocolos.sqlite3"
        self.config = Configuracao.from_env({"SQLITE_PATH": str(self.caminho)})
        inicializar_banco(self.caminho)
        self.dados = DadosSolicitacao(
            tipo="segunda_via_certificado",
            turma="Turma 6001",
            justificativa="Segunda via para arquivo acadêmico.",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def quantidade(self) -> int:
        conexao = sqlite3.connect(self.caminho)
        try:
            return int(conexao.execute("SELECT COUNT(*) FROM solicitacoes").fetchone()[0])
        finally:
            conexao.close()

    def confirmar(
        self,
        gestor: GestorRascunhos,
        sessao: str = "sessao-a",
        dados: DadosSolicitacao | None = None,
    ):
        gestor.preparar(sessao, dados or self.dados)
        gestor.apresentar_resumo(sessao)
        return gestor.processar_comando(sessao, "CONFIRMAR", config=self.config)

    def test_contrato_aceita_tipo_permitido_e_remove_espacos(self) -> None:
        dados = DadosSolicitacao(
            tipo="segunda_via_certificado",
            turma="  Turma 6001  ",
            justificativa="  Necessito da segunda via.  ",
        )
        self.assertEqual(dados.turma, "Turma 6001")
        self.assertEqual(dados.justificativa, "Necessito da segunda via.")

    def test_rejeita_tipo_proibido_campos_ausentes_vazios_e_extras(self) -> None:
        invalidos = [
            {"tipo": "alteracao_nota", "turma": "6001", "justificativa": "x"},
            {"tipo": "segunda_via_certificado", "justificativa": "x"},
            {"tipo": "segunda_via_certificado", "turma": " ", "justificativa": "x"},
            {"tipo": "segunda_via_certificado", "turma": "6001"},
            {"tipo": "segunda_via_certificado", "turma": "6001", "justificativa": " "},
            {
                "tipo": "segunda_via_certificado",
                "turma": "6001",
                "justificativa": "x",
                "confirmado": True,
            },
        ]
        for entrada in invalidos:
            with self.subTest(entrada=entrada), self.assertRaises(ValidationError):
                DadosSolicitacao.model_validate(entrada)

    def test_dados_validos_sem_confirmacao_nao_escrevem(self) -> None:
        gestor = GestorRascunhos()
        gestor.preparar("sessao", self.dados)
        gestor.apresentar_resumo("sessao")
        self.assertEqual(self.quantidade(), 1)

    def test_confirmacao_sem_rascunho_nao_escreve(self) -> None:
        resposta = GestorRascunhos().processar_comando(
            "ausente", "CONFIRMAR", config=self.config
        )
        self.assertFalse(resposta.sucesso)
        self.assertEqual(self.quantidade(), 1)

    def test_confirmacao_antes_do_resumo_nao_escreve(self) -> None:
        gestor = GestorRascunhos()
        gestor.preparar("sessao", self.dados)
        resposta = gestor.processar_comando("sessao", "CONFIRMAR", config=self.config)
        self.assertFalse(resposta.sucesso)
        self.assertIn("resumo", resposta.erro)
        self.assertEqual(self.quantidade(), 1)

    def test_cancelar_descarta_sem_escrever(self) -> None:
        gestor = GestorRascunhos()
        gestor.preparar("sessao", self.dados)
        gestor.apresentar_resumo("sessao")
        resposta = gestor.processar_comando("sessao", "CANCELAR", config=self.config)
        repeticao = gestor.processar_comando("sessao", "CONFIRMAR", config=self.config)
        self.assertFalse(resposta.sucesso)
        self.assertFalse(repeticao.sucesso)
        self.assertEqual(self.quantidade(), 1)

    def test_invocacao_direta_da_tool_e_recusada_antes_do_sqlite(self) -> None:
        with (
            patch("instituto_horizonte.solicitacoes.sqlite3.connect") as conectar,
            self.assertRaises(ErroAutorizacao),
        ):
            registrar_solicitacao.invoke(self.dados.model_dump())
        conectar.assert_not_called()

    def test_registro_autorizado_persiste_aberto_e_preserva_sol_1001(self) -> None:
        resposta = self.confirmar(GestorRascunhos())

        self.assertTrue(resposta.sucesso)
        self.assertEqual(resposta.protocolo, "SOL-1002")
        self.assertEqual(resposta.status, "aberto")
        criado = consultar_protocolo_servico(resposta.protocolo, config=self.config)
        fixture = consultar_protocolo_servico("SOL-1001", config=self.config)
        self.assertTrue(criado.encontrado)
        self.assertEqual(criado.status, "aberto")
        self.assertEqual(criado.tipo, "segunda_via_certificado")
        self.assertEqual(fixture.status, "em_analise")

    def test_repeticao_da_confirmacao_retorna_mesmo_protocolo_sem_duplicar(self) -> None:
        gestor = GestorRascunhos(chave_factory=lambda: "chave-opaca-repetida")
        primeira = self.confirmar(gestor)
        segunda = gestor.processar_comando("sessao-a", "CONFIRMAR", config=self.config)

        self.assertEqual(primeira, segunda)
        self.assertEqual(self.quantidade(), 2)

    def test_repeticao_transacional_da_mesma_chave_e_dados_reutiliza_registro(self) -> None:
        chave = lambda: "chave-opaca-idempotente"
        primeiro_gestor = GestorRascunhos(chave_factory=chave)
        segundo_gestor = GestorRascunhos(chave_factory=chave)

        primeira = self.confirmar(primeiro_gestor, "primeira")
        segunda = self.confirmar(segundo_gestor, "segunda")

        self.assertTrue(primeira.sucesso)
        self.assertEqual(segunda, primeira)
        self.assertEqual(self.quantidade(), 2)

    def test_mesma_chave_com_dados_diferentes_retorna_conflito(self) -> None:
        chave = lambda: "chave-opaca-em-conflito"
        primeira = GestorRascunhos(chave_factory=chave)
        segunda = GestorRascunhos(chave_factory=chave)
        self.assertTrue(self.confirmar(primeira, "a").sucesso)
        diferentes = DadosSolicitacao(
            tipo="segunda_via_certificado",
            turma="Turma 7002",
            justificativa="Outro pedido.",
        )

        conflito = self.confirmar(segunda, "b", diferentes)

        self.assertFalse(conflito.sucesso)
        self.assertIn("idempotência", conflito.erro)
        self.assertEqual(self.quantidade(), 2)

    def test_falha_sqlite_faz_rollback_sem_sucesso_falso(self) -> None:
        conexao = sqlite3.connect(self.caminho)
        try:
            conexao.execute(
                """
                CREATE TRIGGER falhar_registro BEFORE INSERT ON solicitacoes
                WHEN NEW.origem = 'agente'
                BEGIN SELECT RAISE(ABORT, 'falha injetada'); END
                """
            )
            conexao.commit()
        finally:
            conexao.close()

        resposta = self.confirmar(GestorRascunhos())

        self.assertFalse(resposta.sucesso)
        self.assertIsNone(resposta.protocolo)
        self.assertIsNone(resposta.status)
        self.assertIn("IntegrityError", resposta.erro)
        self.assertEqual(self.quantidade(), 1)

    def test_rascunhos_de_sessoes_sao_isolados(self) -> None:
        gestor = GestorRascunhos()
        gestor.preparar("a", self.dados)
        gestor.apresentar_resumo("a")

        resposta_b = gestor.processar_comando("b", "CONFIRMAR", config=self.config)
        resposta_a = gestor.processar_comando("a", "CONFIRMAR", config=self.config)

        self.assertFalse(resposta_b.sucesso)
        self.assertTrue(resposta_a.sucesso)
        self.assertEqual(self.quantidade(), 2)

    def test_fluxo_nao_requer_groq_nem_rede(self) -> None:
        ambiente = {chave: valor for chave, valor in os.environ.items() if chave != "GROQ_API_KEY"}
        with (
            patch.dict(os.environ, ambiente, clear=True),
            patch.object(socket, "create_connection", side_effect=AssertionError("rede usada")),
        ):
            resposta = self.confirmar(GestorRascunhos())
        self.assertTrue(resposta.sucesso)


if __name__ == "__main__":
    unittest.main()
