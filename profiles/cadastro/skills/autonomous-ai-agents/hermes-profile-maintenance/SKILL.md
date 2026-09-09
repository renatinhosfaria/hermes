---
name: hermes-profile-maintenance
description: "Use when maintaining Hermes. Verify safely and validate."
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [hermes, configuration, profiles, verification, gateway, self-improvement]
    category: autonomous-ai-agents
---

# Manutenção segura de profiles Hermes

## When to Use

Use para configurar ou verificar um profile Hermes, especialmente quando a
mudança envolve memória persistente, skills, revisão automática, toolsets ou um
gateway de mensagens.

## Procedure

1. **Carregue a orientação aplicável antes de agir.** Para comportamento do
   Hermes, consulte o skill `hermes-agent` e a documentação instalada; para uma
   tarefa específica, carregue também o skill do domínio. Não invente nomes de
   chaves a partir de memória.
2. **Confirme o profile e o escopo.** Use o profile explicitamente em todos os
   comandos (`hermes -p <profile> ...`) e altere somente a configuração do
   profile autorizado. Preserve segredos e não os inclua no relatório.
3. **Altere configuração pelo CLI nativo.** Use
   `hermes -p <profile> config set <chave> <valor>`; não edite `config.yaml`
   diretamente, porque o CLI preserva a estrutura e normaliza o valor. Para
   chaves suportadas, confirme imediatamente com
   `hermes -p <profile> config get <chave>`.
4. **Valide a configuração inteira.** Execute
   `hermes -p <profile> config check` e só considere a alteração concluída se o
   comando retornar sucesso. Se uma chave customizada for aceita com aviso,
   confirme no código/documentação que o runtime realmente a lê antes de
   mantê-la.
5. **Verifique a capacidade e a semântica dos gatilhos, não só o arquivo.** Para
   a aprendizagem automática, confirme separadamente memória persistente
   habilitada, o toolset `skills` disponível (inclui `skill_manage`),
   `auxiliary.background_review.enabled: true` e os intervalos de nudge. Trate
   `memory.nudge_interval` como contador de turnos do usuário e
   `skills.creation_nudge_interval` como contador de iterações de ferramenta;
   não os compare como se tivessem a mesma unidade. Use `memory status`,
   `tools list` e uma sondagem do runtime ou testes focados. A configuração
   habilitada não prova persistência: confirme uma gravação e uma recuperação em
   processo independente quando a tarefa exigir prova de execução. O fork nativo
   só dispara após uma resposta final não interrompida e depende das ferramentas
   disponíveis.
6. **Valide o encerramento por superfície.** Em execuções one-shot do CLI,
   confirme que o hook oficial `on_session_finalize` ou equivalente aguarda a
   revisão em segundo plano antes do cleanup, com limite de espera explícito
   (até 300 segundos quando configurado). Em canais gateway, trate a revisão como
   assíncrona e não exija espera síncrona. A revisão automática pós-turno captura
   memória e atualiza skills; o curator mantém a biblioteca e a consolidação LLM
   é uma opção separada, mais ampla e com custo. Não habilite consolidação apenas
   para ativar aprendizagem.
7. **Teste pelo ambiente declarado do projeto.** Para testes do código-fonte,
   prefira o extra de desenvolvimento declarado pelo projeto, por exemplo
   `uv run --extra dev pytest <testes-focados>`, em vez de presumir que o
   virtualenv do launcher contém as dependências de teste.
8. **Respeite o limite do gateway.** Se a manutenção for executada dentro do
   próprio processo do gateway, o Hermes pode recusar restart/stop para evitar
   que o processo mate o comando filho. Não contorne a recusa com `systemctl` ou
   outro caminho equivalente. Deixe a configuração persistida, registre que o
   gateway continua ativo e, se a aplicação imediata for indispensável, indique
   que o operador deve reiniciar a partir de um shell externo.
9. **Relate evidência e lacunas.** Informe somente o que mudou, os componentes
   verificados, os comandos e resultados reais, além de limitações. Separe
   configuração persistida, capacidade detectada, testes executados e estado do
   gateway; não declare uma execução automática que não foi observada.

## Pitfalls

- Não habilite recursos apenas porque são defaults: torne explícita somente a
  chave necessária e confirme o valor resolvido, reduzindo diffs e ambiguidades.
- Não confunda `curator.enabled` com a revisão de aprendizagem pós-turno; eles
  têm gatilhos, custos e efeitos diferentes.
- Não reinicie um gateway a partir de dentro dele; a proteção existe porque o
  processo pai pode propagar SIGTERM ao comando de manutenção.
- Não trate `config get`, `config check` ou um teste unitário isolado como prova
  de que um gateway antigo recarregou a configuração; valide o processo e
  informe quando a nova sessão ainda for necessária.
- Não trate a saída de uma execução one-shot como prova de persistência da
  revisão; confirme o readback em processo independente, porque uma thread
  daemon pode ser encerrada no cleanup antes de gravar.
- Não inclua tokens, valores de `.env`, Authorization, conteúdo bruto de
  configuração ou PII no handoff.

## Verification

A manutenção está verificada quando o `config check` passa, cada chave alterada
foi relida, os toolsets/capacidades relevantes foram observados no runtime, os
semântica e gatilhos de aprendizagem foram exercitados quando aplicável, os
testes focados passam quando disponíveis e o estado do gateway foi consultado.
Para persistência, a evidência forte é uma gravação e a recuperação posterior em
processo independente; para o ciclo de vida, verifique a espera limitada no CLI
e o comportamento assíncrono nos gateways.
