"""Contrato e validação determinística das respostas do agente."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


StatusResposta = Literal[
    "respondida",
    "sem_evidencia",
    "protocolo_nao_encontrado",
    "pendente_dados",
    "pendente_confirmacao",
    "registrada",
    "cancelada",
    "recusada",
    "erro",
]

PADRAO_FONTE = re.compile(r"^ACAD-\d{3}$")
PADRAO_CITACAO = re.compile(r"\bACAD[-‑–—](\d{3})\b", re.IGNORECASE)
PADRAO_NUMERO = re.compile(r"(?<![\w‑–—-])\d+(?:[.,]\d+)?%?")
TERMOS_FATO_ESPECIFICO = {
    "frequencia",
    "percentual",
    "porcentagem",
    "prazo",
    "preco",
    "quanto",
    "valor",
}
TERMOS_DOMINIO_ACADEMICO = {
    "atividade",
    "biblioteca",
    "calendario",
    "cancelamento",
    "certificado",
    "cobranca",
    "credencial",
    "declaracao",
    "disciplina",
    "edital",
    "frequencia",
    "matricula",
    "nota",
    "pagamento",
    "portal",
    "protocolo",
    "revisao",
    "senha",
    "solicitacao",
    "trancamento",
}
PALAVRAS_COMUNS = {
    "a",
    "ao",
    "como",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "meu",
    "minha",
    "o",
    "os",
    "para",
    "por",
    "qual",
    "que",
    "um",
    "uma",
}


class RespostaAgente(BaseModel):
    """Parte conversacional estrita e estável da saída pública."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    resposta: str = Field(min_length=1)
    status: StatusResposta
    fontes: list[str] = Field(default_factory=list)
    protocolo: str | None = None

    @field_validator("resposta")
    @classmethod
    def rejeitar_resposta_em_branco(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("resposta não pode estar vazia")
        return valor

    @field_validator("fontes")
    @classmethod
    def validar_formato_fontes(cls, fontes: list[str]) -> list[str]:
        if len(fontes) != len(set(fontes)):
            raise ValueError("fontes não podem se repetir")
        if any(PADRAO_FONTE.fullmatch(fonte) is None for fonte in fontes):
            raise ValueError("fonte deve usar o formato ACAD-nnn")
        return fontes

    @model_validator(mode="after")
    def validar_coerencia_estrutural(self) -> RespostaAgente:
        if self.status == "registrada" and self.protocolo is None:
            raise ValueError("status registrada exige protocolo")
        if self.status == "protocolo_nao_encontrado" and self.protocolo is None:
            raise ValueError("protocolo_nao_encontrado exige o número consultado")
        if self.status in {"sem_evidencia", "recusada", "erro"} and self.fontes:
            raise ValueError(f"status {self.status} não aceita fontes")
        if self.status in {
            "sem_evidencia",
            "pendente_dados",
            "pendente_confirmacao",
            "cancelada",
            "recusada",
            "erro",
        } and self.protocolo is not None:
            raise ValueError(f"status {self.status} não aceita protocolo")
        return self


def _normalizar(texto: str) -> str:
    decomposicao = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(caractere for caractere in decomposicao if not unicodedata.combining(caractere))


def _tokens(texto: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", _normalizar(texto))
        if len(token) >= 3 and token not in PALAVRAS_COMUNS
    }


def _numeros(texto: str) -> set[str]:
    return {numero.replace(",", ".") for numero in PADRAO_NUMERO.findall(texto)}


def pergunta_exige_evidencia(pergunta: str) -> bool:
    """Classifica conservadoramente temas de regras, serviços e procedimentos."""

    tokens = _tokens(pergunta)
    return bool(tokens.intersection(TERMOS_FATO_ESPECIFICO | TERMOS_DOMINIO_ACADEMICO))


def _resposta_segura_sem_evidencia() -> RespostaAgente:
    return RespostaAgente(
        resposta="A informação solicitada não consta das normas disponíveis.",
        status="sem_evidencia",
        fontes=[],
        protocolo=None,
    )


def _evidencias_confiaveis(
    resultados: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    evidencias: dict[str, str] = {}
    for resultado in resultados:
        identificador = resultado.get("id")
        fonte = resultado.get("fonte")
        conteudo = resultado.get("conteudo")
        if (
            isinstance(identificador, str)
            and identificador == fonte
            and PADRAO_FONTE.fullmatch(identificador)
            and isinstance(conteudo, str)
        ):
            textos = [
                str(resultado.get(campo, ""))
                for campo in ("titulo", "categoria", "conteudo")
            ]
            evidencias[identificador] = " ".join(textos)
    return evidencias


def _evidencia_sustenta(pergunta: str, resposta: str, corpus: str) -> bool:
    if not corpus.strip():
        return False
    tokens_pergunta = _tokens(pergunta)
    tokens_corpus = _tokens(corpus)
    if not tokens_pergunta.intersection(tokens_corpus):
        return False

    numeros_pergunta = _numeros(pergunta)
    numeros_corpus = _numeros(corpus)
    if numeros_pergunta and not numeros_pergunta.issubset(numeros_corpus):
        return False

    if tokens_pergunta.intersection(TERMOS_FATO_ESPECIFICO) and not numeros_corpus:
        return False

    numeros_resposta = _numeros(resposta)
    if numeros_resposta and not numeros_resposta.issubset(numeros_corpus):
        return False
    return True


def evidencia_sustenta_pergunta(
    pergunta: str, resultados: Sequence[Mapping[str, Any]]
) -> bool:
    """Faz o gate conservador que independe de texto gerado pelo modelo."""

    evidencias = _evidencias_confiaveis(resultados)
    corpus = " ".join(evidencias.values())
    if not corpus.strip():
        return False
    tokens_pergunta = _tokens(pergunta)
    tokens_corpus = _tokens(corpus)
    if not tokens_pergunta.intersection(tokens_corpus):
        return False
    numeros_pergunta = _numeros(pergunta)
    numeros_corpus = _numeros(corpus)
    if numeros_pergunta and not numeros_pergunta.issubset(numeros_corpus):
        return False
    if tokens_pergunta.intersection(TERMOS_FATO_ESPECIFICO) and not numeros_corpus:
        return False
    return True


def validar_resposta_backend(
    *,
    resposta_candidata: str,
    pergunta: str,
    resultados_normas: Sequence[Mapping[str, Any]],
    resultado_protocolo: Mapping[str, Any] | None,
    erros: Sequence[str],
) -> RespostaAgente:
    """Valida fatos contra resultados de Tools, sem confiar em afirmações do LLM."""

    if erros:
        return RespostaAgente(
            resposta=str(erros[-1]), status="erro", fontes=[], protocolo=None
        )

    if resultado_protocolo is not None:
        protocolo = resultado_protocolo.get("protocolo")
        encontrado = resultado_protocolo.get("encontrado")
        status = resultado_protocolo.get("status")
        if encontrado is True and isinstance(protocolo, str) and isinstance(status, str):
            return RespostaAgente(
                resposta=f"O protocolo {protocolo} está com status {status}.",
                status="respondida",
                fontes=[],
                protocolo=protocolo,
            )
        if encontrado is False and isinstance(protocolo, str):
            return RespostaAgente(
                resposta=f"O protocolo {protocolo} não foi encontrado.",
                status="protocolo_nao_encontrado",
                fontes=[],
                protocolo=protocolo,
            )
        return RespostaAgente(
            resposta="Falha controlada ao validar a consulta de protocolo.",
            status="erro",
            fontes=[],
            protocolo=None,
        )

    texto = resposta_candidata.strip()
    if not texto:
        return RespostaAgente(
            resposta="O modelo não produziu uma resposta válida.",
            status="erro",
            fontes=[],
            protocolo=None,
        )

    evidencias = _evidencias_confiaveis(resultados_normas)
    fontes = sorted(evidencias)
    consulta_normativa = bool(resultados_normas) or pergunta_exige_evidencia(pergunta)
    if consulta_normativa:
        citacoes = {f"ACAD-{sufixo}" for sufixo in PADRAO_CITACAO.findall(texto)}
        if not citacoes.issubset(fontes):
            return _resposta_segura_sem_evidencia()
        fontes_declaradas = sorted(citacoes) if citacoes else fontes
        corpus = " ".join(evidencias[fonte] for fonte in fontes_declaradas)
        if not fontes or not _evidencia_sustenta(pergunta, texto, corpus):
            return _resposta_segura_sem_evidencia()
        return RespostaAgente(
            resposta=texto,
            status="respondida",
            fontes=fontes_declaradas,
            protocolo=None,
        )

    if PADRAO_CITACAO.search(texto):
        return _resposta_segura_sem_evidencia()
    return RespostaAgente(
        resposta=texto, status="respondida", fontes=[], protocolo=None
    )
