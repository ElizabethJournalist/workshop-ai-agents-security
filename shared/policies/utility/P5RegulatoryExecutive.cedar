permit(
  principal is AgentCore::OAuthUser,
  action in [
    AgentCore::Action::"regulatoryapi___generate_report",
    AgentCore::Action::"regulatoryapi___get_compliance_data"
  ],
  resource == AgentCore::Gateway::"{gateway_arn}"
)
when {
  principal.hasTag("cognito:groups") &&
  principal.getTag("cognito:groups") like "*managers*"
};
