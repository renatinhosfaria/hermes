# Aprendizagem do Dev

Use ao concluir uma tarefa, receber correção do operador ou comprovar um
procedimento reutilizável. A autorização permanente está em `SOUL.md`; não
peça autorização novamente para registrar uma lição dentro desse escopo.

## Seleção e gravação

1. Identifique o que foi comprovado e o que é apenas hipótese. Se não houver
   aprendizado durável, encerre sem criar conteúdo artificial.
2. Use `memory` para fatos estáveis do trabalho e preferências duráveis pertinentes
   ao profile. Histórico de execução e estado transitório não são memória permanente.
3. Use skills para procedimentos, pré-requisitos, armadilhas e verificação.
   Procure cobertura com `skills_list`, leia com `skill_view` e prefira atualizar
   a skill pertinente usando `skill_manage`.
4. Crie uma nova skill somente para uma classe de tarefas ainda não coberta.
   Descreva quando usar, passos comprovados, limites e critério de verificação;
   não crie uma skill por tarefa nem registre resultados inventados.
5. Grave somente no próprio profile. Generalize exemplos e exclua dados de
   terceiros, segredos, conversas brutas, estado de clientes e hipóteses não confirmadas.
6. Confira o retorno da gravação e recarregue o conteúdo pelas ferramentas nativas.
   Uma leitura independente comprova persistência; não prova decisão autônoma futura.

## Workers, revisão automática e delegados

Em workers CLI/Kanban curtos, registre a lição antes da resposta final e de
encerrar o cartão. A revisão automática complementa esse trabalho e pode
concluir sem gravar nada. O plugin `fama-learning-lifecycle` aguarda revisões no
encerramento do CLI por tempo limitado; não garante que houve gravação.

Preserve as guardas nativas de conteúdo, proveniência e leitura antes de alteração.
`write_approval: false` não remove essas guardas. Aprender não autoriza apagar
skills, alterar políticas comerciais ou ampliar permissões.

Filhos de `delegate_task` não podem usar `memory`. Devem devolver ao pai lições,
procedimentos comprovados e limitações. O pai verifica e consolida; não contorne
as restrições nativas de memória compartilhada.

Versione mudanças de skills da tarefa com os demais arquivos autorizados, após
conferir sua origem. Memória privada continua fora do Git. Revisões automáticas
usam ferramentas nativas de memória/skills e não precisam de terminal ou Git;
não amplie suas permissões para conseguir commit. Alterações dessas revisões
exigem auditoria antes de serem incorporadas a uma tarefa de versionamento.

Para validar gatilhos, recuperação e o encerramento dos workers, use a referência
`references/memory-and-skill-learning.md` da skill `hermes-runtime-verification`.
