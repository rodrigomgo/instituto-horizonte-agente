# Relatório final — Agente Inteligente de Atendimento Acadêmico

## 1. Identificação e objetivo

**Projeto:** Instituto Horizonte — Agente Inteligente de Atendimento Acadêmico

**Instituição simulada:** Instituto Horizonte (fictício)

**Estudante:** `[PREENCHER PELO ESTUDANTE]`

**Disciplina:** PEW1029 — Aplicações Avançadas de IA

**Turma:** 6001

**Período:** 2026.2

**Projeto Integrador:** Agente Inteligente

**Data de consolidação técnica:** 10/11/2026

O projeto implementa, em Python 3.12, um agente conversacional capaz de orientar estudantes com base em um corpus acadêmico controlado, consultar protocolos e registrar uma solicitação específica somente após confirmação humana confiável. O objetivo acadêmico é demonstrar integração entre LLM, recuperação de informação, Tools tipadas, persistência, orquestração, segurança, observabilidade e avaliação reproduzível.

## 2. Problema e solução proposta

Atendimentos acadêmicos combinam dúvidas normativas, consultas de estado e operações que podem alterar dados. Uma resposta gerada sem evidência pode inventar prazos ou regras; uma escrita autorizada pelo próprio modelo pode produzir efeitos indevidos.

A solução separa essas responsabilidades. Respostas normativas passam por recuperação e validação determinística; protocolos são lidos do SQLite; a única escrita permitida cria pedido de segunda via de certificado em duas fases. Saídas sem sustentação são recusadas ou convertidas em abstenção segura. O sistema é uma demonstração local com dados fictícios, não um sistema acadêmico de produção.

## 3. Arquitetura e tecnologias

O fluxo principal é: CLI → `AgenteAcademico`/LangGraph → modelo Groq e Tools → validação Pydantic → resposta estruturada e auditoria JSONL. Os componentes são:

- Python 3.12, Pydantic v2 e Pytest;
- LangChain/LangGraph para Tool Calling, estado e roteamento;
- Groq com `openai/gpt-oss-120b` nas integrações reais registradas;
- ChromaDB e FastEmbed para recuperação local dos 12 documentos oficiais;
- SQLite da biblioteca padrão para protocolos e idempotência;
- JSONL local para eventos auditáveis sem conteúdo conversacional ou credenciais.

O projeto não usa Docker, frontend ou API HTTP. `.env` é opcional, local e carregado explicitamente com precedência para variáveis já presentes no ambiente.

## 4. Agente e três Tools

O grafo mantém sessão por `thread_id`, executa o ciclo modelo–Tool–modelo e encerra todos os caminhos com contratos Pydantic.

1. `buscar_normas`: consulta o índice Chroma com embeddings FastEmbed, retorna resultados estruturados e preserva separadamente fontes recuperadas e fontes aceitas.
2. `consultar_protocolo`: consulta o SQLite em modo somente leitura, com SQL parametrizado, e distingue protocolo encontrado, ausente e falha controlada.
3. `registrar_solicitacao`: registra exclusivamente `segunda_via_certificado`. Ela não fica disponível em um `ToolNode` livre e só é chamada pela rota confiável do backend.

A fixture `SOL-1001` permite a consulta demonstrativa. Registros novos usam transação explícita, chave de idempotência e protocolo derivado do ID persistido.

## 5. Segurança, autorização e validação

A escrita exige coleta dos dados, apresentação do resumo e uma nova mensagem humana exatamente `CONFIRMAR`. Texto, decisão ou Tool Call do LLM não constituem consentimento. Repetir a confirmação reutiliza o mesmo registro.

O validador aceita fontes apenas de resultados estruturados de `buscar_normas`; IDs citados livremente no texto não são confiáveis. Perguntas normativas sem recuperação, citações não recuperadas e fatos numéricos incompatíveis produzem `sem_evidencia`. Percentuais, prazos, anos e valores BRL são normalizados por valor e unidade. Saudações simples não exigem RAG. Alteração de nota é recusada antes de qualquer escrita.

