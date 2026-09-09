#!/usr/local/lib/hermes-agent/venv/bin/python
"""Verify profile learning with HERMES_HOME explicitly set to the profile home.

native: exercise real stores with unique temporary entries and remove them.
live: use the configured model and natural post-turn counters; the native review
may save a verified infrastructure lesson in this profile. No external tools or
messages, production business writes, fake model responses, or session DB writes.
recall: internal subprocess phase for independent persistence verification.
"""
import argparse,json,logging,os,subprocess,sys,threading,uuid
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,'/usr/local/lib/hermes-agent')
parser=argparse.ArgumentParser(); parser.add_argument('phase',choices=['native','recall','live']); parser.add_argument('--marker'); args=parser.parse_args()
home=Path(os.environ['HERMES_HOME']); os.chdir(home)
from hermes_cli.config import load_config_readonly
from tools.memory_tool import load_on_disk_store,memory_tool
from tools.skills_tool import skill_view
from tools.skill_manager_tool import skill_manage
from tools.skill_provenance import set_current_write_origin,reset_current_write_origin
from agent.background_review import load_background_review_settings
cfg=load_config_readonly()
def parsed(value): return json.loads(value) if isinstance(value,str) else value
def ok(value):
 result=parsed(value)
 assert result.get('success'),{k:v for k,v in result.items() if k in ('error','success','status')}
 assert not result.get('pending'), 'Write staged instead of persisted'
 return result
if args.phase=='recall':
 assert args.marker in load_on_disk_store().format_for_system_prompt('memory')
 result=ok(skill_view(args.marker))
 assert 'Verified independent reload.' in result['content']
 print(json.dumps({'independent_recall':True})); sys.exit(0)
from hermes_cli.tools_config import _get_platform_tools
from toolsets import resolve_multiple_toolsets
from model_tools import get_tool_definitions
required={'memory','skills_list','skill_view','skill_manage'}
surfaces={}
for platform in cfg['platform_toolsets']:
 enabled=_get_platform_tools(cfg,platform,include_default_mcp_servers=False)
 resolved=set(resolve_multiple_toolsets(list(enabled)))
 assert required<=resolved,(platform,required-resolved)
 surfaces[platform]=True
assert cfg['memory']['memory_enabled'] and cfg['memory']['user_profile_enabled']
assert cfg['memory']['write_approval'] is False and cfg['skills']['write_approval'] is False
assert cfg['memory']['nudge_interval']==1 and cfg['skills']['creation_nudge_interval']==1
assert load_background_review_settings()[0]
assert (home/'plugins/fama-learning-lifecycle/plugin.yaml').is_file()
assert 'fama-learning-lifecycle' in cfg['plugins']['enabled']
if args.phase=='native':
 marker='learning-probe-'+uuid.uuid4().hex[:12]
 store=load_on_disk_store(); made_skill=made_memory=False
 try:
  ok(memory_tool(action='add',target='memory',content=marker,store=store)); made_memory=True
  token=set_current_write_origin('background_review')
  try:
   ok(skill_manage(action='create',name=marker,content=f'---\nname: {marker}\ndescription: Temporary controlled learning validation.\n---\n# Controlled validation\n\nUse only during the operator learning validation.\nRead the saved result in an independent process.\n'))
   made_skill=True
   ok(skill_view(marker))
   ok(skill_manage(action='patch',name=marker,old_string='Read the saved result in an independent process.',new_string='Verified independent reload.'))
  finally: reset_current_write_origin(token)
  result=subprocess.run([sys.executable,__file__,'recall','--marker',marker],capture_output=True,text=True,env=os.environ)
  assert result.returncode==0,result.stderr[-800:]
  print(json.dumps({'profile':home.name,'surfaces':surfaces,'memory_write':True,'background_skill_create_patch':True,'independent_recall':True}),flush=True)
 finally:
  if made_memory: ok(memory_tool(action='remove',target='memory',old_text=marker,store=load_on_disk_store()))
  if made_skill: ok(skill_manage(action='delete',name=marker))
 sys.exit(0)
