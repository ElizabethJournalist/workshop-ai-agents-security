// obs-links.js — deterministic builders for AWS console deep links.
//
// AWS Console uses a proprietary multi-step encoding for fragments
// (especially CloudWatch Logs Insights). Reference:
//   - https://openillumi.com/en/en-aws-cloudwatch-logs-url-auto-generate-encoding/
//   - JSURL-like protocol: ~()  for objects, '  for string prefix
//
// The two key transforms are:
//   1) For internal string values: encodeURIComponent(s).replace(/%/g, '*')
//   2) For the final URL fragment: encodeURIComponent(everything).replace(/%/g, '$')
//      (only path components / queryDetail wrapper)

let _cache = null;

async function fetchObsConfig() {
  if (_cache) return _cache;
  const resp = await fetch('/api/config/public');
  if (!resp.ok) throw new Error('failed to load /api/config/public');
  const data = await resp.json();
  _cache = {
    accountId:      data.observability?.accountId      || '',
    region:         data.observability?.region         || 'us-east-1',
    gatewayId:      data.observability?.gatewayId      || '',
    logGroups:      data.observability?.logGroups      || { gateway: '', lambdas: [], runtimes: {} },
    cloudtrailName: data.observability?.cloudtrailName || 'agents-governance-trail',
    specialists:    data.specialists                   || [],
  };
  return _cache;
}

// AWS Console JSURL-like value encoder.
// encodeURIComponent then replace %XX with *xx (LOWERCASE hex — matches
// what the AWS console actually generates when you copy a query URL).
function _v(s) {
  return encodeURIComponent(String(s))
    .replace(/%([0-9A-F]{2})/g, (_, h) => '*' + h.toLowerCase());
}

// Top-level fragment encoder: encodeURIComponent then % → $.
function _frag(s) {
  return encodeURIComponent(s).replace(/%/g, '$');
}

// Log group path encoder: double-encode and substitute % → $.
// Used for #logsV2:log-groups/log-group/<encoded> and similar.
function _path(s) {
  return encodeURIComponent(encodeURIComponent(s)).replace(/%/g, '$');
}

/** CloudWatch Logs Insights — opens the editor with a pre-populated query. */
function cwInsights({ logGroup, query, hours = 1 }) {
  if (!logGroup) return '#missing-log-group';
  const c = _cache;
  const region = c?.region || 'us-east-1';

  // Build the JSURL-encoded queryDetail object.
  const startSeconds = -1 * Math.max(60, hours * 3600);
  const queryDetail =
    `~(end~0` +
    `~start~${startSeconds}` +
    `~timeType~'RELATIVE` +
    `~unit~'seconds` +
    `~editorString~'${_v(query)}` +
    `~queryId~'` +
    `~source~(~'${_v(logGroup)}))`;

  // Wrap in the queryDetail param and apply the top-level $-encoding.
  const fragment = `?queryDetail=${queryDetail}`;
  const encoded  = _frag(fragment);

  return (
    `https://${region}.console.aws.amazon.com/cloudwatch/home?region=${region}` +
    `#logsV2:logs-insights${encoded}`
  );
}

/** Log group viewer — direct view with no Insights query (lighter alternative). */
function cwLogGroup(logGroup) {
  if (!logGroup) return '#missing-log-group';
  const c = _cache;
  const region = c?.region || 'us-east-1';
  return (
    `https://${region}.console.aws.amazon.com/cloudwatch/home?region=${region}` +
    `#logsV2:log-groups/log-group/${_path(logGroup)}`
  );
}

/** X-Ray (CloudWatch ServiceLens) trace details by trace ID. */
function xrayTrace(traceId) {
  if (!traceId) return '#missing-trace-id';
  const c = _cache;
  const region = c?.region || 'us-east-1';
  return (
    `https://${region}.console.aws.amazon.com/cloudwatch/home?region=${region}` +
    `#xray:traces/${encodeURIComponent(traceId)}`
  );
}

/** X-Ray service map. */
function xrayServiceMap(_hours = 1) {
  const c = _cache;
  const region = c?.region || 'us-east-1';
  return (
    `https://${region}.console.aws.amazon.com/cloudwatch/home?region=${region}` +
    `#xray:service-map/map`
  );
}

/** Bedrock AgentCore spans log group — has span data even when X-Ray is empty. */
function spansLogGroup() {
  const c = _cache;
  const region = c?.region || 'us-east-1';
  return cwLogGroup('aws/spans');
}

