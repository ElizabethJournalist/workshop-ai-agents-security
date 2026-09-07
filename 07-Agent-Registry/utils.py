"""
07-Agent-Registry/utils.py — helpers de AgentCore Registry.

Fluxo de governança:
    create_registry()        → cria o catálogo
    register_agent()         → cria um record CUSTOM com metadados de risco (status DRAFT)
    submit_for_approval()    → DRAFT → PENDING_APPROVAL
    approve_record()         → PENDING_APPROVAL → APPROVED (simula VP de Governança)
    list_registry_records()  → lista records (opcionalmente por status)
    cleanup_registry()       → remove records + registry

Status válidos: DRAFT, PENDING_APPROVAL, APPROVED, REJECTED, DEPRECATED.
"""
from __future__ import annotations

import json
import time

import boto3
from botocore.exceptions import ClientError


def _wait_for_status(get_fn, target_statuses, label, *, timeout: int = 120) -> str:
    start = time.time()
    while time.time() - start < timeout:
        status = get_fn().get("status", "")
        if status in target_statuses:
            return status
        if "FAILED" in status or "ERROR" in status:
            raise RuntimeError(f"{label} falhou: {status}")
        time.sleep(4)
    raise TimeoutError(f"{label} não atingiu {target_statuses} em {timeout}s")


def create_registry(
    name: str = "workshop-registry",
    *,
    description: str = "Workshop AI Agents Security — catálogo de agentes com workflow de aprovação",
    region: str = "us-east-1",
) -> str:
    """Cria o registry e aguarda READY. Retorna o registry_id."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)

    # Idempotência: procura por nome nos registries existentes
    try:
        for r in client.list_registries(maxResults=50).get("items", []):
            if r.get("name") == name:
                rid = r.get("registryId") or r.get("registryArn", "").split("/")[-1]
                print(f"  ~ Registry já existe: {rid}")
                return rid
    except ClientError:
        pass

    resp = client.create_registry(name=name, description=description)
    registry_id = resp["registryArn"].split("/")[-1]
    print(f"  ✓ Registry criado: {registry_id} (aguardando READY...)")
    _wait_for_status(
        lambda: client.get_registry(registryId=registry_id),
        ["READY", "ACTIVE"],
        "Registry",
    )
    print(f"  ✓ Registry READY")
    return registry_id


def register_agent(
    registry_id: str,
    agent: dict,
    *,
    region: str = "us-east-1",
) -> str | None:
    """
    Cria um record CUSTOM com os metadados de governança do agente (status DRAFT).

    `agent` deve conter: name, description, risk_level, team, tools, policies,
    owasp_controls.

    Retorna record_id (ou None se já existir).
    """
    client = boto3.client("bedrock-agentcore-control", region_name=region)

    # Pula se já existe
    try:
        resp = client.list_registry_records(registryId=registry_id, maxResults=100)
        for r in (resp.get("registryRecords") or resp.get("items", [])):
            if r.get("name") == agent["name"]:
                print(f"  ~ Record já existe: {agent['name']}")
                return None
    except ClientError:
        pass

    content = json.dumps({
        "name": agent["name"],
        "description": agent["description"],
        "risk_level": agent["risk_level"],
        "team": agent["team"],
        "tools": agent.get("tools", []),
        "policies": agent.get("policies", []),
        "owasp_controls": agent.get("owasp_controls", ""),
        "stage": "production",
    })

    resp = client.create_registry_record(
        registryId=registry_id,
        name=agent["name"],
        descriptorType="CUSTOM",
        descriptors={"custom": {"inlineContent": content}},
        recordVersion="1.0",
    )
    record_id = resp["recordArn"].split("/")[-1]
    print(f"  ✓ Record criado: {agent['name']} (risk={agent['risk_level']}) {record_id}")
    _wait_for_status(
        lambda: client.get_registry_record(registryId=registry_id, recordId=record_id),
        ["DRAFT"],
        f"Record:{agent['name']}",
    )
    return record_id


def submit_for_approval(registry_id: str, record_id: str, *, region: str = "us-east-1") -> None:
    """DRAFT → PENDING_APPROVAL."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    client.submit_registry_record_for_approval(registryId=registry_id, recordId=record_id)
    print(f"  ✓ Submetido para aprovação: {record_id}")


