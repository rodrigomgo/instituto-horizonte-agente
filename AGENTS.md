# Regras de trabalho para Codex

## Contexto

Projeto Integrador — agente acadêmico do Instituto Horizonte (fictício). Todo requisito e decisão devem estar alinhados aos documentos `docs/00_INTENCAO.md` até `docs/06_ADR.md`. O enunciado do professor prevalece sobre decisões locais se houver conflito.

## Regras

1. Trabalhe somente na Task solicitada. Leia dependências e critérios de aceite de `docs/04_TAREFAS.md`.
2. Antes de editar, escreva plano curto com arquivos afetados e testes previstos.
3. Preserve **bytes e fatos** de `data/base_conhecimento_academica.json` e `data/cenarios_de_teste_aluno.csv`; nunca facilitar perguntas de teste.
4. Nunca crie ou versiona `.env` com chave. Nunca imprima tokens nos logs. Respeite `.gitignore`.
5. O modelo não autoriza escrita: confirmação deve ser verificada pelo backend com estado confiável. Não adicionar Tools de alterar notas.
6. Evidências, screenshots, commits, saídas de testes e chamadas ao LLM precisam ser **reais**; distinguir mocks de integração real.
7. Mantenha nomes de Tools `buscar_normas`, `consultar_protocolo` e `registrar_solicitacao`; preserve os IDs `ACAD-nnn`.
8. Prefira Python 3.12, biblioteca padrão quando suficiente, typing explícito, validação Pydantic, Pytest e logs sem segredos.
9. Não adicione Docker, frontend, API HTTP, serviços pagos ou abstrações desnecessárias.
10. Explique incompatibilidades de biblioteca/provedor e registre propostas de mudança em ADR, sem alterar a escolha silenciosamente.
11. Ao finalizar, informe: arquivos alterados, testes/comandos executados, resultados observados, limitações, mudanças de decisões e commit sugerido.
12. Não marque Task como concluída sem teste e revisão do estudante.

## Ordem de leitura

1. `docs/00_INTENCAO.md`
2. `docs/01_ESPECIFICACAO.md`
3. `docs/02_ARQUITETURA.md`
4. `docs/03_PLANO.md`
5. `docs/04_TAREFAS.md`
6. `docs/05_TESTES_E_ACEITE.md`
7. `docs/06_ADR.md`

## Primeira Task

TSK-001 conforme `docs/07_PROMPT_CODEX.md`. Não gerar toda a aplicação de uma vez.
