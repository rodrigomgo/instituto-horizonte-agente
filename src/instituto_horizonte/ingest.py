"""Carregamento e preparação determinística da base acadêmica oficial."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, field_validator

from instituto_horizonte.config import RAIZ_PROJETO


CAMINHO_BASE_OFICIAL = RAIZ_PROJETO / "data" / "base_conhecimento_academica.json"
IDS_OFICIAIS = frozenset(f"ACAD-{numero:03d}" for numero in range(1, 13))
IdentificadorAcademico = Annotated[str, StringConstraints(pattern=r"^ACAD-\d{3}$")]


class ErroIngestao(ValueError):
    """Erro controlado da leitura ou validação da base acadêmica."""


class DocumentoAcademico(BaseModel):
    """Registro canônico da base, sem normalização dos valores originais."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: IdentificadorAcademico
    titulo: str
    categoria: str
    fonte: IdentificadorAcademico
    conteudo: str
    instituicao: str

    @field_validator("titulo", "categoria", "conteudo", "instituicao")
    @classmethod
    def rejeitar_texto_vazio(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("campo obrigatório não pode ser vazio")
        return valor


class MetadadosDocumento(BaseModel):
    """Metadados estáveis destinados à futura coleção vetorial."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: IdentificadorAcademico
    fonte: IdentificadorAcademico
    categoria: str
    titulo: str
    instituicao: str
    hash_conteudo: str = Field(pattern=r"^[0-9a-f]{64}$")


class DocumentoPreparado(BaseModel):
    """Representação intermediária, ainda sem embedding ou banco vetorial."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id_estavel: IdentificadorAcademico
    texto_embedding: str
    conteudo_original: str
    metadados: MetadadosDocumento
    hash_conteudo: str = Field(pattern=r"^[0-9a-f]{64}$")


def _formatar_erros_schema(error: ValidationError) -> str:
    problemas: list[str] = []
    for item in error.errors(include_input=False, include_url=False):
        localizacao = item["loc"]
        if localizacao and isinstance(localizacao[0], int):
            registro = f"registro {localizacao[0] + 1}"
            campo = ".".join(str(parte) for parte in localizacao[1:])
        else:
            registro = "raiz"
            campo = ".".join(str(parte) for parte in localizacao)
        alvo = f"{registro}.{campo}" if campo else registro
        problemas.append(f"{alvo}: {item['msg']}")
    return "; ".join(problemas)


def _validar_unicidade(documentos: list[DocumentoAcademico], campo: str) -> None:
    valores = [getattr(documento, campo) for documento in documentos]
    duplicados = sorted(valor for valor, total in Counter(valores).items() if total > 1)
    if duplicados:
        raise ErroIngestao(f"Valores duplicados em {campo}: {', '.join(duplicados)}.")


def _validar_conjunto_oficial(documentos: list[DocumentoAcademico]) -> None:
    for indice, documento in enumerate(documentos, start=1):
        if documento.id != documento.fonte:
            raise ErroIngestao(
                f"Registro {indice}: id e fonte não correspondem "
                f"({documento.id} != {documento.fonte})."
            )

    ids = {documento.id for documento in documentos}
    ausentes = sorted(IDS_OFICIAIS - ids)
    inesperados = sorted(ids - IDS_OFICIAIS)
    if len(documentos) != len(IDS_OFICIAIS) or ausentes or inesperados:
        detalhes = [f"esperados 12 registros, recebidos {len(documentos)}"]
        if ausentes:
            detalhes.append(f"ausentes: {', '.join(ausentes)}")
        if inesperados:
            detalhes.append(f"inesperados: {', '.join(inesperados)}")
        raise ErroIngestao("Conjunto oficial inválido: " + "; ".join(detalhes) + ".")


def carregar_documentos(caminho: Path = CAMINHO_BASE_OFICIAL) -> list[DocumentoAcademico]:
    """Lê e valida integralmente a fonte canônica em UTF-8."""

    try:
        texto = caminho.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ErroIngestao(f"Arquivo da base não encontrado: {caminho}.") from None
    except OSError as error:
        raise ErroIngestao(
            f"Não foi possível ler o arquivo da base ({type(error).__name__})."
        ) from None

    try:
        dados: Any = json.loads(texto)
    except json.JSONDecodeError as error:
        raise ErroIngestao(
            f"JSON malformado na linha {error.lineno}, coluna {error.colno}."
        ) from None

    if not isinstance(dados, list):
        raise ErroIngestao("A raiz do JSON deve ser uma lista de documentos.")

    documentos: list[DocumentoAcademico] = []
    problemas: list[str] = []
    for indice, registro in enumerate(dados):
        try:
            documentos.append(DocumentoAcademico.model_validate(registro))
        except ValidationError as error:
            erros = _formatar_erros_schema(error)
            # Ajusta o índice local do model para a posição real na lista.
            problemas.append(f"registro {indice + 1}: {erros.replace('raiz.', '')}")
    if problemas:
        raise ErroIngestao("Registros inválidos: " + "; ".join(problemas) + ".")

    _validar_unicidade(documentos, "id")
    _validar_unicidade(documentos, "fonte")
    _validar_conjunto_oficial(documentos)
    return documentos


def calcular_hash_conteudo(conteudo: str) -> str:
    """Calcula SHA-256 dos bytes UTF-8 do conteúdo literal."""

    return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()


def preparar_documento(documento: DocumentoAcademico) -> DocumentoPreparado:
    """Converte um registro canônico em uma unidade determinística de indexação."""

    hash_conteudo = calcular_hash_conteudo(documento.conteudo)
    texto_embedding = (
        f"Título: {documento.titulo}\n"
        f"Categoria: {documento.categoria}\n"
        f"Conteúdo: {documento.conteudo}"
    )
    metadados = MetadadosDocumento(
        id=documento.id,
        fonte=documento.fonte,
        categoria=documento.categoria,
        titulo=documento.titulo,
        instituicao=documento.instituicao,
        hash_conteudo=hash_conteudo,
    )
    return DocumentoPreparado(
        id_estavel=documento.id,
        texto_embedding=texto_embedding,
        conteudo_original=documento.conteudo,
        metadados=metadados,
        hash_conteudo=hash_conteudo,
    )


def preparar_documentos(
    documentos: list[DocumentoAcademico],
) -> list[DocumentoPreparado]:
    """Prepara um documento por registro, preservando a ordem canônica."""

    return [preparar_documento(documento) for documento in documentos]
