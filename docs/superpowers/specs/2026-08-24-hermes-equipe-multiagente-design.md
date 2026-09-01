# Desenho técnico — Equipe multiagente Hermes no VPS

> **Documento histórico.** Este arquivo registra a arquitetura da primeira
> implantação em 24/08/2026. Gateways individuais, Brain, FamaChat e o
> Amendment 2 o supersederam. O contrato vigente está em
> `2026-09-01-hermes-equipe-multiagente-as-built-design.md`.

Data: 2026-08-24  
Status: aprovado para planejamento de implementação

## 1. Objetivo

Implantar no VPS atual uma equipe de seis Profiles Hermes, com um único gateway
de mensageria e o Kanban como barramento operacional durável entre o
orquestrador e os especialistas.

Os seis agentes serão:

- `default`, com identidade funcional e visual **CEO**;
- `porteiro`;
- `cadastro`;
- `famaagent`;
- `reno`;
- `dev`.

Todos usarão o modelo `gpt-5.6-luna-900k`.

## 2. Escopo e não objetivos

### Incluído nesta fase

- preservar `default` como ID técnico e defini-lo como CEO;
- criar os quatro Profiles ainda ausentes: `porteiro`, `cadastro`,
  `famaagent` e `reno`;
- preservar e restringir o Profile `dev` existente;
- manter somente `hermes-gateway.service` como gateway ativo;
- receber Renato pelo Telegram com allowlist explícita;
- integrar WhatsApp Web por Baileys/QR ao gateway do `default`;
- operar o Kanban em modo Manual, com dispatcher no gateway;
- preparar os Profiles com metadata compatível com Bot Mode;
- validar o fluxo com tarefas sintéticas no Kanban.

### Fora desta fase

- Profile `brain`;
- Profile `procura-imoveis`;
- Profile `marketing`;
- criação de `profiles/ceo`;
- Hermes Desktop e Bot Mode visual/operacional;
- MCP FamaChat, suas credenciais, permissões e mapeamentos;
- consultas ou cadastros reais no FamaChat;
- atualização do código-fonte instalado do Hermes;
- gateway, bot Telegram ou canal externo próprio para especialistas.

## 3. Estado inicial observado

- Hermes `v0.20.5` (`2026.8.19`) instalado em
  `/usr/local/lib/hermes-agent`.
- O checkout local possui alterações de histórico em relação ao upstream;
  portanto não deve ser atualizado como parte desta implantação.
- O VPS possui 4 CPUs, aproximadamente 8 GiB de RAM e capacidade suficiente
  para os limites atuais de workers.
- Profiles existentes: `default` e `dev`.
- Gateways existentes e ativos:
  - `hermes-gateway.service`, associado ao `default`;
  - `hermes-gateway-dev.service`, associado ao `dev`.
- Telegram já está conectado nos dois gateways, mas a topologia aprovada
  permite apenas o gateway do `default`.
- WhatsApp ainda não está habilitado ou pareado.
- Não há MCP configurado nos Profiles atuais.
- O Kanban já executou com sucesso um handoff durável entre `default` e `dev`.
- O Kanban já está com `dispatch_in_gateway: true` e
  `auto_decompose: false`.
- Não existem blocos `ui_meta.hermes-bots` nos Profiles atuais.

## 4. Arquitetura aprovada

```text
Telegram — allowlist Renato ─┐
                             ├─> hermes-gateway.service
WhatsApp Web — Baileys/QR ───┘          │
                                        └─> default/CEO
                                                │
                                                └─> Kanban Manual
                                                     ├─ porteiro
                                                     ├─ cadastro
                                                     ├─ famaagent
                                                     ├─ reno
                                                     └─ dev
```

Decisões:

- `default` é o ID técnico; CEO é sua identidade funcional e visual.
- `hermes-gateway.service` é o único gateway e o único proprietário do
  dispatcher Kanban.
- O adaptador WhatsApp oficial inicia e supervisiona o subprocesso Node.js
  Baileys a partir do gateway principal.
- Especialistas são executados sob demanda pelo dispatcher e não possuem
  gateway.
- `hermes-gateway-dev.service` será parado e desabilitado, mas preservado para
  rollback.
- `kanban.orchestrator_profile: default` ficará explícito por clareza. Com
  `auto_decompose: false`, ele não é necessário para decomposição automática.
- Bot Mode será apenas preparado por metadata; sem Desktop ele não estará
  operacional.

## 5. Estrutura e responsabilidades dos Profiles

Cada Profile seguirá esta disciplina:

