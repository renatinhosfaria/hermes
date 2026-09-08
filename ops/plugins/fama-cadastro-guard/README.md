# Validação do Cadastro

Plugin externo do Hermes, habilitado somente no profile Cadastro. O dispatcher
cria um processo por execução com `HERMES_PROFILE`, `HERMES_KANBAN_TASK` e
`HERMES_KANBAN_RUN_ID`; os hooks vinculam a evidência a essa execução e sessão.
O gateway administrativo sem tarefa mantém seu modo de manutenção.

O plugin observa `kanban_show`, Brain e as três APIs FamaChat existentes. Faz
comparação completa do telefone, inclusive país, pontuação e nono dígito;
exige paginação completa; impede POST com cliente Reno não arquivado; reserva
uma tentativa de POST antes da chamada e exige readback independente com ID,
telefone, brokerId e status. O handoff substitui contagens e decisões do modelo
por dados calculados da mesma evidência. Contagens ausentes ficam ausentes,
em vez de virar zero. Nenhum telefone é persistido pelo plugin ou incluído
na conclusão. As respostas originais continuam nos registros normais do Hermes.

`transform_tool_result` só acrescenta uma anotação por página; a decisão não
confia nessa anotação. O observador recalcula a partir do payload original,
inclusive quando o executor aplica a transformação antes do post hook.

## Validação local

Na raiz do repositório:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/local/lib/hermes-agent/venv/bin/python -m unittest discover -s ops/plugins/fama-cadastro-guard/tests -v
PYTHONDONTWRITEBYTECODE=1 /usr/local/lib/hermes-agent/venv/bin/python -m unittest discover -s ops/hermes-team/tests -v
```

Os testes usam fixtures sintéticas. A integração usa o carregador e dispatcher
de hooks reais em um profile temporário, sem executar ferramentas de negócio.
`replay.py --state-db <arquivo> --session <id>` lê o SQLite em modo somente
leitura e reaplica os hooks às respostas já registradas; imprime somente
identificadores operacionais, bloqueios e o metadata canônico. Não chama MCP,
não grava no Kanban e não manda notificações.

## Instalação e conferência

Copiar apenas `__init__.py` e `plugin.yaml` para
`/root/.hermes/profiles/cadastro/plugins/fama-cadastro-guard/` antes de habilitar.
Preservar outros plugins se a lista configurada tiver mudado.

```bash
hermes -p cadastro config set plugins.enabled '["fama-cadastro-guard"]'
hermes -p cadastro config get plugins.enabled
hermes -p cadastro config check
PYTHONDONTWRITEBYTECODE=1 /usr/local/lib/hermes-agent/venv/bin/python ops/plugins/fama-cadastro-guard/verify_activation.py
```

Os próximos workers leem os arquivos e a configuração atualizados. Não é
necessário reiniciar CEO, Brain ou o gateway Cadastro. Execuções já iniciadas
não ganham o plugin retroativamente. Conferir `validator_version` no próximo
handoff real. Não criar lead em produção para fazer teste.

Rollback: restaurar a versão anterior de SOUL/skill e retirar apenas
`fama-cadastro-guard` de `plugins.enabled` pela CLI. Manter código/evidências
versionados. O rollback afeta novos workers, sem apagar ou alterar clientes.

## Limites

A proteção depende do carregamento do plugin pelo Hermes. `verify_activation.py`
detecta ausência, código divergente e hooks ausentes; não transforma um erro no
loader do core em bloqueio global. O limite de POST é por execução: este plugin
não cria trava distribuída entre workers nem uma chave de idempotência no CRM.
Múltiplos clientes Reno para o telefone exigem conferência. Mudanças no contrato
MCP ou respostas incompletas bloqueiam criação/conclusão de sucesso.

Novos testes sintéticos devem usar `test_mode: true` booleano e
`fixture.decision` ou `fixture.cadastro.decision`, com IDs textuais sintéticos
(`lead-test-001`, por exemplo). Modo ambíguo, duplicado ou cartão sem corpo
impede consultas. Cartões reais antigos com prosa que não forma YAML continuam
compatíveis se não houver declaração ambígua de `test_mode`.
