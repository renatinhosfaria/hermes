# Agendamento — implantação em 09/09/2026

Profile instalado em `/root/.hermes/profiles/agendamento`, com SOUL.md, config.yaml, profile.yaml, .hermes.md e skill `fama-agendamento-runtime`.

Fluxo ativo: Reno combina com o cliente → CEO cria tarefa → Agendamento executa e confere → CEO cria continuação Reno → Reno prepara resposta → CEO envia. Escopo inicial brokerId=35; cinco ferramentas MCP autorizadas no CLI. Reno perdeu as duas permissões de agenda e mantém suas demais operações.

Telegram: @agendamentofama_bot conectado, grupo Agendamento -1003944432295, operador 8564576789, sem MCP comercial. Token somente no ambiente privado; group_allowed_chats vazio evita autorização geral do grupo. Autenticação do modelo usa o mecanismo nativo sem cópia de sessões OAuth.

Validação: 56 testes da equipe e 36 dos monitores passaram. Oito cenários comportamentais com modelo e ferramentas fictícias passaram: criar, remarcar, cancelar, tarefa repetida, resposta perdida, divergência no registro, outra carteira e retorno ao Reno. A execução de criação passou no validador de comportamento; a checagem posterior de imutabilidade detectou uma alteração administrativa concorrente autorizada no config.yaml do Telegram, sem mudança no cenário comercial. Nenhuma visita real foi criada e nenhuma mensagem foi enviada a clientes nos testes.

Verificação final full: apenas 10 divergências preexistentes em Porteiro/Cadastro/FamaAgent; CEO, Reno e Agendamento aceitos. Os três gateways estão em execução e conectados.

Atualização das instruções carregadas por SessionDB nativo em reinício gracioso: 10 snapshots do CEO e 5 do Reno renovados; mensagens preservadas (CEO 6448, Reno 3131). Hooks temporários removidos após sucesso. Backup privado: `/root/.codex/rollback-backups/agendamento-20260909T162914Z`.

Alterações permanecem locais, sem commit/push. Proteção atômica contra gravações concorrentes no servidor permanece fora deste escopo.

Atualização posterior: as 10 divergências preexistentes foram resolvidas. Consulte `TEAM-DIVERGENCES-RESOLVED.md`; a verificação full agora passa.
