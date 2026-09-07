forbid(
  principal is AgentCore::OAuthUser,
  action == AgentCore::Action::"maintenanceapi___create_work_order",
  resource == AgentCore::Gateway::"{gateway_arn}"
)
when {
  context.input has priority &&
  context.input.priority == "high" &&
  !(principal.hasTag("cognito:groups") &&
    principal.getTag("cognito:groups") like "*managers*")
};
