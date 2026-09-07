---
title: "Module 9: End-to-End"
weight: 100
---

## The Payoff

You have built nine security layers across eight modules. Now you see them all working together in a single interactive demo.

## What You Will Do

Launch the workshop portal UI and run complete user journeys:

- **Log in as Ana (operator)**, see which tools she can access and which are denied by Cedar
- **Log in as Carlos (manager)**, see the different permission set and tools available
- **Trigger agent operations**, watch the router delegate to specialists with proper authorization
- **Observe in real time**, Cedar decision spans appear in CloudWatch, Guardrails filter content, memory is isolated per user

## Why This Matters

This module proves the platform works as a system. When a customer asks "show me it working end to end," this is the demo. A user logs in through Cognito, the Gateway validates their token, Cedar checks whether they can call the tool, the agent executes with a scoped IAM role using isolated memory, Guardrails filter the response, and the whole chain shows up in CloudWatch.

## Labs

| Lab | Title | What You Do | Time |
|---|---|---|---|
| 09.1 | [Launch Portal and Run Journeys](lab-09-1/) | Start the UI, log in as different personas, run full agent journeys | 15 min |

## After the Workshop

You now have a reference architecture for securing AI agents at scale with Amazon Bedrock AgentCore. The short version: start with identity, layer your controls independently (authentication, authorization, content filtering, observability), enforce at the platform level rather than per-agent, log every authorization decision, and use the registry to control what runs in production.
