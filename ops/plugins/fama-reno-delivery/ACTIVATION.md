# Ativação — 08/09/2026

Ativado às **20:06:33 de Brasília** (2026-09-08T23:06:33Z), somente para entregas
registradas a partir desse corte. Autorização: operador aprovou a sequência de
envio e pediu explicitamente preservação do código-fonte/configuração da
instalação oficial Hermes.

## Resultado verificado

- 35 testes da integração, 26 de observabilidade e 18 da equipe: **79 passaram**
  executados também sobre os arquivos instalados.
- Carregador real do Hermes confirmou os dois hooks no profile Reno; tentativa
  de PATCH sem evidência foi bloqueada sem executar ferramenta de negócio.
- `verify_team.py core`: PASS, preservando allowlists e perfis de ferramentas.
- Timer habilitado/ativo; serviço executou repetidamente com Result=success e
  ExecMainStatus=0. Até a conferência inicial, zero recibos novos e zero tarefas
  de atualização criadas; nenhuma alteração em cliente como teste.
- Git da instalação oficial limpo, mesmo HEAD e hashes de seis arquivos críticos
  inalterados. Nenhum código, configuração, wrapper ou monkeypatch no upstream.
- Não foi necessário reiniciar gateways, Brain nem WhatsApp.

## Replay somente leitura

| Cartão / run | Resultado da proteção |
| --- | --- |
| t_33290b1a / 344 | Bloqueou Em Atendimento: apenas entrada inicial. |
| t_f23c2902 / 351 | Bloqueou Em Atendimento: apenas entrada inicial. |
| t_035f479b / 362 | Bloqueou Em Atendimento: apenas entrada inicial. |
| t_96e98dac / 334 | Preservou autorização da transição com continuidade válida. |

Um dry-run do correlacionador encontrou 21 correspondências históricas exatas;
nenhuma foi executada. O corte de ativação impede reconciliação retroativa.

Revisão independente encontrou e teve corrigidas duas condições: herança de
assinatura alterada entre leitura/criação e reset de sessão entre resposta/envio.
Validação da assinatura e criação compartilham transação IMMEDIATE por API
nativa; o guard confere também a assinatura do filho. Sessão obsoleta ou empate
temporal não autoriza associação. Testes de regressão cobrem ambos os casos.

## Arquivos e limite prático

Alterados somente SOUL/skills CEO e Reno, config do profile Reno para habilitar
a extensão, código operacional Fama e monitor Fama. Units locais em
`/etc/systemd/system/hermes-reno-delivery.{service,timer}`. A instalação
`/usr/local/lib/hermes-agent` permanece somente leitura para o novo serviço.

Backup dos arquivos anteriores, corte e hashes ficam em
`/root/.hermes/plugin-data/fama-reno-delivery/`; o diretório contém dados
operacionais privados e não deve ser publicado. Rollback descrito no README.

A execução completa com um novo contato real ainda não foi observada. Os testes
validaram componentes, integração de hooks, transações e registros históricos;
não provam a execução comercial futura pelo modelo/MCP. Nenhuma mensagem foi
enviada a cliente real para validar esta mudança.
