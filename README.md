# Instituto Horizonte — Agente Inteligente (Projeto Integrador)

**Versão:** 0.1 — implementação incremental orientada pelos documentos SDD.
**Estado:** TSK-001 a TSK-004 concluídas; RAG local com FastEmbed, Chroma e `buscar_normas` validado.

Projeto acadêmico de IA aplicada: RAG sobre 12 documentos fictícios, consultas de protocolos SQLite, registro autorizado de solicitações, LangChain, LangGraph, Pydantic, observabilidade e testes de dez cenários oficiais.

## Escopo implementado

- Pacote Python 3.12 no layout `src/`, instalável em modo editável.
- Configuração tipada e validada com Pydantic v2.
- Comando local que exibe somente um resumo seguro da configuração.
- Testes locais da configuração válida e inválida.
- Arquivos de ambiente de exemplo e exclusões para segredos e artefatos.
- Smoke test reproduzível de Tool Calling local e Structured Output Pydantic via Groq.
- Loader validado dos 12 documentos acadêmicos oficiais.
- Indexação Chroma persistente e idempotente com FastEmbed local.
- Tool tipada `buscar_normas`, com distâncias brutas e logs sanitizados de recuperação.

Ainda não existem SQLite, LangGraph, as Tools de protocolo/registro nem execução ponta a ponta dos dez cenários. Esses itens pertencem às Tasks posteriores.

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

O arquivo `.env.example` documenta as variáveis previstas. Os pontos de entrada carregam explicitamente o arquivo `.env` da raiz do projeto; a importação dos módulos, por si só, não altera o ambiente. Variáveis já definidas no sistema têm prioridade sobre o arquivo local.

Para desenvolvimento local, crie o arquivo ignorado pelo Git e preencha a chave em um editor, nunca no comando:

```powershell
Copy-Item .env.example .env
code .env
```

Não versione nem compartilhe `.env`. A ausência desse arquivo é aceita e configurações fornecidas diretamente pelo ambiente continuam funcionando.

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

## Smoke test Groq da TSK-002

Opção sem `.env`: defina temporariamente a chave sem colocá-la no comando nem no histórico do PowerShell:

```powershell
$chaveSegura = Read-Host "GROQ_API_KEY" -AsSecureString
$ponte = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($chaveSegura)
try {
    $env:GROQ_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ponte)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ponte)
}
python scripts/smoke_test_llm.py
Remove-Item Env:GROQ_API_KEY
```

O script faz chamadas reais e separadas:

1. o LLM solicita a Tool demonstrativa `somar_inteiros` com argumentos tipados;
2. o Python executa localmente a soma, sem escrita, e envia o resultado de volta;
3. o LLM produz uma resposta final;
4. outra chamada usa JSON Schema estrito e valida `SaidaEstruturadaSmoke` com Pydantic.

O script não imprime a chave nem a mensagem bruta de exceções do provedor.

## Testes locais sem rede

```powershell
python -m pytest -q -p no:cacheprovider
```

Os testes cobrem configuração, fluxo mock de Tool Calling, ausência de chave, HTTP 401, timeout, HTTP 429, saída estruturada inválida e ocultação da chave. Eles não fazem chamadas externas.

## Validar a base acadêmica — TSK-003

O JSON oficial é carregado em UTF-8, validado por Pydantic e preparado de forma determinística, com um documento por registro e sem gerar embeddings:

```powershell
python scripts/validate_documents.py
python -m pytest -q -p no:cacheprovider
```

O script não requer `GROQ_API_KEY` nem acesso à internet. Ele exibe quantidade, IDs, categorias e hashes SHA-256 do campo `conteudo`, sem modificar os arquivos em `data/`.

## Indexar e consultar normas — TSK-004

Na primeira execução, o FastEmbed baixa aproximadamente 220 MB para `.local/fastembed_cache`. O índice Chroma persistente fica em `.local/chroma`; ambos são ignorados pelo Git e não usam Groq:

```powershell
python scripts/index_documents.py
python scripts/index_documents.py  # repetição idempotente: permanece com 12 registros
python scripts/evaluate_retrieval.py
```

Consulta direta pela Tool LangChain tipada:

```powershell
python -c "from instituto_horizonte.retrieval import buscar_normas; print(buscar_normas.invoke({'consulta': 'Qual é o prazo da declaração de matrícula?', 'top_k': 3}))"
```

Para usar outro diretório local sem alterar o padrão:

```powershell
$env:CHROMA_DIR = ".local/chroma-alternativo"
python scripts/index_documents.py
Remove-Item Env:CHROMA_DIR
```

Testes unitários usam embeddings falsos e não baixam modelos. A integração real é habilitada separadamente:

```powershell
python -m pytest -q -p no:cacheprovider
$env:RUN_FASTEMBED_TESTS = "1"
python -m pytest -q -p no:cacheprovider tests/test_fastembed_real.py
Remove-Item Env:RUN_FASTEMBED_TESTS
```

As distâncias retornadas são distâncias de cosseno brutas, não percentuais de confiança. A TSK-004 não define limiar de abstenção.

## Versões validadas na TSK-002

- Python 3.12.10;
- `langchain-groq==1.1.3`;
- `langchain-core==1.7.6` (dependência transitiva observada);
- `groq==0.37.1` (dependência transitiva observada);
- `pydantic==2.14.3`;
- `python-dotenv==1.2.4`;
- `pytest==8.4.2`.

## Stack planejada para Tasks posteriores

SQLite e LangGraph ainda não foram adicionados. FastEmbed multilíngue e Chroma local persistente foram validados na TSK-004.

## Restrições de origem

Os dados e perguntas oficiais não podem ser alterados para facilitar avaliação. A base de protocolos de teste será criada pelo projeto, pois **não foi fornecida** pelo professor. Nenhum `.env` secreto deve entrar no repositório. Saídas locais (`.local/`, `artifacts/`) e ambientes virtuais são ignorados.

## Próxima etapa

A TSK-004 foi concluída após revisão humana e correções técnicas. A próxima etapa planejada é a TSK-005, que implementará SQLite e o seed reexecutável do protocolo fictício `SOL-1001`; ela não faz parte desta entrega.

## Referências de rastreabilidade

Material original: `Atividade_Aluno_IA_Avancada.docx` no ZIP recebido, `base_conhecimento_academica.json` e `cenarios_de_teste_aluno.csv`. Consulte as seções 4, 5, 7 e 8 do enunciado quanto a requisitos, entregáveis, avaliação e política de IA.
