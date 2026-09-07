---
title: "Module 2: AgentCore Gateway"
weight: 30
---

## The Problem

Without a gateway, agents are exposed directly. Any client that knows the endpoint can call any tool. There is no JWT validation, no centralized access control, and no single point to enforce authentication before an agent operation executes.

In the DIY approach, each agent or MCP server handles its own authentication, if it handles it at all. This creates inconsistent security posture across the agent fleet and makes it impossible to audit access centrally.

## What You Will Build

An AgentCore Gateway that serves as the single authenticated entry point for all agent operations:

- **JWT Authorizer** that validates tokens against your Cognito User Pool from Module 1
- **Lambda targets** behind the Gateway that simulate agent tools (grid status, work orders, alerts)
- **Bearer token flow** where authenticated users invoke MCP tools through the Gateway

## Why This Matters

The Gateway is the enforcement point between the user and every agent operation. Once it is in place, no unauthenticated request reaches any tool. It also becomes the point where Cedar policies (Module 3) will enforce fine-grained authorization, but first, authentication must be solid.

## Labs

| Lab | Title | What You Do | Time |
|---|---|---|---|
| 02.1 | [Create Gateway with JWT Authorizer](lab-02-1/) | Create the Gateway, configure the JWT authorizer with Cognito discovery URL | 10 min |
| 02.2 | [Add Lambda Targets](lab-02-2/) | Deploy Lambda functions as tools and register them as Gateway targets | 10 min |
| 02.3 | [Invoke MCP with Bearer Token](lab-02-3/) | Authenticate as a user, get a token, call a tool through the Gateway | 5 min |

## Key Concepts

- **AgentCore Gateway**, managed API gateway for agent operations with built-in JWT validation
- **JWT Authorizer**, validates every request against the Cognito OIDC discovery endpoint
- **Lambda Targets**, serverless functions registered as tools the Gateway can route to
- **Bearer Token**, the JWT passed in the Authorization header on every request

::alert[At this stage, any authenticated user can call any tool. Authorization comes in Module 3 with Cedar policies.]{type="info" header="Authentication ≠ Authorization"}

➡️ After completing this module, proceed to [Module 3: AgentCore Policy (Cedar)](/module-3-policy)
