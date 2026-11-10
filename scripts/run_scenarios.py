"""Executa a avaliação real dos cenários oficiais somente com consentimento explícito."""

from __future__ import annotations

import argparse

from pydantic import ValidationError

from instituto_horizonte.config import (
    Configuracao,
    carregar_dotenv_projeto,
    formatar_erros_configuracao,
)
from instituto_horizonte.scenarios import (
    ErroCenarios,
    carregar_cenarios,
    criar_diretorio_execucao,
    executar_avaliacao_real,
    salvar_relatorio,
)


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Avalia os dez cenários oficiais.")
    parser.add_argument(
        "--real",
        action="store_true",
        help="autoriza chamadas reais ao Groq (obrigatório para executar)",
    )
    parser.add_argument("--case", metavar="TNN", help="executa somente um caso")
    parser.add_argument(
        "--t05-flow",
        action="store_true",
        help="executa também o fluxo complementar multiturmo do T05",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = criar_parser().parse_args(argv)
    if not args.real:
        print("Nenhuma avaliação executada: use --real para autorizar chamadas ao Groq.")
        return 2
    try:
        carregar_dotenv_projeto()
        config = Configuracao.from_env()
        cenarios = carregar_cenarios()
        if args.case:
            cenarios = [item for item in cenarios if item.caso == args.case.upper()]
            if not cenarios:
                raise ErroCenarios("Caso inválido; informe um ID entre T01 e T10.")
        destino = criar_diretorio_execucao()
        relatorio = executar_avaliacao_real(
            config,
            casos=cenarios,
            destino=destino,
            incluir_fluxo_t05=args.t05_flow,
        )
        json_path, md_path = salvar_relatorio(relatorio, destino)
    except ValidationError as error:
        print(f"Configuração inválida: {formatar_erros_configuracao(error)}")
        return 2
    except ErroCenarios as error:
        print(f"Avaliação não executada: {error}")
        return 2
    except Exception as error:
        print(f"Avaliação falhou de forma controlada ({type(error).__name__}).")
        return 1

    contagens = {nome: 0 for nome in ("passou", "parcial", "falhou")}
    for resultado in relatorio.resultados:
        contagens[resultado.classificacao] += 1
    print(
        "Avaliação concluída: "
        f"passou={contagens['passou']}, parcial={contagens['parcial']}, "
        f"falhou={contagens['falhou']}."
    )
    print(f"Relatório JSON: {json_path}")
    print(f"Relatório Markdown: {md_path}")
    print("Classificações semânticas aguardam revisão humana.")
    return 0 if contagens["falhou"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
