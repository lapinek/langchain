import os
import re
from langchain_community.tools.pangea.base import PangeaBaseTool

from pydantic import SecretStr
from typing import Optional, ClassVar

try:
    from pangea import PangeaConfig
    from pangea.services import IpIntel
except ImportError as e:
    raise ImportError(
        "Cannot import pangea, please install `pip install pangea-sdk==5.1.0`."
    ) from e


class PangeaIpGuardError(RuntimeError):
    """
    Exception raised for unexpected scenarios or when malicious IPs are found.
    """
    def __init__(self, message: str) -> None:
        super().__init__(message)


class PangeaIpIntelGuard(PangeaBaseTool):
    """
    This tool guard finds malicious ips in the input text using the Pangea IP Intel service.
    Details of the service can be found here:
        [IP Intel API Reference docs](https://pangea.cloud/docs/api/ip-intel)

    Requirements:
        - Environment variable ``PANGEA_IP_INTEL_TOKEN`` must be set,
          or passed as a named parameter to the constructor.

    How to use:
        .. code-block:: python
            import os
            from langchain_community.tools.pangea.ip_intel_guard import PangeaIpIntelGuard
            from pydantic import SecretStr

            # Initialize parameters
            token = SecretStr(os.getenv("PANGEA_IP_INTEL_TOKEN"))
            config = PangeaConfig(domain="aws.us.pangea.cloud")

            # Setup Pangea Ip Intel Tool
            tool = PangeaIpIntelGuard(token=token, config_id="", config=config)
            tool.run("Please click here to confirm your order:http://113.235.101.11:54384/order/123 .  Leave us a feedback here: http://malware123.com/feedback")
    """

    """Name of the tool."""
    name: str = "pangea-ip-intel-guard-tool"

    """Description of the tool."""
    description: str = "Detects malicious IP addresses in the input text using the Pangea IP Intel service."

    _threshold: int = 80
    _ip_pattern: ClassVar[str] = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"

    def __init__(
        self,
        *,
        token: Optional[SecretStr] = None,
        config: PangeaConfig | None = None,
        threshold: int = 80,
        token_env_key_name: str = "PANGEA_IP_INTEL_TOKEN",
    ) -> None:
        """
        Args:
            token: Pangea API token.
            config: PangeaConfig object.
        """

        if not token:
            token = SecretStr(os.getenv(token_env_key_name, ""))

        if not token or not token.get_secret_value() or token.get_secret_value() == "":
            raise ValueError(f"'{token_env_key_name}' must be set or passed")

        super().__init__()

        self._threshold = threshold
        self._ip_intel_client = IpIntel(token=token.get_secret_value(), config=config)

    def _process_text(self, input_text: str) -> str:

        # Find all IPs using the regex pattern
        ips = re.findall(self._ip_pattern, input_text)

        # If no ips found return the original text
        if len(ips) == 0:
            return input_text

        # Check the reputation of each Ip found
        intel = self._ip_intel_client.reputation_bulk(ips)

        if not intel.result:
            raise PangeaIpGuardError("Result is invalid or missing")

        # Check if the score is higher than the set threshold for any ip
        if any(ip_data.score >= self._threshold for ip_data in intel.result.data.values()):
            input_text = "Malicious IPs found in the provided input."

        # Return unchanged input_text
        return input_text