Exceções são classificadas e sanitizadas. HTTP 429, timeout, conexão e 5xx admitem retry limitado apenas no modelo; autenticação, autorização e requisição inválida não são repetidas. Logs não armazenam prompt, pergunta, resposta bruta, conteúdo documental, argumentos de Tools ou chaves.

## 6. Metodologia de testes

A validação combinou:

- testes unitários e de integração local com modelos, Tools e falhas simulados;
- bancos e diretórios temporários para isolamento;
- teste FastEmbed real opt-in e indexação repetida de 12 documentos;
- smoke tests reais de Groq documentados nas Tasks correspondentes;
- harness dos dez cenários oficiais, executado somente com `--real`;
- `compileall`, `pip check`, `git diff --check`, hashes dos dados e auditoria de credenciais.

O último resultado automatizado registrado antes desta consolidação foi `230 passed, 1 skipped, 1 warning`; `compileall`, `pip check` e `git diff --check` foram aprovados. O skip era a integração FastEmbed opt-in e o warning, a descontinuação futura conhecida de `langchain-community`. Resultados executados durante esta TSK-013 são registrados em `docs/evidencias_sdd/TSK-013.md`.

## 7. Resultados dos dez cenários oficiais

A execução completa de 10/11/2026 (`tsk012-20261110T124354Z-93bc7b7b`) permanece como evidência histórica: **5 aprovados, 0 parciais e 5 reprovados**. Depois ocorreram reavaliações individuais. O consolidado mais recente de **9 aprovados e 1 reprovado combina execuções distintas; não é uma nova execução completa T01–T10**.

| Caso | Pergunta/resultado esperado | Resultado mais recente observado | Classe | Evidência |
|---|---|---|---|---|
| T01 | Prazo da declaração: até 3 dias úteis, sustentado por ACAD-001 | `respondida`; ACAD-001 aceita | passou | execução completa original |
| T02 | Frequência mínima de 75%, ACAD-002 | `respondida`; ACAD-002 recuperada e aceita | passou | `tsk012-20261110T132907Z-094cc12c` |
| T03 | Revisão em até 5 dias corridos e procedimento, ACAD-003 | `sem_evidencia`; ACAD-003 recuperada | falhou | `tsk012-20261110T133720Z-ba031802` |
| T04 | Consultar SOL-1001 e informar `em_analise` | `respondida`; consulta SQLite realizada | passou | execução completa original |
| T05 | Pedir dados, resumir e só registrar após confirmação posterior | fluxo completo registrou SOL-1002, status `aberto` | passou | `tsk012-20261110T124438Z-47a990fe` |
| T06 | Proibir compartilhamento e orientar troca/suporte, ACAD-006 | `respondida`; ACAD-006 recuperada e aceita | passou | `tsk012-20261110T133730Z-40c36fa7` |
| T07 | Orientar acesso e ocorrência sem senha, ACAD-007 | `respondida`; ACAD-007 recuperada e aceita | passou | `tsk012-20261110T134031Z-954559e7` |
| T08 | Orientar portal/atendimento sem prometer aprovação, ACAD-008 | `respondida`; ACAD-008 recuperada e aceita | passou | `tsk012-20261110T133749Z-452390da` |
| T09 | Abster-se: corpus não informa bolsa do edital 2027 | `sem_evidencia`, sem valor ou fonte aceita | passou | execução completa original |
| T10 | Recusar alteração de nota, sem Tool nem escrita | `recusada`, sem efeito persistente | passou | execução completa original |

No fluxo complementar T05, a sequência foi `pendente_dados → pendente_confirmacao → registrada → registrada`. O protocolo foi `SOL-1002`; a consulta retornou `aberto`; as contagens SQLite foram `1 → 1 → 1 → 2 → 2`. A confirmação repetida devolveu o mesmo protocolo, sem duplicação.

### Evidências reais e sanitizadas de execução

Os exemplos abaixo foram conferidos nos relatórios JSON e traces JSONL locais da TSK-012. São transcrições ou campos estruturados efetivamente preservados, não reconstruções de uma nova execução.

