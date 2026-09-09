# Divergências da equipe — correção em 09/09/2026

As 10 divergências anteriores foram resolvidas. Seis eram expectativas desatualizadas de platform_toolsets em Porteiro, Cadastro e FamaAgent. As quatro mensagens restantes descreviam dois vazamentos de escopo: Brain/FamaChat expostos no Telegram de Cadastro e FamaAgent pela ausência de no_mcp.

Atualizado verify_team.py para reconhecer memória/skills e os demais toolsets já autorizados. Adicionado no_mcp ao Telegram de Cadastro e FamaAgent via config set nativo, preservando os demais toolsets e todas as capacidades CLI. O Porteiro não precisou de alteração de configuração.

Incluídos testes de isolamento comercial no Telegram, manutenção administrativa e continuidade comercial/aprendizagem no CLI. Resultado: 58 testes passaram; config check dos dois profiles passou; verify_team.py full passou, sem divergências. Não foram feitas chamadas comerciais ou testes com clientes reais.

Os dois gateways reiniciaram graciosamente e conectaram. Para evitar a restauração de ferramentas antigas, a API nativa SessionDB limpou um cache de nomes de ferramentas Telegram em cada profile, após drenagem. Teste sintético confirmou preservação das instruções, mensagens e sessões CLI, além de idempotência. Históricos de produção preservados: Cadastro 108 sessões/1819 mensagens; FamaAgent 28 sessões/322 mensagens. Hooks temporários removidos.

Backup privado das configurações, verificador e listas anteriores de ferramentas: /root/.codex/rollback-backups/team-divergences-20260909T170403Z. Alterações locais, sem commit/push.
