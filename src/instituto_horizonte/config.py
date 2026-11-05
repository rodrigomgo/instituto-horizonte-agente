"""Configuração tipada e carregamento explícito do ``.env`` local."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator


RAIZ_PROJETO = Path(__file__).resolve().parents[2]


def caminho_dotenv(raiz_projeto: Path | None = None) -> Path:
    """Resolve o ``.env`` a partir da raiz, nunca do diretório corrente."""

    raiz = RAIZ_PROJETO if raiz_projeto is None else raiz_projeto
    return raiz.resolve() / ".env"


def carregar_dotenv_projeto(raiz_projeto: Path | None = None) -> bool:
    """Carrega explicitamente o ``.env``; o ambiente existente tem prioridade."""

    return load_dotenv(dotenv_path=caminho_dotenv(raiz_projeto), override=False)


class Configuracao(BaseModel):
    """Configurações previstas pelos documentos SDD.

    A chave Groq é opcional na configuração geral e exigida somente pelos
    comandos que realizam integração externa.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    groq_api_key: SecretStr | None = None
    groq_model: str = Field(default="openai/gpt-oss-120b", min_length=1)
    embedding_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        min_length=1,
    )
    chroma_dir: Path = Path(".local/chroma")
    sqlite_path: Path = Path(".local/protocolos.sqlite3")
    rag_top_k: int = Field(default=3, ge=1, le=5)
    max_agent_rounds: int = Field(default=6, ge=1, le=50)
    log_dir: Path = Path("artifacts/logs")

    @field_validator("groq_api_key", mode="before")
    @classmethod
    def normalizar_chave_vazia(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("groq_model", "embedding_model", mode="before")
    @classmethod
    def rejeitar_texto_em_branco(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
        return value

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Configuracao:
        """Cria configuração a partir do mapping informado ou do ambiente atual.

        Esta função não carrega ``.env`` implicitamente. Os pontos de entrada
        devem chamar :func:`carregar_dotenv_projeto` quando desejarem esse apoio.
        """

        source = os.environ if environ is None else environ
        mapping = {
            "GROQ_API_KEY": "groq_api_key",
            "GROQ_MODEL": "groq_model",
            "EMBEDDING_MODEL": "embedding_model",
            "CHROMA_DIR": "chroma_dir",
            "SQLITE_PATH": "sqlite_path",
            "RAG_TOP_K": "rag_top_k",
            "MAX_AGENT_ROUNDS": "max_agent_rounds",
            "LOG_DIR": "log_dir",
        }
        values: dict[str, Any] = {
            field_name: source[env_name]
            for env_name, field_name in mapping.items()
            if env_name in source
        }
        return cls.model_validate(values)

    def resumo_seguro(self) -> dict[str, str | int | bool]:
        """Retorna dados operacionais sem revelar o valor da chave de API."""

        return {
            "groq_api_key_configurada": self.groq_api_key is not None,
            "groq_model": self.groq_model,
            "embedding_model": self.embedding_model,
            "chroma_dir": str(self.chroma_dir),
            "sqlite_path": str(self.sqlite_path),
            "rag_top_k": self.rag_top_k,
            "max_agent_rounds": self.max_agent_rounds,
            "log_dir": str(self.log_dir),
        }


def formatar_erros_configuracao(error: ValidationError) -> str:
    """Produz erros legíveis sem ecoar entradas potencialmente sensíveis."""

    mensagens = []
    for item in error.errors(include_input=False, include_url=False):
        campo = ".".join(str(part) for part in item["loc"])
        mensagens.append(f"{campo}: {item['msg']}")
    return "; ".join(mensagens)
