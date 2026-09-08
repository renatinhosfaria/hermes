#!/usr/bin/env python3
# pyright: reportMissingImports=false
# Hermes imports are resolved from the installed source through sys.path below.
"""Verify Dev learning stores; --live exercises a controlled post-turn review.

Uses installed Hermes read-only. The live probe prepares only its temporary
agent's counters at the configured thresholds; it does not change config,
permissions or the live gateway. Real review writes remain subject to native
policy. No model output or credential values are printed.
"""
import argparse
import json
import logging
import os
from pathlib import Path
import sys
import threading
import uuid

HOME = Path('/root/.hermes/profiles/dev')
SOURCE = Path('/usr/local/lib/hermes-agent')
sys.dont_write_bytecode = True
sys.path.insert(0, str(SOURCE))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    if Path(os.environ.get('HERMES_HOME', '')).resolve() != HOME:
        raise RuntimeError('Run with HERMES_HOME=/root/.hermes/profiles/dev')
    os.chdir(HOME)
    from hermes_cli.config import load_config_readonly
    from agent.background_review import load_background_review_settings
    from tools.memory_tool import load_on_disk_store
    from tools.skills_tool import skill_view

    cfg = load_config_readonly()
    mem = cfg['memory']
    skills = cfg['skills']
    assert mem['memory_enabled'] is True
    assert mem['write_approval'] is False
    assert skills['write_approval'] is False
    assert skills['guard_agent_created'] is True
    assert int(mem['nudge_interval']) > 0
    assert int(skills['creation_nudge_interval']) > 0
    enabled, review_cfg = load_background_review_settings()
    assert enabled
    assert not review_cfg.get('extra_tools'), 'Unexpected extra review tools'
    store = load_on_disk_store()
    assert 'revisão automática em segundo plano' in store.format_for_system_prompt('memory')
    result = skill_view('hermes-runtime-verification', file_path='references/memory-and-skill-learning.md')
    if isinstance(result, str):
        result = json.loads(result)
    assert result['success'] and '## Guardas e prova de execução' in result['content']
    print('PASS: persisted config, native memory reload and native skill reload', flush=True)
    if not args.live:
        return

    from hermes_cli.runtime_provider import resolve_runtime_provider
    from run_agent import AIAgent
    runtime = resolve_runtime_provider(requested=cfg['model']['provider'], target_model=cfg['model']['default'])
    agent = AIAgent(
        model=runtime.get('model') or cfg['model']['default'],
        provider=runtime['provider'], api_key=runtime.get('api_key'),
        base_url=runtime.get('base_url'), api_mode=runtime.get('api_mode'),
        credential_pool=runtime.get('credential_pool'),
        enabled_toolsets=cfg['platform_toolsets']['telegram'],
        platform='telegram', session_id='dev-learning-probe-' + uuid.uuid4().hex,
        quiet_mode=True, max_iterations=12, run_budget_seconds=240,
        skip_background_review=False, load_soul_identity=True,
    )
    assert {'memory', 'skill_manage', 'skill_view'} <= set(agent.valid_tool_names)
    assert agent._memory_nudge_interval == int(mem['nudge_interval'])
    assert agent._skill_nudge_interval == int(skills['creation_nudge_interval'])
    # Controlled threshold setup, not evidence of natural production counting.
    agent._iters_since_skill = agent._skill_nudge_interval
    agent._turns_since_memory = agent._memory_nudge_interval - 1
    done = threading.Event()
    completions = []
    failures = []

    class Capture(logging.Handler):
        def emit(self, record):
            text = record.getMessage()
            if text.startswith('Background review complete:'):
                completions.append(text)
                done.set()
            elif text.startswith('Background memory/skill review failed:'):
                failures.append(True)
                done.set()

    logger = logging.getLogger('agent.background_review')
    old_level = logger.level
    handler = Capture()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        result = agent.run_conversation(
            'Teste controlado do aprendizado do próprio Dev. Carregue fama-dev-runtime, '
            'depois hermes-runtime-verification e sua referência '
            'references/memory-and-skill-learning.md. Explique brevemente a diferença '
            'entre result=none, revisão executada e skill persistida, e entre escrita '
            'em memória e snapshot congelado. Somente leitura neste turno: não faça '
            'commits, não escreva configuração, não reinicie serviços nem execute '
            'terminal. Esta verificação já pertence à tarefa do operador; não crie '
            'conteúdo artificial nem duplique skills ou memórias apenas para o teste.'
        )
        assert result.get('final_response'), 'No foreground response'
        assert done.wait(300), 'No background review completion within 300 seconds'
        assert not failures, 'Native review failed; inspect local logs'
        assert completions and 'result=error' not in completions[-1]
        print('PASS: fresh agent + real inference + native automatic post-turn fork (controlled counters)', flush=True)
        print(completions[-1], flush=True)
    finally:
        run = getattr(agent, '_background_review_run', None)
        if run is not None:
            run.request_done.wait(10)
        logger.removeHandler(handler)
        logger.setLevel(old_level)
        agent.close()


if __name__ == '__main__':
    main()
