"""
05-AgentCore-Runtime/utils.py — helpers de AgentCore Runtime.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.parse import quote

import boto3
import requests
from botocore.exceptions import ClientError

WORKSHOP_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_PYTHON = "PYTHON_3_11"


# ─────────────────────────────────────────────────────────────────────────────
# S3
# ─────────────────────────────────────────────────────────────────────────────

def ensure_s3_bucket(bucket: str, *, region: str) -> None:
    s3 = boto3.client("s3", region_name=region)
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"  ~ Bucket existe: {bucket}")
    except ClientError:
        kwargs = {"Bucket": bucket}
        if region != "us-east-1":
            kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
        s3.create_bucket(**kwargs)
        print(f"  ✓ Bucket criado: {bucket}")


# ─────────────────────────────────────────────────────────────────────────────
# Packaging
# ─────────────────────────────────────────────────────────────────────────────

def build_zip(agent_py: str | Path, req_file: str | Path, *, sector: str = "utility") -> bytes:
    """
    Instala dependências arm64 Linux e empacota em ZIP.

    O AgentCore Runtime executa em arm64 Linux (Python 3.11), portanto as
    dependências precisam ser instaladas com wheels compatíveis com essa plataforma.
    """
    agent_path = Path(agent_py)
    req_path = Path(req_file)

    with tempfile.TemporaryDirectory() as tmpdir:
        pkg_dir = Path(tmpdir) / "package"
        pkg_dir.mkdir()

        pip_python = os.environ.get("WORKSHOP_PYTHON", sys.executable)
        if req_path.exists():
            subprocess.check_call(
                [pip_python, "-m", "pip", "install",
                 "-r", str(req_path),
                 "-t", str(pkg_dir),
                 "--platform", "manylinux2014_aarch64",
                 "--python-version", "3.11",
                 "--only-binary", ":all:",
                 "--upgrade", "-q"],
            )

        shutil.copy(agent_path, pkg_dir / agent_path.name)

        base_py = agent_path.parent / "base.py"
        if base_py.exists():
            shutil.copy(base_py, pkg_dir / "base.py")

        if agent_path.name == "smart_agent.py":
            prompt_md = WORKSHOP_ROOT / "shared" / "prompts" / sector / "smart_agent.md"
            if prompt_md.exists():
                shutil.copy(prompt_md, pkg_dir / "smart_agent.md")

        zip_path = Path(tmpdir) / f"{agent_path.stem}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in pkg_dir.rglob("*"):
                if f.is_file() and "__pycache__" not in f.parts and not f.name.endswith(".pyc"):
                    zf.write(f, f.relative_to(pkg_dir))

        size_mb = zip_path.stat().st_size / 1024 / 1024
        print(f"  ✓ ZIP: {zip_path.name} ({size_mb:.1f} MB)")
        return zip_path.read_bytes()


# ─────────────────────────────────────────────────────────────────────────────
# Deploy
# ─────────────────────────────────────────────────────────────────────────────

def find_existing_runtime(name: str, *, region: str) -> str | None:
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    paginator = client.get_paginator("list_agent_runtimes")
    for page in paginator.paginate():
        for r in page.get("agentRuntimes", []):
            if r.get("agentRuntimeName") == name:
                return r["agentRuntimeId"]
    return None


def deploy_runtime(
    name: str,
    agent_py: str | Path,
    req_file: str | Path,
    role_arn: str,
    s3_bucket: str,
    *,
    sector: str = "utility",
    cognito_pool_id: str,
    cognito_client_id: str,
    region: str,
    env_vars: dict[str, str] | None = None,
    entry_point: list[str] | None = None,
) -> dict:
    """Deploy idempotente de um agente como AgentCore Runtime."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    s3 = boto3.client("s3", region_name=region)
    agent_path = Path(agent_py)

    zip_bytes = build_zip(agent_path, req_file, sector=sector)
    s3_key = f"workshop-agents/{name}/{agent_path.stem}.zip"
    s3.upload_fileobj(io.BytesIO(zip_bytes), s3_bucket, s3_key)
    print(f"  ✓ Upload: s3://{s3_bucket}/{s3_key}")

    if entry_point is None:
        entry_point = ["opentelemetry-instrument", agent_path.name]

    artifact = {
        "codeConfiguration": {
            "code": {"s3": {"bucket": s3_bucket, "prefix": s3_key}},
            "entryPoint": entry_point,
            "runtime": RUNTIME_PYTHON,
        }
    }

    discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{cognito_pool_id}/.well-known/openid-configuration"
    authorizer_cfg = {
        "customJWTAuthorizer": {
            "discoveryUrl": discovery_url,
            "allowedClients": [cognito_client_id],
            "allowedScopes": ["aws.cognito.signin.user.admin"],
            "customClaims": [{
                "inboundTokenClaimName": "token_use",
                "inboundTokenClaimValueType": "STRING",
                "authorizingClaimMatchValue": {
                    "claimMatchValue": {"matchValueString": "access"},
                    "claimMatchOperator": "EQUALS",
                },
            }],
        }
    }

    request_header_cfg = {
        "requestHeaderAllowlist": ["Authorization", "traceparent", "tracestate", "baggage"]
    }

    existing_id = find_existing_runtime(name, region=region)
    if existing_id:
        print(f"  ~ Runtime existe ({existing_id}), atualizando...")
        client.update_agent_runtime(
            agentRuntimeId=existing_id,
            agentRuntimeArtifact=artifact,
            environmentVariables=env_vars or {},
            roleArn=role_arn,
            networkConfiguration={"networkMode": "PUBLIC"},
            authorizerConfiguration=authorizer_cfg,
            requestHeaderConfiguration=request_header_cfg,
        )
        resp = client.get_agent_runtime(agentRuntimeId=existing_id)
        return {"runtime_id": existing_id, "runtime_arn": resp.get("agentRuntimeArn", "")}

    resp = client.create_agent_runtime(
        agentRuntimeName=name,
        description=f"Workshop AI Agents Security — {name}",
        agentRuntimeArtifact=artifact,
        roleArn=role_arn,
        networkConfiguration={"networkMode": "PUBLIC"},
        authorizerConfiguration=authorizer_cfg,
        requestHeaderConfiguration=request_header_cfg,
        environmentVariables=env_vars or {},
        tags={"project": "workshop-ai-agents-security", "sector": sector},
    )
    print(f"  ✓ Runtime criado: {name} ({resp['agentRuntimeId']})")
    return {"runtime_id": resp["agentRuntimeId"], "runtime_arn": resp["agentRuntimeArn"]}