from hermes_cli.runtime_provider import resolve_runtime_provider
from run_agent import AIAgent
rt=resolve_runtime_provider(requested=cfg['model']['provider'],target_model=cfg['model']['default'])
events=[]
class Capture(logging.Handler):
 def emit(self,record):
  message=record.getMessage()
  if message.startswith(('Background review complete:','Background memory/skill review failed:','Learning CLI drain:')): events.append(message)
handler=Capture()
log=logging.getLogger('agent.background_review'); log.addHandler(handler); log.setLevel(logging.INFO)
agent=AIAgent(model=rt.get('model') or cfg['model']['default'],provider=rt['provider'],api_key=rt.get('api_key'),base_url=rt.get('base_url'),api_mode=rt.get('api_mode'),credential_pool=rt.get('credential_pool'),request_overrides=rt.get('request_overrides') or {},enabled_toolsets=['no_mcp','memory','skills'],platform='cli',load_soul_identity=True,skip_memory=False,skip_background_review=False,session_db=None,quiet_mode=True,max_iterations=8,run_budget_seconds=240,reasoning_config={'effort':cfg['agent']['reasoning_effort']},ephemeral_system_prompt='Validação administrativa autorizada da aprendizagem do próprio profile. Não é atendimento nem cartão. Use apenas memory e ferramentas de skills. Não envie mensagens, não use MCPs, não abra cartões. No primeiro plano apenas leia e explique. A revisão nativa pode salvar exclusivamente lições técnicas verificadas sobre a própria infraestrutura de aprendizagem, quando faltarem nas skills existentes. Preserve instruções de negócio; não crie logs ou conteúdo artificial para satisfazer um teste.')
agent._persist_disabled=True; agent._end_session_on_close=False; agent._skip_mcp_refresh=True
assert agent._memory_nudge_interval==1 and agent._skill_nudge_interval==1
assert required<=set(agent.valid_tool_names)
try:
 result=agent.run_conversation('Verificação autorizada do seu aprendizado: consulte skills_list e explique brevemente quando salvar memória versus skill. Evidências verificadas diretamente no código Hermes instalado e em testes desta manutenção: memory.nudge_interval conta turnos de usuário; skills.creation_nudge_interval conta iterações de ferramenta; ambos agora são 1 neste profile. O fork nativo só dispara após resposta final não interrompida e depende das ferramentas disponíveis. O encerramento one-shot do CLI não aguardava a thread daemon bg-review; um teste reproduziu perda da gravação ao sair. O plugin local fama-learning-lifecycle, pelo hook oficial on_session_finalize, agora aguarda as revisões somente no CLI por até 300 segundos antes do cleanup; canais gateway continuam assíncronos. Os testes de término, isolamento de canal e limite de espera passaram. Configuração habilitada sozinha não prova persistência; a validação nativa criou e alterou uma skill, gravou memória e recuperou ambas em processo independente neste profile, sem aprovação. Não grave no primeiro plano e não execute outros testes agora. Explique a lição técnica reutilizável; a revisão automática habitual fica responsável pela consolidação que julgar pertinente.')
 assert result.get('final_response'),'No model response'
 # Exercise the actual lifecycle entry point; do not call/prime the review trigger.
 from hermes_cli.lifecycle import finalize_session
 finalize_session(session_id=agent.session_id,platform='cli',reason='shutdown')
 assert any('Background review complete:' in e and 'result=error' not in e for e in events),events
 assert not any('review failed:' in e for e in events),events
 names=[c.get('function',{}).get('name') for m in agent._session_messages for c in m.get('tool_calls',[])]
 assert 'skills_list' in names,names
 assert not {'memory','skill_manage'}&set(names),names
 print(json.dumps({'profile':home.name,'real_model':agent.model,'foreground_calls':agent.session_api_calls,'automatic_review':events,'natural_counters':True,'foreground_tools':names},ensure_ascii=False),flush=True)
finally:
 agent.release_clients()
