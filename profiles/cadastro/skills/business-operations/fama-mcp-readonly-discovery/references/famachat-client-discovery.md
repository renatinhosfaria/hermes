# FamaChat — referência de descoberta de clientes (sessão 2026-08-26)

Esta referência registra apenas fatos estruturais observados durante uma
sondagem de contrato em modo somente leitura. Não é uma especificação
permanente; recarregue `fc_catalog` e `tool_describe` se o manifesto mudar.

## Capacidade e catálogo

- `fc_catalog` sem filtro informou 271 endpoints em 41 módulos.
- O catálogo de ferramentas do runtime apresentou 277 nomes `famachat`.
- Esses números têm unidades/fontes diferentes e não devem ser misturados sem
  explicação.
- `fc_catalog` com busca de cliente retornou 23 rotas, incluindo as ferramentas
  de leitura `fc_get_clientes`, `fc_get_clientes_by_id`, `fc_get_clientes_all`
  e a de criação `fc_post_clientes`.

## Consulta de clientes

- `fc_get_clientes` é `GET /api/clientes`.
- A definição da ferramenta expõe `query` como objeto genérico; não há lista
  tipada de propriedades.
- A descrição textual do schema dá `limit` e `status` como exemplos de query.
  Isso é evidência documental para `status`, mas não substitui teste controlado.
- Em uma única consulta de sondagem, foi enviado um sentinela não-PII em
  `telefone` junto de `limit: 1`. A resposta efetiva trouxe 100 registros,
  portanto esses nomes/valores não produziram a restrição esperada nessa
  interface. Não concluir que outro alias, como `phone`, seja aceito sem
  evidência adicional.
- O envelope retornou `data` e `pagination`; os metadados observados foram
  `total: 100`, `page: 1` e `pageSize: 100`.
- Se um parâmetro de limite não for respeitado, classifique-o como ignorado ou
  não confirmado, não como filtro funcional.

## Forma do registro

Campos de primeiro nível observados:

`id`, `fullName`, `email`, `phone`, `source`, `sourceDetails`,
`preferredContact`, `cpf`, `brokerId`, `status`, `hasWhatsapp`, `whatsappJid`,
`profilePicUrl`, `idEmpreendimento`, `dataDeNascimento`,
`sobreABuscaPorUmImovel`, `vaiComprar`, `metaData`, `createdAt`, `updatedAt`.

- Telefone no registro: `phone`.
- Corretor no registro: `brokerId`, observado como número inteiro.
- Status no registro: `status`.
- Exemplo de máscara que preserva forma sem expor telefone: `(**) *****-XXXX`.

A presença desses campos na resposta não prova que sejam parâmetros aceitos na
consulta ou no corpo de criação.

## Criação

- `fc_post_clientes` é `POST /api/clientes`.
- A definição exposta aceita `query` e `body`, ambos genéricos.
- Não foram expostos `required`, propriedades tipadas, defaults, contrato de
  `brokerId`/`broker_id`, parâmetro de `status` ou schema de sucesso.
- Esses pontos devem ser reportados como não expostos/indeterminados. A
  ferramenta de criação não deve ser chamada para descobrir o contrato.

## Consulta de usuário

Para verificar um ID solicitado, use `fc_get_users` somente em leitura e reporte
apenas existência, cargo, departamento e atividade quando esses forem os
campos pedidos. Se o filtro parecer ignorado e a resposta vier completa, não
republique os outros usuários nem qualquer PII.

## Higiene de saída

Não registrar nesta referência nomes, e-mails, telefones reais, mensagens,
IDs de clientes ou dumps de resposta. Processar respostas grandes localmente e
emitir somente contagens, chaves, tipos e atributos explicitamente solicitados.