- `SOUL.md`: identidade, responsabilidade e invariantes permanentes;
- `skills/<workflow>/SKILL.md`: workflows e protocolos operacionais
  complexos;
- `.hermes.md`: somente contexto de projeto descoberto pelo working
  directory/git root, quando aplicável;
- `profile.yaml`: nome visual, descrição e metadata de UI/Bot Mode;
- `config.yaml`: modelo, toolsets, capabilities e configuração técnica;
- `.env` e autenticação: somente credenciais indispensáveis ao Profile.

`profile.yaml` usará, no mínimo:

```yaml
display_name: <nome visual>
description: <descrição operacional curta>
description_auto: false
ui_meta:
  hermes-bots:
    title: <nome visual>
```

`display_name` é apenas apresentação; os IDs técnicos não mudam.
`ui_meta.hermes-bots` marca a instalação como gerenciada por Bot Mode e torna
o protocolo `message_agent` tecnicamente disponível nas sessões apropriadas.
Mesmo assim, o barramento operacional de produção continuará sendo o Kanban.

### 5.1 `default` / CEO

- Único gateway e orquestrador central.
- Recebe Telegram, WhatsApp e conclusões do Kanban.
- Classifica a intenção, cria cartões autossuficientes e valida handoffs.
- É o único agente autorizado a enviar mensagens externas.
- Não executa trabalho especializado nem inventa resultados ausentes.

### 5.2 `porteiro`

- Verifica se o contato corresponde a um corretor ativo.
- Retorna `active_broker`, `not_active` ou `indeterminate`.
- Quando disponível, retorna ID, nome e evidência mínima.
- Não atende a demanda, não cadastra pessoas e não envia mensagens.

### 5.3 `cadastro`

- Só processa contatos não confirmados como corretores ativos.
- Classifica como `existing_client`, `new_lead` ou `indeterminate`.
- Futuramente, com MCP, criará leads e retornará seus identificadores.
- Nesta fase não simulará integração permanente nem fará escrita externa.

### 5.4 `famaagent`

- Worker terminal de atendimento a corretor ativo.
- Recebe identidade verificada, mensagem original e contexto necessário.
- Produz resposta operacional/comercial pronta, evidências e escalonamento.
- Não verifica identidade, não cadastra e não atende clientes/leads.
- Não delega diretamente; devolve ao CEO qualquer necessidade adicional.

### 5.5 `reno`

- Worker terminal de atendimento comercial a clientes e leads.
- Recebe mensagem original, resultado de cadastro, ID interno e contexto
  comercial mínimo.
- Produz a próxima resposta comercial pronta para envio.
- Não envia WhatsApp e não delega diretamente.

### 5.6 `dev`

- Especialista interno de engenharia e manutenção.
- Recebe tarefas técnicas autossuficientes.
- Retorna resultado, evidências, arquivos afetados e riscos.
- Mantém capabilities técnicas necessárias, sem gateway próprio.

## 6. Canais e fronteiras de confiança

### Telegram

- Plano de controle confiável.
- Exclusivo de Renato.
- Controle obrigatório por `TELEGRAM_ALLOWED_USERS=<id do Renato>`.

### WhatsApp

- Plano de dados externo e não confiável.
- Aceita contatos desconhecidos porque os leads chegam de campanhas
  click-to-WhatsApp.
- Configuração obrigatória:

```env
WHATSAPP_ENABLED=true
WHATSAPP_MODE=bot
WHATSAPP_ALLOWED_USERS=*
```

- Política:

```yaml
whatsapp:
  dm_policy: open
  group_policy: disabled
```

- `WHATSAPP_ALLOW_ALL_USERS=true` não será usado, pois o wildcard explícito é
  suficiente.
- Mensagens do WhatsApp não autorizam operações administrativas, leitura de
  segredos, alteração da equipe ou execução técnica direta.
- Demandas técnicas legítimas são transformadas pelo CEO em cartões para
  `dev`.

### Baileys

- O bridge é iniciado como subprocesso do gateway principal.
- A API local permanece em `127.0.0.1`.
- A sessão persistida fica em
  `/root/.hermes/platforms/whatsapp/session` com modo `0700`.
- O pareamento por QR é o único checkpoint que exige ação externa de Renato.
- Reinícios reutilizam a sessão enquanto ela for válida.
- Desconexões temporárias usam a reconexão do Hermes.
- Alerta de falha persistente para Telegram é lógica da aplicação, não uma
  garantia nativa do Hermes.
