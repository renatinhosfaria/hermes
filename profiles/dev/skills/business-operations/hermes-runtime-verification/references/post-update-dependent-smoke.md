# Post-update dependent smoke verification

Use after evidence shows the installed Hermes checkout changed, especially when a restart also rewrites a systemd service definition. Keep the install audit and dependent-application validation distinct: rewriting a unit does not by itself prove that code changed at the same instant.

## Establish the update timeline

Capture safe, read-only evidence:

```bash
hermes --version
git -C /usr/local/lib/hermes-agent log --oneline -5
git -C /usr/local/lib/hermes-agent status --porcelain
git -C /usr/local/lib/hermes-agent reflog -5 --date=iso
stat -c '%y %n' /usr/local/lib/hermes-agent/hermes_state_common.py
```

Interpretation:

- A reflog transition with timestamp establishes that `HEAD` moved and identifies the prior and current commits.
- An empty installed-tree status proves only that the current checkout is clean; it does not prove that no update occurred.
- File and unit mtimes help correlate events but are supporting evidence, not commit identity.
- Report a service-definition rewrite separately from the source update timeline.

## Run dependent integration checks

After every confirmed Hermes update, locate and execute the dependent system's canonical runbook checks rather than inventing an ad-hoc probe. For the Fama Brain integration, the validated read-only sequence is:

```bash
cd /root/brain
/root/brain/.venv/bin/python scripts/hermes_integration_check.py; echo "exit=$?"
/root/brain/.venv/bin/python scripts/smoke_test.py; echo "exit=$?"
PYTHONPATH=src /root/brain/.venv/bin/python -m unittest discover -s tests 2>&1 | tail -5
```

Reporting rules:

1. Quote the complete output and explicit exit code of each canonical smoke script.
2. If either smoke script fails, preserve the exact `FAIL` message and stop remediation unless the task separately authorizes a fix.
3. Quote only the requested tail for the unit suite when the operator asks for that format.
4. A pipeline's shell status normally comes from its last process. If the acceptance criterion requires the unit runner's true exit status, use `set -o pipefail` or capture the full command status separately—but do not silently change a literal operator-requested command.
5. Re-check `/usr/local/lib/hermes-agent` cleanliness after verification. These checks must not patch the installation, restart gateways, or touch credentials/live state.
