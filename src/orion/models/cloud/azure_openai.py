"""Azure OpenAI cloud provider for ORION.

Uses Azure's deployment-scoped Chat Completions endpoint, which has a
slightly different URL shape from vanilla OpenAI:

    https://{resource}.openai.azure.com/openai/deployments/{deployment}/chat/completions?api-version=...

The provider takes the resource + deployment explicitly (rather than
parsing a full URL) so that the deployment name and the API version
can be validated up front.
"""

from __future__ import annotations

from typing import Any

from .base import (
    BaseHttpCloudProvider,
    CloudProviderError,
    HttpCloudConfig,
    env_or_none,
)


class AzureOpenAIProvider(BaseHttpCloudProvider):
    """Azure OpenAI deployment-scoped chat adapter."""

    DEFAULT_API_VERSION = "2024-02-01"

    def __init__(
        self,
        *,
        resource: str | None = None,
        deployment: str | None = None,
        api_version: str | None = None,
        api_key: str | None = None,
        endpoint: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if endpoint is not None:
            # Explicit override path — caller is responsible for the shape.
            pass
        else:
            resource = resource or env_or_none("AZURE_OPENAI_RESOURCE")
            deployment = deployment or env_or_none("AZURE_OPENAI_DEPLOYMENT")
            if not resource or not deployment:
                raise CloudProviderError(
                    "azure_openai: resource and deployment are required (or set "
                    "AZURE_OPENAI_RESOURCE and AZURE_OPENAI_DEPLOYMENT)"
                )
        api_version = api_version or env_or_none("AZURE_OPENAI_API_VERSION") or self.DEFAULT_API_VERSION
        api_key = api_key or env_or_none("AZURE_OPENAI_API_KEY")
        if endpoint is None:
            endpoint = f"https://{resource}.openai.azure.com/openai/deployments/{deployment}"
        cfg = HttpCloudConfig(
            endpoint=endpoint,
            api_key=api_key,
            model=deployment,
            timeout_seconds=timeout_seconds,
            extra_headers={"api-key": api_key or ""} if api_key else {},
        )
        super().__init__(name="azure_openai", config=cfg)
        self._api_version = api_version

    def _path(self) -> str:
        return f"/chat/completions?api-version={self._api_version}"

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not prompt or not prompt.strip():
            raise CloudProviderError("azure_openai: empty prompt")
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body: dict[str, Any] = {"messages": messages}
        if "temperature" in kwargs:
            body["temperature"] = float(kwargs["temperature"])
        if "max_tokens" in kwargs:
            body["max_tokens"] = int(kwargs["max_tokens"])
        resp = self._request("POST", self._path(), body=body)
        try:
            choice = resp["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise CloudProviderError(
                f"azure_openai: malformed response: {exc}; keys={list(resp.keys())}"
            ) from exc
        if not isinstance(content, str):
            raise CloudProviderError("azure_openai: response content is not a string")
        return content
