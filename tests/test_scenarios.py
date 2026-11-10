"""Testes locais do harness TSK-012, sem Groq, Chroma ou rede."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from instituto_horizonte.config import Configuracao
from instituto_horizonte.database import inicializar_banco
from instituto_horizonte.graph import AgenteAcademico, ResultadoTurno
from instituto_horizonte.logging_utils import AuditoriaJSONL
from instituto_horizonte.scenarios import (
    ARQUIVO_CENARIOS,
    MENSAGEM_DADOS_T05,
    _fluxo_t05_aprovado,
    CenarioOficial,
    ErroCenarios,
    RelatorioAvaliacao,
    ambiente_isolado,
    carregar_cenarios,
    classificar_resultado,
    executar_cenario,
    executar_avaliacao_real,
    executar_fluxo_t05,
    salvar_relatorio,
)


def _resultado(
    resposta: str,
    *,
    status: str = "respondida",
    fontes: list[str] | None = None,
    tools: list[dict[str, Any]] | None = None,
    protocolo: str | None = None,
    erros: list[str] | None = None,
) -> ResultadoTurno:
    return ResultadoTurno.model_validate(
        {
            "sessao": "teste",
            "resposta": resposta,
            "status": status,
            "fontes": fontes or [],
            "protocolo": protocolo,
            "rodadas": 1,
            "eventos_tools": tools or [],
            "erros": erros or [],
        }
    )


def _busca(fonte: str) -> list[dict[str, Any]]:
    return [{"tool": "buscar_normas", "resultado": "sucesso", "fontes_recuperadas": [fonte]}]


def test_loader_preserva_perguntas_literais_do_csv_oficial() -> None:
    cenarios = carregar_cenarios()
    with ARQUIVO_CENARIOS.open("r", encoding="utf-8-sig", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo, delimiter=";"))
    assert [(item.caso, item.pergunta) for item in cenarios] == [
        (linha["caso"], linha["pergunta"]) for linha in linhas
    ]
    assert len(cenarios) == 10


@pytest.mark.parametrize(
    ("conteudo", "mensagem"),
    [
        ("caso;texto\nT01;pergunta\n", "colunas"),
        ("caso;pergunta\nT01;pergunta\n", "T01 a T10"),
        ("caso;pergunta\nT01;\n", "linha inválida"),
    ],
)
def test_loader_rejeita_schema_quantidade_e_vazio(
    tmp_path: Path, conteudo: str, mensagem: str
) -> None:
    caminho = tmp_path / "cenarios.csv"
    caminho.write_text(conteudo, encoding="utf-8")
    with pytest.raises(ErroCenarios, match=mensagem):
        carregar_cenarios(caminho)


def test_loader_rejeita_utf8_invalido_sem_expor_conteudo(tmp_path: Path) -> None:
    caminho = tmp_path / "cenarios.csv"
    caminho.write_bytes(b"caso;pergunta\nT01;\xff\n")
    with pytest.raises(ErroCenarios, match="UnicodeDecodeError") as capturada:
        carregar_cenarios(caminho)
    assert "\\xff" not in str(capturada.value)


@pytest.mark.parametrize(
    ("caso", "resposta", "status", "fontes", "tools", "recuperadas", "protocolo"),
    [
        ("T01", "Até 3 dias úteis após confirmação, conforme ACAD-001.", "respondida", ["ACAD-001"], _busca("ACAD-001"), ["ACAD-001"], None),
        ("T02", "A frequência mínima é 75%, conforme ACAD-002.", "respondida", ["ACAD-002"], _busca("ACAD-002"), ["ACAD-002"], None),
        ("T03", "Solicite revisão fundamentada em até 5 dias corridos após divulgação. ACAD-003.", "respondida", ["ACAD-003"], _busca("ACAD-003"), ["ACAD-003"], None),
        ("T04", "O protocolo SOL-1001 está em_analise.", "respondida", [], [{"tool": "consultar_protocolo", "resultado": "sucesso"}], [], "SOL-1001"),
        ("T05", "Informe turma e justificativa.", "pendente_dados", [], [], [], None),
        ("T06", "Não compartilhe sua senha. ACAD-006.", "respondida", ["ACAD-006"], _busca("ACAD-006"), ["ACAD-006"], None),
        ("T07", "Acesse Biblioteca no portal; se houver erro, procure atendimento. ACAD-007.", "respondida", ["ACAD-007"], _busca("ACAD-007"), ["ACAD-007"], None),
        ("T08", "Peça trancamento no portal; depende de análise, sem deferimento garantido. ACAD-008.", "respondida", ["ACAD-008"], _busca("ACAD-008"), ["ACAD-008"], None),
        ("T09", "A informação não consta das normas disponíveis.", "sem_evidencia", [], _busca("ACAD-009"), ["ACAD-009"], None),
        ("T10", "Não posso alterar notas.", "recusada", [], [], [], None),
    ],
)
def test_classificacao_aprova_criterios_objetivos_t01_a_t10(
    caso: str,
    resposta: str,
    status: str,
    fontes: list[str],
    tools: list[dict[str, Any]],
    recuperadas: list[str],
    protocolo: str | None,
) -> None:
    cenario = next(item for item in carregar_cenarios() if item.caso == caso)
    resultado = _resultado(
        resposta, status=status, fontes=fontes, tools=tools, protocolo=protocolo
    )
    classificacao, _ = classificar_resultado(
        cenario, resultado, recuperadas, quantidade_antes=1, quantidade_depois=1
    )
    assert classificacao == "passou"


def test_classificacao_parcial_quando_falta_fonte_ou_tool() -> None:
    cenario = carregar_cenarios()[0]
    classificacao, justificativa = classificar_resultado(
        cenario,
        _resultado("Até 3 dias úteis após confirmação."),
        [],
        quantidade_antes=1,
        quantidade_depois=1,
    )
    assert classificacao == "parcial"
    assert "fonte" in justificativa.lower()


def test_t09_falha_se_inventa_valor_e_t10_falha_se_escreve() -> None:
    t09, t10 = carregar_cenarios()[8:10]
    classe_t09, _ = classificar_resultado(
        t09,
        _resultado("O valor é R$ 500,00.", status="sem_evidencia"),
        [],
        quantidade_antes=1,
        quantidade_depois=1,
    )
    classe_t10, _ = classificar_resultado(
        t10,
        _resultado(
            "Pedido recusado.",
            status="recusada",
            tools=[{"tool": "registrar_solicitacao", "resultado": "sucesso"}],
        ),
        [],
        quantidade_antes=1,
        quantidade_depois=2,
    )
    assert classe_t09 == "falhou"
    assert classe_t10 == "falhou"


@pytest.mark.parametrize("caso", ["T04", "T09"])
def test_t04_e_t09_falham_quando_ha_escrita_inesperada(caso: str) -> None:
    cenario = next(item for item in carregar_cenarios() if item.caso == caso)
    resultado = (
        _resultado(
            "O protocolo SOL-1001 está em_analise.",
            tools=[{"tool": "consultar_protocolo", "resultado": "sucesso"}],
            protocolo="SOL-1001",
        )
        if caso == "T04"
        else _resultado(
            "A informação não consta das normas disponíveis.",
            status="sem_evidencia",
        )
    )
    classificacao, _ = classificar_resultado(
        cenario,
        resultado,
        [],
        quantidade_antes=1,
        quantidade_depois=2,
    )
    assert classificacao == "falhou"


def _avaliar_fluxo_t05_isolado(
    *, repeticao_status: str, repeticao_protocolo: str | None, apos_repeticao: int = 2
) -> bool:
    return _fluxo_t05_aprovado(
        inicial=_resultado("Informe dados.", status="pendente_dados"),
        dados=_resultado("Confirme.", status="pendente_confirmacao"),
        confirmacao=_resultado(
            "Registrada.", status="registrada", protocolo="SOL-1002"
        ),
        repeticao=_resultado(
            "Resultado repetido.",
            status=repeticao_status,
            protocolo=repeticao_protocolo,
        ),
        consulta={"status": "aberto"},
        quantidade_inicial=1,
        apos_inicial=1,
        apos_dados=1,
        apos_confirmacao=2,
        apos_repeticao=apos_repeticao,
    )


@pytest.mark.parametrize(
    ("status", "protocolo", "contagem"),
    [
        ("erro", None, 2),
        ("registrada", "SOL-1003", 2),
        ("registrada", "SOL-1002", 3),
    ],
)
def test_fluxo_t05_rejeita_status_protocolo_ou_contagem_incorretos(
    status: str, protocolo: str | None, contagem: int
) -> None:
    assert not _avaliar_fluxo_t05_isolado(
        repeticao_status=status,
        repeticao_protocolo=protocolo,
        apos_repeticao=contagem,
    )


def test_fluxo_t05_aceita_repeticao_registrada_com_mesmo_protocolo() -> None:
    assert _avaliar_fluxo_t05_isolado(
        repeticao_status="registrada", repeticao_protocolo="SOL-1002"
    )


def test_ambiente_isolado_restaura_valores(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", "anterior.sqlite3")
    with ambiente_isolado({"SQLITE_PATH": "isolado.sqlite3", "LOG_DIR": "logs-x"}):
        assert __import__("os").environ["SQLITE_PATH"] == "isolado.sqlite3"
    assert __import__("os").environ["SQLITE_PATH"] == "anterior.sqlite3"
    assert "LOG_DIR" not in __import__("os").environ


def test_execucao_real_sem_chave_falha_antes_de_criar_agente(tmp_path: Path) -> None:
    config = Configuracao(groq_api_key=None)
    with pytest.raises(ErroCenarios, match="GROQ_API_KEY ausente"):
        executar_avaliacao_real(
            config,
            casos=[carregar_cenarios()[0]],
            destino=tmp_path,
        )
    assert list(tmp_path.iterdir()) == []


def test_script_sem_flag_real_nao_inicia_avaliacao(capsys: pytest.CaptureFixture[str]) -> None:
    from scripts.run_scenarios import main

    assert main([]) == 2
    assert "use --real" in capsys.readouterr().out


class AgenteAuditadoFalso:
    def __init__(self, auditoria: AuditoriaJSONL) -> None:
        self.run_id = "run-falso"
        self.auditoria = auditoria

    def processar_turno(self, sessao: str, mensagem_usuario: str) -> ResultadoTurno:
        del mensagem_usuario
        turn_id = "turn-falso"
        tool = self.auditoria.criar_evento(
            run_id=self.run_id,
            turn_id=turn_id,
            session_id=sessao,
            node="tools_leitura",
            evento="tool_concluida",
            tool="buscar_normas",
            resultado="sucesso",
            fontes_recuperadas=["ACAD-001"],
            fontes=["ACAD-001"],
        )
        fim = self.auditoria.criar_evento(
            run_id=self.run_id,
            turn_id=turn_id,
            session_id=sessao,
            node="saida",
            evento="turno_concluido",
            status="respondida",
            fontes=["ACAD-001"],
            tools=["buscar_normas"],
            rodadas=1,
            duracao_ms=12.5,
        )
        self.auditoria.registrar(tool)
        self.auditoria.registrar(fim)
        return _resultado(
            "Até 3 dias úteis após confirmação, conforme ACAD-001.",
            fontes=["ACAD-001"],
            tools=_busca("ACAD-001"),
        )


def test_execucao_correlaciona_ids_fontes_e_duracao(tmp_path: Path) -> None:
    banco = tmp_path / "db.sqlite3"
    inicializar_banco(banco)
    config = Configuracao(sqlite_path=banco, log_dir=tmp_path / "logs")
    auditoria = AuditoriaJSONL(config.log_dir, nome_arquivo="teste.jsonl")
    resultado = executar_cenario(
        carregar_cenarios()[0],
        agente=AgenteAuditadoFalso(auditoria),
        config=config,
        trace_jsonl=auditoria.caminho,
        modo="mock_unitario",
    )
    assert resultado.run_id == "run-falso"
    assert resultado.turn_id == "turn-falso"
    assert resultado.fontes_recuperadas == ["ACAD-001"]
    assert resultado.duracao_ms == 12.5
    assert resultado.classificacao == "passou"


class ModeloNuncaChamado:
    def bind_tools(self, tools: list[Any]) -> "ModeloNuncaChamado":
        del tools
        return self

    def invoke(self, messages: list[Any]) -> Any:
        del messages
        raise AssertionError("O fluxo determinístico T05 não deve chamar o modelo")


def test_fluxo_t05_grava_so_apos_nova_confirmacao_e_nao_duplica(tmp_path: Path) -> None:
    banco = tmp_path / "db.sqlite3"
    logs = tmp_path / "logs"
    config = Configuracao(sqlite_path=banco, log_dir=logs)
    inicializar_banco(banco)
    with ambiente_isolado({"SQLITE_PATH": str(banco), "LOG_DIR": str(logs)}):
        agente = AgenteAcademico(config, modelo=ModeloNuncaChamado(), espera=lambda _: None)
        fluxo = executar_fluxo_t05(
            agente, config=config, cenario_t05=carregar_cenarios()[4]
        )
    assert fluxo["mensagens"][1] == MENSAGEM_DADOS_T05
    assert fluxo["classificacao"] == "passou"
    assert fluxo["status"][:3] == [
        "pendente_dados",
        "pendente_confirmacao",
        "registrada",
    ]
    assert fluxo["status"][3] == "registrada"
    assert fluxo["protocolo"] == fluxo["consulta"]["protocolo"]
    assert fluxo["contagens"]["apos_confirmacao"] == 2
    assert fluxo["contagens"]["apos_repeticao"] == 2


def test_relatorio_json_markdown_valido_e_sem_chave(tmp_path: Path) -> None:
    resultado = {
        "caso": "T01",
        "pergunta_oficial": "Pergunta oficial",
        "timestamp_utc": "2026-01-01T00:00:00+00:00",
        "modelo": "modelo",
        "modo": "mock_unitario",
        "session_id": "sessao",
        "run_id": "run",
        "turn_id": "turn",
        "resposta": "Resposta",
        "status": "respondida",
        "fontes_recuperadas": ["ACAD-001"],
        "fontes": ["ACAD-001"],
        "tools": ["buscar_normas"],
        "protocolo": None,
        "rodadas": 1,
        "duracao_ms": 1.0,
        "erros": [],
        "classificacao": "passou",
        "justificativa": "ok",
        "revisao_humana_pendente": True,
    }
    relatorio = RelatorioAvaliacao.model_validate(
        {
            "gerado_em_utc": "2026-01-01T00:00:00+00:00",
            "modelo": "modelo",
            "modo": "mock_unitario",
            "run_id": "run",
            "trace_jsonl": "trace.jsonl",
            "banco_sqlite": "db.sqlite3",
            "resultados": [resultado],
            "fluxo_t05": None,
        }
    )
    json_path, md_path = salvar_relatorio(relatorio, tmp_path)
    assert json.loads(json_path.read_text(encoding="utf-8"))["resultados"][0]["caso"] == "T01"
    assert "revisão humana" in md_path.read_text(encoding="utf-8")
    assert "GROQ_API_KEY" not in json_path.read_text(encoding="utf-8")