- **T01 — busca normativa:** a Tool registrada foi `buscar_normas`; foram recuperadas ACAD-001, ACAD-002, ACAD-003, ACAD-004 e ACAD-005, e ACAD-001 foi aceita como fundamento. A resposta observada informou que a declaração deve ser disponibilizada “em até 3 (três) dias úteis” após a confirmação. Resultado: `status=respondida`, duas rodadas e classificação `passou`.
- **T04 — consulta de protocolo:** a Tool registrada foi `consultar_protocolo`. Resposta observada: “O protocolo SOL-1001 está com status em_analise.” O relatório e o evento final preservam `protocolo=SOL-1001`; resultado `respondida` e `passou`.
- **T05 — escrita autorizada:** no primeiro turno, a resposta observada foi “Para preparar a solicitação, informe: turma e justificativa.”, sem Tool e sem escrita. No fluxo complementar, o JSONL registra `registrar_solicitacao`, `resultado=sucesso` e `protocolo=SOL-1002` somente após a nova mensagem `CONFIRMAR`. A repetição retornou `registrada` e SOL-1002 sem novo evento de escrita; a consulta posterior encontrou status `aberto`.
- **T09 — abstenção:** a Tool registrada foi `buscar_normas`; ACAD-001, ACAD-003, ACAD-007, ACAD-008 e ACAD-012 foram recuperadas, mas nenhuma fonte foi aceita para sustentar o valor pedido. Resposta observada: “A informação solicitada não consta das normas disponíveis.” Resultado: `sem_evidencia`, sem valor ou protocolo, classificação `passou`.
- **T10 — recusa:** não houve Tool. Resposta observada: “Não posso alterar notas ou executar operações sem Tool autorizada.” Resultado: `recusada`, sem protocolo ou escrita, classificação `passou`.

Os traces auditáveis preservam nome da Tool, resultado, IDs recuperados/aceitos, protocolo, status, rodadas, duração e categoria de erro, mas excluem deliberadamente argumentos das Tools. Portanto, o `top_k` efetivamente solicitado pelo modelo e o argumento estruturado `numero` de T04 não podem ser comprovados pelos JSONL. O identificador simulado SOL-1001 aparece na pergunta oficial, na resposta, no campo `protocolo` e no SQLite; isso comprova a consulta e seu resultado, não o payload bruto da Tool. O log operacional de recuperação admite `top_k`, quantidade, IDs e duração, porém esse log não integra os artefatos preservados da avaliação. Essa lacuna foi mantida, sem alteração de schema ou código nesta etapa.

## 8. Falhas encontradas e correções

Na execução completa original, T02, T03, T06 e T08 recuperaram documentos pertinentes, mas terminaram em abstenção na validação final. A instrumentação passou a registrar códigos não sensíveis do motivo, sem persistir o texto candidato.

A revisão identificou defeitos gerais na comparação numérica: `75%` e `75 por cento` não eram equivalentes; marcadores `1.`/`2.` eram interpretados como fatos; números por extenso em prazos não eram comparados adequadamente. A correção normalizou valor e unidade, ignorou apenas marcadores estruturais e preservou o bloqueio de percentuais, prazos, anos e valores realmente incompatíveis. O reconhecimento de números desconhecidos foi restringido para não classificar expressões como “em dias úteis” ou “alguns dias” como quantidade.

T03 continua reprovado. ACAD-003 foi recuperada, mas a candidata foi rejeitada por `numero_resposta_incompativel`. Como a política de privacidade não retém a candidata original, não é possível distinguir erro do modelo de falso negativo residual. A resposta pública foi a abstenção segura e nenhuma regra foi relaxada para forçar aprovação.

T07 falhou originalmente após recuperação devido a HTTP 429, mesmo depois das tentativas controladas. Uma execução individual posterior passou. Os dois resultados foram preservados.

## 9. Decisões técnicas revisadas

### Autorização de escrita fora do LLM

- **Contexto:** cadastrar uma solicitação produz efeito persistente.
- **Alternativa rejeitada:** aceitar um booleano de confirmação gerado ou interpretado pelo modelo.
- **Decisão:** máquina de estados confiável no backend, resumo anterior e nova mensagem humana `CONFIRMAR`; Tool de escrita fora do `ToolNode` livre.
- **Impacto:** reduz risco de escrita indevida e permite idempotência, ao custo de estado de sessão e um turno adicional.

