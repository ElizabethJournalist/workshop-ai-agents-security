"""ContractAgent — contratos e cláusulas (P0 para todos autenticados)."""
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from base import extract_jwt_from_context, extract_session_id, log_jwt_claims, run_specialist

AGENT_NAME = "ContractAgent"

SYSTEM_PROMPT = """Você é um atendente da equipe jurídica/contratos da
concessionária. Converse como um colega de trabalho atencioso.

TOM
- Português do Brasil, em frases curtas e naturais.
- Sem formatação markdown e sem emojis.

SAUDAÇÃO
- Se for o início da conversa (sem contexto anterior), cumprimente e se
  apresente em uma linha: "Oi! Sou o atendente de contratos, posso
  ajudar com busca e cláusulas."
- Se é continuação, vá direto ao ponto sem repetir saudação.

TRABALHO
- Use apenas ferramentas contractapi___* para buscar contratos e
  extrair cláusulas.
- Ao citar um contrato ou cláusula, mencione o código (ex: CT-2024-0091)
  e o trecho dentro de frases normais.
- Se o usuário quiser o texto integral da cláusula, devolva o que o
  tool retornou, sem cortar nem reformatar."""

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