/** CloudWatch Metrics graph — Cedar Allow vs Deny across all 13 tools.
 *
 * Validated empirically (aws cloudwatch get-metric-statistics):
 *   - Namespace: AWS/Bedrock-AgentCore
 *   - 3-dim signature: TargetResource, ToolName, OperationName
 *
 * Per AWS docs (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-policy-metrics.html),
 * AgentCore publishes the same datapoint with multiple dimension signatures
 * — we use the simplest 3-dim signature which is always present.
 *
 * Each tool maps to one or more policies in our demo:
 *   gridapi___get_grid_status         → P1 (operators)
 *   gridapi___get_outage_alerts       → P1 (operators)
 *   maintenanceapi___create_work_order → P0 (all) + P8 (forbid priority=high unless manager — context-based)
 *   maintenanceapi___get_asset_history → P0 (all)
 *   maintenanceapi___approve_work_order → P2 (managers permit) + P3 (operators forbid)
 *   contractapi___search_contracts    → P0 (all)
 *   contractapi___extract_clause      → P0 (all)
 *   billingapi___get_invoice          → P4 (governance/billing)
 *   billingapi___get_consumption_history → P4 (governance/billing)
 *   regulatoryapi___generate_report   → P5 (managers)
 *   regulatoryapi___get_compliance_data → P5 (managers)
 *   regulatoryapi___submit_to_regulator → P6 (universal deny)
 *   x_amz_bedrock_agentcore_search    → P7 (semantic search for all)
 */
const CEDAR_TOOLS = [
  // Tool name                                    Color   Policies
  ['gridapi___get_grid_status',                   '17becf'], // P1
  ['gridapi___get_outage_alerts',                 '1f77b4'], // P1
  ['maintenanceapi___create_work_order',          '2ca02c'], // P0 + P8 (priority=high needs manager)
  ['maintenanceapi___get_asset_history',          '98df8a'], // P0
  ['maintenanceapi___approve_work_order',         'ff7f0e'], // P2/P3
  ['contractapi___search_contracts',              '8c564b'], // P0
  ['contractapi___extract_clause',                'c49c94'], // P0
  ['billingapi___get_invoice',                    '9467bd'], // P4
  ['billingapi___get_consumption_history',        'c5b0d5'], // P4
  ['regulatoryapi___generate_report',             'e377c2'], // P5
  ['regulatoryapi___get_compliance_data',         'f7b6d2'], // P5
  ['regulatoryapi___submit_to_regulator',         'd62728'], // P6
  ['x_amz_bedrock_agentcore_search',              '7f7f7f'], // P7
];

function cedarMetrics(metric = 'AllowDecisions') {
  const c = _cache;
  const region = c?.region || 'us-east-1';
  const gw = c?.gatewayId || '';
  if (!gw) {
    return `https://${region}.console.aws.amazon.com/cloudwatch/home?region=${region}#metricsV2:graph=~()`;
  }

  // metricsV2 graph format. Each metric line:
  // ~(~'Namespace~'MetricName~'Dim1Name~'Dim1Value~'Dim2Name~'Dim2Value...)
  // Suffix `~(~(stat~'Sum~color~'XXXXXX))` for styling.
  const line = (m, tool, color) =>
    `~(~'AWS*2fBedrock-AgentCore` +
    `~'${m}` +
    `~'TargetResource~'${gw}` +
    `~'ToolName~'${tool}` +
    `~'OperationName~'PartiallyAuthorizeActions` +
    `~(~(stat~'Sum~color~'*23${color}~label~'${tool})))`;

  const lines = CEDAR_TOOLS.map(([tool, color]) => line(metric, tool, color)).join('');

  const graph =
    `~(metrics~(${lines})` +
    `~view~'timeSeries~stacked~false~region~'${region}` +
    `~start~'-PT3H~end~'P0D~period~60` +
    `~title~'Cedar*20${metric}*20by*20Tool)`;

  return (
    `https://${region}.console.aws.amazon.com/cloudwatch/home?region=${region}` +
    `#metricsV2:graph=${graph}`
  );
}

/** CloudTrail — Event History filtered by event name and/or principal. */
function cloudtrail({ eventName = '', principalId = '' } = {}) {
  const c = _cache;
  const region = c?.region || 'us-east-1';
  const filters = [];
  if (eventName)   filters.push({ key: 'EventName',  value: eventName });
  if (principalId) filters.push({ key: 'Username',   value: principalId });

  let fragment = '#/events';
  if (filters.length) {
    const qs = filters.map(f => `${encodeURIComponent(f.key)}=${encodeURIComponent(f.value)}`).join('&');
    fragment += `?${qs}`;
  }
  return (
    `https://${region}.console.aws.amazon.com/cloudtrailv2/home?region=${region}${fragment}`
  );
}

/** CloudTrail filtered by EventSource (broader than EventName — catches all
 *  bedrock-agentcore events including ListGateways, ListAgentRuntimes, etc). */