def approve_record(
    registry_id: str,
    record_id: str,
    *,
    reason: str = "Revisado e aprovado pela governança. Políticas Cedar e Guardrail verificados.",
    region: str = "us-east-1",
) -> None:
    """PENDING_APPROVAL → APPROVED (simula VP de Governança)."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    client.update_registry_record_status(
        registryId=registry_id,
        recordId=record_id,
        status="APPROVED",
        statusReason=reason,
    )
    print(f"  ✓ Aprovado: {record_id}")


def list_registry_records(
    registry_id: str,
    *,
    status: str | None = None,
    region: str = "us-east-1",
) -> list[dict]:
    """Lista records do registry. Opcionalmente filtra por status."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    kwargs = {"registryId": registry_id, "maxResults": 100}
    if status:
        kwargs["status"] = status
    resp = client.list_registry_records(**kwargs)
    return resp.get("registryRecords") or resp.get("items", [])


def cleanup_registry(registry_id: str, *, region: str = "us-east-1") -> bool:
    """Remove records + registry. Idempotente."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    try:
        for r in list_registry_records(registry_id, region=region):
            rid = r.get("recordId") or r.get("recordArn", "").split("/")[-1]
            try:
                client.delete_registry_record(registryId=registry_id, recordId=rid)
                print(f"  ✓ Record deletado: {rid}")
            except ClientError:
                pass
        client.delete_registry(registryId=registry_id)
        print(f"  ✓ Registry deletado: {registry_id}")
        return True
    except ClientError as e:
        if "ResourceNotFoundException" in type(e).__name__:
            return False
        raise


# Metadados de governança dos 5 specialists (setor utility)
UTILITY_AGENT_RECORDS = [
    {
        "name": "GridMonitorAgent",
        "description": "Monitoramento da rede elétrica. Consulta status da grid e alertas de falha por setor. Somente leitura de dados operacionais.",
        "risk_level": "MEDIUM",
        "team": "grid-operations",
        "tools": ["gridapi___get_grid_status", "gridapi___get_outage_alerts"],
        "policies": ["P1GridOperators"],
        "owasp_controls": "LLM08-mitigated-via-Cedar",
    },
    {
        "name": "MaintenanceAgent",
        "description": "Gestão de ordens de manutenção. Cria ordens e consulta histórico de ativos. Aprovação requer perfil de gestor (P2/P3).",
        "risk_level": "HIGH",
        "team": "maintenance",
        "tools": ["maintenanceapi___create_work_order", "maintenanceapi___approve_work_order", "maintenanceapi___get_asset_history"],
        "policies": ["P2ManagerApprove", "P3DenyOperatorApprove"],
        "owasp_controls": "LLM08-mitigated-via-Cedar,SoD-enforced",
    },
    {
        "name": "ContractAgent",
        "description": "Análise de contratos. Busca contratos e extrai cláusulas. Somente leitura da base de contratos.",
        "risk_level": "MEDIUM",
        "team": "legal",
        "tools": ["contractapi___search_contracts", "contractapi___extract_clause"],
        "policies": [],
        "owasp_controls": "LLM08-mitigated-via-Cedar",
    },
    {
        "name": "CustomerBillingAgent",
        "description": "Faturamento. Acessa faturas e histórico de consumo. Restrito a billing e governance (P4). PII mascarado via Guardrail.",
        "risk_level": "LOW",
        "team": "billing",
        "tools": ["billingapi___get_invoice", "billingapi___get_consumption_history"],
        "policies": ["P4BillingIsolation"],
        "owasp_controls": "LLM06-mitigated-via-Guardrail,LLM08-mitigated-via-Cedar",
    },
    {
        "name": "RegulatoryReportAgent",
        "description": "Relatórios regulatórios. Gera relatórios e consulta conformidade. NUNCA submete ao regulador (four-eyes via P6). Requer clearance executive (P5).",
        "risk_level": "HIGH",
        "team": "governance",
        "tools": ["regulatoryapi___generate_report", "regulatoryapi___get_compliance_data"],
        "policies": ["P5RegulatoryExecutive", "P6BlockSubmitRegulator"],
        "owasp_controls": "LLM08-mitigated-via-Cedar,four-eyes-principle",
    },
]
