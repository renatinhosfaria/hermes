# Encerramento por 90 dias de inatividade

Plugin local `fama-session-lifecycle`, exclusivo do CEO/default. Não modifica o
código upstream do Hermes, não expõe ferramentas ao modelo e não envia mensagens.

A cada dia procura sessões WhatsApp individuais abertas há pelo menos 90 dias
sem atividade externa. O prazo é calculado a partir da última mensagem recebida
ou saída confirmada, considerando o histórico do mesmo chat. A confirmação de
saída é coletada a cada minuto em um banco próprio, pois o ledger do Hermes tem
retenção curta. Guardamos somente SID e horário, sem copiar mensagens ou telefone.

O executor revalida somente a sessão candidata no loop do gateway, sem `await`,
com limite de tempo para as consultas e lease nativa. Encerra usando
`SessionDB.promote_to_session_reset(sid, reason="idle")`. Na próxima mensagem,
o próprio Hermes substitui a rota encerrada por uma nova sessão. Os testes
usam o schema/API instalados e confirmam preservação das mensagens e nova rota.

## Regras de proteção

- Entrada externa comprovada é necessária; sessões vazias não são encerradas.
- Mensagens internas classificadas e `[SILENT]` não reiniciam o prazo.
- Registros antigos não classificados e respostas finais sem confirmação
  conservada funcionam como barreira conservadora: podem adiar o encerramento.
- Sessões fixadas, handoff, pausa humana no store real, tarefas não terminais,
  entregas pendentes, turnos, filas, debounce ou mídia em recebimento impedem
  encerramento. Atividade concorrente provoca nova tentativa após um minuto.
- Erro de schema, configuração, API ou mudança nos arquivos upstream auditados
  impede encerramentos. `compatibility.json` é exclusivo deste plugin; não
  substitui nem atualiza a baseline de integridade geral do Hermes.
- `sessions.auto_prune: false` é obrigatório no CEO. Isso desativa a poda
  automática desse banco, preservando também sessões encerradas. O banco pode
  crescer; nenhum prazo de exclusão foi implementado. Outros profiles mantêm
  suas políticas atuais. Exclusões manuais continuam sendo operações distintas.

A verificação diária pode encerrar uma sessão depois do instante exato dos 90
dias; pausas e trabalho pendente podem prolongar a espera. O encerramento local
não fecha o aplicativo WhatsApp nem bloqueia o contato. O Brain mantém seu
acesso autorizado aos registros preservados; suas regras de autorização não mudam.

## Instalação e operação

Fonte: `/root/.hermes/ops/session-lifecycle`. A instalação é um link de
`/root/.hermes/plugins/fama-session-lifecycle` para o subdiretório `plugin`.
No `config.yaml` do CEO, incluir o nome em `plugins.enabled` e definir:

```yaml
sessions:
  auto_prune: false
```

Após testes e simulação, carregar com `hermes gateway restart`, que drena os
turnos ativos. Não reiniciar especialistas. O primeiro ciclo ocorre cerca de
um minuto após o carregamento. Apenas um supervisor obtém o lock local.

Simulação somente leitura:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/local/lib/hermes-agent/venv/bin/python /root/.hermes/ops/session-lifecycle/lifecycle.py
```

Validação com dados sintéticos:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/local/lib/hermes-agent/venv/bin/python -m unittest discover -s /root/.hermes/ops/session-lifecycle/tests -v
/root/brain/.venv/bin/ruff check /root/.hermes/ops/session-lifecycle
/root/brain/.venv/bin/ruff format --check /root/.hermes/ops/session-lifecycle
```

Estado agregado: `/root/.hermes/session-lifecycle/status.json`. Horários de
saída: `activity.sqlite3` nesse mesmo diretório privado. Encerramentos são
registrados no log do gateway como `session_idle_closed`, com SID e sem conteúdo.
O estado `ready` inclui o resultado da última varredura durante aquele processo;
`waiting_for_idle_gateway` significa nova tentativa no próximo ciclo.

Após atualizar o Hermes, revisar os módulos de integração e executar testes
antes de atualizar os hashes auditados. Nunca recapturar hashes apenas para
eliminar um bloqueio. Uma incompatibilidade deixa o plugin inoperante e aparece
no status. A ativação inicial é documentada em `VALIDATION.md`.

Para desativar, remover somente o nome deste plugin de `plugins.enabled` e usar
o restart nativo. Manter `sessions.auto_prune: false` para não apagar histórico
encerrado na inicialização seguinte. Não apagar bancos ou arquivos de sessões.
