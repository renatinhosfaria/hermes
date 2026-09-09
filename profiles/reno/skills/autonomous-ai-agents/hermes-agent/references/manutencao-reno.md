# Manutenção do profile Reno

Use no modo administrativo autenticado definido no SOUL.md. Os caminhos e a
disciplina de mudança são definidos no `.hermes.md` do profile. Este procedimento
não autoriza instalação, acesso a credenciais ou alterações fora desse escopo.

## Procedimento

1. Delimite o pedido e leia os arquivos afetados antes de editar. Carregue a
   referência técnica da skill pertinente e confronte-a com o código/documentação
   instalados, especialmente se a referência estiver desatualizada.
2. Use `terminal`, `read_file`, `write_file`, `patch` e `skill_manage` conforme
   as capacidades do canal e as guardas nativas. Para configuração, use desde
   o início `hermes -p reno config set <chave> <valor>`; para remover uma chave,
   `hermes -p reno config unset <chave>`. Não use edição direta de `config.yaml`
   por `write_file` ou `patch`, pois o Hermes a bloqueia.
3. Confira valores com `hermes -p reno config get <chave>`. Após unset, confirme
   a ausência da chave no YAML e avalie o valor padrão resolvido, quando houver.
4. Valide YAML e execute `hermes -p reno config check`. Esse comando informa
   versão e configuração faltante; não prova inferência, autenticação, conexão
   MCP, escrita comercial ou aprendizagem.
5. Confira o diff e a resolução das ferramentas por canal, preservando Telegram
   administrativo e a allowlist do operador. Verifique o carregamento do SOUL,
   contexto e skills, incluindo referências movidas, sem bloqueio ou truncamento.
6. Quando a mudança afetar execução, faça verificação focada e uma inferência
   curta com dados sintéticos e efeitos externos desabilitados. Não use o teste
   para alterar clientes ou executar atendimento real. Relate o que foi de fato
   validado; não declare comportamento comprovado apenas por sintaxe válida.
7. Para mudança de aprendizagem, siga a referência
   `references/infraestrutura-aprendizagem.md` de `reno-aprendizado-continuo`.
   Para a entrega administrativa, siga o formato do `.hermes.md`.
