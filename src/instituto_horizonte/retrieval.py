"""Indexação Chroma, recuperação semântica e Tool ``buscar_normas``."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Any, Annotated

import chromadb
from fastembed import TextEmbedding
from langchain_chroma import Chroma
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from instituto_horizonte.config import Configuracao, RAIZ_PROJETO
from instituto_horizonte.ingest import (
    IDS_OFICIAIS,
    DocumentoPreparado,
    carregar_documentos,
    preparar_documentos,
)


LOGGER = logging.getLogger(__name__)
NOME_COLECAO = "instituto_horizonte_normas"
VERSAO_SCHEMA_COLECAO = 1
CHAVES_AMBIENTE_RAG = ("EMBEDDING_MODEL", "CHROMA_DIR", "RAG_TOP_K")
ConsultaTexto = Annotated[str, StringConstraints(min_length=1, max_length=500)]


class ErroRecuperacao(RuntimeError):
    """Falha controlada de embedding, persistência ou consulta."""


class ConsultaNormas(BaseModel):
    """Entrada tipada da Tool de recuperação."""

    model_config = ConfigDict(extra="forbid", strict=True)

    consulta: ConsultaTexto
    top_k: int = Field(default=3, ge=1, le=5)

    @field_validator("consulta")
    @classmethod
    def rejeitar_consulta_vazia(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("consulta não pode ser vazia")
        return valor


class ResultadoNorma(BaseModel):
    """Documento real recuperado do índice."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    id: str
    titulo: str
    categoria: str
    fonte: str
    conteudo: str
    relevancia: float | None = None
    distancia: float | None = Field(default=None, ge=0)


class RespostaBuscaNormas(BaseModel):
    """Saída tipada da Tool ``buscar_normas``."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    resultados: list[ResultadoNorma]
    total: int = Field(ge=0)


class ResultadoIndexacao(BaseModel):
    """Resumo verificável de uma indexação."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    quantidade: int
    ids: list[str]
    colecao: str
    modelo_embedding: str
    dimensao_embedding: int
    diretorio: str


def configuracao_rag_do_ambiente(
    environ: Mapping[str, str] | None = None,
) -> Configuracao:
    """Lê somente variáveis não secretas necessárias ao RAG."""

    origem = os.environ if environ is None else environ
    filtrado = {chave: origem[chave] for chave in CHAVES_AMBIENTE_RAG if chave in origem}
    return Configuracao.from_env(filtrado)


def resolver_diretorio_chroma(caminho: Path) -> Path:
    """Resolve caminhos relativos a partir da raiz do projeto."""

    if caminho.is_absolute():
        return caminho.resolve()
    resolvido = (RAIZ_PROJETO / caminho).resolve()
    try:
        resolvido.relative_to(RAIZ_PROJETO.resolve())
    except ValueError:
        raise ErroRecuperacao(
            "CHROMA_DIR relativo deve permanecer dentro da raiz do projeto."
        ) from None
    return resolvido


def obter_modelo_suportado(nome_modelo: str) -> dict[str, Any]:
    """Confirma modelo e dimensão no catálogo da versão instalada."""

    modelo = next(
        (
            item
            for item in TextEmbedding.list_supported_models()
            if item.get("model") == nome_modelo
        ),
        None,
    )
    if modelo is None:
        raise ErroRecuperacao(
            f"Modelo de embedding não suportado pela versão instalada: {nome_modelo}."
        )
    dimensao = modelo.get("dim")
    if not isinstance(dimensao, int) or dimensao <= 0:
        raise ErroRecuperacao("Catálogo FastEmbed não informou dimensão válida.")
    return modelo


@lru_cache(maxsize=4)
def criar_embeddings_fastembed(nome_modelo: str) -> tuple[Embeddings, int]:
    """Cria o adapter LangChain/FastEmbed com cache local ignorado pelo Git."""

    info = obter_modelo_suportado(nome_modelo)
    cache = RAIZ_PROJETO / ".local" / "fastembed_cache"
    try:
        embeddings = FastEmbedEmbeddings(
            model_name=nome_modelo,
            cache_dir=str(cache),
            doc_embed_type="default",
        )
    except Exception as error:
        raise ErroRecuperacao(
            f"Falha ao inicializar FastEmbed ({type(error).__name__}). "
            "Verifique conexão no primeiro download e o cache local."
        ) from None
    return embeddings, int(info["dim"])


