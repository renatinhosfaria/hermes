# Hermes profile review checklist

Use this matrix for a read-only review. Replace `<profile>` with the canonical path returned by `hermes profile show`.

## Command matrix

| Purpose | Command | Scope note |
|---|---|---|
| Find canonical profile | `hermes profile list` | Global inventory |
| Confirm identity | `hermes profile show dev` | Profile metadata |
| Validate config | `HERMES_HOME=<profile> hermes config check` | Profile-scoped when env is honored |
| Summarize config | `HERMES_HOME=<profile> hermes config` | Never copy secret values |
| Diagnose dependencies/auth | `HERMES_HOME=<profile> hermes doctor` | Distinguish profile findings from shared workspace warnings |
| Inspect effective tools | `HERMES_HOME=<profile> hermes tools list` | A bundle in YAML may expand to many tools |
| Audit dependencies | `HERMES_HOME=<profile> hermes security audit` | Use as profile evidence |
| Inspect permissions | `stat -c '%A %a %U:%G %n' ...` | Linux; use native equivalent elsewhere |

## Safe evidence to collect

- profile path, model, provider, gateway state, and alias;
- config version and deprecated-key status;
- presence of `.env`, `auth.json`, and `SOUL.md`;
- provider status such as logged-in/not logged-in, never credentials;
- enabled toolset names and high-impact capabilities;
- permission bits and ownership of sensitive files;
- security-audit result;
- whether no changes were made.

## Report template

```markdown
## Veredito
<aprovado para uso interno sob demanda | aprovado com ressalvas | não aprovado>

### Fatos verificados
- ...

### Pontos positivos
- ...

### Pontos de atenção
- **Fato:** ...
- **Inferência:** ...
- **Desconhecido:** ...

### Próximas decisões
- ...

Nenhuma configuração foi alterada durante a revisão.
```

Do not call `doctor --fix`, `hermes setup`, `hermes config set`, or edit files as part of this checklist unless remediation was explicitly requested.
