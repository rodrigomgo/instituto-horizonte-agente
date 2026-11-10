"""Testes da CLI interativa com agente falso e sem acesso à rede."""

from __future__ import annotations

import io
import os
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest

from instituto_horizonte import cli
from instituto_horizonte.config import Configuracao
from instituto_horizonte.graph import ResultadoTurno


def resultado(
    status: str = "respondida",
    *,
    resposta: str = "Resposta de teste.",
    fontes: list[str] | None = None,
    protocolo: str | None = None,
) -> ResultadoTurno:
    return ResultadoTurno(
        sessao="sessao-teste",
        resposta=resposta,
        status=status,
        fontes=[] if fontes is None else fontes,
        protocolo=protocolo,
        rodadas=1,
        eventos_tools=[],
        erros=[] if status != "erro" else ["falha controlada"],
    )


class AgenteFalso:
    def __init__(self, respostas: list[ResultadoTurno] | None = None) -> None:
        self.respostas = list(respostas or [resultado()])
        self.chamadas: list[tuple[str, str]] = []

    def processar_turno(self, sessao: str, mensagem_usuario: str) -> ResultadoTurno:
        self.chamadas.append((sessao, mensagem_usuario))
        if not self.respostas:
            return resultado()
        return self.respostas.pop(0)


def entradas(*valores: str) -> Any:
    iterador: Iterator[str] = iter(valores)

    def ler(prompt: str) -> str:
        del prompt
        return next(iterador)

    return ler


@patch.dict(os.environ, {}, clear=True)
def test_comando_original_de_validacao_continua_funcionando(monkeypatch) -> None:
    monkeypatch.setattr(cli, "carregar_dotenv_projeto", lambda: False)
    saida = io.StringIO()
    codigo = cli.main([], saida=saida)
    assert codigo == 0
    assert "Configuração válida (TSK-001)." in saida.getvalue()
    assert "groq_api_key_configurada" in saida.getvalue()


@patch.dict(os.environ, {}, clear=True)
def test_require_api_key_preserva_falha_sem_chave(monkeypatch) -> None:
    monkeypatch.setattr(cli, "carregar_dotenv_projeto", lambda: False)
    saida = io.StringIO()
    codigo = cli.main(["--require-api-key"], saida=saida)
    assert codigo == 2
    assert "GROQ_API_KEY não está configurada" in saida.getvalue()


@patch.dict(os.environ, {"GROQ_API_KEY": "chave-falsa"}, clear=True)
def test_chat_inicia_loop_por_main(monkeypatch) -> None:
    agente = AgenteFalso()
    criados: list[AgenteFalso] = []

    def factory(config: Configuracao) -> AgenteFalso:
        assert config.groq_api_key is not None
        criados.append(agente)
        return agente

    monkeypatch.setattr(cli, "carregar_dotenv_projeto", lambda: False)
    monkeypatch.setattr(cli, "validar_pre_requisitos_chat", lambda config: [])
    saida = io.StringIO()
    codigo = cli.main(
        ["--chat"],
        agente_factory=factory,
        entrada=entradas("/sair"),
        saida=saida,
        sessao_factory=lambda: "opaca",
    )
    assert codigo == 0
    assert len(criados) == 1
    assert "Assistente Acadêmico" in saida.getvalue()


def test_reutiliza_agente_e_sessao_e_repassa_comandos_de_negocio() -> None:
    agente = AgenteFalso([resultado(), resultado(), resultado()])
    saida = io.StringIO()
    codigo = cli.executar_chat(
        Configuracao.from_env({}),
        agente_factory=lambda config: agente,
        entrada=entradas(
            "",
            "/ajuda",
            "Primeira pergunta",
            "CONFIRMAR",
            "CANCELAR",
            "/sair",
        ),
        saida=saida,
        sessao_factory=lambda: "sessao-opaca",
    )
    assert codigo == 0
    assert agente.chamadas == [
        ("sessao-opaca", "Primeira pergunta"),
        ("sessao-opaca", "CONFIRMAR"),
        ("sessao-opaca", "CANCELAR"),
    ]
    assert "CONFIRMAR ou CANCELAR separadamente" in saida.getvalue()