def _metadata_colecao(nome_modelo: str, dimensao: int) -> dict[str, str | int]:
    return {
        "embedding_model": nome_modelo,
        "embedding_dimension": dimensao,
        "schema_version": VERSAO_SCHEMA_COLECAO,
        "hnsw:space": "cosine",
    }


def _validar_compatibilidade(
    metadata: Mapping[str, Any] | None,
    nome_modelo: str,
    dimensao: int,
    configuracao_colecao: Mapping[str, Any] | None = None,
) -> None:
    esperada = _metadata_colecao(nome_modelo, dimensao)
    if metadata is None:
        raise ErroRecuperacao("Coleção existente não possui metadata de compatibilidade.")
    for chave in ("embedding_model", "embedding_dimension", "schema_version"):
        if metadata.get(chave) != esperada[chave]:
            raise ErroRecuperacao(
                "Coleção incompatível com o modelo, dimensão ou schema configurado. "
                "Use outro CHROMA_DIR ou reindexe explicitamente; nenhum dado foi apagado."
            )
    hnsw = configuracao_colecao.get("hnsw") if configuracao_colecao else None
    espaco_efetivo = hnsw.get("space") if isinstance(hnsw, Mapping) else None
    if espaco_efetivo is None:
        espaco_efetivo = metadata.get("hnsw:space")
    if espaco_efetivo != "cosine":
        raise ErroRecuperacao(
            "Coleção incompatível: a métrica vetorial efetiva deve ser cosine. "
            "Use outro CHROMA_DIR ou reindexe explicitamente; nenhum dado foi apagado."
        )


def _cliente_chroma(diretorio: Path) -> chromadb.ClientAPI:
    try:
        return chromadb.PersistentClient(path=str(diretorio))
    except Exception as error:
        raise ErroRecuperacao(
            f"Falha ao abrir armazenamento Chroma ({type(error).__name__})."
        ) from None


def _nomes_colecoes(client: chromadb.ClientAPI) -> set[str]:
    try:
        return {colecao.name for colecao in client.list_collections()}
    except Exception as error:
        raise ErroRecuperacao(
            f"Falha ao listar coleções Chroma ({type(error).__name__})."
        ) from None


def _fechar_cliente(client: chromadb.ClientAPI) -> None:
    """Libera arquivos persistentes sem apagar coleções ou dados."""

    fechar = getattr(client, "close", None)
    if callable(fechar):
        try:
            fechar()
        except Exception as error:
            LOGGER.warning("falha ao fechar Chroma tipo=%s", type(error).__name__)


def _documento_langchain(documento: DocumentoPreparado) -> Document:
    metadata = documento.metadados.model_dump()
    metadata["conteudo_original"] = documento.conteudo_original
    return Document(page_content=documento.texto_embedding, metadata=metadata)


def indexar_documentos(
    config: Configuracao,
    *,
    embeddings: Embeddings | None = None,
    dimensao_embedding: int | None = None,
) -> ResultadoIndexacao:
    """Indexa por upsert e verifica os 12 IDs persistidos sem apagar dados."""

    try:
        preparados = preparar_documentos(carregar_documentos())
    except Exception as error:
        raise ErroRecuperacao(
            f"Falha ao validar documentos antes da persistência ({type(error).__name__})."
        ) from None

    diretorio = resolver_diretorio_chroma(config.chroma_dir)
    if embeddings is None:
        embeddings, dimensao = criar_embeddings_fastembed(config.embedding_model)
    else:
        if dimensao_embedding is None or dimensao_embedding <= 0:
            raise ErroRecuperacao("Dimensão deve ser informada para embeddings injetados.")
        dimensao = dimensao_embedding

    client = _cliente_chroma(diretorio)
    metadata_esperada = _metadata_colecao(config.embedding_model, dimensao)
    try:
        nomes = _nomes_colecoes(client)
        if NOME_COLECAO in nomes:
            colecao = client.get_collection(NOME_COLECAO)
            _validar_compatibilidade(
                colecao.metadata,
                config.embedding_model,
                dimensao,
                colecao.configuration,
            )
        else:
            colecao = client.create_collection(
                NOME_COLECAO,
                metadata=metadata_esperada,
            )

        vectorstore = Chroma(
            client=client,
            collection_name=NOME_COLECAO,
            embedding_function=embeddings,
            create_collection_if_not_exists=False,
        )
        vectorstore.add_documents(
            documents=[_documento_langchain(documento) for documento in preparados],
            ids=[documento.id_estavel for documento in preparados],
        )
        persistidos = colecao.get(include=[])
        ids = sorted(persistidos["ids"])
        quantidade = colecao.count()
    except ErroRecuperacao:
        raise
    except Exception as error:
        raise ErroRecuperacao(
            f"Falha ao indexar documentos no Chroma ({type(error).__name__})."
        ) from None
    finally:
        _fechar_cliente(client)

    if quantidade != 12 or set(ids) != IDS_OFICIAIS:
        raise ErroRecuperacao(
            "Coleção contém quantidade ou IDs inesperados; nenhum dado foi apagado."
        )
    return ResultadoIndexacao(
        quantidade=quantidade,
        ids=ids,
        colecao=NOME_COLECAO,
        modelo_embedding=config.embedding_model,
        dimensao_embedding=dimensao,
        diretorio=str(diretorio),
    )


