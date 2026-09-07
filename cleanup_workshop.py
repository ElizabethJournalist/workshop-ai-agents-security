#!/usr/bin/env python3
"""
cleanup_workshop.py — Deleta TODOS os recursos AWS criados pelos labs.

Idempotente: pode rodar várias vezes; ignora recursos que já não existem.
Ordem de deleção respeita dependências (dependentes antes de dependências).

Uso (no SageMaker terminal):
    cd ~/Workshop-AI-Agents-Security
    python3 cleanup_workshop.py

Ou com flag pra ver o que faria sem deletar:
    python3 cleanup_workshop.py --dry-run

Recursos cobertos:
    - Cognito User Pool (workshop-ai-agents-pool) + domain
    - Bedrock Guardrail (workshop-guardrail)
    - AgentCore Runtimes (6 — workshop-*)
    - AgentCore Memory (workshop-memory)
    - AgentCore Policy Engine (workshop_policy_engine) + 9 policies
    - AgentCore Gateway (workshop-gateway) + targets
    - AgentCore Registry (workshop-agent-registry) + records
    - Lambda functions (workshop-utility-*)
    - CloudTrail (workshop-trail) + bucket S3
    - CloudWatch Alarms (workshop-*)
    - IAM roles (workshop-*)
"""
from __future__ import annotations

import argparse
import sys
import time

import boto3
from botocore.exceptions import ClientError


REGION = "us-east-1"
PROJECT_PREFIX = "workshop"
DRY_RUN = False


def log(emoji: str, msg: str) -> None:
    print(f"  {emoji} {msg}", flush=True)


def safe(action: str, fn, *args, **kwargs):
    """Executa fn(*args, **kwargs) — log success/skip/fail; nunca propaga."""
    if DRY_RUN:
        log("🔍", f"[dry-run] {action}")
        return None
    try:
        return fn(*args, **kwargs)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("ResourceNotFoundException", "NoSuchEntity",
                    "TrailNotFoundException", "NotFoundException"):
            log("~", f"{action} (já não existe)")
        else:
            log("✗", f"{action} falhou: {code}: {str(e)[:120]}")
    except Exception as e:
        log("✗", f"{action} erro: {type(e).__name__}: {str(e)[:120]}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Runtimes (top-level — deletar primeiro)
# ─────────────────────────────────────────────────────────────────────────────

def cleanup_runtimes():
    print("\n[1/9] AgentCore Runtimes")
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)
    runtimes = []
    try:
        for r in client.list_agent_runtimes(maxResults=100).get("items", []):
            if r.get("name", "").startswith(f"{PROJECT_PREFIX}-"):
                runtimes.append(r)
    except ClientError as e:
        log("✗", f"list runtimes: {e}")
        return

    if not runtimes:
        log("~", "nenhum runtime")
        return

    for r in runtimes:
        rid = r["agentRuntimeId"]
        safe(f"delete runtime {r['name']}", client.delete_agent_runtime, agentRuntimeId=rid)
        time.sleep(1)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Registry (precisa deletar records primeiro)
# ─────────────────────────────────────────────────────────────────────────────

def cleanup_registry():
    print("\n[2/9] Agent Registry")
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)
    try:
        regs = client.list_registries(maxResults=50).get("items", [])
    except ClientError as e:
        log("✗", f"list registries: {e}")
        return

    for reg in regs:
        name = reg.get("name", "")
        if not name.startswith(PROJECT_PREFIX):
            continue
        # Delete records first
        try:
            for rec in client.list_registry_records(registryName=name, maxResults=100).get("items", []):
                rid = rec.get("registryRecordId") or rec.get("recordId")
                safe(f"delete record {rec.get('recordName')}",
                     client.delete_registry_record,
                     registryName=name, registryRecordId=rid)
        except ClientError:
            pass
        safe(f"delete registry {name}", client.delete_registry, name=name)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Gateway (deletar targets primeiro, depois gateway)
# ─────────────────────────────────────────────────────────────────────────────

def cleanup_gateway():
    print("\n[3/9] AgentCore Gateway")
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)
    try:
        gws = client.list_gateways(maxResults=100).get("items", [])
    except ClientError as e:
        log("✗", f"list gateways: {e}")
        return

    for gw in gws:
        name = gw.get("name", "")
        if not name.startswith(PROJECT_PREFIX):
            continue
        gid = gw["gatewayId"]
        # Targets primeiro
        try:
            for t in client.list_gateway_targets(gatewayIdentifier=gid, maxResults=100).get("items", []):
                safe(f"delete target {t.get('name')}",
                     client.delete_gateway_target,
                     gatewayIdentifier=gid, targetId=t["targetId"])
                time.sleep(1)
        except ClientError:
            pass
        safe(f"delete gateway {name}", client.delete_gateway, gatewayIdentifier=gid)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Policy Engine (deletar policies primeiro)
