# Instituto Horizonte — Agente Inteligente (Projeto Integrador)

**Versão:** 0.1 — implementação incremental orientada pelos documentos SDD.
**Estado:** TSK-001 a TSK-011 concluídas; observabilidade e retry revisados e aprovados.

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
- Infraestrutura SQLite com schema reproduzível e seed idempotente de `SOL-1001`.
- Tool LangChain tipada `consultar_protocolo`, com acesso SQLite somente leitura.
- Tool `registrar_solicitacao` protegida por confirmação confiável e idempotência.
- `StateGraph` explícito com sessões em memória, Tools de leitura e rota de escrita protegida.
- Saída `RespostaAgente` validada por Pydantic e por evidências estruturadas das Tools.

Ainda não existe CLI conversacional nem execução automatizada ponta a ponta dos dez cenários. Esses itens pertencem às Tasks posteriores.

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

## Inicializar o banco de protocolos — TSK-005

O banco usa somente `sqlite3` da biblioteca padrão. O caminho padrão é `.local/protocolos.sqlite3`, resolvido a partir da raiz e ignorado pelo Git:

```powershell
python scripts/init_db.py
python scripts/init_db.py  # reexecução preserva a fixture sem duplicar
```

O script carrega `.env` explicitamente, com prioridade para variáveis já definidas. Um caminho absoluto pode ser usado para testes isolados:

```powershell
$env:SQLITE_PATH = "C:\temp\instituto-horizonte-teste.sqlite3"
python scripts/init_db.py
Remove-Item Env:SQLITE_PATH
```

A fixture `SOL-1001` é uma decisão do projeto: `tipo=solicitacao_academica_demonstracao`, `status=em_analise` e `origem=seed`. O professor forneceu apenas o número de exemplo, não o status. O inicializador não atualiza status ou timestamps existentes e interrompe de forma controlada se o ID 1001 estiver ocupado por registro incompatível.

Testes específicos, sem rede ou chave Groq:

```powershell
python -m pytest -q -p no:cacheprovider tests/test_database.py
```

Esta Task fornece somente schema, seed e verificação técnica. A Tool `consultar_protocolo` foi implementada posteriormente na TSK-006; a escrita autorizada pertence à TSK-007.

## Consultar protocolo existente — TSK-006

Inicialize o banco e consulte protocolos pelo terminal:

```powershell
python scripts/init_db.py
python scripts/consult_protocol.py SOL-1001
python scripts/consult_protocol.py SOL-9999
```

O script carrega `.env` explicitamente e respeita `SQLITE_PATH`. A consulta abre exclusivamente um banco existente em modo SQLite somente leitura; não cria schema, não executa seed e não altera solicitações. Números devem seguir `SOL-nnnn` com pelo menos quatro dígitos.

Invocação direta da Tool LangChain, sem LLM:

```powershell
python -c "from instituto_horizonte.protocols import consultar_protocolo; print(consultar_protocolo.invoke({'numero': 'SOL-1001'}))"
```

Testes específicos:

```powershell
python -m pytest -q -p no:cacheprovider tests/test_protocols.py
```

A Tool apenas verifica protocolos existentes. Ela não cria, altera, resolve ou cancela solicitações.

## Registrar solicitação autorizada — TSK-007

A única operação permitida é `segunda_via_certificado`, com turma e justificativa. O backend mantém um rascunho em memória, apresenta o resumo e somente aceita `CONFIRMAR` em uma interação posterior. `CANCELAR` descarta o rascunho sem escrita.

A Tool `registrar_solicitacao` não possui argumento `autorizado` ou `confirmado`. A autorização é transportada por contexto interno do backend e comparada aos dados validados; uma invocação direta da Tool é recusada antes de abrir o SQLite.

A persistência usa `BEGIN IMMEDIATE`, timestamps UTC, chave opaca criada pelo backend e a restrição `UNIQUE` do banco. Repetir a mesma chave com os mesmos dados retorna o protocolo existente; reutilizá-la com dados diferentes produz erro controlado.

Testes específicos, incluindo a demonstração determinística em banco temporário:

```powershell
python -m pytest -q -p no:cacheprovider tests/test_solicitacoes.py
```

O gerenciamento conversacional foi integrado ao LangGraph na TSK-008.

## Orquestração LangGraph — TSK-008

O grafo usa `StateGraph`, `START`, `END`, `ToolNode`, arestas condicionais e `InMemorySaver`. Somente `buscar_normas` e `consultar_protocolo` são vinculadas ao modelo. A Tool de escrita permanece fora do conjunto disponível ao LLM e é chamada pelo backend apenas depois de uma nova mensagem humana exatamente igual a `CONFIRMAR`, associada a um resumo pendente da mesma sessão.

Smoke test real e limitado aos cenários T01 e T04:

```powershell
python scripts/smoke_test_graph.py
```

O script carrega `.env` explicitamente, não imprime a chave e retorna falha controlada se a configuração ou o provedor falharem. Testes do grafo, sem rede:

```powershell
python -m pytest -q -p no:cacheprovider tests/test_graph.py
```

## Validação de respostas e evidências — TSK-009

Toda parte conversacional da saída valida no contrato Pydantic `RespostaAgente`: texto não vazio, status permitido, fontes acadêmicas e protocolo opcional. `ResultadoTurno` herda esse contrato e acrescenta somente sessão, rodadas, eventos de Tools e erros.

