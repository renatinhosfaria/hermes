# Cadastro CTWA — validação de 10/09/2026

## Contrato implementado

CEO transporta atribuição CTWA normalizada a Cadastro e Reno. Cadastro consulta
empreendimento somente para novo cliente. Nomes completos do anúncio e campanha
devem corresponder positivamente ao mesmo candidato único, confirmado por ID.
O POST envia `body.idEmpreendimento: [id]`; readback confirma a lista exata.
Sem identificação segura, cria sem vínculo e reporta pendência ao Reno. Cliente
existente não recebe criação nem alteração.

Fontes de API consultadas em `renatinhosfaria/famachat`, branch main:

- `shared/schema.ts`: `clientes.idEmpreendimento` é array JSON na coluna
  `id_empreendimento`; `insertClienteSchema` inclui esse campo.
- `server/routes/clientes.ts`, blob `85390eb540da1e4fca26735028e5e33f20243ab4`:
  POST valida `insertClienteSchema` e persiste `parseResult.data`.
- `server/routes/empreendimentos-page.ts`, blob
  `cc64f26c7e2d2e727093f4f8ed42d3a5ac58c7ce`: busca por `query.termo`
  retorna lista; leitura por ID retorna objeto.
- `server/models/empreendimentos-schema.ts`, blob
  `9b1782851c2a642f4a904e9d9fb71a85a99b1612`: campo `id` representa a
  coluna `id_empreendimento`.

O manifesto MCP real foi consultado por `tools/list`, sem chamar ferramentas
comerciais. A definição de POST tem body genérico; a confirmação dos campos
veio do código da API, não desse manifesto isolado.

## Verificações antes da instalação

- Baseline do guard: 17 testes passaram; casos CTWA novos reproduziram rejeição
  do campo adicional e ausência de proteção das novas leituras.
- Guard atualizado: 35 testes passaram, incluindo chamadas indiretas
  `tool_call`, envelopes externos e carregador/hooks nativos em home temporário.
- Equipe: 76 testes passaram, incluindo preservação de histórico e seleção de
  snapshots WhatsApp na renovação CTWA do CEO.
- Registro, filtro e resolução de toolsets nativos com manifesto MCP real:
  exatamente 5 ferramentas FamaChat CLI, 0 Telegram, 0 WhatsApp.
- Smoke do Brain: compatibilidade de bancos, resolver, capability dos workers,
  transporte MCP e allowlist aprovada.
- Política Git e `git diff --check`: aprovados no checkout isolado.
- Revisão independente encerrou os achados de YAML e de campanha conflitante;
  testes de instrução sintéticos confirmaram repasse, payload, fallback,
  handoff e tratamento de readback divergente.

Nenhum cliente foi criado ou alterado para testar. Esses resultados demonstram
o contrato em fixtures e a exposição das ferramentas; não provam um atendimento
real completo depois da instalação.

## Divergências anteriores à mudança

A cópia instalada tinha guard 1.0.1 e a fonte 1.0.0. A atualização preserva a
contenção instalada que bloqueia negócios fora de worker Kanban e reconhece
profile pelo HERMES_HOME quando HERMES_PROFILE não está definido.

`verify_team.py core` e `full` falhavam antes desta mudança: allowlist/grupos de
Telegram de Porteiro/Cadastro, guarda de instruções do FamaAgent e marcadores
de contrato de Cadastro/Reno/Agendamento. Os marcadores do Cadastro foram
ajustados para consultar a referência canônica já adotada pelo profile. As
demais divergências ficam fora deste escopo; não foram relaxadas para obter PASS.

## Limites e ativação

O guard usa comparação conservadora, não um mapa formal de anúncio para
empreendimento. Abreviações, nomes sem correspondência em uma das pistas,
homônimos e resultados incompletos criam sem vínculo. A seleção de termos e a
cópia fiel do contexto pelo CEO seguem as instruções; `ctwa_handoff_check.py`
permite comparar o cartão com o retorno original do Brain.

Novos workers leem a cópia instalada/configuração atualizada. Para o CEO, o
helper de snapshots com `fama-cadastro-ctwa-v1` renova somente WhatsApp durante
partida após drenagem nativa. Preserve sessões e histórico; não restaure um
banco inteiro por uma divergência de vínculo.

## Instalação conferida

- Commit de implementação `4c22a8c` integrado localmente por fast-forward.
- Cópias instaladas do guard e manifesto sincronizadas; esses dois arquivos
  já eram rastreados no Git apesar da regra geral de ignore para plugins.
  Sua atualização é versionada junto ao registro de instalação, sem `add -f`.
- `verify_activation.py`: fonte e cópia iguais, plugin habilitado, três hooks
  nativos carregados e POST sem evidência bloqueado.
- Testes no checkout principal: guard 35/35 e equipe 76/76.
- `verify_team.py core/full`: sete falhas preexistentes remanescentes; quatro
  marcadores desatualizados do Cadastro foram substituídos pelas verificações
  da referência canônica. Nenhuma falha nova de allowlist ou vínculo CTWA.
- Restart do CEO via `hermes gateway restart`, com drenagem nativa. O
  ExecStartPre renovou quatro snapshots de WhatsApp pela API nativa e reportou
  `conversation_history: preserved`; consulta posterior encontrou zero snapshots
  antigos. O drop-in temporário foi removido após a partida.
- CEO ativo e bridge WhatsApp com `status: connected` após o restart.
- Smoke Brain novamente aprovado após ativação.
- Backup privado consistente do estado do CEO e dos arquivos de implantação
  em `/root/hermes-rollout-backups/cadastro-ctwa-20260910-RsQCg1`.

A confirmação de um cadastro real com vínculo permanece dependente de uma
próxima entrada CTWA elegível. Não foram gerados contatos nem mensagens de teste
em produção.