# ─────────────────────────────────────────────────────────────────────────────

def cleanup_policy_engines():
    print("\n[4/9] Policy Engines + Policies")
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)

    try:
        engines = client.list_policy_engines().get("policyEngines", []) or \
                  client.list_policy_engines().get("items", [])
    except ClientError as e:
        log("✗", f"list engines: {e}")
        return

    for eng in engines:
        name = eng.get("name", "")
        # Pega tanto workshop_ quanto workshop-
        if not (name.startswith(f"{PROJECT_PREFIX}_") or name.startswith(f"{PROJECT_PREFIX}-")):
            continue
        eid = eng.get("policyEngineId") or eng.get("id")
        try:
            for p in client.list_policies(policyEngineId=eid, maxResults=100).get("policies", []):
                safe(f"delete policy {p['name']}",
                     client.delete_policy,
                     policyEngineId=eid, policyId=p["policyId"])
                time.sleep(1)
        except ClientError:
            pass
        safe(f"delete engine {name}", client.delete_policy_engine, policyEngineId=eid)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Memory
# ─────────────────────────────────────────────────────────────────────────────

def cleanup_memory():
    print("\n[5/9] AgentCore Memory")
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)
    try:
        mems = client.list_memories(maxResults=50).get("memories", [])
    except ClientError as e:
        log("✗", f"list memories: {e}")
        return

    for m in mems:
        if not m.get("id", "").startswith(f"{PROJECT_PREFIX}-"):
            continue
        safe(f"delete memory {m['id']}", client.delete_memory, memoryId=m["id"])


# ─────────────────────────────────────────────────────────────────────────────
# 6. Bedrock Guardrail
# ─────────────────────────────────────────────────────────────────────────────

