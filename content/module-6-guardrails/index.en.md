---
title: "Module 6: Bedrock Guardrails"
weight: 70
---

## The Problem

Cedar controls who can call what. But it does not inspect the content of what flows through the agent. A properly authorized user can still submit a prompt injection attack, and a properly authorized agent can still return PII in its response. Content-level filtering is a separate security layer from authorization.

The enterprise question: *How do we prevent agents from leaking sensitive data in their outputs, even when the user and the tool call are fully authorized?*

## What You Will Build

A Bedrock Guardrail that filters agent inputs and outputs for:

- **Prompt injection attacks**, detect and block attempts to override agent instructions
- **PII detection and anonymization**, automatically mask email addresses, installation codes, and other sensitive patterns
- **Content filters**, block hate speech, insults, misconduct
- **Custom regex patterns**, catch domain-specific sensitive data (e.g., Brazilian CPF, installation codes)

## Why This Matters

Guardrails and Cedar solve different problems. Cedar controls who can call what. Guardrails inspect the content that flows through. Both can run at the same time, and both should. A Guardrail is a global resource that you attach to agents, so content filtering stays consistent across the fleet.

## Labs

| Lab | Title | What You Do | Time |
|---|---|---|---|
| 06.1 | [Create Guardrail and Wire into Agents](lab-06-1/) | Create a guardrail, test it in isolation, then attach it to a running agent | 15 min |

## Key Concepts

- **Bedrock Guardrail**, managed content filter for model inputs and outputs
- **Content Filters**, block prompt attacks, hate speech, insults, misconduct
- **PII Filters**, detect and anonymize personally identifiable information
- **Regex Filters**, custom patterns for domain-specific sensitive data
- **Two ways to use**, (1) test in isolation via `apply_guardrail`; (2) attach to agents via environment variable

::alert[Cedar authorizes the request. Guardrails filter the content. Both are active. This is layered security.]{type="info" header="Authorization + Content Filtering"}

➡️ After completing this module, proceed to [Module 7: Agent Registry](/module-7-registry)
