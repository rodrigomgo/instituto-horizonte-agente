# ADR — Registro de decisões arquiteturais (05/11/2026)

## ADR-001 — CLI Python sem Docker (Aceita)

**Contexto:** enunciado aceita backend local Python e não exige UI, Docker ou API.  
**Decisão:** Python 3.12, `venv`, VS Code + Codex, CLI.  
**Alternativas:** Flask/FastAPI, Docker, React, Flutter, C#/.NET.  
**Motivo:** concentra esforço em RAG, LangChain, LangGraph e evidências — itens pontuados.  
**Consequência:** testes devem comprovar experiência multimensagem sem frontend.

## ADR-002 — Groq como provedor inicial, substituível (Aceita e validada)

**Contexto:** serviço remoto reduz exigência de hardware; conta gratuita pode ter limitação.  
**Decisão:** `ChatGroq`, modelo inicial `openai/gpt-oss-120b`, com Tool Calling real e Structured Output testados antes de avançar.  
**Alternativas:** Gemini API, outro modelo Groq compatível, OpenRouter, Ollama.  
**Revisão obrigatória:** uma chamada real que execute Tool local e uma resposta validada como Pydantic. Sem sucesso nesse smoke test, escolher alternativa e registrar novo ADR. Não afirmar que a cota é garantida.

**Validação registrada:** o estudante informou execução manual bem-sucedida com `openai/gpt-oss-120b`, Tool Calling de `somar_inteiros`, execução Python local, devolução do resultado ao modelo e Structured Output com os campos esperados. O Codex não repetiu essa chamada nem recebeu trace bruto; consulte `docs/evidencias_sdd/TSK-002.md`.

## ADR-003 — FastEmbed multilíngue + Chroma local (Aceita)

**Contexto:** 12 documentos curtos em português.  
**Decisão:** modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` por FastEmbed; Chroma persistente, um documento por registro, Top-K inicial 3.  
**Alternativas:** embeddings de API, Qdrant Cloud, LanceDB.  
**Motivo:** base pequena, custo operacional mínimo, modelo multilíngue confirmado na documentação oficial.  
**Consequência:** primeiro download pode ser lento; trocar modelo exige reindexar.

## ADR-004 — SQLite com protocolo fictício explicitado (Aceita)

**Contexto:** há T04 com `SOL-1001`, porém não há banco de protocolos no material do professor.  
**Decisão:** fixture documentada `SOL-1001` com status inicial `em_analise`; inserção com seed idempotente, sem manipular resposta conforme teste.  
**Consequência:** relatório deve deixar explícito que o status foi criado pelo projeto para simular dado persistido, não informado pelo docente.

## ADR-005 — Confirmação explícita em duas fases (Aceita)

**Contexto:** o requisito é registrar apenas com autorização; T05 tem intenção, mas está sem campos.  
**Decisão:** pedir dados + mostrar resumo + aguardar `CONFIRMAR` na **próxima mensagem**; a confirmação é validada no backend com rascunho pendente.  
**Alternativa:** considerar o comando inicial `Abra` como autorização imediata.  
**Motivo:** risco de escrita acidental e demonstração de limites do agente.  
**Consequência:** criar teste complementar multimensagem; o cenário T05 original não pode gerar protocolo.

## ADR-006 — RAG sem fonte inventada e sem limiar arbitrário (Aceita)

**Contexto:** busca vetorial sempre pode devolver um documento relativamente próximo, mesmo quando a pergunta é fora do domínio.  
**Decisão:** a recuperação apresenta fontes reais; o agente deve abster-se quando o conteúdo não sustenta a resposta; calibrar distância/score empiricamente com T09 e outros casos negativos.  
**Alternativa:** tratar qualquer Top-K como evidência.  
**Motivo:** evitar respostas falsas como preço da bolsa 2027.  
**Consequência:** registrar recuperações e decidir validação apenas após ver dados.

## ADR-007 — Escrita determinística e Tool tipada (Aceita)

**Contexto:** a saída de um LLM é não confiável para autorização.  
**Decisão:** o nó de escrita controlado pelo backend invoca a Tool de ação **após** confirmação validada; a camada de serviço também aplica guarda e idempotência.  
**Alternativa:** incluir `autorizado: bool` entre argumentos gerados pelo modelo.  
**Motivo:** um parâmetro autodeclarado pelo LLM não prova consentimento humano.  
**Consequência:** grafo terá ToolNode para leitura e nó/Tool equivalente seguro para escrita.

## ADR-008 — Reprodutibilidade antes de sofisticar a aplicação (Aceita)

**Contexto:** avaliação exige código, dependências, README, testes e evidências.  
**Decisão:** teste de instalação e API antes do RAG; commits por Task; relatório preenchido somente com saídas reais; não adicionar interface nem componentes extras sem necessidade.  
**Consequência:** maior chance de entrega concluída dentro das 24–36 horas.

## ADR-009 — Carregamento explícito de `.env` local (Aceita)

**Contexto:** a TSK-001 aceitava apenas variáveis previamente definidas no ambiente. Para desenvolvimento local no Windows, o estudante solicitou suporte seguro e reproduzível a um `.env` não versionado.
**Decisão:** usar `python-dotenv`; os pontos de entrada chamam explicitamente uma função que resolve `.env` pela raiz do projeto e usa `override=False`. Importar módulos não carrega arquivos. `Configuracao.from_env()` continua aceitando ambiente ou mapping sem depender de `.env`.
**Alternativas:** manter somente variáveis temporárias; carregar automaticamente durante imports; usar `pydantic-settings`.
**Motivo:** reduz atrito local preservando precedência do ambiente, testabilidade e ausência de efeitos colaterais na importação.
**Consequência:** `.env` deve permanecer no `.gitignore`; testes usam diretórios temporários e ambiente isolado; mensagens e resumos não podem revelar a chave.

## Decisões ainda a validar na implementação

- Distância mínima/critério de evidência do Chroma para perguntas sem resposta.
- Uso de ToolNode para escrita versus nó especializado; ambos devem demonstrar execução de Tool tipada, controle no backend e tracing.
- Versões fixadas de dependências e instruções executáveis no Windows.

**Autoria:** decisões propostas nesta especificação devem ser confirmadas/revisadas pelo estudante durante os marcos. O relatório final não deve afirmar revisões que não ocorreram.
