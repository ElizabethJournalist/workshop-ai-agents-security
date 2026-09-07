# Workshop AI Agents Security — Bug Report (Testing Review)

Tester: Elizabeth Smith (flatout)
Date started: 2026-06-23
Account: 354820845663 (us-east-1)

---

## Bug #1 — Lab 04: Memory name validation error

**File:** `04-AgentCore-Memory/01-create-memory-resource.ipynb`
**Cell:** `create_memory` call (inline, not via utils.py)
**Error:** `ValidationException: Value at 'name' failed to satisfy constraint: Member must satisfy regular expression pattern: [a-zA-Z][a-zA-Z0-9_]{0,47}`
**Root cause:** Name uses hyphen (`"workshop-memory"`) but API only accepts letters, numbers, and underscores.
**Fix:** Change `name="workshop-memory"` to `name="workshop_memory"`
**Note:** `utils.py` line 39 already has the correct version. Only the notebook inline call needs updating.
**Status:** Fixed locally, reported to Ariane.

---

## Bug #2 — Lab 04: Same hyphen issue in cell 8

**File:** `04-AgentCore-Memory/01-create-memory-resource.ipynb`
**Cell:** 8 (Step 3)
**Error:** Same as Bug #1 — name uses hyphen instead of underscore.
**Fix:** Change `name="workshop-memory"` to `name="workshop_memory"`
**Status:** Fixed locally, reported to Ariane.

---

## Bug #3 — Lab 05: X-Ray Delivery fails without CloudWatch Logs Trace Segment Destination

**File:** `05-AgentCore-Runtime/utils.py` (function `enable_traces_delivery`)
**Cell:** Step 3 (after SmartAgent deploys successfully)
**Error:** `ValidationException: X-Ray Delivery Destination is supported with CloudWatch Logs as a Trace Segment Destination. Please enable the CloudWatch Logs destination for your traces using the UpdateTraceSegmentDestination API`
**Impact:** SmartAgent deploys fine (READY), but observability/tracing setup fails. May affect Lab 08.
**Fix:** Added `xray.update_trace_segment_destination(Destination="CloudWatchLogs")` call at the top of `enable_traces_delivery()` before attempting X-Ray delivery setup.
**Status:** ✅ Fixed locally (Sep 5, 2026).

---

## Bug #4 — Lab 05: Runtime list filter uses hyphen instead of underscore + stale client

**File:** `05-AgentCore-Runtime/02-deploy-specialists.ipynb`
**Cell:** Validation cell (lists runtimes)
**Error:** No output — filter `startswith("workshop-")` doesn't match agents named `workshop_*`. Additionally, after fixing the filter, the cached boto3 client still returned empty until a fresh client was instantiated.
**Fix:** (1) Change `startswith("workshop-")` to `startswith("workshop_")`. (2) Replace the validation cell with a fresh client call:
```python
import boto3
client = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
resp = client.list_agent_runtimes()
for r in resp.get("agentRuntimes", []):
    print(r["agentRuntimeName"], r.get("status"))
```
**Root cause:** Naming inconsistency (hyphen vs underscore) + boto3 client caching stale credentials.
**Status:** Fixed locally.

---

## Bug #5 — Lab 06: Missing "Next lab" link at bottom

**File:** `06-Bedrock-Guardrails/01-create-guardrail-and-wire-into-agents.ipynb`
**Error:** No navigation link to Lab 07 at the bottom of the notebook. All other labs have this.
**Fix:** Add a markdown cell at the end linking to `../07-Agent-Registry/`
**Status:** ✅ Fixed locally (Sep 5, 2026). Added `➡️ [Lab 07 — Agent Registry](../07-Agent-Registry/)` navigation cell.

---

## Bug #6 — Lab 08: Log group '/aws/spans' does not exist

**File:** `08-AgentCore-Observability/01-cloudtrail-and-spans-aws-spans.ipynb`
**Cells:** Step 2 cell 5 AND cell 7 — both fail with same error
**Error:** `ResourceNotFoundException: Log group '/aws/spans' does not exist for account ID '354820845663'`
**Root cause:** Related to Bug #3 — the X-Ray/CloudWatch Logs trace segment destination was never set up (failed in Lab 04). The `/aws/spans` log group is created when tracing is properly configured.
**Fix:** Either add a cell that creates the log group, or add a prerequisite step calling `UpdateTraceSegmentDestination` to enable CloudWatch Logs (same fix as Bug #3). These bugs are connected.
**Impact:** Entire spans section of Lab 08 is blocked.
**Status:** ✅ Fixed locally (Sep 5, 2026). Added log group existence check in `query_aws_spans()` — returns empty list with helpful message instead of crashing. Root cause fix in Bug #3 enables the log group upstream.

---

## Bug #7 — Lab 09: UI "Cedar spans" link opens empty CloudWatch Insights

**File:** `09-End-to-End-with-UI/ui/server.py` (or static HTML)
**Error:** Clicking "Cedar spans" in the portal opens CloudWatch Insights with query against `/aws/spans` — but log group doesn't exist. No data displayed.
**Root cause:** Downstream effect of Bug #3/#6 — trace segment destination never configured.
**Impact:** Observability section of the UI demo is non-functional. Agent routing, guardrails, and login work fine.
**Fix:** Same as Bug #3 — configure trace segment destination. Once `/aws/spans` exists, the UI link works.
**Status:** ✅ Fixed locally (Sep 5, 2026). Added `ResourceNotFoundException` handler to both Cedar spans queries in `server.py` — returns empty results with warning instead of 500 error. Root cause fix in Bug #3 creates the log group upstream.

---

## Bug #8 — (next issue goes here)

---

# Next Steps (June 24, 2026)

## 1. Fix SSH access to GitLab
- Port 22 blocked even on VPN
- Port 443 SSH didn't work either (connection closed)
- `mwinit -o -s` / `mwinit --fido2` didn't resolve
- Options to try: different VPN endpoint, SSH ProxyCommand via corp proxy, ask Ariane to add as collaborator with push access via web UI

## 2. Push bug fixes to the repo
- Once SSH resolved, create branch with fixes and submit MR
- Fixes are all documented in TESTING-BUGS.md

## 3. Localize to English
- Workshop is currently in Portuguese (Brazilian)
- Question: can we support both languages in one repo without duplicating notebooks?
- Options to explore:
  - i18n layer (markdown cells pull from a locale file)
  - Separate branches (pt-br / en)
  - Duplicate notebooks in language folders (01-Identity-Foundation/en/, 01-Identity-Foundation/pt/)
  - Single notebook with language toggle (unlikely for Jupyter)
- Most practical: likely separate folder or branch per language. Discuss with Ariane.

## 4. Add latency tracking to the demo
- Use case: detect anomalous request patterns (e.g., insider threat flooding the system, prompt injection attempts causing long responses, resource abuse)
- Valid because:
  - Latency spikes indicate model overload, guardrail processing overhead, or abnormal input size
  - An insider sending adversarial/sabotage prompts would show up as latency outliers (guardrails processing, longer reasoning chains, repeated retries)
  - Baseline latency per agent/specialist enables anomaly detection
  - Pairs well with the existing CloudWatch alarms in Lab 08
- Where to add: Lab 08 (observability) or as a new section in Lab 09 (UI dashboard metric)
- Metrics to track: p50/p95/p99 response time per agent, requests per user per minute, guardrail trigger rate by user


