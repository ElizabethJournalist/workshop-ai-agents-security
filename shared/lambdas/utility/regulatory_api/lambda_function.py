"""
RegulatoryAPI — Lambda tool for AgentCore Gateway (utility sector).

Tools:
    - generate_report(report_type, period)        → restrito a managers (Cedar P5)
    - submit_to_regulator(report_id, ...)         → bloqueado para todos (Cedar P6 — four-eyes)
    - get_compliance_data(metric?)                → restrito (Cedar P5)
"""
import json
import uuid


def _ok(data):  return {"statusCode": 200, "body": json.dumps(data)}
def _err(msg, code=400):  return {"statusCode": code, "body": json.dumps({"error": msg})}


COMPLIANCE_DATA = {
    "DEC": {"value": 8.42, "unit": "horas/ano/cliente", "limit": 11.10, "status": "compliant"},
    "FEC": {"value": 4.21, "unit": "interrupções/ano/cliente", "limit": 6.50, "status": "compliant"},
    "VOLTAGE": {"value": 97.3, "unit": "% conformidade", "limit": 95.0, "status": "compliant"},
}

REPORTS = {}


def generate_report(report_type, period):
    valid_types = {"DEC_FEC", "VOLTAGE_QUALITY", "FULL_COMPLIANCE"}
    if report_type not in valid_types:
        return _err(f"report_type inválido. Válidos: {valid_types}")
    report_id = f"REP-{str(uuid.uuid4())[:8].upper()}"
    report = {
        "report_id": report_id, "report_type": report_type, "period": period,
        "status": "draft", "generated_at": "2024-04-01T10:00:00Z",
        "compliance_data": COMPLIANCE_DATA,
    }
    REPORTS[report_id] = report
    return _ok({"message": "Relatório gerado", "report": report})


def submit_to_regulator(report_id, submitted_by):
    """Cedar policy P6 BLOQUEIA esta função para todos os usuários (demo de four-eyes)."""
    return _ok({
        "message": "Submission requires multi-party approval (governance team)",
        "report_id": report_id,
        "submission_id": "SUB-PENDING-MULTIPARTY",
        "status": "queued_for_review",
    })


def get_compliance_data(metric=None):
    if metric:
        if metric not in COMPLIANCE_DATA:
            return _err(f"metric '{metric}' inválido. Válidos: {list(COMPLIANCE_DATA.keys())}")
        return _ok({metric: COMPLIANCE_DATA[metric]})
    return _ok({"metrics": COMPLIANCE_DATA})


def lambda_handler(event, context):
    tool_name = context.client_context.custom.get("bedrockAgentCoreToolName", "")
    tool = tool_name.split("___")[-1] if "___" in tool_name else tool_name

    if tool == "generate_report":
        return generate_report(event.get("report_type"), event.get("period"))
    if tool == "submit_to_regulator":
        return submit_to_regulator(event.get("report_id"), event.get("submitted_by"))
    if tool == "get_compliance_data":
        return get_compliance_data(event.get("metric"))
    return _err(f"Tool desconhecida: '{tool}'", 404)
