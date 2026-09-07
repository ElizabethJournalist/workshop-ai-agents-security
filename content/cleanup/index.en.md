---
title: "Cleanup"
weight: 110
---

## Remove Workshop Resources

To remove all resources created during the workshop, run the cleanup script from the repository root:

:::code{language=bash showCopyAction=true showLineNumbers=false}
python cleanup_workshop.py
:::

This removes:
- Cognito User Pool and app clients
- AgentCore Gateway and Lambda targets
- Cedar policies
- AgentCore Memory resources
- AgentCore Runtime agents
- Bedrock Guardrails
- Agent Registry entries
- CloudWatch alarms and log groups
- IAM roles created for the workshop

::alert[The cleanup script only removes resources with the `workshop-` or `workshop_` prefix. It will not affect any other resources in your account.]{type="info" header="Safe cleanup"}

## Manual Cleanup

If you prefer to remove resources manually, each lab notebook includes a cleanup section at the bottom with the specific `delete` or `cleanup` commands for that lab's resources.

## Workshop Studio Event Accounts

If you are running this workshop in a Workshop Studio event, the account and all resources will be automatically cleaned up when the event ends. No manual cleanup is needed.
