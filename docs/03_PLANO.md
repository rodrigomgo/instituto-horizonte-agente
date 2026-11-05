# PLAN — Plano de implementação orientado por marcos

**Modo de trabalho:** VS Code + Codex; uma Task por vez, com revisão, teste e commit.  
**Tempo previsto:** 24–36 horas, com referência de planejamento de 30 horas.  
**Entrega atual:** somente documentação SDD, dados oficiais e instruções para o Codex; **não** há aplicação implementada nesta fase.

## Marco M0 — Especificação (entrega atual)

- Finalizar Intent, Spec, arquitetura, Tasks, testes e decisões.
- Registrar escolhas [DOCENTE] x [PROJETO].
- Aceite: documentação consistente e dados canônicos presentes no repositório.

## Marco M1 — Ambiente e viabilidade de modelo (2–3 h)

- Configurar projeto Python 3.12, venv, `.env.example` e `.gitignore`.
- Instalar somente dependências necessárias; criar smoke test real que prova Tool Calling e Structured Output com o Groq escolhido.
- Testar erro sem chave, 429/timeout com mocks, sem necessidade de consumir cota real para cada falha.
- **Bloqueio de avanço:** não construir grafo inteiro antes de comprovar que modelo + LangChain funcionam. Se falhar, revisar ADR-002.

## Marco M2 — Dados e recuperação (3–5 h)

- Carregar e validar o JSON original; gerar embeddings; persistir Chroma.
- Testar consultas associadas a T01–T03 e T06–T09; registrar IDs retornados e scores/distâncias observados.
- Calibrar `top_k` e procedimento de abstenção; decidir sobre qualquer limiar **a partir de dados reais**.
- Aceite: 12 registros indexados, sem duplicação, com metadados fiéis.

## Marco M3 — Persistência e três Tools (4–6 h)

- SQLite com `SOL-1001` fictício e script de seed idempotente.
- Tools tipadas: busca, consulta, registro; testar validação de argumentos.
- Implementar guarda de autorização, transação e idempotência no registro.
- Aceite: consultas corretas e nenhum registro sem confirmação; escrita autorizada consultável.

## Marco M4 — Orquestração (4–6 h)

- `AgentState` e `StateGraph`, nó agente, nó leitura, nó real de validação/autorização e rotas condicionais.
- Sessão multimensagem, estado de rascunho e `CONFIRMAR`/`CANCELAR`.
- Controle de rodadas e fallback para schema/LLM/tool errors.
- Aceite: fluxos T01, T04, T05 e T10 reproduzidos manualmente com trace.

## Marco M5 — Segurança, qualidade e relatório (7–10 h)

- Testes unitários e de integração; executar os dez casos originais sem alterar textos.
- Registrar resultados reais, classificações, logs sanitizados e ao menos uma limitação/falha analisada.
- README com instalação, ingestão, execução e comandos de teste; documentação da ajuda de IAs e de 2 decisões revisadas pelo estudante.
- Aceite: checklist do enunciado preenchido, ambiente reproduzível e nenhuma credencial no repositório.

## Regra de avanço

Uma Task só muda para `Concluída` após o Codex: (1) indicar arquivos alterados, (2) apresentar comandos usados, (3) apresentar saídas reais de testes, (4) reconhecer limitações e (5) obter revisão humana do comportamento esperado. Nenhuma evidência pode ser fabricada.

## Estratégia de commits

Formato sugerido: `docs(sdd): ...`, `chore(env): ...`, `feat(rag): ...`, `feat(tools): ...`, `feat(graph): ...`, `test(scenarios): ...`, `docs(report): ...`. Associar o ID da Task ao corpo da mensagem.

## Regra para desvios

Se a decisão técnica mudar (ex.: Groq indisponível), criar uma entrada ADR com contexto, alternativas, justificativa, impacto em requisitos e novo teste de aceitação. A decisão fica com o estudante, não com o Codex.
