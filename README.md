# Instituto Horizonte — Agente Inteligente (Projeto Integrador)

**Versão:** 0.1 — estrutura inicial da TSK-001.
**Estado:** pacote Python e validação de configuração implementados; integrações ainda não implementadas.

Projeto acadêmico de IA aplicada: RAG sobre 12 documentos fictícios, consultas de protocolos SQLite, registro autorizado de solicitações, LangChain, LangGraph, Pydantic, observabilidade e testes de dez cenários oficiais.

## Escopo implementado

- Pacote Python 3.12 no layout `src/`, instalável em modo editável.
- Configuração tipada e validada com Pydantic v2.
- Comando local que exibe somente um resumo seguro da configuração.
- Testes locais da configuração válida e inválida.
- Arquivos de ambiente de exemplo e exclusões para segredos e artefatos.

Não existem ainda LLM, RAG, Tools, LangGraph, SQLite nem execução dos dez cenários. Esses itens pertencem às Tasks posteriores.

## Conteúdo de referência

- `docs/00_INTENCAO.md`: propósito, escopo, critérios de sucesso.
- `docs/01_ESPECIFICACAO.md`: requisitos RF, regras do agente, schemas das três Tools, persistência e segurança.
- `docs/02_ARQUITETURA.md`: stack, fluxos, grafo, estado, árvore-alvo e links técnicos.
- `docs/03_PLANO.md`: marcos de implementação e gates de validação.
- `docs/04_TAREFAS.md`: backlog com dependências, estimativas e rastreabilidade.
- `docs/05_TESTES_E_ACEITE.md`: dez perguntas oficiais e testes complementares.
- `docs/06_ADR.md`: decisões arquiteturais justificadas.
- `docs/07_PROMPT_CODEX.md`: prompt para iniciar a primeira Task.
- `AGENTS.md`: instruções do repositório para o Codex.
- `data/base_conhecimento_academica.json`: arquivo **original** do professor, 12 documentos.
- `data/cenarios_de_teste_aluno.csv`: arquivo **original** do professor, 10 casos.

## Instalação local no Windows/PowerShell

Pré-requisito: Python 3.12. O projeto restringe a versão a `>=3.12,<3.13`.

```powershell
# Na raiz do projeto. Use `python` se o launcher `py` não estiver instalado.
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Se a política do PowerShell impedir a ativação, a instalação e os comandos podem ser executados diretamente:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m instituto_horizonte
```

O arquivo `.env.example` documenta as variáveis previstas. Na TSK-001 o pacote lê somente variáveis já presentes no ambiente e **não carrega `.env` automaticamente**. Não copie uma chave real para arquivos versionados.

## Validar configuração

```powershell
python -m instituto_horizonte
instituto-horizonte
```

Para verificar antecipadamente a ausência da chave que será usada na TSK-002:

```powershell
python -m instituto_horizonte --require-api-key
```

O comando retorna código `2` se uma configuração for inválida. O valor de `GROQ_API_KEY` nunca aparece no resumo.

Exemplo de configuração temporária na sessão atual do PowerShell:

```powershell
$env:RAG_TOP_K = "3"
$env:MAX_AGENT_ROUNDS = "6"
python -m instituto_horizonte
```

## Testes da TSK-001

```powershell
python -m pytest -q
```

Os testes cobrem valores padrão, conversão de variáveis, rejeição de limites inválidos e ocultação da chave. Eles não fazem chamadas externas.

## Stack planejada para Tasks posteriores

Groq API (`openai/gpt-oss-120b`, sujeito a verificação); LangChain; LangGraph; FastEmbed multilíngue; Chroma local persistente e SQLite. Nenhuma dessas integrações foi adicionada na TSK-001.

## Restrições de origem

Os dados e perguntas oficiais não podem ser alterados para facilitar avaliação. A base de protocolos de teste será criada pelo projeto, pois **não foi fornecida** pelo professor. Nenhum `.env` secreto deve entrar no repositório. Saídas locais (`.local/`, `artifacts/`) e ambientes virtuais são ignorados.

## Próxima etapa

Após revisão humana da TSK-001, a TSK-002 deve realizar o smoke test real de Groq, Tool Calling e Structured Output. Não avance para a orquestração antes desse gate técnico.

## Referências de rastreabilidade

Material original: `Atividade_Aluno_IA_Avancada.docx` no ZIP recebido, `base_conhecimento_academica.json` e `cenarios_de_teste_aluno.csv`. Consulte as seções 4, 5, 7 e 8 do enunciado quanto a requisitos, entregáveis, avaliação e política de IA.
