"""Avalia o ranking real das perguntas acadêmicas oficiais da TSK-004."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from time import perf_counter

from instituto_horizonte.config import RAIZ_PROJETO, carregar_dotenv_projeto
from instituto_horizonte.retrieval import (
    ErroRecuperacao,
    configuracao_rag_do_ambiente,
    consultar_normas,
)


CASOS_ESPERADOS = {
    "T01": "ACAD-001",
    "T02": "ACAD-002",
    "T03": "ACAD-003",
    "T05": "ACAD-005",
    "T06": "ACAD-006",
    "T07": "ACAD-007",
    "T08": "ACAD-008",
    "T09": None,
}
CAMINHO_CENARIOS = RAIZ_PROJETO / "data" / "cenarios_de_teste_aluno.csv"


def carregar_perguntas(caminho: Path = CAMINHO_CENARIOS) -> dict[str, str]:
    with caminho.open("r", encoding="utf-8-sig", newline="") as arquivo:
        return {
            linha["caso"]: linha["pergunta"]
            for linha in csv.DictReader(arquivo, delimiter=";")
        }


def main() -> int:
    carregar_dotenv_projeto()
    perguntas = carregar_perguntas()
    config = configuracao_rag_do_ambiente()
    avaliacoes: list[dict[str, object]] = []
    try:
        for caso, esperado in CASOS_ESPERADOS.items():
            pergunta = perguntas[caso]
            inicio = perf_counter()
            resposta = consultar_normas(pergunta, top_k=config.rag_top_k, config=config)
            duracao_ms = (perf_counter() - inicio) * 1000
            ids = [resultado.id for resultado in resposta.resultados]
            avaliacoes.append(
                {
                    "caso": caso,
                    "pergunta": pergunta,
                    "esperado": esperado,
                    "ids_ranking": ids,
                    "distancias": [
                        resultado.distancia for resultado in resposta.resultados
                    ],
                    "esperado_no_top_k": esperado in ids if esperado else None,
                    "duracao_ms": round(duracao_ms, 3),
                    "observacao": (
                        "T09 não possui resposta específica; resultados próximos não "
                        "autorizam inferir valor de bolsa."
                        if caso == "T09"
                        else None
                    ),
                }
            )
    except (ErroRecuperacao, KeyError) as error:
        print(f"Avaliação falhou: {error}")
        return 1
    print(json.dumps(avaliacoes, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
