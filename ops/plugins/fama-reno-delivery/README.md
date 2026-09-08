# Etapa Reno após envio confirmado

Integração operacional Fama, fora da instalação oficial. Nenhum arquivo,
configuração, classe ou função do código-fonte Hermes é alterado ou substituído.
O timer só lê o ledger e cria tarefas usando a API Kanban instalada; o plugin
Reno usa exclusivamente hooks públicos. Só o Reno escreve no FamaChat.

## Operação

Em cada execução Kanban, o próprio Reno chama
`skill_view(name="fama-reno-runtime")` para ler seu procedimento. O toolset nativo
`skills` está habilitado no CLI desse profile. A instrução está no SOUL do Reno;
o CEO não prescreve nem envia a skill na tarefa, e os cartões internos criados
pelo timer também não preenchem `skills`.

O guard observa a resposta bem-sucedida de `skill_view` na mesma sessão antes
de liberar MCPs e `kanban_complete`. Listar skills, abrir outro manual ou somente
um arquivo vinculado não satisfaz essa exigência. Se a leitura falhar, Reno
registra o impedimento com `kanban_block`. Não há injeção automática do manual
no prompt pelo plugin. O grupo nativo inclui também manutenção de skills,
sujeita à autorização permanente e aos limites já definidos no profile.

`delivery.py` é executado pelo timer a cada 15 segundos, após a execução anterior.
Cruza `response_ready` exato com ledger `delivered`, execução concluída,
destinatário, thread e sessão. Exige um único candidato. A resposta continua
sendo enviada normalmente pelo CEO. O timer não envia mensagens nem chama CRM.

O recibo privado é persistido antes da criação do cartão. Lock entre processos,
chave por run e busca incluindo tarefas arquivadas evitam duplicação e recuperam
interrupção entre essas etapas. Notificações herdadas precisam ser uma única
assinatura WhatsApp DM em modo wake; nenhuma notificação passiva é criada.
Pausa humana é consultada na criação e no guard antes da escrita/conclusão.

O guard exige leitura recente, ID vinculado ao cartão, brokerId 35, expectedStatus,
transição autorizada e uma única tentativa de escrita por execução. Conclusão
interna requer leitura independente após PATCH; payload externo/anexos do modelo
são removidos da conclusão interna. A regra de primeiro anúncio tem proteção
mínima pelo histórico Brain observado: precisa encontrar a entrada e uma mensagem
distinta posterior. Ela não é um classificador de intenção nem de outro anúncio;
a conduta ainda exige que Reno reconheça continuidade humana independente.

## Testes e instalação

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/local/lib/hermes-agent/venv/bin/python -m unittest discover -s ops/plugins/fama-reno-delivery/tests -v
```

Instalar `__init__.py`, `delivery.py` e `plugin.yaml` em
`profiles/reno/plugins/fama-reno-delivery/`, habilitando apenas esse plugin em
`profiles/reno/config.yaml` sem remover plugins existentes. Instalar os dois
units operacionais em `/etc/systemd/system`. Criar uma vez
`plugin-data/fama-reno-delivery/activation.json` com `cutoff` Unix de ativação;
não retroceder esse valor para testar. Ele exclui entregas históricas.

O CLI do Reno deve incluir `[clarify, brain, famachat, skills]` em
`platform_toolsets.cli`. Aplique com `hermes --profile reno config set`.

```bash
systemctl daemon-reload
systemctl enable --now hermes-reno-delivery.timer
systemctl status hermes-reno-delivery.timer --no-pager
PYTHONDONTWRITEBYTECODE=1 /usr/local/lib/hermes-agent/venv/bin/python ops/plugins/fama-reno-delivery/verify_activation.py
```

Novos workers carregam config e plugin. Não é necessário reiniciar gateways.
Não executar MCP nem enviar WhatsApp a cliente real como teste. `--dry-run`
consulta dados reais em modo somente leitura e imprime apenas contagens.

## Limites e rollback

O ledger confirma aceite do envio, não leitura do destinatário. Só é reconhecido
texto final literal, com metadados e vínculo suficientes. Texto reescrito,
legado ambíguo, anexo sem texto ou ausência de correlação não autoriza atualização.
O timer reconcilia enquanto o ledger retém o recibo (até 500 registros / sete
dias no core atual). Indisponibilidade além da retenção exige auditoria.
O resultado do Reno depende do MCP e do modelo executar a tarefa; o guard impede
escrita indevida, mas não substitui a execução. Novo cliente respondendo entre a
consulta ao histórico e a escrita pode exigir avanço pelo cartão comercial; uma
etapa já avançada nunca é sobrescrita graças à leitura e expectedStatus.

Se o serviço falhar, conferir `journalctl -u hermes-reno-delivery.service`.
`ambiguous > 0` pede inspeção, não associação por aproximação. Falha do loader
é detectada pelo verificador de ativação, mas não vira bloqueio global do Hermes.

Rollback: parar/desabilitar o timer, remover só este plugin de plugins.enabled
do Reno e restaurar SOUL/skills a partir do backup da ativação. Não apagar
recibos, tarefas nem registros de clientes. A instalação oficial permanece intacta.