def consultar_normas(
    consulta: str,
    top_k: int = 3,
    *,
    config: Configuracao | None = None,
    embeddings: Embeddings | None = None,
    dimensao_embedding: int | None = None,
) -> RespostaBuscaNormas:
    """Consulta documentos reais e preserva a distância bruta do Chroma."""

    entrada = ConsultaNormas(consulta=consulta, top_k=top_k)
    config = configuracao_rag_do_ambiente() if config is None else config
    diretorio = resolver_diretorio_chroma(config.chroma_dir)
    client = _cliente_chroma(diretorio)
    try:
        if NOME_COLECAO not in _nomes_colecoes(client):
            raise ErroRecuperacao(
                "Coleção acadêmica não inicializada; execute scripts/index_documents.py."
            )
        colecao = client.get_collection(NOME_COLECAO)
        if colecao.count() == 0:
            raise ErroRecuperacao("Coleção acadêmica está vazia; execute a indexação.")

        if embeddings is None:
            embeddings, dimensao = criar_embeddings_fastembed(config.embedding_model)
        else:
            if dimensao_embedding is None or dimensao_embedding <= 0:
                raise ErroRecuperacao("Dimensão deve ser informada para embeddings injetados.")
            dimensao = dimensao_embedding
        _validar_compatibilidade(
            colecao.metadata,
            config.embedding_model,
            dimensao,
            colecao.configuration,
        )

        vectorstore = Chroma(
            client=client,
            collection_name=NOME_COLECAO,
            embedding_function=embeddings,
            create_collection_if_not_exists=False,
        )
        inicio = perf_counter()
        encontrados = vectorstore.similarity_search_with_score(
            entrada.consulta,
            k=entrada.top_k,
        )
        duracao_ms = (perf_counter() - inicio) * 1000
    except ErroRecuperacao:
        raise
    except Exception as error:
        raise ErroRecuperacao(
            f"Falha na recuperação semântica ({type(error).__name__})."
        ) from None
    finally:
        _fechar_cliente(client)

    resultados: list[ResultadoNorma] = []
    try:
        for documento, distancia in encontrados:
            metadata = documento.metadata
            resultados.append(
                ResultadoNorma(
                    id=str(metadata["id"]),
                    titulo=str(metadata["titulo"]),
                    categoria=str(metadata["categoria"]),
                    fonte=str(metadata["fonte"]),
                    conteudo=str(metadata["conteudo_original"]),
                    relevancia=None,
                    distancia=float(distancia),
                )
            )
    except (KeyError, TypeError, ValueError) as error:
        raise ErroRecuperacao(
            f"Documento persistido possui metadata inválida ({type(error).__name__})."
        ) from None

    LOGGER.info(
        "retrieval concluído ids=%s quantidade=%d top_k=%d duracao_ms=%.3f",
        [resultado.id for resultado in resultados],
        len(resultados),
        entrada.top_k,
        duracao_ms,
    )
    return RespostaBuscaNormas(resultados=resultados, total=len(resultados))


@tool("buscar_normas", args_schema=ConsultaNormas)
def buscar_normas(consulta: str, top_k: int = 3) -> dict[str, Any]:
    """Busca normas acadêmicas oficiais por similaridade semântica."""

    return consultar_normas(consulta, top_k).model_dump(mode="json")
