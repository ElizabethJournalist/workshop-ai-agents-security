permit(
  principal is AgentCore::OAuthUser,
  action == AgentCore::Action::"maintenanceapi___approve_work_order",
  resource == AgentCore::Gateway::"{gateway_arn}"
)
when {
  principal.hasTag("cognito:groups") &&
  principal.getTag("cognito:groups") like "*managers*"
};