def wait_runtime_ready(runtime_id: str, *, region: str, timeout: int = 300) -> str:
    """Aguarda o Runtime atingir status READY."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    start = time.time()
    while time.time() - start < timeout:
        resp = client.get_agent_runtime(agentRuntimeId=runtime_id)
        status = resp.get("status", "")
        elapsed = int(time.time() - start)
        print(f"  {runtime_id[:24]}... status={status} ({elapsed}s)")
        if status == "READY":
            return status
        if "FAILED" in status:
            raise RuntimeError(f"Runtime {runtime_id} FAILED: {resp.get('statusReasons', '')}")
        time.sleep(10)
    raise TimeoutError(f"Runtime não ficou READY em {timeout}s")


def enable_traces_delivery(runtime_id: str, runtime_arn: str, *, region: str) -> None:
    """Configura entrega de traces OTEL ao CloudWatch Transaction Search."""
    logs = boto3.client("logs", region_name=region)
    xray = boto3.client("xray", region_name=region)

    # Ensure CloudWatch Logs is enabled as trace segment destination (required for X-Ray delivery)
    try:
        xray.update_trace_segment_destination(Destination="CloudWatchLogs")
        print(f"  ✓ Trace segment destination: CloudWatch Logs enabled")
    except Exception as e:
        # May already be configured or not available — proceed anyway
        print(f"  ~ Trace segment destination: {e}")

    source_name = f"{runtime_id}-traces-source"
    dest_name = f"{runtime_id}-traces-destination"
    try:
        logs.put_delivery_source(name=source_name, logType="TRACES", resourceArn=runtime_arn)
    except logs.exceptions.ResourceAlreadyExistsException:
        pass
    try:
        resp = logs.put_delivery_destination(name=dest_name, deliveryDestinationType="XRAY")
        dest_arn = resp["deliveryDestination"]["arn"]
    except logs.exceptions.ResourceAlreadyExistsException:
        dest_arn = logs.get_delivery_destination(name=dest_name)["deliveryDestination"]["arn"]
    try:
        logs.create_delivery(deliverySourceName=source_name, deliveryDestinationArn=dest_arn)
        print(f"  ✓ Traces: {runtime_id} → aws/spans")
    except logs.exceptions.ConflictException:
        print(f"  ~ Traces já configurado: {runtime_id}")


# ─────────────────────────────────────────────────────────────────────────────
# Invoke (HTTPS + SSE)
# ─────────────────────────────────────────────────────────────────────────────

def invoke_runtime(
    runtime_arn: str,
    prompt: str,
    bearer_token: str,
    *,
    session_id: str | None = None,
    region: str,
    timeout: int = 180,
) -> str:
    """Invoca um Runtime via HTTPS POST com streaming SSE."""
    import uuid
    if not session_id:
        session_id = f"workshop-{uuid.uuid4()}"
    if len(session_id) < 33:
        session_id = (session_id + "0" * 40)[:64]

    url = (
        f"https://bedrock-agentcore.{region}.amazonaws.com"
        f"/runtimes/{quote(runtime_arn, safe='')}/invocations?qualifier=DEFAULT"
    )
    resp = requests.post(
        url,
        json={"prompt": prompt},
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        },
        timeout=timeout,
        stream=True,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")

    full_text = []
    for line in resp.iter_lines():
        if not line:
            continue
        line_str = line.decode("utf-8")
        if line_str.startswith("data:"):
            try:
                event = json.loads(line_str[5:].strip())
                if event.get("type") == "delta":
                    full_text.append(event.get("text", ""))
            except json.JSONDecodeError:
                pass
    return "".join(full_text)


def cleanup_runtime(runtime_id: str, *, region: str) -> bool:
    """Remove um Runtime. Idempotente."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    try:
        client.delete_agent_runtime(agentRuntimeId=runtime_id)
        print(f"  ✓ Runtime deletado: {runtime_id}")
        return True
    except ClientError as e:
        if "ResourceNotFoundException" in type(e).__name__:
            print(f"  ~ Runtime não existe: {runtime_id}")
            return False
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Agentes do setor utility
# Nomes no formato workshop-<NomeDoAgente> para isolamento de recursos.
# ─────────────────────────────────────────────────────────────────────────────

