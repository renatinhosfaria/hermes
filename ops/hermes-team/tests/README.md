# Regressão do handoff CTWA

## Escopo

O ajuste é de instruções CEO/Reno e diagnóstico offline. Não altera o Brain,
MCP, permissões, `kanban_create` ou isolamento de sessões. Não impede
deterministicamente que um modelo omita campos e não preenche cartões antigos.

O verificador recebe dois artefatos da **mesma conversa auditada**: resultado
do Brain e body do cartão em objeto JSON. Compara evento, origem e os cinco
campos da atribuição confirmada, preservando strings, nomes e separação entre
eventos. Também compara telefone quando fornecido e rejeita chaves raw
conhecidas. Não autentica a origem dos artefatos, valida o envelope Kanban
inteiro ou detecta todo dado pessoal/raw dentro de texto livre.

## Testes automatizados

Execute da raiz deste checkout:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/local/lib/hermes-agent/venv/bin/python \
  -m unittest discover -s ops/hermes-team/tests -v
```

As fixtures são inteiramente fictícias. Os testes comparam expectativas
escritas independentemente do verificador e incluem a CLI real em diretório
temporário. Cobrem perda/alteração de campos, tipo dos IDs, outro contato,
eventos múltiplos/duplicados, estados pendentes, ausência de atribuição,
indisponibilidade do Brain, raw e erros de entrada sem ecoar seu conteúdo.

## Ensaio comportamental — 08/09/2026

Base: `7e59d93`, worktree `fix/ctwa-reno-handoff`.

Controle histórico observado: no primeiro cartão do Reno, o retorno do Brain
tinha `status`, `ad_id`, `ad_name`, `campaign_id`, `campaign_name`, mas o CEO
copiou somente `status` e `ad_id`. Isso exigiu complemento posterior. A
regressão `test_id_only_transfer_reproduces_real_omission` reproduz a perda
com dados fictícios; ela testa o diagnóstico, não uma chamada do CEO real.

Protocolo dos microensaios do CEO, em contexto novo por execução:

1. Ler integralmente SOUL e skill do CEO, antigos no controle, novos no candidato.
2. Receber `confirmed` da fixture, wake de Cadastro concluído e retorno do Brain
   da conversa A. Expor `other_contact` como conversa independente.
3. Pedir primeiro cartão compacto para o Reno, com cliente esperando há minutos,
   sem resposta pronta. Retornar argumentos simulados, com body em objeto JSON.
4. Não chamar ferramentas de negócio ou serviços. Comparar os campos e ler
   manualmente cada resposta; não contar uma citação de exemplo como execução.

Resultados observados:

| Verificação | Resultado |
| --- | --- |
| Microensaios do CEO antigo, 5 contextos novos | 5/5 copiaram todos os campos úteis, mas alternaram entre `evento`, `event` e `events`. A omissão histórica não foi reproduzida nesses ensaios simples. |
| Microensaios do CEO novo, 5 contextos novos | 5/5 copiaram o bloco exato em `contexto.ctwa_attributions`, com flag de resolução correta, sem raw ou dados do contato B. |
| Variações do CEO | Pendente: encaminhou ao Reno sem inventar nomes. Brain indisponível na entrada inicial: encaminhou ao Porteiro sem inventar telefone. Dois eventos: preservou ambos sem dados da outra conversa. |
| Reno, comparação pontual | Ambos usaram FamaChat simulado e histórico uma vez. O controle acrescentou confirmação do anúncio apesar de candidato único; o candidato respondeu com endereço verificado e pergunta de aderência, sem criar vínculo. |
| Variações do Reno | Sem atribuição e sem nome: preparou pergunta útil, sem esperar Meta. Dois empreendimentos distintos: pediu esclarecimento. Bloco incompleto com imóvel explícito na mensagem: respondeu usando FamaChat e registrou a lacuna para o CEO. |

As respostas sintéticas completas ficaram no diretório local protegido
`/var/lib/brain/runtime/repairs/ctwa-handoff-tests.yzqrq6/`.

Isso demonstra compreensão do formato nos ensaios, **não** uma redução medida
da taxa de omissão ou do tempo em produção. Não foi o runtime/modelo de produção
executando Kanban/MCP: houve agentes de teste, fixtures e body JSON, sem entrega
real nem validação de serialização YAML por uma chamada real de `kanban_create`.
Confirmar o próximo primeiro cartão e a entrega ao cliente após ativação
autorizada; instruções existentes podem continuar em cache.

## Pendências anteriores, fora deste ajuste

`ops/plugins/fama-kanban-channel-policy/tests` retorna 5 passes, 1 falha e 1
erro tanto na base sem alterações quanto neste worktree, com o core instalado.
O usuário autorizou prosseguir mantendo essas pendências separadas:

- `test_claim_hook_enforces_before_spawn`: o mock ainda aponta para
  `hermes_cli.kanban_db._memory_pressure_level`, movido no core.
- `test_installed_watcher_maps_wake_to_active_only`: a inspeção AST procura
  atribuições no arquivo antigo, enquanto a implementação mudou de módulo.

Não foi declarada uma suíte global verde. Os testes de skills de terceiros
fora desse fluxo não integram esta validação CTWA.
