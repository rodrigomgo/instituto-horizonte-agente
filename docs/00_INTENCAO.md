# INTENT — Agente Inteligente de Atendimento Acadêmico

**Projeto:** Instituto Horizonte (instituição fictícia)  
**Disciplina:** Aplicações Avançadas de IA — Projeto Integrador, turma 6001, 2026.2  
**Versão:** 0.1 — especificação inicial, 05/11/2026  
**Situação:** aprovada a direção técnica; implementação ainda não iniciada.

## 1. Problema

Construir um agente conversacional executável, verificável e seguro que responda dúvidas acadêmicas com fontes, consulte protocolos **existentes** e registre solicitações **somente com autorização explícita**. O objetivo acadêmico é demonstrar separação entre LLM, recuperação de conhecimento, Tools, orquestração e validação, com evidências reais de execução.

## 2. Resultado esperado

Uma aplicação Python em terminal, em português do Brasil, capaz de:

1. Consultar a base oficial simulada (12 documentos, ACAD-001 a ACAD-012) por RAG, usando embeddings e banco vetorial local.
2. Responder dúvidas citando IDs das fontes realmente recuperadas, sem fabricar prazos ou regras.
3. Consultar em SQLite um protocolo simulado como `SOL-1001` e devolver o estado efetivamente encontrado.
4. Orientar e executar a abertura de solicitações permitidas, validando os dados, exibindo um resumo e exigindo confirmação explícita antes de gravar.
5. Recusar alterações de nota e demais ações sem ferramenta/autorização.
6. Fornecer resposta tipada e logs de decisões e ações, permitindo avaliar os dez cenários do professor.

## 3. Critérios de sucesso

- O sistema é executável em Windows no VS Code, com `venv`, sem Docker, frontend, GPU ou serviço pago obrigatório.
- Os 12 documentos são indexados com `fonte`, `categoria`, `titulo` e `id` preservados.
- As três Tools exigidas estão implementadas com entradas validadas.
- Há um `StateGraph` com pelo menos um nó de validação real e controle de ciclos.
- Os dez casos oficiais são executados e documentados com classificação `passou`, `parcial` ou `falhou`, evidência e limitação.
- Um fluxo de registro completo, incluindo confirmação do usuário, gera um protocolo persistido e consultável depois.
- Uma entrada adversarial solicitando alteração de nota não provoca modificação de dados.
- Código, README, dependências, `.env.example` e relatório são reproduzíveis; nenhuma chave é versionada.
- Há rastreabilidade do processo SDD: Intent → Spec → Plan → Tasks → Implement/Test/Validate.

## 4. Público e responsabilidades

- **Operador:** aluno que executa o aplicativo e valida os resultados.
- **Usuário simulado:** estudante do Instituto Horizonte, que pergunta, consulta e solicita.
- **Agente:** sugere e consulta; não tem autoridade para inventar regras ou executar operações fora das Tools.
- **Backend:** controla autorização, persistência, formatos, limites e auditoria; nunca delega segurança exclusivamente ao LLM.

## 5. Escopo negativo (decisões de projeto)

Não desenvolver, salvo exigência nova: interface web, API HTTP, autenticação real de estudantes, alteração de notas, integração com sistema acadêmico de produção, suporte a dados reais, Docker, deploy público, Fine-tuning, treinamento de LLM, monitoramento 24/7, métricas sofisticadas de retrieval ou múltiplos provedores simultâneos.

## 6. Origem dos requisitos

- **[DOCENTE]** Enunciado `Atividade_Aluno_IA_Avancada.docx`, seções 1 a 9; `base_conhecimento_academica.json`; `cenarios_de_teste_aluno.csv`.
- **[PROJETO]** As escolhas de stack, controles extras e fluxos detalhados são decisões de implementação, não requisitos adicionais do docente.

## 7. Premissas e riscos

1. O provedor Groq precisa estar habilitado na conta e oferecer um modelo com Tool Calling; a cota do plano pode variar.
2. O modelo multilíngue de embeddings fará download local na primeira execução, precisando de internet nessa ocasião.
3. O ZIP do docente **não contém uma base de protocolos**: criaremos `SOL-1001` como fixture fictícia e identificada.
4. O cenário T05 contém uma intenção de registro, mas não inclui turma nem justificativa; não se deve gravar prematuramente.
5. O cronograma de 24–36 horas é uma previsão, não uma garantia.

## 8. Definição de pronto do projeto

Código-fonte + dados oficiais intactos + execução real da integração com LLM + índice vetorial persistente + Tools + StateGraph + validação + testes + logs/evidências + relatório + instruções de reprodução, todos consistentes entre si.