UTILITY_AGENTS = [
    # (runtime_name, agent_file, config_env_key, entry_point)
    ("workshop_SmartAgent",            "smart_agent.py",        "RUNTIME_SMART_AGENT_ARN",       ["opentelemetry-instrument", "smart_agent.py"]),
    ("workshop_GridMonitorAgent",      "grid_monitor_agent.py", "RUNTIME_GRID_AGENT_ARN",        ["opentelemetry-instrument", "grid_monitor_agent.py"]),
    ("workshop_MaintenanceAgent",      "maintenance_agent.py",  "RUNTIME_MAINTENANCE_AGENT_ARN", ["opentelemetry-instrument", "maintenance_agent.py"]),
    ("workshop_ContractAgent",         "contract_agent.py",     "RUNTIME_CONTRACT_AGENT_ARN",    ["opentelemetry-instrument", "contract_agent.py"]),
    ("workshop_CustomerBillingAgent",  "billing_agent.py",      "RUNTIME_BILLING_AGENT_ARN",     ["opentelemetry-instrument", "billing_agent.py"]),
    ("workshop_RegulatoryReportAgent", "regulatory_agent.py",   "RUNTIME_REGULATORY_AGENT_ARN",  ["opentelemetry-instrument", "regulatory_agent.py"]),
]
