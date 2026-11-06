"""Testes do loader acadêmico sem alterar a base oficial ou acessar rede."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from instituto_horizonte.ingest import (
    CAMINHO_BASE_OFICIAL,
    IDS_OFICIAIS,
    ErroIngestao,
    calcular_hash_conteudo,
    carregar_documentos,
    preparar_documentos,
)


RAIZ_PROJETO = Path(__file__).resolve().parents[1]


def ler_registros_oficiais() -> list[dict[str, str]]:
    dados = json.loads(CAMINHO_BASE_OFICIAL.read_text(encoding="utf-8"))
    assert isinstance(dados, list)
    return dados


def escrever_json(caminho: Path, dados: object) -> None:
    caminho.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class IngestaoBaseOficialTests(unittest.TestCase):
    def test_carrega_os_12_documentos_oficiais(self) -> None:
        documentos = carregar_documentos()

        self.assertEqual(len(documentos), 12)
        self.assertEqual({documento.id for documento in documentos}, IDS_OFICIAIS)

    def test_preserva_todos_os_valores_originais(self) -> None:
        registros = ler_registros_oficiais()
        documentos = carregar_documentos()

        self.assertEqual(
            [documento.model_dump() for documento in documentos],
            registros,
        )

    def test_ids_e_fontes_sao_unicos_e_correspondentes(self) -> None:
        documentos = carregar_documentos()
        ids = [documento.id for documento in documentos]
        fontes = [documento.fonte for documento in documentos]

        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(fontes), len(set(fontes)))
        self.assertTrue(all(documento.id == documento.fonte for documento in documentos))

    def test_preparacao_preserva_conteudo_e_metadados(self) -> None:
        documentos = carregar_documentos()
        preparados = preparar_documentos(documentos)

        self.assertEqual(len(preparados), len(documentos))
        for original, preparado in zip(documentos, preparados, strict=True):
            self.assertEqual(preparado.id_estavel, original.id)
            self.assertEqual(preparado.conteudo_original, original.conteudo)
            self.assertEqual(preparado.metadados.id, original.id)
            self.assertEqual(preparado.metadados.fonte, original.fonte)
            self.assertEqual(preparado.metadados.categoria, original.categoria)
            self.assertEqual(preparado.metadados.titulo, original.titulo)
            self.assertEqual(preparado.metadados.instituicao, original.instituicao)

    def test_execucoes_repetidas_sao_deterministicas(self) -> None:
        primeira = preparar_documentos(carregar_documentos())
        segunda = preparar_documentos(carregar_documentos())

        self.assertEqual(primeira, segunda)
        self.assertEqual(
            [documento.model_dump() for documento in primeira],
            [documento.model_dump() for documento in segunda],
        )

    def test_hash_sha256_usa_conteudo_utf8_literal(self) -> None:
        documento = carregar_documentos()[0]
        esperado = hashlib.sha256(documento.conteudo.encode("utf-8")).hexdigest()
        preparado = preparar_documentos([documento])[0]

        self.assertEqual(calcular_hash_conteudo(documento.conteudo), esperado)
        self.assertEqual(preparado.hash_conteudo, esperado)
        self.assertEqual(preparado.metadados.hash_conteudo, esperado)


class IngestaoDadosInvalidosTests(unittest.TestCase):
    def executar_com_dados(self, dados: object) -> list[object]:
        with TemporaryDirectory() as diretorio:
            caminho = Path(diretorio) / "base.json"
            escrever_json(caminho, dados)
            return carregar_documentos(caminho)

    def test_rejeita_id_duplicado(self) -> None:
        registros = deepcopy(ler_registros_oficiais())
        registros[1]["id"] = registros[0]["id"]

        with self.assertRaisesRegex(ErroIngestao, "Valores duplicados em id: ACAD-001"):
            self.executar_com_dados(registros)

    def test_rejeita_fonte_duplicada(self) -> None:
        registros = deepcopy(ler_registros_oficiais())
        registros[1]["fonte"] = registros[0]["fonte"]

        with self.assertRaisesRegex(ErroIngestao, "Valores duplicados em fonte: ACAD-001"):
            self.executar_com_dados(registros)

    def test_rejeita_id_e_fonte_sem_correspondencia(self) -> None:
        registros = deepcopy(ler_registros_oficiais())
        registros[0]["fonte"] = "ACAD-013"

        with self.assertRaisesRegex(ErroIngestao, "id e fonte não correspondem"):
            self.executar_com_dados(registros)

    def test_rejeita_campo_obrigatorio_ausente(self) -> None:
        registros = deepcopy(ler_registros_oficiais())
        del registros[3]["titulo"]

        with self.assertRaisesRegex(ErroIngestao, r"registro 4.*titulo.*Field required"):
            self.executar_com_dados(registros)

    def test_rejeita_conteudo_vazio(self) -> None:
        registros = deepcopy(ler_registros_oficiais())
        registros[4]["conteudo"] = "   "

        with self.assertRaisesRegex(ErroIngestao, r"registro 5.*conteudo.*não pode ser vazio"):
            self.executar_com_dados(registros)

    def test_rejeita_id_fora_do_formato(self) -> None:
        registros = deepcopy(ler_registros_oficiais())
        registros[0]["id"] = "acad-1"

        with self.assertRaisesRegex(ErroIngestao, r"registro 1.*id.*pattern"):
            self.executar_com_dados(registros)

    def test_rejeita_registro_extra_e_id_nao_oficial(self) -> None:
        registros = deepcopy(ler_registros_oficiais())
        extra = deepcopy(registros[-1])
        extra["id"] = "ACAD-013"
        extra["fonte"] = "ACAD-013"
        registros.append(extra)

        with self.assertRaisesRegex(ErroIngestao, r"inesperados: ACAD-013"):
            self.executar_com_dados(registros)

    def test_rejeita_registro_oficial_ausente(self) -> None:
        registros = deepcopy(ler_registros_oficiais())[:-1]

        with self.assertRaisesRegex(ErroIngestao, r"ausentes: ACAD-012"):
            self.executar_com_dados(registros)

    def test_rejeita_raiz_que_nao_e_lista(self) -> None:
        with self.assertRaisesRegex(ErroIngestao, "raiz do JSON deve ser uma lista"):
            self.executar_com_dados({"documentos": ler_registros_oficiais()})

    def test_rejeita_json_malformado(self) -> None:
        with TemporaryDirectory() as diretorio:
            caminho = Path(diretorio) / "invalido.json"
            caminho.write_text('[{"id": "ACAD-001"}', encoding="utf-8")

            with self.assertRaisesRegex(ErroIngestao, r"JSON malformado na linha 1"):
                carregar_documentos(caminho)

    def test_rejeita_bytes_utf8_invalidos_com_erro_controlado(self) -> None:
        with TemporaryDirectory() as diretorio:
            caminho = Path(diretorio) / "utf8-invalido.json"
            caminho.write_bytes(b"[\xff]")

            with self.assertRaises(ErroIngestao) as context:
                carregar_documentos(caminho)

        self.assertEqual(
            str(context.exception),
            "Arquivo da base não contém texto UTF-8 válido.",
        )
        self.assertIsNone(context.exception.__cause__)

    def test_trata_arquivo_inexistente(self) -> None:
        with TemporaryDirectory() as diretorio:
            caminho = Path(diretorio) / "nao-existe.json"

            with self.assertRaisesRegex(ErroIngestao, "Arquivo da base não encontrado"):
                carregar_documentos(caminho)

    def test_erro_de_schema_nao_expoe_conteudo_do_registro(self) -> None:
        segredo_falso = "dado-privado-nao-deve-aparecer"
        registros = deepcopy(ler_registros_oficiais())
        registros[0]["conteudo"] = segredo_falso
        registros[0]["titulo"] = 123

        with self.assertRaises(ErroIngestao) as context:
            self.executar_com_dados(registros)

        self.assertNotIn(segredo_falso, str(context.exception))


class ScriptValidacaoTests(unittest.TestCase):
    def test_script_funciona_sem_chave_e_sem_rede(self) -> None:
        ambiente = os.environ.copy()
        ambiente.pop("GROQ_API_KEY", None)
        ambiente["PYTHONIOENCODING"] = "utf-8"
        script = RAIZ_PROJETO / "scripts" / "validate_documents.py"

        with TemporaryDirectory() as diretorio:
            resultado = subprocess.run(
                [sys.executable, str(script)],
                cwd=diretorio,
                env=ambiente,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                timeout=15,
            )

        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("Base acadêmica válida.", resultado.stdout)
        self.assertIn('"quantidade": 12', resultado.stdout)
        self.assertNotIn("GROQ_API_KEY", resultado.stdout)


if __name__ == "__main__":
    unittest.main()