- Se uma futura mudança no protocolo WhatsApp Web quebrar o Baileys, uma
  atualização futura do Hermes poderá ser necessária; isso não altera esta
  implantação.

## 7. Kanban e contrato de handoff

Configuração arquitetural:

```yaml
kanban:
  orchestrator_profile: default
  dispatch_in_gateway: true
  auto_decompose: false
  auto_subscribe_on_create: true
  failure_limit: 2
  max_in_progress: 4
  max_spawn: 2
```

O Kanban fornece o registro durável, a atribuição, o dispatcher, o lifecycle,
o `idempotency_key` nativo e a injeção automática do surface `kanban_*` para
workers. A serialização por chat, correlação, vigência de turnos e descarte de
resultados atrasados são regras da aplicação implementadas pelo CEO.

As demais capabilities de cada worker — terminal, web, filesystem e outras —
serão removidas ou restringidas no respectivo `config.yaml`; isso não acontece
automaticamente por usar Kanban.

### 7.1 Corpo do cartão

O envelope lógico admite estes campos:

```yaml
schema_version: 1
correlation_id: <uuid>
idempotency_key: <canal:chat:mensagem:etapa>
source:
  platform: whatsapp
  chat_id: <id>
  message_id: <id>
contact:
  internal_id: <id-ou-null>
  phone_e164: <somente-quando-necessário>
original_message: <somente-quando-necessária>
conversation_context: <contexto-mínimo>
upstream_result: <resultado-anterior-ou-null>
request: <trabalho-exato>
expected_output: <contrato-esperado>
test_mode: false
```

Esse é um catálogo de campos possíveis, não um bloco copiado integralmente
para todo cartão. Cada worker recebe apenas os dados indispensáveis. Nenhum
worker depende de cartões irmãos, memória de outro Profile ou contexto
implícito do CEO.

### 7.2 Resultado estruturado

Workers usam `kanban_complete(summary=..., metadata=...)` para handoff bem
sucedido. A metadata free-form seguirá este contrato lógico:

```yaml
status: success | needs_information | escalate | error
decision: <resultado-específico>
entities: {}
response_ready: <texto-ou-null>
evidence: []
reason: <explicação-curta>
requested_next_action: return_to_ceo
```

Em produção, `famaagent` e `reno` são os Profiles que normalmente retornam
`response_ready` para contatos externos.

### 7.3 Minimização de dados

- `body`: somente dados necessários ao worker.
- `summary`: conclusão curta, sem PII, segredos, telefone ou mensagem bruta.
- `metadata`: resultado estruturado e IDs internos quando possível.
- Segredos nunca entram em body, summary, metadata, memória ou logs
  deliberados.
- Histórico completo de WhatsApp não é copiado; usa-se o turno e contexto
  limitado.
- `porteiro` recebe telefone apenas porque a consulta de identidade depende
  dele.
- `famaagent` e `reno` recebem a mensagem original apenas porque precisam
  produzir a resposta.
- `dev` recebe dados sanitizados, salvo autorização explícita.

### 7.4 Idempotência e ordenação

- O CEO usa uma chave nativa diferente por canal, conversa, mensagem e etapa.
- A mesma etapa não é criada duas vezes para a mesma mensagem.
- Há somente um fluxo de atendimento ativo por chat.
- Mensagens novas formam novo turno e não alteram silenciosamente um cartão em
  execução.
- Antes do envio, o CEO confere `chat_id`, `correlation_id` e vigência do
  turno.
- Resultados duplicados, atrasados ou superados ficam auditáveis, mas não são
  enviados automaticamente.

## 8. Fluxos de negócio

### Corretor ativo

```text
WhatsApp
   ↓
CEO → cartão porteiro
   ↓
porteiro → active_broker + identidade + evidência
   ↓
CEO → cartão autossuficiente famaagent
   ↓
famaagent → resposta pronta + evidências/escalonamento
   ↓
CEO valida correlação/turno e envia no WhatsApp
```

### Cliente ou lead

```text
WhatsApp
   ↓
CEO → cartão porteiro
   ↓
porteiro → not_active
   ↓
CEO → cartão cadastro
   ↓
cadastro → existing_client | new_lead + identificador
   ↓
CEO → cartão autossuficiente reno
   ↓
reno → resposta comercial pronta
   ↓
CEO valida correlação/turno e envia no WhatsApp
```

Sem o MCP, `porteiro` e `cadastro` não inventam classificações. Em produção,
uma dependência ausente bloqueia a ramificação e o CEO escala a exceção para
Renato pelo Telegram.