def cleanup_guardrail():
    print("\n[6/9] Bedrock Guardrail")
    client = boto3.client("bedrock", region_name=REGION)
    try:
        for g in client.list_guardrails(maxResults=100).get("guardrails", []):
            if g.get("name", "").startswith(f"{PROJECT_PREFIX}-"):
                safe(f"delete guardrail {g['name']}",
                     client.delete_guardrail, guardrailIdentifier=g["id"])
    except ClientError as e:
        log("✗", f"list guardrails: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 7. Lambdas
# ─────────────────────────────────────────────────────────────────────────────

def cleanup_lambdas():
    print("\n[7/9] Lambda functions")
    client = boto3.client("lambda", region_name=REGION)
    try:
        paginator = client.get_paginator("list_functions")
        for page in paginator.paginate():
            for fn in page.get("Functions", []):
                if fn["FunctionName"].startswith(f"{PROJECT_PREFIX}-"):
                    safe(f"delete lambda {fn['FunctionName']}",
                         client.delete_function, FunctionName=fn["FunctionName"])
    except ClientError as e:
        log("✗", f"list lambdas: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 8. Cognito + CloudTrail + S3 + Alarms
# ─────────────────────────────────────────────────────────────────────────────

def cleanup_cognito():
    print("\n[8a/9] Cognito User Pool")
    client = boto3.client("cognito-idp", region_name=REGION)
    paginator = client.get_paginator("list_user_pools")
    for page in paginator.paginate(MaxResults=60):
        for p in page.get("UserPools", []):
            if not p["Name"].startswith(f"{PROJECT_PREFIX}-"):
                continue
            pool_id = p["Id"]
            # Domain
            try:
                desc = client.describe_user_pool(UserPoolId=pool_id)["UserPool"]
                if desc.get("Domain"):
                    safe(f"delete domain {desc['Domain']}",
                         client.delete_user_pool_domain,
                         Domain=desc["Domain"], UserPoolId=pool_id)
            except ClientError:
                pass
            safe(f"delete user pool {p['Name']}",
                 client.delete_user_pool, UserPoolId=pool_id)


def cleanup_cloudtrail():
    print("\n[8b/9] CloudTrail")
    client = boto3.client("cloudtrail", region_name=REGION)
    try:
        for t in client.describe_trails().get("trailList", []):
            if t.get("Name", "").startswith(f"{PROJECT_PREFIX}-"):
                safe(f"delete trail {t['Name']}",
                     client.delete_trail, Name=t["Name"])
    except ClientError as e:
        log("✗", f"describe trails: {e}")

    # S3 bucket
    s3 = boto3.client("s3", region_name=REGION)
    try:
        sts = boto3.client("sts")
        account = sts.get_caller_identity()["Account"]
        bucket = f"{PROJECT_PREFIX}-cloudtrail-{account}-{REGION}"
        # Esvazia primeiro
        if not DRY_RUN:
            paginator = s3.get_paginator("list_object_versions")
            for page in paginator.paginate(Bucket=bucket):
                objs = (page.get("Versions") or []) + (page.get("DeleteMarkers") or [])
                if objs:
                    s3.delete_objects(Bucket=bucket, Delete={
                        "Objects": [{"Key": o["Key"], "VersionId": o["VersionId"]} for o in objs]
                    })
        safe(f"delete bucket {bucket}", s3.delete_bucket, Bucket=bucket)
    except ClientError as e:
        if "NoSuchBucket" not in str(e):
            log("~", f"bucket cloudtrail: {str(e)[:120]}")


def cleanup_alarms():
    print("\n[8c/9] CloudWatch Alarms")
    client = boto3.client("cloudwatch", region_name=REGION)
    try:
        alarms = client.describe_alarms(AlarmNamePrefix=f"{PROJECT_PREFIX}-").get("MetricAlarms", [])
        if alarms and not DRY_RUN:
            client.delete_alarms(AlarmNames=[a["AlarmName"] for a in alarms])
            log("✓", f"{len(alarms)} alarme(s) deletado(s)")
        elif alarms:
            log("🔍", f"[dry-run] {len(alarms)} alarme(s)")
        else:
            log("~", "nenhum alarme")
    except ClientError as e:
        log("✗", f"alarms: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 9. IAM Roles (por último — recursos podem precisar dela durante delete)
# ─────────────────────────────────────────────────────────────────────────────

def cleanup_iam_roles():
    print("\n[9/9] IAM Roles")
    iam = boto3.client("iam")
    paginator = iam.get_paginator("list_roles")
    for page in paginator.paginate():
        for r in page["Roles"]:
            if not r["RoleName"].startswith(f"{PROJECT_PREFIX}-"):
                continue
            name = r["RoleName"]
            # detach managed
            try:
                for p in iam.list_attached_role_policies(RoleName=name).get("AttachedPolicies", []):
                    iam.detach_role_policy(RoleName=name, PolicyArn=p["PolicyArn"])
            except ClientError:
                pass
            # delete inline
            try:
                for pname in iam.list_role_policies(RoleName=name).get("PolicyNames", []):
                    iam.delete_role_policy(RoleName=name, PolicyName=pname)
            except ClientError:
                pass
            safe(f"delete role {name}", iam.delete_role, RoleName=name)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    global DRY_RUN, PROJECT_PREFIX
    parser = argparse.ArgumentParser(description="Deleta todos os recursos do workshop")
    parser.add_argument("--dry-run", action="store_true", help="Não deleta — só mostra")
    parser.add_argument("--region", default=REGION, help=f"Região (default: {REGION})")
    parser.add_argument("--prefix", default=PROJECT_PREFIX, help=f"Prefix (default: {PROJECT_PREFIX})")
    parser.add_argument("--yes", action="store_true", help="Pula confirmação")
    args = parser.parse_args()

    DRY_RUN = args.dry_run
    PROJECT_PREFIX = args.prefix

    # Valida conta
    sts = boto3.client("sts")
    ident = sts.get_caller_identity()
    print(f"\nConta: {ident['Account']}")
    print(f"Região: {args.region}")
    print(f"Prefixo: {PROJECT_PREFIX}-*")
    print(f"Modo: {'DRY-RUN (não vai deletar)' if DRY_RUN else 'EXECUÇÃO REAL'}")

    if not DRY_RUN and not args.yes:
        resp = input("\n⚠️  Vai deletar tudo. Confirma? (digite 'yes' para confirmar): ")
        if resp.strip().lower() != "yes":
            print("Cancelado.")
            return 1

    # Ordem importa
    cleanup_runtimes()
    cleanup_registry()
    cleanup_gateway()
    cleanup_policy_engines()
    cleanup_memory()
    cleanup_guardrail()
    cleanup_lambdas()
    cleanup_cognito()
    cleanup_cloudtrail()
    cleanup_alarms()
    cleanup_iam_roles()

    print("\n✓ Cleanup concluído.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
