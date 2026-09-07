"""
08-AgentCore-Observability/utils.py — helpers de observabilidade.

Funções:
    setup_cloudtrail()                  → cria trail multi-region
    create_governance_alarms()          → 8 alarmes CloudWatch
    query_aws_spans()                   → CloudWatch Insights query em /aws/spans
    cleanup_cloudtrail()                → remove trail + bucket
    cleanup_alarms()                    → remove alarmes
"""
from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import ClientError


# ─────────────────────────────────────────────────────────────────────────────
# CloudTrail
# ─────────────────────────────────────────────────────────────────────────────

def setup_cloudtrail(
    name: str = "workshop-trail",
    *,
    bucket_name: str | None = None,
    multi_region: bool = True,
    lambda_arns: list[str] | None = None,
    region: str = "us-east-1",
) -> dict:
    """
    Cria CloudTrail multi-region. Cria também o bucket S3 se necessário.

    Args:
        lambda_arns: ARNs das Lambdas de tools para data events (auditoria
                     em nível de invocação). Se None, só management events.

    Returns:
        Dict com trail_arn, bucket_name.
    """
    sts = boto3.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    bucket_name = bucket_name or f"workshop-cloudtrail-{account_id}-{region}"

    s3 = boto3.client("s3", region_name=region)
    cloudtrail = boto3.client("cloudtrail", region_name=region)

    # Bucket
    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f"  ~ Bucket S3 já existe: {bucket_name}")
    except ClientError:
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": region})
        # Bloqueia todo acesso público
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True, "IgnorePublicAcls": True,
                "BlockPublicPolicy": True, "RestrictPublicBuckets": True,
            },
        )
        # Bucket policy para CloudTrail
        import json
        s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AWSCloudTrailAclCheck",
                    "Effect": "Allow",
                    "Principal": {"Service": "cloudtrail.amazonaws.com"},
                    "Action": "s3:GetBucketAcl",
                    "Resource": f"arn:aws:s3:::{bucket_name}",
                },
                {
                    "Sid": "AWSCloudTrailWrite",
                    "Effect": "Allow",
                    "Principal": {"Service": "cloudtrail.amazonaws.com"},
                    "Action": "s3:PutObject",
                    "Resource": f"arn:aws:s3:::{bucket_name}/AWSLogs/{account_id}/*",
                    "Condition": {"StringEquals": {"s3:x-amz-acl": "bucket-owner-full-control"}},
                },
            ],
        }))
        # Retenção de 90 dias (custo baixo)
        s3.put_bucket_lifecycle_configuration(
            Bucket=bucket_name,
            LifecycleConfiguration={"Rules": [{
                "ID": "expire-cloudtrail-logs", "Status": "Enabled",
                "Filter": {"Prefix": ""}, "Expiration": {"Days": 90},
            }]},
        )
        print(f"  ✓ Bucket criado: {bucket_name} (retenção 90 dias)")

    # Trail
    try:
        resp = cloudtrail.create_trail(
            Name=name,
            S3BucketName=bucket_name,
            IsMultiRegionTrail=multi_region,
            EnableLogFileValidation=True,
            IncludeGlobalServiceEvents=True,
            TagsList=[{"Key": "project", "Value": "workshop-ai-agents-security"}],
        )
        cloudtrail.start_logging(Name=name)
        trail_arn = resp["TrailARN"]
        print(f"  ✓ Trail criado: {trail_arn}")
    except cloudtrail.exceptions.TrailAlreadyExistsException:
        resp = cloudtrail.describe_trails(trailNameList=[name])
        trail_arn = resp["trailList"][0]["TrailARN"]
        print(f"  ~ Trail já existe: {trail_arn}")

    # Event selectors: management events (todos) + Lambda data events (auditoria por invocação)
    event_selector = {
        "ReadWriteType": "All",
        "IncludeManagementEvents": True,
    }
    if lambda_arns:
        event_selector["DataResources"] = [
            {"Type": "AWS::Lambda::Function", "Values": lambda_arns}
        ]
    cloudtrail.put_event_selectors(TrailName=trail_arn, EventSelectors=[event_selector])
    print(f"  ✓ Event selectors: management events" + (f" + {len(lambda_arns)} Lambda data events" if lambda_arns else ""))

    return {"trail_arn": trail_arn, "bucket_name": bucket_name}


# ─────────────────────────────────────────────────────────────────────────────
# CloudWatch Alarms
# ─────────────────────────────────────────────────────────────────────────────

