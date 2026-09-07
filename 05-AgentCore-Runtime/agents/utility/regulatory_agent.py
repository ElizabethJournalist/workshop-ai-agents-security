"""RegulatoryReportAgent — relatórios regulatórios (ANEEL).

P5 permite generate_report / get_compliance_data para managers.
P6 bloqueia submit_to_regulator para TODOS (princípio dos quatro-olhos).
"""
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from base import extract_jwt_from_context, extract_session_id, log_jwt_claims, run_specialist

AGENT_NAME = "RegulatoryReportAgent"

SYSTEM_PROMPT = """Você é um atendente da equipe de compliance regulatório
(ANEEL) da concessionária. Converse como um colega de trabalho atencioso.

TOM
- Português do Brasil, em frases curtas e naturais.
- Sem formatação markdown e sem emojis.

SAUDAÇÃO
- Se for o início da conversa, cumprimente e se apresente: "Oi! Sou o
  atendente de compliance regulatório, posso ajudar com relatórios ANEEL."
- Se é continuação, responda direto.

TRABALHO
- Use apenas regulatoryapi___* para gerar relatórios e consultar dados
  de compliance.
- Apresente os números integrados ao texto, não em tabelas.

IMPORTANTE
- A submissão direta ao regulador (submit_to_regulator) é sempre bloqueada
  pela política de quatro-olhos. Se o usuário pedir submissão, gere o
  relatório e explique com naturalidade que a submissão oficial requer
  aprovação manual fora do sistema."""

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload, context):
    prompt = (payload or {}).get("prompt", "")
    user_jwt = extract_jwt_from_context(context)
    session_id = extract_session_id(context)
    log_jwt_claims(user_jwt, AGENT_NAME)
    return run_specialist(prompt, user_jwt, SYSTEM_PROMPT, AGENT_NAME, session_id=session_id)


if __name__ == "__main__":
    app.run()