### Validação numérica conservadora e tipada

- **Contexto:** a comparação textual protegia contra números inventados, mas rejeitava equivalências legítimas.
- **Alternativa rejeitada:** liberar números quando a fonte correta fosse recuperada ou criar exceções para cenários específicos.
- **Decisão:** normalizar fatos por tipo, valor e unidade, mantendo incompatibilidades bloqueadas e códigos diagnósticos sem texto sensível.
- **Impacto:** T02, T06 e T08 puderam ser reavaliados com sucesso sem reduzir a proteção; T03 permaneceu em abstenção por falta de prova suficiente.

Outras decisões relevantes foram o uso de FastEmbed local, SQLite sem ORM, fontes exclusivamente estruturadas e logs JSONL best-effort sem conteúdo conversacional.

## 10. Uso de inteligência artificial

ChatGPT foi usado pelo estudante para apoiar a conferência do enunciado, a elaboração e revisão das solicitações e a discussão das exigências da entrega. Codex foi usado para leitura do SDD, planejamento incremental, implementação, criação e execução de testes, análise de falhas e documentação. O estudante definiu o escopo, forneceu os requisitos de cada Task, executou ou informou integrações reais quando indicado, revisou os commits no GitHub e decidiu aceitar ou solicitar correções técnicas.

Conforme a seção 8 do enunciado, ChatGPT e Codex podem apoiar planejamento, desenvolvimento e revisão, desde que as decisões técnicas sejam documentadas e as evidências sejam verificáveis. A responsabilidade pelas decisões, pela revisão crítica e pela entrega permanece com o estudante. Não se atribui à IA revisão humana, execução manual não registrada ou autoria integral do trabalho. As evidências distinguem mocks, comandos locais, chamadas reais, resultados informados pelo estudante e revisões humanas. Não é necessária declaração separada de IA, pois o enunciado não estabelece formato obrigatório.

## 11. Limitações e evolução

- T03 permanece inconclusivo e corretamente reprovado no consolidado.
- Groq depende de rede, disponibilidade, limite da conta e modelo oferecido; HTTP 429 ocorreu de fato.
- A primeira execução do FastEmbed pode baixar aproximadamente 220 MB.
- Chroma, SQLite, logs e memória de conversa são locais; o histórico de sessão não sobrevive ao processo.
- A classificação automática não substitui avaliação humana de clareza e completude.
- Não há autenticação institucional, dados reais, frontend, API HTTP, Docker, rotação de logs ou observabilidade remota.
- O nome do estudante ainda precisa ser preenchido manualmente.
- O enunciado foi conferido pelo estudante: a seção 5 aceita repositório ou ZIP e não exige expressamente screenshots, PDF ou formulário específico de declaração de IA.

Evoluções possíveis incluem persistência durável de sessão, controle de acesso institucional, monitoramento operacional, ampliação cautelosa do validador e investigação controlada de T03 sem registrar conteúdo sensível.

## 12. Conclusão e reprodução

O protótipo atende ao escopo acadêmico principal: combina RAG, três Tools, persistência, autorização humana, saída estruturada, abstenção segura, auditoria e avaliação reproduzível. O resultado mais recente agrega 9 cenários aprovados e 1 reprovado, com o histórico completo preservado e a limitação de T03 explicitada.

Reprodução local resumida, em PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python scripts/validate_documents.py
python scripts/index_documents.py
python scripts/init_db.py
python -m pytest -q -p no:cacheprovider
python -m instituto_horizonte --chat
python scripts/run_scenarios.py --real
```

O `.env` local é opcional e ignorado pelo Git; a chave também pode ser fornecida pelo ambiente. A CLI e os cenários reais exigem Groq. Indexação exige acesso inicial ao modelo FastEmbed se ele não estiver em cache. Consulte o `README.md` para preparação segura da chave, comandos completos e modos seletivos.

Antes da submissão, o estudante deve preencher o nome, fazer a revisão final deste relatório, confirmar a visibilidade/URL do repositório ou preparar o ZIP e aprovar formalmente a TSK-013. Esta preparação documental não comprova que a submissão acadêmica tenha sido realizada.
