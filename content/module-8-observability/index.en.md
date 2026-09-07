---
title: "Module 8: Observability"
weight: 90
---

## The Problem

You have identity, authorization, content filtering, and lifecycle governance. But if you cannot see what agents are doing in real time, you cannot detect anomalies, investigate incidents, or prove compliance. The audit question: *Can you show me every authorization decision an agent made in the last 24 hours?*

## What You Will Build

A comprehensive observability layer for the agent platform:

- **CloudTrail integration**, audit trail of all API calls across AgentCore services
- **Cedar decision spans**, every PERMIT/DENY decision logged to `/aws/spans` with the full evaluation context
- **CloudWatch alarms**, automated alerts for authorization failures, high latency, error rates, and potential abuse patterns

## Why This Matters

Observability closes the loop. You have controls in place for identity, authorization, and content filtering, but without visibility into what agents are actually doing, you cannot tell whether those controls are working. When something goes wrong, the audit trail is where you start.

Cedar decision spans are particularly useful here. Every policy evaluation gets logged with the principal, action, resource, context, and decision. The governance team can query this data to see exactly what was authorized and what was denied across the agent fleet.

## Labs

| Lab | Title | What You Do | Time |
|---|---|---|---|
| 08.1 | [CloudTrail and Cedar Spans](lab-08-1/) | Query CloudTrail events and Cedar authorization decisions in CloudWatch Logs | 12 min |
| 08.2 | [CloudWatch Alarms for Governance](lab-08-2/) | Create alarms for authorization failures, latency spikes, and abuse detection | 8 min |

## Key Concepts

- **CloudTrail**, logs all AWS API calls, including AgentCore operations
- **Cedar Decision Spans**, authorization evaluation results logged to `/aws/spans`
- **CloudWatch Logs Insights**, query engine for analyzing spans and CloudTrail events
- **CloudWatch Alarms**, automated alerts when metrics cross governance thresholds

➡️ After completing this module, proceed to [Module 9: End-to-End](/module-9-end-to-end)
