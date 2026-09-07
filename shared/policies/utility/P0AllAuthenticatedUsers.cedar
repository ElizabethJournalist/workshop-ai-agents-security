permit(
  principal is AgentCore::OAuthUser,
  action in [
    AgentCore::Action::"maintenanceapi___create_work_order",
    AgentCore::Action::"maintenanceapi___get_asset_history",
    AgentCore::Action::"contractapi___search_contracts",
    AgentCore::Action::"contractapi___extract_clause"
  ],
  resource == AgentCore::Gateway::"{gateway_arn}"
);
