# Validação da infraestrutura de aprendizagem

## Sequência de verificação

1. Delimite a fase e o escopo permitido antes de agir. Quando o primeiro plano estiver restrito a leitura, leia skills e o snapshot inicial sem gravar; deixe eventual persistência para a revisão nativa autorizada.
2. Em manutenção com acesso autorizado à configuração, consulte os valores com `hermes -p reno config get <chave>` e confronte a semântica com documentação oficial e código instalado. Inspecione `memory.memory_enabled`, `memory.user_profile_enabled`, `memory.write_approval`, `skills.write_approval`, `auxiliary.background_review.enabled` e `auxiliary.background_review.provider`. Separe habilitação, exigência de aprovação e seleção de provider; nenhum desses valores comprova execução.
3. Verifique as unidades dos gatilhos: `nudge_interval` de memória conta turnos de usuário; `creation_nudge_interval` de skills conta iterações de ferramenta. Não interprete intervalos iguais como cadências equivalentes, pois os contadores medem eventos diferentes.
4. Distinga os mecanismos: o fork de revisão nasce após a resposta quando acionado, não obrigatoriamente a cada mensagem; o Curator periódico mantém o ciclo de vida das skills. Não use `curator.consolidate=false` como diagnóstico de aprendizagem desligada: essa opção controla consolidação, não substitui nem desativa o fork pós-turno.
5. Para permitir manutenção autônoma de uma skill não gerenciada, use adoção individual somente em manutenção de primeiro plano explicitamente autorizada: `hermes -p reno curator adopt reno-aprendizado-continuo`. Na revisão autônoma, não adote nem altere skills protegidas: recomende a adoção ao operador e preserve o conteúdo. Não estenda adoção a manuais comerciais ou skills externas. Preserve guardas de proteção e leitura prévia do arquivo exato antes de patch; adoção não é autorização para contornar uma recusa.
6. Comprove separadamente configuração, execução da revisão, gravação e recuperação em outra execução. Use o resultado real da escrita e a leitura posterior do alvo permitido; não declare persistência por haver configuração ligada, uma intenção de salvar ou apenas conteúdo presente no contexto.
7. No relatório, diferencie resultados observados nesta execução de verificações anteriores fornecidas como contexto. Se o escopo impedir comprovar uma etapa, declare essa limitação em vez de produzir evidência simulada.

## Teste controlado com o modelo real

Use `tests/learning_smoke.py` no home do Reno para reproduzir a validação, após carregar `hermes-agent`, confirmar autorização administrativa e revisar o escopo do script. Execute com o Python do ambiente instalado e `-B`, preservando a instalação somente leitura. Rode as fases `review` e `recall` em processos separados e sequenciais; não mantenha escritores concorrentes nos mesmos arquivos de memória.

- Na fase `review`, o script antecipa somente os contadores da instância descartável para testar o disparo pós-turno nativo em uma execução; não altera intervalos de produção nem simula saída do modelo. Essa antecipação testa o mecanismo, não a passagem espontânea de dez turnos no gateway.
- Aguarde o término da thread `bg-review` antes de encerrar o processo; uma thread daemon pode morrer junto com o processo e invalidar a verificação.
- Distinga conclusão de revisão de gravação: `result=none` pode ser legítimo quando não há novidade. Para comprovar uma escrita, exija resumo de operação aplicada e releitura do alvo. Não fabrique novidade nem duplique uma skill para fazer o teste passar.
- Na fase `recall`, use memória carregada do disco, sem fornecer o conteúdo esperado no prompt nem reutilizar o histórico da primeira execução; carregue também a referência salva via `skill_view`.
- Mantenha `session_db=None`, persistência da conversa desativada, MCPs fora do conjunto de ferramentas e as escritas do teste limitadas à skill de aprendizagem. Não use sessões de plataforma ou dados comerciais como material de teste.

## Verificação ad hoc de código de apoio

1. Use a suíte existente quando cobrir a alteração. Se não houver uma adequada, crie um verificador temporário focado, com prefixo `hermes-verify-`, em vez de inventar um comando oficial do projeto. Use `unittest` da biblioteca padrão quando ele bastar; um teste pequeno não precisa acrescentar dependências.
2. Separe asserções estruturais de evidência comportamental. AST e compilação podem conferir sintaxe, ferramentas habilitadas, ausência de histórico reutilizado e isolamento de persistência; para comprovar recuperação, execute `learning_smoke.py recall` em processo novo com o modelo real e valide sua saída JSON. Confira resposta não vazia, chamadas reais ao modelo, memória ativa, leitura da skill e referência e ausência de ferramentas de escrita. Não substitua essa execução por respostas simuladas.
3. Execute o módulo temporário explicitamente com o intérprete correto e `-B`. Para um arquivo `/tmp/hermes-verify-<sufixo>.py`, use `/tmp` como diretório de trabalho e `python -B -m unittest 'hermes-verify-<sufixo>' -v`, substituindo `python` pelo intérprete do ambiente. Evite `unittest discover` para nomes com hífen: a descoberta pode ignorá-los por não corresponderem a nomes de módulo aceitos pelo seu filtro.
4. Confira o número de testes executados, além de `OK` e do código de saída. Se aparecer `Ran 0 tests`, corrija a seleção e rode novamente; nenhum comportamento foi exercitado por esse resultado. Não encerre só porque o comando retornou zero.
5. Remova o verificador temporário após registrar o resultado, inclusive quando precisar corrigir o comando de execução. No relatório, diga quais comportamentos foram testados e distinga a verificação focada da suíte completa; não atribua um aviso persistente do runtime a uma causa técnica ainda não demonstrada.

## Snapshot e conteúdo durável

- Recupere preferências já existentes do snapshot inicial sem regravá-las; uma solicitação de teste não constitui por si só nova preferência durável.
- Registre procedimentos de validação nesta skill, não como fatos globais de memória; configurações atuais são estado verificável, não identidade do usuário.
- Preserve apenas o procedimento e seu critério de sucesso; exclua logs, marcadores de teste, identificação do operador e dados comerciais.
