"""
shared.utils — Infraestrutura cross-setor (não-AgentCore) usada pelos labs.

Submódulos:
    config           load_config / save_config para config.env
    prompts          load_smart_agent_prompt(sector)
    iam              create_*_role helpers
    lambda_helpers   package_and_deploy_lambda(sector, api_name)
    cleanup          CLI de teardown global

Importação típica nos notebooks:

    from shared.utils.config import load_config, save_config
    from shared.utils.iam import create_gateway_role
    from shared.utils.lambda_helpers import deploy_lambda
    from shared.utils.prompts import load_smart_agent_prompt
"""

__all__ = ["config", "prompts", "iam", "lambda_helpers", "cleanup"]
