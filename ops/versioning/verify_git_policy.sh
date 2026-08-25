#!/usr/bin/env bash
set -euo pipefail

repo_dir="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)}"
cd "$repo_dir"

fail() {
    printf 'FAIL: %s\n' "$1" >&2
    exit 1
}

git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || fail "$repo_dir ainda não é um repositório Git"

must_be_ignored=(
    .env
    auth.json
    state.db
    sessions/sessions.json
    profiles/famaagent/.env
    profiles/famaagent/auth.json
    profiles/famaagent/state.db
    platforms/whatsapp/session/creds.json
)

for path in "${must_be_ignored[@]}"; do
    git check-ignore -q -- "$path" \
        || fail "arquivo sensível ou transitório não está ignorado: $path"
done

must_be_allowed=(
    .gitignore
    .gitattributes
    .env.example
    VERSIONAMENTO.md
    SOUL.md
    .hermes.md
    config.yaml
    profile.yaml
    profiles/famaagent/.env.example
    profiles/famaagent/SOUL.md
    profiles/famaagent/.hermes.md
    profiles/famaagent/config.yaml
    profiles/famaagent/profile.yaml
    ops/versioning/verify_git_policy.sh
)

for path in "${must_be_allowed[@]}"; do
    if git check-ignore -q -- "$path"; then
        fail "personalização prevista está sendo ignorada: $path"
    fi
done

tracked_paths="$(git ls-files)"
while IFS= read -r path; do
    [ -z "$path" ] && continue
    case "$path" in
        .env|.env.*|*/.env|*/.env.*|auth.json|*/auth.json|*.db|*.db-*|*.sock|*.pid|*.lock)
            case "$path" in
                .env.example|*/.env.example) ;;
                *) fail "arquivo proibido já está rastreado: $path" ;;
            esac
            ;;
    esac
done <<< "$tracked_paths"

for example in .env.example profiles/*/.env.example; do
    [ -e "$example" ] || continue
    if awk '
        /^[[:space:]]*(#|$)/ { next }
        {
            line=$0
            sub(/^[[:space:]]*export[[:space:]]+/, "", line)
            if (line !~ /^[A-Za-z_][A-Za-z0-9_]*[[:space:]]*=[[:space:]]*$/) {
                exit 1
            }
        }
    ' "$example"; then
        :
    else
        fail "exemplo de ambiente contém valor ou sintaxe inesperada: $example"
    fi
done

if [ -n "$tracked_paths" ]; then
    secret_pattern='(sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|[0-9]{8,12}:[A-Za-z0-9_-]{30,})'
    leaked_files="$(git grep -IlE "$secret_pattern" -- $tracked_paths 2>/dev/null || true)"
    [ -z "$leaked_files" ] \
        || fail "padrão de credencial encontrado em arquivo rastreado: $leaked_files"
fi

printf 'OK: política Git segura verificada em %s\n' "$repo_dir"