def create_governance_alarms(
    *,
    policy_engine_id: str | None = None,
    guardrail_id: str | None = None,
    guardrail_version: str = "DRAFT",
    lambda_function_names: list[str] | None = None,
    sns_topic_arn: str | None = None,
    account_id: str | None = None,
    region: str = "us-east-1",
) -> list[str]:
    """
    Cria 8 alarmes CloudWatch mapeados aos planos de controle do workshop:
      1. CedarDenySpike       — burst de decisões DENY do policy engine
      2. LambdaErrors-{tool}  — erros em cada uma das 5 Lambdas de tools
      3. GuardrailIntervened  — Guardrail bloqueando/anonimizando conteúdo
      4. RuntimeSystemErrors  — 5xx do AgentCore Runtime

    Métricas só aparecem após tráfego real; até lá ficam em INSUFFICIENT_DATA.

    Returns:
        Lista de nomes de alarmes criados.
    """
    cw = boto3.client("cloudwatch", region_name=region)
    actions = [sns_topic_arn] if sns_topic_arn else []
    prefix = "workshop"
    created = []

    def _put(name, description, namespace, metric, dimensions, threshold):
        cw.put_metric_alarm(
            AlarmName=name,
            AlarmDescription=description,
            ActionsEnabled=bool(actions),
            AlarmActions=actions,
            OKActions=actions,
            Namespace=namespace,
            MetricName=metric,
            Dimensions=dimensions,
            Statistic="Sum",
            Period=300,
            EvaluationPeriods=1,
            Threshold=threshold,
            ComparisonOperator="GreaterThanOrEqualToThreshold",
            TreatMissingData="notBreaching",
            Tags=[{"Key": "project", "Value": "workshop-ai-agents-security"}],
        )
        created.append(name)
        print(f"  ✓ Alarme: {name} (>= {threshold:.0f})")

    # 1. Cedar DENY spike
    if policy_engine_id:
        _put(f"{prefix}-CedarDenySpike",
             "Burst de decisões DENY do policy engine em 5 min.",
             "AWS/Bedrock-AgentCore", "DenyDecisions",
             [{"Name": "PolicyEngine", "Value": policy_engine_id}], 10)
    else:
        print("  ! policy_engine_id ausente — pulando CedarDenySpike")

    # 2. Lambda errors (5 tools)
    for fn_name in (lambda_function_names or []):
        tool = fn_name.split("-")[-1]
        _put(f"{prefix}-LambdaErrors-{tool}",
             f"Lambda {fn_name} retornando erros.",
             "AWS/Lambda", "Errors",
             [{"Name": "FunctionName", "Value": fn_name}], 5)

    # 3. Guardrail intervened
    if guardrail_id:
        guardrail_arn = (
            f"arn:aws:bedrock:{region}:{account_id}:guardrail/{guardrail_id}"
            if account_id else guardrail_id
        )
        _put(f"{prefix}-GuardrailIntervened",
             "Guardrail interveio (PII anonimizada ou conteúdo bloqueado) > 5x em 5 min.",
             "AWS/Bedrock/Guardrails", "InvocationsIntervened",
             [{"Name": "GuardrailArn", "Value": guardrail_arn},
              {"Name": "GuardrailVersion", "Value": guardrail_version}], 5)
    else:
        print("  ! guardrail_id ausente — pulando GuardrailIntervened")

    # 4. Runtime system errors
    _put(f"{prefix}-RuntimeSystemErrors",
         "AgentCore Runtime retornou erros 5xx.",
         "AWS/Bedrock-AgentCore", "SystemErrors", [], 3)

    return created


# ─────────────────────────────────────────────────────────────────────────────
# CloudWatch Logs Insights
# ─────────────────────────────────────────────────────────────────────────────

def query_aws_spans(
    query: str,
    *,
    hours: int = 1,
    region: str = "us-east-1",
) -> list[dict]:
    """
    Executa Logs Insights query em /aws/spans (onde AgentCore grava traces).

    Args:
        query: Query CloudWatch Logs Insights.
        hours: Janela de tempo em horas.
        region: Região AWS.

    Returns:
        Lista de result dicts.
    """
    import time as time_module
    logs = boto3.client("logs", region_name=region)

    # Verify /aws/spans log group exists before querying
    try:
        logs.describe_log_groups(logGroupNamePrefix="/aws/spans", limit=1)
        groups = logs.describe_log_groups(logGroupNamePrefix="/aws/spans", limit=1).get("logGroups", [])
        if not any(g["logGroupName"] == "/aws/spans" for g in groups):
            print("⚠️ Log group /aws/spans não existe. Execute o Lab 05 com traces habilitados primeiro.")
            print("   O trace segment destination precisa estar configurado (UpdateTraceSegmentDestination).")
            return []
    except Exception as e:
        print(f"⚠️ Erro ao verificar /aws/spans: {e}")
        return []

    end = int(time_module.time())
    start = end - (hours * 3600)

    resp = logs.start_query(
        logGroupName="/aws/spans",
        startTime=start,
        endTime=end,
        queryString=query,
    )
    qid = resp["queryId"]

    while True:
        result = logs.get_query_results(queryId=qid)
        if result["status"] in ("Complete", "Failed", "Cancelled"):
            break
        time_module.sleep(2)

    if result["status"] != "Complete":
        raise RuntimeError(f"Query falhou: {result['status']}")

    return [{f["field"]: f["value"] for f in row} for row in result["results"]]


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────────────────

def cleanup_cloudtrail(name: str = "workshop-trail", *, region: str = "us-east-1") -> bool:
    client = boto3.client("cloudtrail", region_name=region)
    try:
        client.delete_trail(Name=name)
        print(f"  ✓ Trail deletado: {name}")
        return True
    except client.exceptions.TrailNotFoundException:
        return False


def cleanup_alarms(*, region: str = "us-east-1") -> int:
    cw = boto3.client("cloudwatch", region_name=region)
    alarms = cw.describe_alarms(AlarmNamePrefix="workshop-").get("MetricAlarms", [])
    if alarms:
        cw.delete_alarms(AlarmNames=[a["AlarmName"] for a in alarms])
        print(f"  ✓ {len(alarms)} alarmes deletados")
    return len(alarms)
