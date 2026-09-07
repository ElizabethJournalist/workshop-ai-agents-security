permit(
  principal is AgentCore::OAuthUser,
  action in [
    AgentCore::Action::"gridapi___get_grid_status",
    AgentCore::Action::"gridapi___get_outage_alerts"
  ],
  resource == AgentCore::Gateway::"{gateway_arn}"
)
when {
  principal.hasTag("cognito:groups") &&
  principal.getTag("cognito:groups") like "*operators*"
};