function cloudtrailBySource(source = 'bedrock-agentcore.amazonaws.com') {
  const c = _cache;
  const region = c?.region || 'us-east-1';
  return (
    `https://${region}.console.aws.amazon.com/cloudtrailv2/home?region=${region}` +
    `#/events?EventSource=${encodeURIComponent(source)}`
  );
}

/** AgentCore Memory console (per-actor sessions). */
function memorySessions(memoryArn) {
  if (!memoryArn) return '#missing-memory-arn';
  const c = _cache;
  const region = c?.region || 'us-east-1';
  const memoryId = memoryArn.split('/').pop();
  return (
    `https://${region}.console.aws.amazon.com/bedrock-agentcore/home?region=${region}` +
    `#/memory/${memoryId}`
  );
}

// ---------------------------------------------------------------------------
// Pre-built queries — one per common observability question.
// ---------------------------------------------------------------------------

/** Cedar policy spans — ALL authorization decisions from both span types.
 *
 * Source: log group `aws/spans`. Two span types are emitted:
 *   1. AgentCore.Policy.AuthorizeAction          — single tool/call → ALLOW or DENY
 *   2. AgentCore.Policy.PartiallyAuthorizeActions — tools/list filtering
 *
 * IMPORTANT: `denied_tools` and `allowed_tools` are arrays — CloudWatch
 * Logs Insights does not support array indexing (`.0`), so we keep the
 * query simple and let the user inspect @message in the console.
 *
 * Reference:
 *   https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-policy-metrics.html
 */
function queryCedarAll() {
  return `fields @timestamp, name, @message
| filter name like /AgentCore.Policy/
| sort @timestamp desc
| limit 200`;
}

/** Cedar DENY decisions only — filter via @message regex.
 *  Matches:
 *    - explicit "DENY" decision (single AuthorizeAction)
 *    - non-empty denied_tools array (PartiallyAuthorizeActions) */
function queryCedarDeny() {
  return `fields @timestamp, name, @message
| filter name like /AgentCore.Policy/
| filter @message like /"DENY"/
   or @message like /denied_tools.*[a-z]/
| sort @timestamp desc
| limit 100`;
}

/** Cedar decisions filtered by a specific policy name (P3, P4, etc).
 *  Searches @message for the policy ID prefix. */
function queryCedarAction(policyName) {
  return `fields @timestamp, name, @message
| filter name like /AgentCore.Policy/
| filter @message like /${policyName}/
| sort @timestamp desc
| limit 100`;
}

/** Filter runtime logs by session ID. */
function queryBySession(sessionId) {
  if (!sessionId) return `fields @timestamp, @message
| sort @timestamp desc
| limit 100`;
  return `fields @timestamp, @message
| filter @message like /${sessionId.slice(0, 24)}/
| sort @timestamp asc
| limit 200`;
}

/** Lambda invocations with timing and X-Ray trace IDs. */
function queryLambdaInvocations() {
  return `fields @timestamp, @duration, @billedDuration, @maxMemoryUsed, @initDuration
| filter @type = "REPORT"
| sort @timestamp desc
| limit 50`;
}

/** Bedrock Guardrail interventions — DISTINCT from Cedar.
 *  Looks for finish_reason = "guardrail_intervened" in runtime logs. */
function queryGuardrail() {
  return `fields @timestamp,
       body.output.messages.0.content.finish_reason as reason,
       body.output.messages.0.content.message as response
| filter body.output.messages.0.content.finish_reason = "guardrail_intervened"
| sort @timestamp desc
| limit 100`;
}

/** Spans (OTel traces) for a specific specialist agent. */
function querySpansBySpecialist(serviceName) {
  if (!serviceName) {
    return `fields @timestamp, resource.attributes.service.name as service, name, attributes
| sort @timestamp desc
| limit 100`;
  }
  return `fields @timestamp, name, attributes
| filter resource.attributes.service.name = "${serviceName}.DEFAULT"
| sort @timestamp desc
| limit 100`;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export const obs = {
  cfg: null,
  async init() {
    this.cfg = await fetchObsConfig();
    return this.cfg;
  },
  cwInsights,
  cwLogGroup,
  xrayTrace,
  xrayServiceMap,
  spansLogGroup,
  cedarMetrics,
  cloudtrail,
  cloudtrailBySource,
  memorySessions,
  queries: {
    cedarAll:           queryCedarAll,
    cedarDeny:          queryCedarDeny,
    cedarAction:        queryCedarAction,
    bySession:          queryBySession,
    lambdaInvocations:  queryLambdaInvocations,
    guardrail:          queryGuardrail,
    spansBySpecialist:  querySpansBySpecialist,
  },
};
