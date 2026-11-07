"""Demonstra T01 e T04 no StateGraph real com Groq, sem CLI interativa."""

from __future__ import annotations

import json

from instituto_horizonte.config import Configuracao, carregar_dotenv_projeto
from instituto_horizonte.graph import AgenteAcademico


def main() -> int:
    carregar_dotenv_projeto()
    config = Configuracao.from_env()
    if config.groq_api_key is None:
        print("Smoke LangGraph não executado: GROQ_API_KEY ausente.")
        return 2
    try:
        agente = AgenteAcademico(config)
        resultados = [
            agente.processar_turno(
                "smoke-t01",
                "Qual é o prazo para emitir a declaração de matrícula?",
            ),
            agente.processar_turno(
                "smoke-t04",
                "Meu protocolo SOL-1001 já foi resolvido?",
            ),
        ]
        if any(resultado.erros for resultado in resultados):
            categorias = sorted(
                {
                    erro.rsplit("(", maxsplit=1)[-1].rstrip(").")
                    for resultado in resultados
                    for erro in resultado.erros
                }
            )
            print(
                "Smoke LangGraph falhou de forma controlada; categorias="
                + ",".join(categorias)
            )
            return 1
    except Exception as error:
        print(f"Smoke LangGraph falhou de forma controlada ({type(error).__name__}).")
        return 1
    print("Smoke LangGraph/Groq concluído.")
    resumo = [
        {
            "sessao": resultado.sessao,
            "status": resultado.status,
            "resposta": resultado.resposta[:500],
            "ferramentas": [
                item.get("tool") for item in resultado.eventos_tools
            ],
            "fontes": resultado.fontes,
            "protocolo": resultado.protocolo,
        }
        for resultado in resultados
    ]
    print(json.dumps(resumo, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
