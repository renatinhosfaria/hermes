# Validated profile-change recipe

Use this recipe only after the user has authorized the configuration change. It
keeps the change, verification, restart ownership, and Git scope separate.

## Before the change

```bash
git -C /root/.hermes status --short
git -C /root/.hermes ls-files -- profiles/PROFILE/config.yaml
```

Confirm the target file and note any pre-existing work. Do not call Telegram
`getUpdates` while a gateway is long-polling.

## Change and resolve

```bash
hermes -p PROFILE config set SECTION.KEY VALUE
hermes -p PROFILE config get SECTION.KEY
hermes -p PROFILE config check
git -C /root/.hermes diff --check
git -C /root/.hermes diff -- profiles/PROFILE/config.yaml
git -C /root/.hermes status --short
```

Treat the getter as the authoritative post-write check. If a getter reports
`Config key not set: SECTION.KEY`, report that exact failure; do not infer a
value. `config check` can emit a long credential checklist; do not copy secret
values into the report.

## Restart and commit boundaries

If the user says another operator will restart the gateway, do not restart it.
The resolved config proves the file state, not that an already-running gateway
has reloaded it.

Only after the diff is acceptable and commit authorization is explicit:

```bash
git -C /root/.hermes commit --only profiles/PROFILE/config.yaml -m "MESSAGE"
git -C /root/.hermes show --format='%h %s' --name-only --no-renames HEAD
git -C /root/.hermes status --short
```

Verify that the commit lists only the requested file and that no push occurred.

## CLI serialization pitfall

`hermes config set` may rewrite YAML formatting or remove comment-only blocks
when it serializes the file. Inspect the diff before committing. If unrelated
churn appears and the user did not clearly accept it, stop and report it rather
than hand-editing `config.yaml` or silently broadening the change.
