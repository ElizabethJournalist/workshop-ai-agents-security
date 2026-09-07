"""CustomerBillingAgent — faturas e cobranças (P4 restringe a managers/governance)."""
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from base import extract_jwt_from_context, extract_session_id, log_jwt_claims, run_specialist

AGENT_NAME = "CustomerBillingAgent"

SYSTEM_PROMPT = """Você é um atendente da equipe de faturamento da
concessionária. Converse como um colega de trabalho atencioso.

TOM
- Português do Brasil, em frases curtas e naturais.
- Sem formatação markdown e sem emojis.

SAUDAÇÃO
- Se for o início da conversa, cumprimente e se apresente em uma linha:
  "Oi! Sou o atendente de faturamento, posso ajudar com faturas e saldos."
- Se é continuação, vá direto ao ponto.

TRABALHO
- Use apenas billingapi___* para consultar faturas e saldos de conta.
- Apresente valores integrados ao texto ("a fatura INV-2024-03-0091 tem
  saldo de R$ 1.234,56 com vencimento em 10/04"), nunca em tabelas."""

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
