---
name: reno-aprendizado-continuo
description: "Use when consolidating Reno lessons. Save verified learning."
version: 1.1.0
---

# Aprendizado contínuo do Reno

## Quando usar

O gatilho e a autorização são definidos no SOUL.md. Em workers curtos, execute
a avaliação e eventual gravação antes da resposta final e do encerramento do
cartão. A revisão em segundo plano complementa esse trabalho. Sem lição durável,
conclua a avaliação sem escrever.

## Procedimento

1. Identifique a diferença entre o procedimento anterior e o que a evidência demonstrou funcionar. Se o resultado não foi verificado, não registre a hipótese como solução.
2. Classifique a informação: preferência durável do operador pertence ao alvo `user` da ferramenta `memory`; fatos estáveis aplicáveis a todas as sessões pertencem ao alvo `memory`; procedimentos, correções e lições operacionais de uma classe de tarefa pertencem à skill correspondente, mesmo quando curtos. O alvo `user` corresponde a `USER.md`; o alvo `memory`, a `MEMORY.md`.
3. Generalize a lição e filtre-a pelos limites de privacidade e confiança do SOUL.md; remova também eventos temporários e detalhes que permitam reconstruir um atendimento.
4. Releia com `skill_view` a skill usada na tarefa durante a própria revisão e procure a lição no texto e nas referências pertinentes; fortaleça a regra existente antes de acrescentar outra, pois duplicatas divergem com o tempo. Priorize essa skill se cobrir a classe de trabalho e permitir manutenção autônoma; só então procure outra com `skills_list`. Respeite skills protegidas ou de propriedade do usuário: não tente contornar recusa de edição. Crie uma nova somente se houver uma classe de tarefa distinta e reutilizável; mantenha regras gerais em SKILL.md e profundidade opcional em referências por assunto, nunca por sessão.
5. Escreva regras acionáveis acompanhadas do motivo: pré-requisitos, sequência comprovada, erro a evitar e critério de verificação. Não narre o incidente nem transforme uma tentativa em comando recomendado.
6. Para memória, use a ferramenta `memory`, com entradas compactas e sem duplicar instruções de contexto. Consolide antes de ultrapassar a capacidade. A ferramenta não tem ação de leitura: o contexto inicial contém o snapshot e as respostas de escrita mostram o estado atual.
7. Confira o resultado das ferramentas e releia a skill ou referência gravada com `skill_view`; para memória, confira o estado retornado pela escrita. Não declare aprendizado salvo quando estiver apenas proposto, pendente de aprovação ou bloqueado. Respeite qualquer aprovação exigida pelo runtime.
8. Em manutenção, relate brevemente o aprendizado efetivamente salvo quando útil. Em atendimento, mantenha a entrega comercial normal e não mencione memória ou skills ao cliente.

## Armadilhas

- Memória persistente não altera os pesos do modelo; melhora futuras execuções por contexto e procedimentos carregados.
- Uma skill carregada é um procedimento, não fonte de preço, disponibilidade, vínculo ou autorização comercial.
- A revisão usa ferramentas nativas de memória e skills; não precisa de terminal ou Git. Preserve os limites do canal definidos no SOUL.md.
- Não crie arquivos de registro por turno: referências devem ser organizadas por assunto e estendidas no lugar.

## Verificação

Para validar a infraestrutura de aprendizado no Telegram administrativo, carregue também `hermes-agent` e consulte a documentação oficial de memória e skills, dentro do escopo autorizado. Siga `references/infraestrutura-aprendizagem.md` para distinguir configuração, disparo da revisão e persistência efetiva. Exija evidência de gravação e recuperação entre execuções: opções habilitadas não comprovam aprendizagem. Se a execução permitir somente leitura de skills e snapshot, não amplie a inspeção; atribua verificações anteriores à evidência fornecida e explicite o que não foi revalidado.

Ao alterar código de apoio à aprendizagem, execute uma verificação focada depois da última alteração. Exija testes efetivamente executados e asserções sobre o comportamento: saída zero, sintaxe válida ou descoberta de zero testes não comprovam funcionamento. Identifique verificações ad hoc como tais, sem apresentá-las como suíte oficial; relate o resultado concreto e remova verificadores temporários ao terminar. A receita de execução está em `references/infraestrutura-aprendizagem.md`.

Para validar uma lição de atendimento, aplique o modo de teste de `fama-reno-runtime`.