## 9. Falhas, tentativas e bloqueios

- Sucesso funcional: `kanban_complete`.
- Incerteza de domínio determinada corretamente: completar com
  `decision: indeterminate`.
- Dependência, credencial ou informação obrigatória ausente: `kanban_block`.
- Falha transitória de execução: lifecycle de falha e retentativa limitada.
- Nenhuma falha autoriza pular `porteiro` ou `cadastro`.
- Respostas externas de contingência são neutras; detalhes técnicos vão apenas
  para Renato.

Semântica registrada para tarefas:

- `max_retries: 2` significa tentativa inicial mais uma retentativa; a tarefa
  bloqueia na segunda tentativa malsucedida.
- Para duas retentativas além da tentativa inicial, usar `max_retries: 3`.
- `max_runtime_seconds` deve ser definido de forma proporcional ao trabalho
  de cada tarefa.

## 10. Estratégia de implantação

1. Registrar versão, commit, serviços, Profiles e configuração efetiva.
2. Criar backup dos arquivos que serão alterados.
3. Completar metadata e identidade do `default`.
4. Criar Profiles mínimos `porteiro`, `cadastro`, `famaagent` e `reno` pelo
   mecanismo oficial de Profiles.
5. Ajustar `dev` sem recriá-lo.
6. Definir o modelo e restringir capabilities dos seis Profiles.
7. Criar `SOUL.md`, skills operacionais e `profile.yaml`.
8. Validar Profiles isoladamente.
9. Configurar e validar o Kanban no `default`.
10. Parar e desabilitar `hermes-gateway-dev.service`.
11. Validar e reiniciar `hermes-gateway.service`.
12. Confirmar Telegram somente para Renato.
13. Configurar WhatsApp, executar QR e conferir sessão/bridge.
14. Executar testes sintéticos e revisar resultados duráveis.

O gateway principal só é reiniciado após os Profiles passarem nas validações
isoladas.

## 11. Testes sintéticos

As fixtures usam `test_mode: true` dentro do body. Esse marcador nunca é
originado por mensagens reais e não substitui o MCP.

### Rota de corretor

```text
CEO → porteiro(active_broker) → CEO → famaagent → response_ready
```

### Rota de cliente/lead

```text
CEO → porteiro(not_active) → CEO → cadastro(new_lead)
    → CEO → reno → response_ready
```

### Dev

```text
CEO → dev → diagnóstico somente leitura → resultado estruturado
```

Os testes também verificam:

- idempotency keys;
- mutações de lifecycle restritas ao próprio cartão;
- summaries e metadata sem PII;
- bloqueio correto quando dependências reais estão ausentes;
- handoff durável e legível pelo CEO.

## 12. Critérios de aceite

- Existem seis Profiles lógicos: `default`, `porteiro`, `cadastro`,
  `famaagent`, `reno` e `dev`.
- Não existe `profiles/ceo`.
- Todos resolvem para `gpt-5.6-luna-900k`.
- Somente `hermes-gateway.service` está habilitado e ativo.
- Telegram aceita apenas Renato.
- WhatsApp/Baileys está autenticado, saudável, aberto para DMs e fechado para
  grupos.
- A sessão Baileys está persistida com permissão `0700`.
- Kanban opera em modo Manual pelo gateway principal.
- As duas rotas sintéticas concluem com handoffs estruturados e respostas
  prontas.
- `dev` conclui seu teste sem gateway próprio.
- Não existe configuração, chave ou chamada ao MCP FamaChat.
- Metadata de Bot Mode existe sem alegar UI operacional.
- Resultados duráveis não contêm segredos ou PII desnecessário.

## 13. Rollback

- Restaurar os arquivos salvos.
- Desabilitar temporariamente o WhatsApp se ele impedir o gateway de subir.
- Reiniciar e validar `hermes-gateway.service`.
- Somente se necessário, reabilitar temporariamente
  `hermes-gateway-dev.service`.
- Não apagar a unit do gateway `dev` nesta fase.
- Não realizar exclusões irreversíveis.

## 14. Decisões adiadas

- credenciais e configuração do MCP FamaChat;
- permissões por ferramenta MCP;
- implementação real de `create_lead`;
- política definitiva de retenção/purga de cartões com dados pessoais;
- Profiles `brain`, `procura-imoveis` e `marketing`;
- operação visual do Bot Mode no Hermes Desktop;
- atualização futura do Hermes caso o protocolo WhatsApp Web exija nova
  versão do Baileys.
