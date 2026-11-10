"""Contrato e validação determinística das respostas do agente."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
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
MotivoRejeicao = Literal[
    "citacao_nao_recuperada",
    "sem_sobreposicao",
    "numero_pergunta_ausente",
    "fato_numerico_sem_evidencia",
    "numero_resposta_incompativel",
    "sem_fontes_confiaveis",
]

PADRAO_FONTE = re.compile(r"^ACAD-\d{3}$")
PADRAO_CITACAO = re.compile(r"\bACAD[-‑–—](\d{3})\b", re.IGNORECASE)
PADRAO_IDENTIFICADOR = re.compile(r"\b(?:acad|sol)[-‐‑–—]\d+\b")
PADRAO_MARCADOR_LISTA = re.compile(r"(?m)^\s*\d+[.)]\s+")
PADRAO_VALOR_DIGITOS = r"(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)"
PALAVRAS_NUMERICAS = {
    "zero": 0,
    "um": 1,
    "uma": 1,
    "dois": 2,
    "duas": 2,
    "tres": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
    "dez": 10,
    "onze": 11,
    "doze": 12,
    "treze": 13,
    "quatorze": 14,
    "catorze": 14,
    "quinze": 15,
    "dezesseis": 16,
    "dezessete": 17,
    "dezoito": 18,
    "dezenove": 19,
    "vinte": 20,
    "trinta": 30,
    "quarenta": 40,
    "cinquenta": 50,
    "sessenta": 60,
    "setenta": 70,
    "oitenta": 80,
    "noventa": 90,
    "cem": 100,
    "cento": 100,
}
PALAVRAS_NUMERICAS_NAO_SUPORTADAS = {
    "mil",
    "milhar",
    "milhares",
    "milhao",
    "milhoes",
    "bilhao",
    "bilhoes",
    "trilhao",
    "trilhoes",
}
PADRAO_PALAVRA_NUMERICA = "(?:" + "|".join(
    sorted(PALAVRAS_NUMERICAS, key=len, reverse=True)
) + ")"
PADRAO_VALOR_EXTENSO = rf"{PADRAO_PALAVRA_NUMERICA}(?:\s+e\s+{PADRAO_PALAVRA_NUMERICA}){{0,2}}"
PADRAO_PALAVRA_NUMERICA_NAO_SUPORTADA = "(?:" + "|".join(
    sorted(PALAVRAS_NUMERICAS_NAO_SUPORTADAS, key=len, reverse=True)
) + ")"
PADRAO_VALOR_EXTENSO_NAO_SUPORTADO = (
    rf"{PADRAO_PALAVRA_NUMERICA_NAO_SUPORTADA}"
    rf"(?:\s+e\s+(?:{PADRAO_PALAVRA_NUMERICA}|"
    rf"{PADRAO_PALAVRA_NUMERICA_NAO_SUPORTADA})){{0,2}}"
)
PADRAO_VALOR = rf"(?:{PADRAO_VALOR_DIGITOS}|{PADRAO_VALOR_EXTENSO})"
PADRAO_PERCENTUAL = re.compile(
    rf"\b(?P<valor>{PADRAO_VALOR})\s*(?:%|por\s+cento)(?!\w)"
)
PADRAO_DIAS = re.compile(
    rf"\b(?P<valor>{PADRAO_VALOR})\s+dias?"
    rf"(?:\s+(?P<tipo>uteis|corridos))?\b"
)
PADRAO_DIAS_DESCONHECIDO = re.compile(
    rf"\b(?P<valor>{PADRAO_VALOR_EXTENSO_NAO_SUPORTADO})\s+dias?"
    r"(?:\s+(?:uteis|corridos))?\b"
)
PADRAO_PERCENTUAL_DESCONHECIDO = re.compile(
    rf"\b(?P<valor>{PADRAO_VALOR_EXTENSO_NAO_SUPORTADO})\s+por\s+cento\b"
)
PADRAO_MOEDA_BRL = re.compile(rf"\br\$\s*(?P<valor>{PADRAO_VALOR_DIGITOS})\b")
PADRAO_NUMERO_SIMPLES = re.compile(rf"(?<![\w‐‑–—-]){PADRAO_VALOR_DIGITOS}")
FatoNumerico = tuple[str, str]
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


def _normalizar_decimal(valor: str) -> str | None:
    texto = valor
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", texto):
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")
    try:
        numero = Decimal(texto)
    except InvalidOperation:
        return None
    normalizado = format(numero, "f")
    if "." in normalizado:
        normalizado = normalizado.rstrip("0").rstrip(".")
    return normalizado


def _normalizar_numero_extenso(valor: str) -> str | None:
    partes = valor.split()
    palavras = [parte for parte in partes if parte != "e"]
    if any(palavra not in PALAVRAS_NUMERICAS for palavra in palavras):
        return None
    numeros = [PALAVRAS_NUMERICAS[palavra] for palavra in palavras]
    if not numeros:
        return None
    if len(numeros) == 1:
        return str(numeros[0])
    if len(numeros) == 2 and numeros[0] in range(20, 100, 10) and 0 < numeros[1] < 10:
        return str(numeros[0] + numeros[1])
    return None


def _normalizar_valor(valor: str) -> str | None:
    return (
        _normalizar_decimal(valor)
        if valor[0].isdigit()
        else _normalizar_numero_extenso(valor)
    )


def _numeros(texto: str) -> set[FatoNumerico]:
    """Extrai fatos comparáveis, ignorando IDs e marcadores estruturais de lista."""

    normalizado = _normalizar(texto)
    normalizado = PADRAO_IDENTIFICADOR.sub(
        lambda match: " " * len(match.group()), normalizado
    )
    normalizado = PADRAO_MARCADOR_LISTA.sub(
        lambda match: " " * len(match.group()), normalizado
    )
    fatos: set[FatoNumerico] = set()
    intervalos: list[tuple[int, int]] = []

    def ocupado(inicio: int, fim: int) -> bool:
        return any(
            inicio < existente_fim and fim > existente_inicio
            for existente_inicio, existente_fim in intervalos
        )

    def adicionar(tipo: str, valor: str, inicio: int, fim: int) -> None:
        interpretado = _normalizar_valor(valor)
        fatos.add((tipo if interpretado is not None else "numero_desconhecido", interpretado or valor))
        intervalos.append((inicio, fim))

    for match in PADRAO_MOEDA_BRL.finditer(normalizado):
        adicionar("moeda_brl", match.group("valor"), *match.span())
    for match in PADRAO_PERCENTUAL.finditer(normalizado):
        if not ocupado(*match.span()):
            adicionar("percentual", match.group("valor"), *match.span())
    for match in PADRAO_DIAS.finditer(normalizado):
        if not ocupado(*match.span()):
            tipo = match.group("tipo")
            adicionar(f"dias_{tipo}" if tipo else "dias", match.group("valor"), *match.span())
    for padrao in (PADRAO_PERCENTUAL_DESCONHECIDO, PADRAO_DIAS_DESCONHECIDO):
        for match in padrao.finditer(normalizado):
            if not ocupado(*match.span()):
                adicionar("numero_desconhecido", match.group("valor"), *match.span())
    for match in PADRAO_NUMERO_SIMPLES.finditer(normalizado):
        if ocupado(*match.span()):
            continue
        valor = _normalizar_decimal(match.group())
        if valor is None:
            continue
        inteiro = Decimal(valor)
        tipo = "ano" if inteiro == inteiro.to_integral() and 1900 <= inteiro <= 2199 else "numero"
        fatos.add((tipo, valor))
    return fatos


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


def _diagnosticar_sustentacao(
    pergunta: str, resposta: str, corpus: str
) -> MotivoRejeicao | None:
    """Explica uma rejeição sem retornar qualquer conteúdo conversacional."""

    if not corpus.strip():
        return "sem_fontes_confiaveis"
    tokens_pergunta = _tokens(pergunta)
    tokens_corpus = _tokens(corpus)
    if not tokens_pergunta.intersection(tokens_corpus):
        return "sem_sobreposicao"

    numeros_pergunta = _numeros(pergunta)
    numeros_corpus = {
        fato for fato in _numeros(corpus) if fato[0] != "numero_desconhecido"
    }
    if any(fato[0] == "numero_desconhecido" for fato in numeros_pergunta):
        return "numero_pergunta_ausente"
    if numeros_pergunta and not numeros_pergunta.issubset(numeros_corpus):
        return "numero_pergunta_ausente"

    if tokens_pergunta.intersection(TERMOS_FATO_ESPECIFICO) and not numeros_corpus:
        return "fato_numerico_sem_evidencia"

    numeros_resposta = _numeros(resposta)
    if any(fato[0] == "numero_desconhecido" for fato in numeros_resposta):
        return "numero_resposta_incompativel"
    if numeros_resposta and not numeros_resposta.issubset(numeros_corpus):
        return "numero_resposta_incompativel"
    return None


def _evidencia_sustenta(pergunta: str, resposta: str, corpus: str) -> bool:
    return _diagnosticar_sustentacao(pergunta, resposta, corpus) is None


def diagnosticar_evidencia_pergunta(
    pergunta: str, resultados: Sequence[Mapping[str, Any]]
) -> MotivoRejeicao | None:
    """Diagnostica o gate anterior ao modelo sem expor pergunta ou documentos."""

    evidencias = _evidencias_confiaveis(resultados)
    corpus = " ".join(evidencias.values())
    return _diagnosticar_sustentacao(pergunta, "", corpus)


def evidencia_sustenta_pergunta(
    pergunta: str, resultados: Sequence[Mapping[str, Any]]
) -> bool:
    """Faz o gate conservador que independe de texto gerado pelo modelo."""

    return diagnosticar_evidencia_pergunta(pergunta, resultados) is None


def validar_resposta_backend_diagnosticada(
    *,
    resposta_candidata: str,
    pergunta: str,
    resultados_normas: Sequence[Mapping[str, Any]],
    resultado_protocolo: Mapping[str, Any] | None,
    erros: Sequence[str],
) -> tuple[RespostaAgente, MotivoRejeicao | None]:
    """Valida a resposta e retorna somente um código seguro quando houver rejeição."""

    if erros:
        return (
            RespostaAgente(
                resposta=str(erros[-1]), status="erro", fontes=[], protocolo=None
            ),
            None,
        )

    if resultado_protocolo is not None:
        protocolo = resultado_protocolo.get("protocolo")
        encontrado = resultado_protocolo.get("encontrado")
        status = resultado_protocolo.get("status")
        if encontrado is True and isinstance(protocolo, str) and isinstance(status, str):
            return (
                RespostaAgente(
                    resposta=f"O protocolo {protocolo} está com status {status}.",
                    status="respondida",
                    fontes=[],
                    protocolo=protocolo,
                ),
                None,
            )
        if encontrado is False and isinstance(protocolo, str):
            return (
                RespostaAgente(
                    resposta=f"O protocolo {protocolo} não foi encontrado.",
                    status="protocolo_nao_encontrado",
                    fontes=[],
                    protocolo=protocolo,
                ),
                None,
            )
        return (
            RespostaAgente(
                resposta="Falha controlada ao validar a consulta de protocolo.",
                status="erro",
                fontes=[],
                protocolo=None,
            ),
            None,
        )

    texto = resposta_candidata.strip()
    if not texto:
        return (
            RespostaAgente(
                resposta="O modelo não produziu uma resposta válida.",
                status="erro",
                fontes=[],
                protocolo=None,
            ),
            None,
        )

    evidencias = _evidencias_confiaveis(resultados_normas)
    fontes = sorted(evidencias)
    consulta_normativa = bool(resultados_normas) or pergunta_exige_evidencia(pergunta)
    if consulta_normativa:
        citacoes = {f"ACAD-{sufixo}" for sufixo in PADRAO_CITACAO.findall(texto)}
        if not citacoes.issubset(fontes):
            return _resposta_segura_sem_evidencia(), "citacao_nao_recuperada"
        fontes_declaradas = sorted(citacoes) if citacoes else fontes
        corpus = " ".join(evidencias[fonte] for fonte in fontes_declaradas)
        motivo = (
            "sem_fontes_confiaveis"
            if not fontes
            else _diagnosticar_sustentacao(pergunta, texto, corpus)
        )
        if motivo is not None:
            return _resposta_segura_sem_evidencia(), motivo
        return (
            RespostaAgente(
                resposta=texto,
                status="respondida",
                fontes=fontes_declaradas,
                protocolo=None,
            ),
            None,
        )

    if PADRAO_CITACAO.search(texto):
        return _resposta_segura_sem_evidencia(), "citacao_nao_recuperada"
    return (
        RespostaAgente(
            resposta=texto, status="respondida", fontes=[], protocolo=None
        ),
        None,
    )


def validar_resposta_backend(
    *,
    resposta_candidata: str,
    pergunta: str,
    resultados_normas: Sequence[Mapping[str, Any]],
    resultado_protocolo: Mapping[str, Any] | None,
    erros: Sequence[str],
) -> RespostaAgente:
    """Preserva o contrato público do validador sem expor o diagnóstico interno."""

    resposta, _ = validar_resposta_backend_diagnosticada(
        resposta_candidata=resposta_candidata,
        pergunta=pergunta,
        resultados_normas=resultados_normas,
        resultado_protocolo=resultado_protocolo,
        erros=erros,
    )
    return resposta
