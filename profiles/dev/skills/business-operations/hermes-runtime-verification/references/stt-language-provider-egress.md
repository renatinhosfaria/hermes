# STT language, provider, and audio-egress audit

Use this reference when a Hermes profile's inbound voice transcription may force
the wrong language or send customer audio to a remote API.

## Claims to separate

1. **Persisted selection:** whether raw `config.yaml` actually contains
   `stt.provider`; a provider subsection such as `stt.openai` configures that
   backend but does not select it.
2. **Resolver semantics:** what `_get_provider()` chooses when the provider is
   absent, including local dependency checks, lazy installation, and cloud
   fallback order.
3. **Observed execution:** what the live gateway log proves was used for an
   actual transcription. Configuration and resolver potential are not proof of
   a completed runtime path.
4. **Egress guarantee:** an auto-detected local-first path is not equivalent to
   an explicit local-only policy if failed local setup can fall through to a
   cloud provider.

## Source-tracing map

Re-check line numbers against the installed checkout on every audit.

- `tools/transcription_tools.py`
  - `_resolve_stt_language`: precedence, empty-string autodetection, and absence
    of a Hermes-side language whitelist.
  - `_get_provider`: explicit selection versus autodetection and fallback order.
  - `_try_lazy_install_stt`: whether local STT may install on first use.
  - `build_local_transcribe_kwargs` and `_transcribe_local`: propagation of the
    language hint into faster-whisper and downstream error handling.
  - cloud-provider transcribers: whether the language and audio file are sent to
    an API and how API errors are surfaced.
- `hermes_cli/config_defaults.py`: documented language format, provider defaults,
  and the empty-string autodetection convention.
- `tools/lazy_deps.py::_allow_lazy_installs`: effective lazy-install policy.
- `gateway/run.py`: how successful, empty, and failed transcripts become
  agent-visible input.

## Procedure

1. Read only the focused `stt` subtree from the target profile. Report provider,
   language, model, and booleans; do not expose credentials or broader config.
2. Use `hermes config get` only for safe scalar keys. Treat “key not set” as a
   meaningful result rather than silently replacing it with a default.
3. Trace the language resolver. Verify whether it validates against an enum or
   merely strips and forwards any non-empty string. An in-memory probe may pass
   representative values (`pt`, a regional tag, garbage, and empty) to the
   resolver; run with `PYTHONDONTWRITEBYTECODE=1` and never call a function that
   can install dependencies.
4. Trace provider selection without invoking `_get_provider()` when that path can
   call a lazy installer. Probe dependency presence and `_allow_lazy_installs()`
   separately, then explain conditional branches.
5. Check the latest gateway log for a provider-specific success/failure entry.
   Absence of evidence means the effective provider is still unobserved.
6. State privacy precisely:
   - explicit/observed local processing: audio remains on the host;
   - explicit cloud processing: audio is uploaded;
   - unset provider with local-first/cloud fallback: intended local path, but no
     strict no-egress guarantee unless source proves fallback is impossible.
7. Confirm both the inspected config repository and installed checkout were not
   changed. Do not restart the gateway during a read-only audit.

## Language conclusions

- Hermes may accept a string that the downstream provider rejects. Distinguish
  “accepted by config/resolver” from “supported by the provider.”
- Prefer the provider's documented language-code form; do not infer support for
  regional tags merely because Hermes forwards them.
- Empty or absent language enables provider autodetection only if no higher- or
  lower-precedence non-empty override (including the legacy environment variable)
  wins.
- If a downstream language value is invalid, trace both the provider error
  envelope and gateway behavior; do not assume config validation catches it.

## Containment and external local backends

When a live gateway must be contained before provisioning STT, persist
`stt.enabled: false`, but do not call that containment active until the running
`GatewayRunner` has reloaded its configuration. Establish process start time and
trace whether `self.config.stt_enabled` is cached or refreshed. A successful
`config get` proves disk state, not live activation; restart only with explicit
authorization.

With STT disabled, trace the disabled branch in `gateway/run.py`. Current
implementations may place the audio's absolute cache path in the agent-visible
message while returning no successful transcript. This prevents automatic
transcript echo, but it is still a potential outbound disclosure if the agent
repeats the path. Distinguish automatic adapter send from model-mediated leakage.

For a local executable backend, audit `HERMES_LOCAL_STT_COMMAND` in
`tools/transcription_tools.py`:

- it is a command template, executed directly after `shlex.split`, not through a
  shell;
- supported placeholders include `input_path`, `output_dir`, `language`, and
  `model`;
- non-native inputs may require `ffmpeg` conversion to WAV;
- success requires exit code zero and a UTF-8 `*.txt` file under `output_dir`;
  stdout is not the transcript;
- the subprocess has a bounded timeout and receives a credential-scrubbed
  environment.

For optional Python dependencies, inspect both modes in `tools/lazy_deps.py`:

- without `HERMES_LAZY_INSTALL_TARGET`, installs target the active Hermes venv;
- with that variable, pip/uv receives `--target <dir>`, and bootstrap appends the
  durable directory to `sys.path` behind core site-packages;
- there is no automatic `$HERMES_HOME` dependency directory merely because a
  profile exists; an external target must be configured explicitly;
- `security.allow_lazy_installs: false` is the user-facing absolute gate for
  both venv and durable-target modes.

Never manually install into a Hermes installation declared read-only. A runtime
lazy-install path that would write there is a security finding, not permission
to reproduce that write manually. Prefer disabling the triggering feature while
an external durable target or command backend is designed.

## Pitfalls

- Calling `_get_provider()` as a read-only probe can trigger a package install.
- A configured `stt.<provider>` subsection is not proof that provider is selected.
- “Local is first in autodetection” is not the same as “audio cannot leave the
  machine.”
- A per-provider empty language does not necessarily neutralize a non-empty
  global language because resolution commonly selects the first non-empty value.
- Do not report a backend as observed unless a real runtime log or safely
  exercised transcription proves it.
- Do not equate persisted `stt.enabled: false` with a live gateway change when
  configuration is cached at process startup.
- Do not describe the disabled-STT path as leak-free until agent-visible media
  placeholders have been checked for absolute paths.
