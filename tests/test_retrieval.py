"""Testes locais do Chroma com embeddings determinísticos, sem rede ou Groq."""

from __future__ import annotations

import hashlib
import os
import socket
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import chromadb
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from pydantic import ValidationError

from instituto_horizonte.config import Configuracao
from instituto_horizonte.ingest import IDS_OFICIAIS, carregar_documentos, preparar_documentos
from instituto_horizonte.retrieval import (
    NOME_COLECAO,
    ConsultaNormas,
    ErroRecuperacao,
    RespostaBuscaNormas,
    ResultadoNorma,
    buscar_normas,
    consultar_normas,
    indexar_documentos,
)
from scripts.evaluate_retrieval import carregar_perguntas


class EmbeddingsFalsos(Embeddings):
    """Embeddings estáveis derivados de SHA-256; não representam semântica real."""

    dimensao = 8

    @staticmethod
    def _vetor(texto: str) -> list[float]:
        digest = hashlib.sha256(texto.encode("utf-8")).digest()
        return [byte / 255 for byte in digest[: EmbeddingsFalsos.dimensao]]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vetor(texto) for texto in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vetor(text)


class EmbeddingsFalhos(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        del texts
        raise RuntimeError("falha falsa de embedding")

    def embed_query(self, text: str) -> list[float]:
        del text
        raise RuntimeError("falha falsa de embedding")


class RetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.diretorio = Path(self.temp.name) / "chroma"
        self.config = Configuracao.from_env(
            {
                "CHROMA_DIR": str(self.diretorio),
                "EMBEDDING_MODEL": "modelo-falso-deterministico",
                "RAG_TOP_K": "3",
            }
        )
        self.embeddings = EmbeddingsFalsos()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def indexar(self):
        return indexar_documentos(
            self.config,
            embeddings=self.embeddings,
            dimensao_embedding=self.embeddings.dimensao,
        )

    def consultar(self, consulta: str, top_k: int = 3):
        return consultar_normas(
            consulta,
            top_k,
            config=self.config,
            embeddings=self.embeddings,
            dimensao_embedding=self.embeddings.dimensao,
        )

    def test_cria_e_reabre_colecao_persistente(self) -> None:
        resultado = self.indexar()
        client_reaberto = chromadb.PersistentClient(path=str(self.diretorio))
        colecao = client_reaberto.get_collection(NOME_COLECAO)

        self.assertEqual(resultado.quantidade, 12)
        self.assertEqual(colecao.count(), 12)
        self.assertEqual(set(colecao.get(include=[])["ids"]), IDS_OFICIAIS)
        client_reaberto.close()

    def test_segunda_indexacao_nao_duplica(self) -> None:
        primeira = self.indexar()
        segunda = self.indexar()

        self.assertEqual(primeira.quantidade, 12)
        self.assertEqual(segunda.quantidade, 12)
        self.assertEqual(primeira.ids, segunda.ids)

    def test_preserva_ids_metadados_e_modelo_da_colecao(self) -> None:
        self.indexar()
        client = chromadb.PersistentClient(path=str(self.diretorio))
        colecao = client.get_collection(NOME_COLECAO)
        registro = colecao.get(ids=["ACAD-001"], include=["metadatas", "documents"])
        metadata = registro["metadatas"][0]

        self.assertEqual(metadata["id"], "ACAD-001")
        self.assertEqual(metadata["fonte"], "ACAD-001")
        self.assertIn("titulo", metadata)
        self.assertIn("categoria", metadata)
        self.assertIn("instituicao", metadata)
        self.assertIn("hash_conteudo", metadata)
        self.assertIn("conteudo_original", metadata)
        self.assertEqual(colecao.metadata["embedding_model"], self.config.embedding_model)
        self.assertEqual(colecao.metadata["embedding_dimension"], self.embeddings.dimensao)
        client.close()

    def test_recupera_conteudo_persistido_e_distancia_bruta(self) -> None:
        self.indexar()
        primeiro = preparar_documentos(carregar_documentos())[0]
        resposta = self.consultar(primeiro.texto_embedding, top_k=1)

        self.assertEqual(resposta.total, 1)
        self.assertEqual(resposta.resultados[0].id, "ACAD-001")
        self.assertEqual(resposta.resultados[0].conteudo, primeiro.conteudo_original)
        self.assertIsNone(resposta.resultados[0].relevancia)
        self.assertIsInstance(resposta.resultados[0].distancia, float)

    def test_valida_top_k(self) -> None:
        for invalido in (0, 6):
            with self.subTest(top_k=invalido), self.assertRaises(ValidationError):
                ConsultaNormas(consulta="pergunta", top_k=invalido)

    def test_rejeita_consulta_vazia(self) -> None:
        for consulta in ("", "   "):
            with self.subTest(consulta=consulta), self.assertRaises(ValidationError):
                ConsultaNormas(consulta=consulta)

    def test_rejeita_colecao_inexistente(self) -> None:
        with self.assertRaisesRegex(ErroRecuperacao, "não inicializada"):
            self.consultar("pergunta")

    def test_rejeita_colecao_vazia(self) -> None:
        client = chromadb.PersistentClient(path=str(self.diretorio))
        client.create_collection(
            NOME_COLECAO,
            metadata={
                "embedding_model": self.config.embedding_model,
                "embedding_dimension": self.embeddings.dimensao,
                "schema_version": 1,
                "hnsw:space": "cosine",
            },
        )
        client.close()

        with self.assertRaisesRegex(ErroRecuperacao, "está vazia"):
            self.consultar("pergunta")

    def test_rejeita_modelo_incompativel_mesmo_com_mesma_dimensao(self) -> None:
        self.indexar()
        config_incompativel = Configuracao.from_env(
            {
                "CHROMA_DIR": str(self.diretorio),
                "EMBEDDING_MODEL": "outro-modelo-mesma-dimensao",
            }
        )

        with self.assertRaisesRegex(ErroRecuperacao, "Coleção incompatível"):
            indexar_documentos(
                config_incompativel,
                embeddings=self.embeddings,
                dimensao_embedding=self.embeddings.dimensao,
            )

        client = chromadb.PersistentClient(path=str(self.diretorio))
        self.assertEqual(client.get_collection(NOME_COLECAO).count(), 12)
        client.close()

    def test_embedding_com_falha_retorna_erro_controlado(self) -> None:
        with self.assertRaisesRegex(ErroRecuperacao, "Falha ao indexar"):
            indexar_documentos(
                self.config,
                embeddings=EmbeddingsFalhos(),
                dimensao_embedding=self.embeddings.dimensao,
            )

    def test_erro_de_armazenamento_e_controlado(self) -> None:
        with (
            patch.object(Chroma, "add_documents", side_effect=OSError("falha falsa")),
            self.assertRaisesRegex(ErroRecuperacao, "Falha ao indexar"),
        ):
            self.indexar()

    def test_fluxo_local_nao_requer_groq_nem_rede(self) -> None:
        ambiente = {chave: valor for chave, valor in os.environ.items() if chave != "GROQ_API_KEY"}
        with (
            patch.dict(os.environ, ambiente, clear=True),
            patch.object(socket, "create_connection", side_effect=AssertionError("rede usada")),
        ):
            self.indexar()
            resposta = self.consultar("consulta local", top_k=2)

        self.assertEqual(resposta.total, 2)


class ContratoToolTests(unittest.TestCase):
    def test_contratos_pydantic_da_tool(self) -> None:
        resposta = RespostaBuscaNormas(
            resultados=[
                ResultadoNorma(
                    id="ACAD-001",
                    titulo="Título",
                    categoria="documentos",
                    fonte="ACAD-001",
                    conteudo="Conteúdo",
                    relevancia=None,
                    distancia=0.25,
                )
            ],
            total=1,
        )
        with patch(
            "instituto_horizonte.retrieval.consultar_normas",
            return_value=resposta,
        ) as consulta_mock:
            saida = buscar_normas.invoke({"consulta": "declaração", "top_k": 1})

        self.assertEqual(saida["total"], 1)
        self.assertEqual(saida["resultados"][0]["fonte"], "ACAD-001")
        consulta_mock.assert_called_once_with("declaração", 1)

    def test_tool_rejeita_argumentos_invalidos(self) -> None:
        with self.assertRaises(ValidationError):
            buscar_normas.invoke({"consulta": "", "top_k": 3})

    def test_avaliador_preserva_perguntas_do_csv_com_bom(self) -> None:
        perguntas = carregar_perguntas()

        self.assertEqual(len(perguntas), 10)
        self.assertEqual(
            perguntas["T01"],
            "Qual é o prazo para emitir a declaração de matrícula?",
        )


if __name__ == "__main__":
    unittest.main()
