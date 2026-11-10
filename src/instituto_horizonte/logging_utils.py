"""Auditoria JSONL local com schema fechado e sem conteúdo conversacional."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from instituto_horizonte.config import RAIZ_PROJETO


EventoNome = Literal[
    "turno_iniciado",
    "modelo_retry",
    "tool_concluida",
    "turno_concluido",
    "turno_com_erro",
]


class EventoAuditoria(BaseModel):
    """Campos permitidos no log; texto de usuário e respostas não existem aqui."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    timestamp_utc: str
    run_id: str
    turn_id: str
    session_id: str
    node: str
    evento: EventoNome
    status: str | None = None
    fontes: list[str] = Field(default_factory=list)
    fontes_recuperadas: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    tool: str | None = None
    resultado: str | None = None
    protocolo: str | None = None
    rodadas: int | None = Field(default=None, ge=0)
    duracao_ms: float | None = Field(default=None, ge=0)
    erro_tipo: str | None = None
    fim_motivo: str | None = None
    tentativa: int | None = Field(default=None, ge=1)


class Auditoria(Protocol):
    def criar_evento(self, **campos: object) -> EventoAuditoria: ...

    def registrar(self, evento: EventoAuditoria) -> bool: ...


class AuditoriaNula:
    """Implementação injetável para testes que não exercitam logs."""

    def criar_evento(self, **campos: object) -> EventoAuditoria:
        return EventoAuditoria(
            timestamp_utc=datetime.now(UTC).isoformat(),
            **campos,
        )

    def registrar(self, evento: EventoAuditoria) -> bool:
        del evento
        return True


class AuditoriaJSONL:
    """Escritor append-only; falhas de I/O nunca escapam para o fluxo do agente."""

    def __init__(
        self,
        log_dir: Path,
        *,
        nome_arquivo: str = "agent.jsonl",
        agora: Callable[[], datetime] | None = None,
    ) -> None:
        self.diretorio = (
            log_dir.resolve()
            if log_dir.is_absolute()
            else (RAIZ_PROJETO / log_dir).resolve()
        )
        self.caminho = self.diretorio / nome_arquivo
        self._agora = agora or (lambda: datetime.now(UTC))

    def criar_evento(self, **campos: object) -> EventoAuditoria:
        return EventoAuditoria(
            timestamp_utc=self._agora().astimezone(UTC).isoformat(),
            **campos,
        )

    def registrar(self, evento: EventoAuditoria) -> bool:
        try:
            self.diretorio.mkdir(parents=True, exist_ok=True)
            linha = json.dumps(
                evento.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            with self.caminho.open("a", encoding="utf-8", newline="\n") as arquivo:
                arquivo.write(linha + "\n")
            return True
        except (OSError, TypeError, ValueError):
            return False
