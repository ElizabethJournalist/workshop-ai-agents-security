---
title: "Summary"
weight: 120
---

## What You Built

A fully governed AI agent platform with nine security layers:

| Layer | Service | What It Enforces |
|---|---|---|
| Identity | Amazon Cognito | Who the user is and what groups they belong to |
| Authentication | AgentCore Gateway | Only valid JWT holders can reach agent operations |
| Authorization | Cedar Policies | Fine-grained control over which users can call which tools |
| Memory Isolation | AgentCore Memory | Per-user data separation at the namespace level |
| Runtime Scoping | AgentCore Runtime | Agents execute with scoped IAM roles, JWT propagated end to end |
| Content Filtering | Bedrock Guardrails | Prompt injection prevention, PII anonymization, sensitive content blocking |
| Lifecycle Governance | Agent Registry | Only approved agents run in production |
| Audit Trail | CloudTrail + Cedar Spans | Every API call and authorization decision is logged |
| Anomaly Detection | CloudWatch Alarms | Automated alerts for authorization failures, latency, and abuse |

## Key Takeaways

1. **Start with identity.** Everything else depends on knowing who the user is.
2. **Layered security is not optional.** Authentication, authorization, and content filtering are three independent layers that reinforce each other.
3. **Controls enforced at the platform level scale.** Enforcing security per-agent does not scale. Enforcing it at the Gateway, Policy, and Guardrail level does.
4. **Audit everything.** Cedar decision spans give you a queryable record of every authorization decision across the fleet.
5. **Govern the fleet.** The Agent Registry is how you answer "which agents are approved for production?" at scale.

## Next Steps

- **Run the workshop with your team**, use this as a hands-on enablement session
- **Adapt the scenario**, replace the utility sector demo data with your customer's industry
- **Build a customer demo**, the End-to-End portal (Module 9) is ready for show-and-tell sessions
- **File PFRs**, if you hit gaps during the workshop, capture them as product feature requests
- **Share feedback**, help us improve the workshop for the next iteration

## Resources

- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [Cedar Policy Language](https://www.cedarpolicy.com/)
- [Amazon Cognito Developer Guide](https://docs.aws.amazon.com/cognito/latest/developerguide/)
- [Bedrock Guardrails Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)

## Thank You

This workshop was built by the AWS Enterprise Support Frontier AI team. Questions, feedback, and contributions are welcome.
