import os
from typing import Optional
from pydantic import SecretStr

from langchain_core._api import beta
from langchain_community.tools.pangea.base import PangeaBaseTool

try:
    from pangea import PangeaConfig
    from pangea.services import AIGuard
except ImportError as e:
    raise ImportError(
        "Cannot import pangea, please install `pip install pangea-sdk==5.2.0b2`."
    ) from e


class PangeaAIGuardError(RuntimeError):
    """
    Exception raised for unexpected scenarios or when malicious prompt is detected.
    """
    def __init__(self, message: str) -> None:
        super().__init__(message)


@beta(message="Pangea AI Guard service is in beta. Subject to change.")
class PangeaAIGuard(PangeaBaseTool):
    """
    Uses Pangea's AI Guard service to monitor, sanitize, and protect sensitive data.

    Requirements:
        - Environment variable ``PANGEA_AI_GUARD_TOKEN`` must be set,
          or passed as a named parameter to the constructor.

    How to use:
        .. code-block:: python
            import os
            from langchain_community.tools.pangea.ai_guard import PangeaAIGuard, PangeaConfig
            from pydantic import SecretStr

            # Initialize parameters
            token = SecretStr(os.getenv("PANGEA_AI_GUARD_TOKEN"))
            config = PangeaConfig(domain="aws.us.pangea.cloud")

            # Setup Pangea AI Guard tool
            ai_guard = PangeaAIGuard(token=token, config_id="", config=config, recipe="pangea_prompt_guard")

            # Run as a tool for agents
            ai_guard.run("My Name is John Doe and my email is john.doe@email.com.  My credit card number is 5555555555554444.")

            # Run as a Runnable for chains
            ai_guard.invoke("My Name is John Doe and my email is john.doe@email.com.  My credit card number is 5555555555554444.")
    """

    """Name of the tool"""
    name: str = "pangea-ai-guard-tool"

    """Description of the tool"""
    description: str = """
    Identifies and redacts PII and sensitive information in AI prompts, responses, and RAG context data.
    Detects and blocks malware submitted by users or ingested via agents or RAG file ingestion.
    Flags or hides malicious IP addresses, domains, and URLs embedded in prompts, responses, or data vectors.
    """

    _client: AIGuard
    _recipe: str

    def __init__(
                self,
                *,
                token: Optional[SecretStr] = None,
                config: PangeaConfig | None = None,
                config_id: str | None = None,
                token_env_key_name: str = "PANGEA_AI_GUARD_TOKEN",
                recipe: str = "pangea_prompt_guard",
            ) -> None:
        """
        Args:
            token: Pangea Prompt Guard API token.
            config_id: Pangea Prompt Guard configuration ID.
            config: PangeaConfig object.
            recipe: Pangea AI Guard recipe.
        """

        if not token:
            token = SecretStr(os.getenv(token_env_key_name, ""))

        if not token or not token.get_secret_value() or token.get_secret_value() == "":
            raise ValueError(f"'{token_env_key_name}' must be set or passed")

        super().__init__()
        self._recipe = recipe
        self._client = AIGuard(token=token.get_secret_value(), config=config, config_id=config_id)

    def _process_text(self, input_text: str) -> str:

        # Guard the input_text
        guarded = self._client.guard_text(input_text, recipe=self._recipe)

        if not guarded.result:
            raise PangeaAIGuardError("Result is invalid or missing")

        if guarded.result.redacted_prompt:
            input_text = guarded.result.redacted_prompt

        return input_text