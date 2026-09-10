# Validação da ativação — 10/09/2026

- 34 testes passaram com o Python instalado do Hermes e bancos sintéticos.
  Incluem seleção 89/90 dias, recebimento e entrega recentes, retenção durável
  da confirmação, pausa humana real, tarefas/entregas pendentes, lease ocupada,
  corrida entre seleção e aplicação, compatibilidade, exclusão mútua e API nativa.
- Ruff check e format --check passaram; diff --check sem erros.
- Política Git passou; diretório operacional privado em 0700 e backup em 0600.
- Smoke do Brain passou: bancos Hermes, resolver, capability worker, transporte
  MCP e allowlist compatíveis.
- Fonte upstream sem alterações no git status após a instalação.
- Configuração do CEO: plugin habilitado e sessions.auto_prune=false.
- Plugin instalado por link para fonte versionável em ops/session-lifecycle.
- Reinício nativo do CEO concluído; serviço ativo, PID 1977730 na verificação.
  Especialistas não foram reiniciados nesta ativação.
- Primeiro ciclo confirmado em 2026-09-10T11:33:16.784599-03:00: 0 candidatas,
  nenhum encerramento de sessão real. Supervisor continua coletando horários;
  status observado: ready. A aplicação foi exercitada em fixtures.
- Registro do plugin importado com sucesso; profile Reno não inicia supervisor.
- Verificador de equipe: 11 falhas antes (core) e as mesmas 11 depois (full).
  Estão relacionadas a contratos/configurações anteriores de Porteiro,
  Cadastro, FamaAgent, Reno e Agendamento; não foram alteradas nesta tarefa.
  Isso não equivale a declarar toda a produção saudável.

Nenhuma mensagem externa foi enviada pela implementação ou pelos testes.
Nenhuma consulta de atendimento real foi usada como fixture. O banco do CEO
continua preservado; apenas a política de poda e o carregamento do plugin mudaram.
A nova política preserva mensagens existentes, mas não recupera dados que já
possam ter sido excluídos antes da instalação.
