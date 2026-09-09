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


## Correção de acesso à skill — 2026-09-08T23:30:22Z

Por orientação explícita do operador, o próprio Reno deve chamar
`skill_view(name="fama-reno-runtime")` em cada execução. O CEO não envia o manual
nem prescreve a skill na tarefa. Habilitado o toolset nativo `skills` no CLI do
Reno, atualizado seu SOUL e removido `skills` dos cartões internos do timer.
O plugin existente observa a leitura completa bem-sucedida antes de liberar
MCPs e conclusão; falha de leitura exige bloqueio do cartão.

Validação: 40 testes da integração, 26 de observabilidade e 18 da equipe passaram
(**84**). Os 40 testes da integração foram repetidos sobre o repositório ativo.
O verificador instalado confirmou `skill_view` disponível, leitura nativa do
manual, bloqueio antes da leitura e liberação depois, sem executar MCPs.
A revisão independente identificou e validou a correção de um caso de cache
quando o manual é aberto pelo nome com categoria antes do nome simples.
`verify_team.py core`: PASS. Timer ativo; serviço com Result=success.
Instalação oficial sem alterações, HEAD `116b03f2efae931e4467eb7ac67f7c3dc7306ac1`.
Nenhum gateway reiniciado. A alteração vale para novos workers; não foi
observado um atendimento real posterior a esta correção.

Backup desta correção em `plugin-data/fama-reno-delivery/skill-self-load-backup-20260908T232752Z/`.
Para revertê-la, restaurar config/SOUL e código fonte/instalado desse backup,
preservando o timer, recibos e a correção anterior de etapas.

## Correção do contrato de identidade — 08/09/2026

O cartão t_29e3af7b/run 368 usou `upstream_result.entities.client_id`;
o guard de leitura procurava somente `upstream_result.client_id`.
Reprodução offline com a versão histórica confirmou o bloqueio do ID correto.

Agora leitura, associação de entrega e verificação de recibo compartilham um
resolvedor. O formato canônico é o aninhado; o antigo continua aceito. Ambos
presentes precisam ser inteiros positivos iguais. O CEO recebe instrução
explícita e a rotina gera novos cartões internos no formato canônico.

Validação antes da instalação: 45 testes de integração (incluindo carregador
nativo e formato do incidente), 26 de observabilidade e 20 da equipe passaram.
A revisão independente não encontrou impedimentos. Os novos testes foram
executados antes da correção e reproduziram a falha. `verify_team.py core`
falhou antes da instalação em divergências já existentes nos toolsets dos
profiles e exposição de MCP no Telegram; nenhuma configuração foi alterada
nesta correção. Isso impede declarar a verificação global da equipe aprovada.

Instalação: substituir `delivery.py` antes de `__init__.py` no plugin do Reno,
com backup em `plugin-data/fama-reno-delivery/client-contract-backup/`.
Validar os hashes e hooks com `verify_activation.py`, que agora testa o ID
canônico e a recusa de outro cliente sem executar ferramentas comerciais.
Novos workers carregam a correção; o timer recarrega o script em cada execução.
Rollback: restaurar os arquivos do backup e as instruções anteriores juntas;
não reexecutar atendimentos nem remover recibos. Cartões novos usam o formato
aninhado e precisam de compatibilidade de leitura antes de qualquer rollback.
O atendimento do incidente não é reaberto nem respondido por esta instalação.
