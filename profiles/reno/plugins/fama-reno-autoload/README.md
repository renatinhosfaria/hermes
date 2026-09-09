# Carregamento automático do Reno

Plugin exclusivo deste profile. O hook nativo `pre_llm_call` lê `SKILL.md` e as
quatro referências de `skills/business-operations/fama-reno-runtime` antes de
cada turno: CLI, workers Kanban, Telegram e demais canais que usem `AIAgent`.
O Hermes acrescenta o pacote à mensagem enviada ao modelo e o mantém nas
chamadas de ferramentas daquele turno. Não depende de decisão do modelo.
O procedimento comercial continua restrito às tarefas de atendimento.

Na versão instalada, o hook de contexto só é aplicado a mensagens de texto.
Para mensagens com imagens ou outras partes multimodais, o middleware nativo
`llm_request` acrescenta uma parte textual completa antes do envio ao modelo,
preservando imagens, histórico e resultados de ferramentas.

Os arquivos canônicos são relidos em cada turno, sem cópias ou cache no plugin.
O scanner de contexto do Hermes verifica cada documento antes da inclusão.
Se um arquivo faltar, estiver vazio ou for bloqueado, o pacote é substituído
por um aviso de erro; o fallback de leitura está no SOUL.md e na skill.
Este hook fornece contexto, não é um bloqueio de ferramentas.

O profile mantém `fama-reno-autoload` em `plugins.enabled` e
`hooks.output_spill.enabled: false`, pois o limite padrão de 10.000 caracteres
reduziria o pacote a uma prévia. Esse ajuste vale para os hooks deste profile.
O conteúdo completo aumenta o contexto de entrada em cada turno. O Hermes
preserva as cópias textuais anteriores em `api_content` para replay do histórico;
em sessões longas isso antecipa a compactação. A versão recebida no turno atual
é a referência vigente, conforme o SOUL.md.

Alterar os documentos tem efeito no próximo turno. Alterar o código do plugin
ou habilitá-lo exige novo processo CLI/worker e reinício de
`hermes-gateway-reno.service` para o gateway já aberto. Processos iniciados com
plugins desabilitados não oferecem este carregamento.

## Verificação

```bash
PYTHONPATH=/usr/local/lib/hermes-agent /usr/local/lib/hermes-agent/venv/bin/python -B /root/.hermes/profiles/reno/plugins/fama-reno-autoload/tests/test_autoload.py
hermes -p reno plugins doctor /root/.hermes/profiles/reno/plugins/fama-reno-autoload --ci
hermes -p reno config check
```

O scanner `agent.prompt_builder._scan_context_content` é uma API interna da
versão instalada; execute os testes de compatibilidade após atualizar o Hermes.
A lista `DOCUMENTS` deve acompanhar mudanças na lista de referências obrigatórias.

Documentação oficial:
- [Plugins: contexto antes de cada turno](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/#pre_llm_call-context-injection)
- [Hooks](https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks#pre_llm_call)
