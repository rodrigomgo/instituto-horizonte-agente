# Prompt de arranque para o Codex — TSK-001

Cole o texto abaixo no painel do Codex, após abrir a pasta do projeto no VS Code.

---

Você está desenvolvendo o projeto acadêmico **Instituto Horizonte — Agente Inteligente de Atendimento Acadêmico**, em Python 3.12, conforme os documentos SDD desta pasta.

Leia primeiro `AGENTS.md`, `docs/00_INTENCAO.md`, `docs/01_ESPECIFICACAO.md`, `docs/02_ARQUITETURA.md`, `docs/03_PLANO.md`, `docs/04_TAREFAS.md`, `docs/05_TESTES_E_ACEITE.md` e `docs/06_ADR.md`.

**Implemente exclusivamente TSK-001:** estrutura de pacote Python em `src/`, suporte a Windows/PowerShell com `venv`, arquivos `.env.example` e `.gitignore`, validação inicial de configurações e documentação de instalação local em `README.md`. Preserve integralmente os arquivos oficiais em `data/`. Não implemente LLM, RAG, Tools, LangGraph ou scripts de testes de cenário nesta Task.

Condições:

1. Não inclua segredos nem `.env` real. Use Python 3.12 e dependências mínimas, sem Docker.
2. Não invente que comandos ou testes passaram: execute os que estiverem disponíveis e mostre saída real; se não puder executá-los, declare isso.
3. Planeje antes de codar: resuma arquivos a criar/alterar, riscos e critérios de aceite, e então implemente.
4. Configure `src/` de modo que a invocação do futuro pacote seja reprodutível (`pyproject.toml` + `pip install -e .` é permitido), sem instalar dependências pesadas prematuramente.
5. Ao terminar, informe arquivos criados, comandos de execução, testes realizados, limitações e uma sugestão de mensagem de commit citando TSK-001.
6. Não altere documentos SDD para justificar desvio de escopo sem antes explicar a decisão.

Pare ao concluir TSK-001. Não avance automaticamente para TSK-002.

---

## Próxima etapa

Após revisar os arquivos e validar o ambiente, pedir TSK-002: smoke test real com Groq, Tool Calling e Pydantic. Esta etapa é um gate técnico: não prosseguir à orquestração se a integração não funcionar.
