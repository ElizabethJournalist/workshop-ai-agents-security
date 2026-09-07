forbid(
  principal is AgentCore::OAuthUser,
  action == AgentCore::Action::"regulatoryapi___submit_to_regulator",
  resource == AgentCore::Gateway::"{gateway_arn}"
);