Fontes são aceitas exclusivamente a partir de `id` e `fonte` coincidentes nos resultados estruturados de `buscar_normas`. IDs mencionados pelo usuário, pelo modelo ou apenas no corpo de um documento não comprovam uma fonte. Quando o modelo cita um documento, fatos numéricos precisam existir no conteúdo desse mesmo documento.

O gate conservador de abstenção exige sobreposição temática e, para perguntas por valor, prazo, frequência ou percentual, evidência numérica explícita. Anos e outros números especificados na pergunta também precisam constar das normas recuperadas. Não é usado limiar arbitrário de distância vetorial.

Testes locais, sem Groq:

```powershell
python -m pytest -q -p no:cacheprovider tests/test_safety.py
```

Verificação real curta de T09, T10 e T01:

```powershell
python scripts/smoke_test_safety.py
```

O validador é deliberadamente conservador. Ele exige evidência também para perguntas sobre regras, procedimentos e serviços acadêmicos, mesmo sem termos numéricos; saudações e conversa simples continuam permitidas sem RAG. Ele comprova origem dos metadados, associação das citações e consistência de fatos numéricos explícitos, mas não pretende provar toda afirmação possível em linguagem natural.

## Atendimento interativo no terminal — TSK-010

O projeto representa o Instituto Horizonte, instituição fictícia, e usa somente dados acadêmicos simulados. Antes do primeiro atendimento, prepare o banco e o índice:

```powershell
python scripts/init_db.py
python scripts/index_documents.py
```

Configure `GROQ_API_KEY` pelo `.env` local ignorado pelo Git ou pela variável de ambiente e inicie uma das formas equivalentes:

```powershell
python -m instituto_horizonte --chat
instituto-horizonte --chat
```

O comportamento padrão continua sendo apenas validar a configuração. `--require-api-key` também permanece disponível.

Comandos locais da conversa:

- `/ajuda`: mostra instruções;
- `/sair`: encerra sem enviar o comando ao modelo;
- `CONFIRMAR` e `CANCELAR`: mensagens humanas de negócio, usadas separadamente quando houver resumo pendente.

Exemplo ilustrativo da apresentação:

```text
Você: Meu protocolo SOL-1001 já foi resolvido?

Instituto Horizonte:
O protocolo SOL-1001 está com status em_analise.

Status: respondida
Protocolo: SOL-1001
```

Uma única instância do agente e um identificador opaco são usados durante toda a sessão, preservando checkpointer e rascunhos. Linhas vazias e comandos locais não chamam Groq. Ctrl+C, EOF e caracteres incompatíveis com CP1252 são tratados sem traceback esperado.

## Logs auditáveis e falhas transitórias — TSK-011

Durante o atendimento, cada turno gera eventos JSONL em `artifacts/logs/agent.jsonl`, diretório ignorado pelo Git. Os comandos que apenas validam configuração não criam logs. Para inspecionar as últimas linhas no PowerShell:

```powershell
Get-Content artifacts/logs/agent.jsonl -Tail 20
```

Cada evento usa um schema fechado e pode conter timestamp UTC, `run_id`, `turn_id`, `session_id`, evento, nó, status, Tools, fontes, protocolo, rodadas, duração, categoria de erro e motivo de encerramento. Eventos de `buscar_normas` distinguem `fontes_recuperadas` daquela chamada das `fontes` aceitas na resposta final. Perguntas, prompts, respostas brutas, conteúdo documental, argumentos de Tools, chaves, senhas e justificativas não são registrados.

Falhas transitórias da chamada ao modelo — HTTP 429, timeout, conexão e HTTP 5xx — permitem no máximo duas novas tentativas, com espera curta e limitada. HTTP 400, 401 e 403 não são repetidos. O retry interno do `ChatGroq` permanece desativado para evitar acúmulo. Tools e operações de escrita nunca são repetidas por essa política.

## Versões validadas na TSK-002

- Python 3.12.10;
- `langchain-groq==1.1.3`;
- `langchain-core==1.7.6` (dependência transitiva observada);
- `groq==0.37.1` (dependência transitiva observada);
- `pydantic==2.14.3`;
- `python-dotenv==1.2.4`;
- `pytest==8.4.2`.

## Stack incorporada incrementalmente

LangGraph, FastEmbed, Chroma e a infraestrutura SQLite foram adicionados somente nas Tasks correspondentes. A TSK-008 usa `langgraph==1.2.20`.

## Restrições de origem

Os dados e perguntas oficiais não podem ser alterados para facilitar avaliação. A base de protocolos de teste será criada pelo projeto, pois **não foi fornecida** pelo professor. Nenhum `.env` secreto deve entrar no repositório. Saídas locais (`.local/`, `artifacts/`) e ambientes virtuais são ignorados.

## Próxima etapa

A TSK-011 foi concluída após revisão técnica do commit `8817bd1` e correção da rastreabilidade por chamada de recuperação. A próxima etapa planejada é a TSK-012, avaliação completa dos dez cenários; ela não foi iniciada nesta entrega.

## Referências de rastreabilidade

Material original: `Atividade_Aluno_IA_Avancada.docx` no ZIP recebido, `base_conhecimento_academica.json` e `cenarios_de_teste_aluno.csv`. Consulte as seções 4, 5, 7 e 8 do enunciado quanto a requisitos, entregáveis, avaliação e política de IA.