@pytest.mark.parametrize(
    ("status", "texto"),
    [
        ("respondida", "Resposta normal."),
        ("sem_evidencia", "Não consta das normas."),
        ("recusada", "Operação recusada."),
        ("erro", "Falha controlada."),
    ],
)
def test_exibe_status_estruturados(status: str, texto: str) -> None:
    saida = io.StringIO()
    cli.apresentar_resposta(resultado(status, resposta=texto), saida=saida)
    assert texto in saida.getvalue()
    assert f"Status: {status}" in saida.getvalue()


def test_exibe_fontes_e_protocolo_sem_representacoes_artificiais() -> None:
    saida = io.StringIO()
    cli.apresentar_resposta(
        resultado(
            resposta="Consulta concluída.",
            fontes=["ACAD-001", "ACAD-002"],
            protocolo="SOL-1001",
        ),
        saida=saida,
    )
    texto = saida.getvalue()
    assert "Fontes: ACAD-001, ACAD-002" in texto
    assert "Protocolo: SOL-1001" in texto
    assert "None" not in texto and "null" not in texto

    sem_opcionais = io.StringIO()
    cli.apresentar_resposta(resultado(), saida=sem_opcionais)
    assert "Fontes:" not in sem_opcionais.getvalue()
    assert "Protocolo:" not in sem_opcionais.getvalue()


@pytest.mark.parametrize("excecao", [EOFError(), KeyboardInterrupt()])
def test_eof_e_ctrl_c_encerram_sem_traceback(excecao: BaseException) -> None:
    def interromper(prompt: str) -> str:
        del prompt
        raise excecao

    saida = io.StringIO()
    codigo = cli.executar_chat(
        Configuracao.from_env({}),
        agente_factory=lambda config: AgenteFalso(),
        entrada=interromper,
        saida=saida,
    )
    assert codigo == 0
    assert "Atendimento encerrado" in saida.getvalue()
    assert "Traceback" not in saida.getvalue()


def test_erro_de_inicializacao_nao_revela_chave() -> None:
    segredo = "chave-super-secreta"

    def falhar(config: Configuracao):
        del config
        raise RuntimeError(segredo)

    saida = io.StringIO()
    codigo = cli.executar_chat(
        Configuracao.from_env({"GROQ_API_KEY": segredo}),
        agente_factory=falhar,
        entrada=entradas("/sair"),
        saida=saida,
    )
    assert codigo == 1
    assert segredo not in saida.getvalue()
    assert "RuntimeError" in saida.getvalue()
    assert "Traceback" not in saida.getvalue()


def test_falha_de_turno_e_controlada_e_loop_continua() -> None:
    class AgenteComFalha:
        def processar_turno(self, sessao: str, mensagem_usuario: str):
            del sessao, mensagem_usuario
            raise TimeoutError("conteúdo privado")

    saida = io.StringIO()
    codigo = cli.executar_chat(
        Configuracao.from_env({}),
        agente_factory=lambda config: AgenteComFalha(),
        entrada=entradas("pergunta", "/sair"),
        saida=saida,
    )
    assert codigo == 0
    assert "TimeoutError" in saida.getvalue()
    assert "conteúdo privado" not in saida.getvalue()
    assert "Traceback" not in saida.getvalue()


def test_saida_unicode_nao_encerra_em_cp1252() -> None:
    buffer = io.BytesIO()
    saida = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")
    agente = AgenteFalso(
        [resultado(resposta="Fonte ACAD‑001 — resposta 🎓")]
    )
    codigo = cli.executar_chat(
        Configuracao.from_env({}),
        agente_factory=lambda config: agente,
        entrada=entradas("pergunta", "/sair"),
        saida=saida,
    )
    saida.flush()
    texto = buffer.getvalue().decode("cp1252")
    assert codigo == 0
    assert "Atendimento encerrado" in texto
    assert "Status: respondida" in texto


@patch.dict(os.environ, {"GROQ_API_KEY": "chave-falsa"}, clear=True)
def test_chat_orienta_pre_requisitos_ausentes(monkeypatch) -> None:
    monkeypatch.setattr(cli, "carregar_dotenv_projeto", lambda: False)
    monkeypatch.setattr(
        cli,
        "validar_pre_requisitos_chat",
        lambda config: [
            "Banco SQLite não preparado. Execute: python scripts/init_db.py",
            "Índice Chroma não preparado. Execute: python scripts/index_documents.py",
        ],
    )
    saida = io.StringIO()
    codigo = cli.main(["--chat"], saida=saida)
    assert codigo == 2
    assert "scripts/init_db.py" in saida.getvalue()
    assert "scripts/index_documents.py" in saida.getvalue()
