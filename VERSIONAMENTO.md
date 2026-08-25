# Versionamento de `/root/.hermes`

Este repositório mantém somente personalizações declarativas e automações
criadas para esta instalação do Hermes. O diretório também contém estado vivo,
credenciais e dados pessoais; por isso, a política é uma lista permitida no
`.gitignore`, e não uma lista aberta de exceções.

## O que entra no Git

- `SOUL.md`, `.hermes.md`, `config.yaml` e `profile.yaml` da raiz;
- os equivalentes de cada diretório em `profiles/`;
- arquivos `.env.example` com valores vazios;
- skills criadas localmente e skills bundled modificadas localmente, tanto na
  raiz quanto dentro dos profiles;
- documentação em `docs/` e automações em `ops/`;
- os arquivos que documentam e verificam esta própria política.

## O que nunca entra em texto puro

- `.env`, `auth.json`, tokens, cookies e credenciais de plataformas;
- bancos `*.db`, arquivos WAL/SHM, sessões, mensagens e memórias;
- logs, caches, PIDs, sockets, locks, snapshots e binários gerenciados;
- skills bundled sem alterações, skills do Hub, metadados de uso, plugins e
  dependências instalados automaticamente.

Um repositório remoto privado não torna seguro registrar uma credencial. Caso
algum segredo precise de histórico, ele deve ser cifrado antes com uma solução
como SOPS/age e liberado explicitamente na política.

## Fluxo de auditoria

Antes de adicionar ou commitar mudanças, execute:

```bash
ops/versioning/verify_git_policy.sh
git status --short
git diff --cached
```

O verificador compara cada diretório de skill da raiz e dos profiles com os
hashes registrados pelo Hermes nos respectivos `.bundled_manifest`. Skills
locais ou bundled modificadas precisam de uma regra explícita no `.gitignore`;
skills oficiais intactas e instalações do Skills Hub precisam continuar
ignoradas. Assim, uma nova skill personalizada faz a auditoria falhar até ser
deliberadamente adicionada à allowlist.

Para começar a rastrear uma nova categoria de personalização, acrescente uma
regra explícita ao `.gitignore` e um caso correspondente ao verificador. Nunca
use `git add -f` para contornar a política.
