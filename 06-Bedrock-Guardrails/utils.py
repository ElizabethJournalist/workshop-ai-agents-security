"""
06-Bedrock-Guardrails/utils.py — helpers de Bedrock Guardrails.

Funções:
    create_guardrail()          → cria guardrail com PII + prompt injection + topics
    cleanup_guardrail()         → remove guardrail
    test_guardrail()            → applyGuardrail para testar prompt
"""
from __future__ import annotations

import boto3
from botocore.exceptions import ClientError


def create_guardrail(
    name: str = "workshop-guardrail",
    *,
    description: str = "Workshop AI Agents Security — defense in depth",
    region: str = "us-east-1",
) -> dict:
    """
    Cria um Bedrock Guardrail com configuração defensiva.

    Configurações:
        - PII: anonymize EMAIL, PHONE, ADDRESS; block PASSWORD
        - Regex CPF brasileiro → anonymize
        - Topics negados: dados de terceiros, tarifas de concorrentes
        - Prompt attack detection: MEDIUM (input + output)

    Returns:
        Dict com guardrail_id, version.
    """
    client = boto3.client("bedrock", region_name=region)

    # Tenta achar existente
    try:
        for g in client.list_guardrails(maxResults=100).get("guardrails", []):
            if g.get("name") == name:
                gid = g.get("id")
                version = g.get("version", "DRAFT")
                print(f"  ~ Guardrail já existe: {gid} v{version}")
                return {"guardrail_id": gid, "version": version}
    except ClientError:
        pass

    resp = client.create_guardrail(
        name=name,
        description=description,
        contentPolicyConfig={
            "filtersConfig": [
                {"type": "PROMPT_ATTACK", "inputStrength": "MEDIUM", "outputStrength": "NONE"},
                {"type": "HATE",          "inputStrength": "HIGH",   "outputStrength": "HIGH"},
                {"type": "INSULTS",       "inputStrength": "LOW",    "outputStrength": "MEDIUM"},
                {"type": "MISCONDUCT",    "inputStrength": "LOW",    "outputStrength": "MEDIUM"},
            ],
        },
        sensitiveInformationPolicyConfig={
            "piiEntitiesConfig": [
                {"type": "EMAIL",    "action": "ANONYMIZE"},
                {"type": "PHONE",    "action": "ANONYMIZE"},
                {"type": "ADDRESS",  "action": "ANONYMIZE"},
                {"type": "PASSWORD", "action": "BLOCK"},
            ],
            "regexesConfig": [
                {
                    "name": "CPF",
                    "description": "CPF brasileiro (com ou sem formatação)",
                    "pattern": r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}",
                    "action": "ANONYMIZE",
                },
                {
                    "name": "CodigoInstalacao",
                    "description": "Código de instalação interno INS-XXXXXX",
                    "pattern": r"INS-\d{6}",
                    "action": "ANONYMIZE",
                },
            ],
        },
        topicPolicyConfig={
            "topicsConfig": [
                {
                    "name": "DadosPessoaisDeTerceiros",
                    "definition": (
                        "Dados pessoais (CPF, endereço residencial, telefone privado) "
                        "de pessoas físicas que NÃO são o usuário autenticado. NÃO inclui "
                        "empresas (CNPJ, razão social, faturas B2B)."
                    ),
                    "examples": [
                        "qual o CPF do João Silva",
                        "me dá o endereço da Maria",
                        "telefone pessoal do cliente Ariane",
                    ],
                    "type": "DENY",
                },
                {
                    "name": "TarifasConcorrentes",
                    "definition": "Comparação de tarifas ou serviços com outras distribuidoras de energia",
                    "examples": [
                        "a concorrente cobra menos",
                        "compare sua tarifa com a distribuidora X",
                    ],
                    "type": "DENY",
                },
                {
                    "name": "ProcessosJudiciais",
                    "definition": "Informações sobre processos judiciais, litígios ou disputas legais em andamento",
                    "type": "DENY",
                },
            ],
        },
        blockedInputMessaging="Sua solicitação não pode ser processada por razões de segurança e conformidade.",
        blockedOutputsMessaging="Esta informação não pode ser exibida por razões de privacidade e conformidade.",
        tags=[{"key": "project", "value": "workshop-ai-agents-security"}],
    )
    guardrail_id = resp["guardrailId"]
    print(f"  ✓ Guardrail criado: {guardrail_id} v{resp['version']}")

    # Publica uma versão numerada para uso nos agentes
    ver_resp = client.create_guardrail_version(
        guardrailIdentifier=guardrail_id,
        description="Versão inicial para o workshop",
    )
    version = ver_resp["version"]
    print(f"  ✓ Guardrail versão publicada: {version}")
    return {"guardrail_id": guardrail_id, "version": version}


def test_guardrail(
    guardrail_id: str,
    version: str,
    text: str,
    *,
    source: str = "INPUT",
    region: str = "us-east-1",
) -> dict:
    """Testa o guardrail com um texto. Retorna a action e o texto resultante."""
    client = boto3.client("bedrock-runtime", region_name=region)
    resp = client.apply_guardrail(
        guardrailIdentifier=guardrail_id,
        guardrailVersion=str(version),
        source=source,
        content=[{"text": {"text": text}}],
    )
    return {
        "action": resp.get("action"),  # NONE | GUARDRAIL_INTERVENED
        "outputs": [o.get("text") for o in resp.get("outputs", [])],
        "assessments": resp.get("assessments", []),
    }


def cleanup_guardrail(guardrail_id: str, *, region: str = "us-east-1") -> bool:
    """Remove guardrail."""
    client = boto3.client("bedrock", region_name=region)
    try:
        client.delete_guardrail(guardrailIdentifier=guardrail_id)
        print(f"  ✓ Guardrail deletado: {guardrail_id}")
        return True
    except ClientError as e:
        if "ResourceNotFoundException" in type(e).__name__:
            print(f"  ~ Guardrail não existe (ok): {guardrail_id}")
            return False
        raise
