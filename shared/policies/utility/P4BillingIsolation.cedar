permit(
  principal is AgentCore::OAuthUser,
  action in [
    AgentCore::Action::"billingapi___get_invoice",
    AgentCore::Action::"billingapi___get_consumption_history"
  ],
  resource == AgentCore::Gateway::"{gateway_arn}"
)
when {
  principal.hasTag("cognito:groups") &&
  (principal.getTag("cognito:groups") like "*governance*" ||
   principal.getTag("cognito:groups") like "*billing*")
};
