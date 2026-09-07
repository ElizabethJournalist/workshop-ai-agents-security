permit(
  principal is AgentCore::OAuthUser,
  action == AgentCore::Action::"x_amz_bedrock_agentcore_search",
  resource == AgentCore::Gateway::"{gateway_arn}"
);
