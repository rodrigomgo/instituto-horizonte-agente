"""Comando de configuração e interface conversacional do projeto."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TextIO

from pydantic import ValidationError

from instituto_horizonte.config import (
    RAIZ_PROJETO,
    Configuracao,
    carregar_dotenv_projeto,
    formatar_erros_configuracao,
)

if TYPE_CHECKING:
    from instituto_horizonte.graph import ResultadoTurno


APRESENTACAO = """Instituto Horizonte
Assistente Acadêmico

Digite sua pergunta ou /ajuda para ver os comandos.
Digite /sair para encerrar."""

AJUDA = """Comandos locais:
  /ajuda  mostra esta ajuda
  /sair   encerra o atendimento

Envie perguntas acadêmicas ou consulte um protocolo SOL-nnnn.
Para registrar uma solicitação, informe os dados pedidos pelo assistente.
Quando houver um resumo pendente, digite CONFIRMAR ou CANCELAR separadamente."""


class AgenteConversacional(Protocol):
    def processar_turno(self, sessao: str, mensagem_usuario: str) -> ResultadoTurno: ...


AgenteFactory = Callable[[Configuracao], AgenteConversacional]


def criar_agente(config: Configuracao) -> AgenteConversacional:
    """Importa a stack do agente somente quando o chat é solicitado."""

    from instituto_horizonte.graph import AgenteAcademico

    return AgenteAcademico(config)


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="instituto-horizonte",
        description="Valida a configuração ou inicia o atendimento acadêmico.",
    )
    parser.add_argument(
        "--require-api-key",
        action="store_true",
        help="falha se GROQ_API_KEY não estiver configurada",
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="inicia a interface conversacional no terminal",
    )
    return parser


def _resolver_local(caminho: Path) -> Path:
    return caminho.resolve() if caminho.is_absolute() else (RAIZ_PROJETO / caminho).resolve()


def validar_pre_requisitos_chat(config: Configuracao) -> list[str]:
    """Verifica artefatos locais sem abrir, criar ou modificar seus dados."""

    ausentes: list[str] = []
    if not _resolver_local(config.sqlite_path).is_file():
        ausentes.append(
            "Banco SQLite não preparado. Execute: python scripts/init_db.py"
        )
    diretorio_chroma = _resolver_local(config.chroma_dir)
    if not (diretorio_chroma.is_dir() and (diretorio_chroma / "chroma.sqlite3").is_file()):
        ausentes.append(
            "Índice Chroma não preparado. Execute: python scripts/index_documents.py"
        )
    return ausentes


def _texto_compativel(texto: str, saida: TextIO) -> str:
    encoding = getattr(saida, "encoding", None)
    if not encoding:
        return texto
    try:
        texto.encode(encoding)
        return texto
    except (LookupError, UnicodeEncodeError):
        return texto.encode(encoding, errors="replace").decode(encoding, errors="replace")


def escrever(texto: str, *, saida: TextIO) -> None:
    """Escreve sem permitir que um caractere encerre o loop no console Windows."""

    saida.write(_texto_compativel(texto, saida) + "\n")
    saida.flush()


def apresentar_resposta(resultado: ResultadoTurno, *, saida: TextIO) -> None:
    escrever("\nInstituto Horizonte:", saida=saida)
    escrever(resultado.resposta, saida=saida)
    escrever(f"\nStatus: {resultado.status}", saida=saida)
    if resultado.fontes:
        escrever("Fontes: " + ", ".join(resultado.fontes), saida=saida)
    if resultado.protocolo:
        escrever(f"Protocolo: {resultado.protocolo}", saida=saida)


def executar_chat(
    config: Configuracao,
    *,
    agente_factory: AgenteFactory = criar_agente,
    entrada: Callable[[str], str] = input,
    saida: TextIO | None = None,
    sessao_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
) -> int:
    """Executa uma sessão mantendo agente, checkpointer e rascunhos em memória."""

    destino = sys.stdout if saida is None else saida
    try:
        agente = agente_factory(config)
    except Exception as error:
        escrever(
            f"Não foi possível iniciar o atendimento ({type(error).__name__}).",
            saida=destino,
        )
        return 1

    sessao = sessao_factory()
    escrever(APRESENTACAO, saida=destino)
    while True:
        try:
            mensagem = entrada("\nVocê: ")
        except (EOFError, KeyboardInterrupt):
            escrever("\nAtendimento encerrado.", saida=destino)
            return 0

        texto = mensagem.strip()
        if not texto:
            continue
        comando = texto.casefold()
        if comando == "/sair":
            escrever("Atendimento encerrado.", saida=destino)
            return 0
        if comando == "/ajuda":
            escrever(AJUDA, saida=destino)
            continue

        try:
            resultado = agente.processar_turno(sessao, texto)
        except Exception as error:
            escrever(
                f"\nFalha controlada no atendimento ({type(error).__name__}).",
                saida=destino,
            )
            continue
        apresentar_resposta(resultado, saida=destino)


def main(
    argv: Sequence[str] | None = None,
    *,
    agente_factory: AgenteFactory = criar_agente,
    entrada: Callable[[str], str] = input,
    saida: TextIO | None = None,
    sessao_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
) -> int:
    args = criar_parser().parse_args(argv)
    destino = sys.stdout if saida is None else saida
    carregar_dotenv_projeto()
    try:
        config = Configuracao.from_env()
    except ValidationError as error:
        escrever(
            f"Configuração inválida: {formatar_erros_configuracao(error)}",
            saida=destino,
        )
        return 2

    if (args.require_api_key or args.chat) and config.groq_api_key is None:
        escrever(
            "Configuração inválida: GROQ_API_KEY não está configurada.",
            saida=destino,
        )
        return 2

    if args.chat:
        problemas = validar_pre_requisitos_chat(config)
        if problemas:
            escrever("Pré-requisitos do chat não atendidos:", saida=destino)
            for problema in problemas:
                escrever(f"- {problema}", saida=destino)
            return 2
        return executar_chat(
            config,
            agente_factory=agente_factory,
            entrada=entrada,
            saida=destino,
            sessao_factory=sessao_factory,
        )

    escrever("Configuração válida (TSK-001).", saida=destino)
    escrever(
        json.dumps(config.resumo_seguro(), ensure_ascii=False, indent=2),
        saida=destino,
    )
    return 0
