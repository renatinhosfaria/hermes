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

# Classify skills from the same origin hashes Hermes records. New local skills
# and bundled skills changed by the user must be versioned; unchanged bundled
# and Skills Hub installations must remain ignored.
skills_root="$repo_dir/skills"
skill_versioned_count=0
skill_managed_count=0
profile_skill_versioned_count=0
profile_skill_managed_count=0
if [ -d "$skills_root" ]; then
    command -v python3 >/dev/null 2>&1 \
        || fail "python3 é necessário para classificar as skills"

    while IFS=$'\t' read -r kind path; do
        [ -z "$kind" ] && continue
        case "$kind" in
            versioned)
                if git check-ignore -q -- "$path"; then
                    fail "skill personalizada ou modificada está ignorada: $path"
                fi
                skill_versioned_count=$((skill_versioned_count + 1))
                ;;
            managed)
                git check-ignore -q -- "$path" \
                    || fail "skill gerenciada foi liberada indevidamente: $path"
                skill_managed_count=$((skill_managed_count + 1))
                ;;
            *) fail "classificação de skill desconhecida: $kind" ;;
        esac
    done < <(SKILLS_ROOT="$skills_root" python3 - <<'PY'
from pathlib import Path
import hashlib
import json
import os
import re

root = Path(os.environ["SKILLS_ROOT"])
manifest_path = root / ".bundled_manifest"
if not manifest_path.is_file():
    raise SystemExit("manifesto de skills bundled ausente")

manifest = {}
for line in manifest_path.read_text(encoding="utf-8").splitlines():
    if ":" in line:
        name, digest = line.rsplit(":", 1)
        manifest[name.strip()] = digest.strip()

hub_names = set()
hub_lock = root / ".hub" / "lock.json"
if hub_lock.is_file():
    def collect_names(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"name", "skill_name", "slug"} and isinstance(child, str):
                    hub_names.add(child)
                collect_names(child)
        elif isinstance(value, list):
            for child in value:
                collect_names(child)

    collect_names(json.loads(hub_lock.read_text(encoding="utf-8")))

def read_name(skill_md):
    text = skill_md.read_text(encoding="utf-8", errors="replace")[:4000]
    match = re.search(r"(?ms)^---\s*$.*?^name:\s*[\"']?([^\n\"']+)", text)
    return match.group(1).strip() if match else skill_md.parent.name

def directory_hash(directory):
    digest = hashlib.md5()
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(directory)).encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()

for skill_md in sorted(root.rglob("SKILL.md")):
    name = read_name(skill_md)
    relative = skill_md.relative_to(root).as_posix()
    if name in manifest:
        kind = "managed" if directory_hash(skill_md.parent) == manifest[name] else "versioned"
    elif name in hub_names:
        kind = "managed"
    else:
        kind = "versioned"
    print(f"{kind}\tskills/{relative}")
PY
    )

    for metadata in \
        skills/.bundled_manifest \
        skills/.usage.json \
        skills/.usage.json.lock \
        skills/.curator_state \
        skills/.curator_ledger.jsonl \
        skills/.hub/lock.json; do
        git check-ignore -q -- "$metadata" \
            || fail "metadado gerenciado de skills não está ignorado: $metadata"
    done
fi

# Apply the same classification independently to every named profile. Profiles
# created with --no-skills legitimately have no bundled manifest; in those
# trees, any skill not recorded by the Skills Hub is local by definition.
if [ -d "$repo_dir/profiles" ]; then
    while IFS=$'\t' read -r kind path; do
        [ -z "$kind" ] && continue
        case "$kind" in
            versioned)
                if git check-ignore -q -- "$path"; then
                    fail "skill personalizada ou modificada de profile está ignorada: $path"
                fi
                profile_skill_versioned_count=$((profile_skill_versioned_count + 1))
                ;;
            managed)
                git check-ignore -q -- "$path" \
                    || fail "skill gerenciada de profile foi liberada indevidamente: $path"
                profile_skill_managed_count=$((profile_skill_managed_count + 1))
                ;;
            *) fail "classificação de skill de profile desconhecida: $kind" ;;
        esac
    done < <(PROFILES_ROOT="$repo_dir/profiles" python3 - <<'PY'
from pathlib import Path
import hashlib
import json
import os
import re

profiles_root = Path(os.environ["PROFILES_ROOT"])

def read_manifest(root):
    result = {}
    path = root / ".bundled_manifest"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if ":" in line:
                name, digest = line.rsplit(":", 1)
                result[name.strip()] = digest.strip()
    return result

def read_hub_names(root):
    result = set()
    path = root / ".hub" / "lock.json"
    if not path.is_file():
        return result

    def collect(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"name", "skill_name", "slug"} and isinstance(child, str):
                    result.add(child)
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(json.loads(path.read_text(encoding="utf-8")))
    return result

def read_name(skill_md):
    text = skill_md.read_text(encoding="utf-8", errors="replace")[:4000]
    match = re.search(r"(?ms)^---\s*$.*?^name:\s*[\"']?([^\n\"']+)", text)
    return match.group(1).strip() if match else skill_md.parent.name

def directory_hash(directory):
    digest = hashlib.md5()
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(directory)).encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()

for profile in sorted(path for path in profiles_root.iterdir() if path.is_dir()):
    root = profile / "skills"
    if not root.is_dir():
        continue
    manifest = read_manifest(root)
    hub_names = read_hub_names(root)
    for skill_md in sorted(root.rglob("SKILL.md")):
        name = read_name(skill_md)
        relative = skill_md.relative_to(profiles_root.parent).as_posix()
        if name in manifest:
            kind = "managed" if directory_hash(skill_md.parent) == manifest[name] else "versioned"
        elif name in hub_names:
            kind = "managed"
        else:
            kind = "versioned"
        print(f"{kind}\t{relative}")
PY
    )

    for profile_dir in "$repo_dir"/profiles/*; do
        [ -d "$profile_dir/skills" ] || continue
        relative_profile="profiles/${profile_dir##*/}/skills"
        for metadata in \
            .bundled_manifest \
            .usage.json \
            .usage.json.lock \
            .curator_state \
            .curator_ledger.jsonl \
            .hub/lock.json; do
            git check-ignore -q -- "$relative_profile/$metadata" \
                || fail "metadado gerenciado de skills de profile não está ignorado: $relative_profile/$metadata"
        done
    done
fi

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
    # Length floors avoid flagging documentation slugs such as
    # "sk-concurrency-diagnosis" and short all-x placeholders while retaining
    # plausible OpenAI/GitHub/Slack/Telegram credential formats.
    secret_pattern='(sk-[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{20,}|[0-9]{8,12}:[A-Za-z0-9_-]{30,})'
    leaked_files="$(git grep -IlE "$secret_pattern" -- $tracked_paths 2>/dev/null || true)"
    [ -z "$leaked_files" ] \
        || fail "padrão de credencial encontrado em arquivo rastreado: $leaked_files"
fi

printf 'OK: política Git segura verificada em %s (skills raiz versionadas=%s, gerenciadas=%s; profiles versionadas=%s, gerenciadas=%s)\n' \
    "$repo_dir" "$skill_versioned_count" "$skill_managed_count" \
    "$profile_skill_versioned_count" "$profile_skill_managed_count"
