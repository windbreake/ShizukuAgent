from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.config import settings
from app.model_identity import model_display_name


class ModelRegistryError(ValueError):
    pass


class ModelRegistry:
    """Resolves providers, models, agent groups, and auxiliary-only APIs."""

    def snapshot(self, reveal_secrets: bool = False) -> dict[str, Any]:
        data = {
            "providers": deepcopy(settings.get("providers") or {}),
            "models": deepcopy(settings.get("models") or {}),
            "model_groups": deepcopy(settings.get("model_groups") or {}),
            "default_model_group": settings.get("default_model_group") or "default",
            "auxiliary_apis": deepcopy(settings.get("auxiliary_apis") or {}),
        }
        for model in data['models'].values():
            model['name'] = model_display_name(model)
        if not reveal_secrets:
            for provider in data["providers"].values():
                provider["has_api_key"] = bool(provider.get("api_key"))
                provider["api_key"] = ""
        return data

    def update(self, incoming: dict[str, Any]) -> dict[str, Any]:
        current = self.snapshot(reveal_secrets=True)
        merged = deepcopy(current)
        for key in ("providers", "models", "model_groups", "auxiliary_apis"):
            if key in incoming:
                if not isinstance(incoming[key], dict):
                    raise ModelRegistryError(f"{key} must be an object")
                merged[key] = deepcopy(incoming[key])
        if "default_model_group" in incoming:
            merged["default_model_group"] = str(incoming["default_model_group"] or "default")

        for provider_id, provider in merged["providers"].items():
            if not isinstance(provider, dict):
                raise ModelRegistryError(f"provider {provider_id} must be an object")
            submitted = str(provider.get("api_key") or "")
            if not submitted or submitted == "***":
                provider["api_key"] = (current["providers"].get(provider_id) or {}).get("api_key") or ""
            provider.setdefault("type", "openai_compatible")
            provider.setdefault("base_url", "https://api.openai.com/v1")

        self._validate(merged)
        for model in merged['models'].values():
            model['name'] = model_display_name(model)
        settings.update(merged, replace_keys=('providers', 'models', 'model_groups', 'auxiliary_apis'))
        return self.snapshot()

    def list_agent_models(self) -> list[dict[str, Any]]:
        result = []
        for model_id, model in (settings.get("models") or {}).items():
            capabilities = list(model.get("capabilities") or [])
            if model.get("auxiliary_only") or "chat" not in capabilities:
                continue
            result.append({"id": model_id, **deepcopy(model), 'name': model_display_name(model)})
        return result

    def resolve_agent_group(self, group_id: str | None = None) -> list[dict[str, Any]]:
        selected = group_id or settings.get("default_model_group") or "default"
        groups = settings.get("model_groups") or {}
        group = groups.get(selected)
        if not group:
            raise ModelRegistryError(f"unknown model group: {selected}")
        if group.get("purpose", "agent") != "agent":
            raise ModelRegistryError(f"model group is not available to agents: {selected}")
        resolved = [self.resolve_model(model_id, for_agent=True) for model_id in group.get("models") or []]
        if not resolved:
            raise ModelRegistryError(f"model group has no usable models: {selected}")
        return resolved

    def resolve_model(self, model_id: str, for_agent: bool = False) -> dict[str, Any]:
        models = settings.get("models") or {}
        model = deepcopy(models.get(model_id) or {})
        if not model:
            raise ModelRegistryError(f"unknown model: {model_id}")
        if not model.get("enabled", True):
            raise ModelRegistryError(f"model is disabled: {model_id}")
        capabilities = list(model.get("capabilities") or [])
        if for_agent and (model.get("auxiliary_only") or "chat" not in capabilities):
            raise ModelRegistryError(f"model cannot participate in agent runs: {model_id}")
        provider_id = str(model.get("provider") or "")
        provider = deepcopy((settings.get("providers") or {}).get(provider_id) or {})
        if not provider:
            raise ModelRegistryError(f"unknown provider for model {model_id}: {provider_id}")
        if provider.get('enabled') is False:
            raise ModelRegistryError(f"provider is disabled: {provider_id}")
        return {"id": model_id, **model, "provider_id": provider_id, "provider_config": provider}

    def resolve_auxiliary(self, api_id: str) -> dict[str, Any]:
        config = deepcopy((settings.get("auxiliary_apis") or {}).get(api_id) or {})
        if not config:
            raise ModelRegistryError(f"unknown auxiliary API: {api_id}")
        if not config.get("enabled", False):
            raise ModelRegistryError(f"auxiliary API is disabled: {api_id}")
        model = self.resolve_model(str(config.get("model") or ""))
        expected = {"search": "search", "speech": "speech", "images": "image"}.get(api_id)
        if expected and expected not in model.get("capabilities", []):
            raise ModelRegistryError(f"model {model['id']} does not support {expected}")
        return {"id": api_id, **config, "model_config": model}

    def _validate(self, data: dict[str, Any]) -> None:
        providers = data["providers"]
        for model_id, model in data["models"].items():
            if not isinstance(model, dict) or not model.get("provider") or not model.get("model"):
                raise ModelRegistryError(f"model {model_id} requires provider and model")
            if model["provider"] not in providers:
                raise ModelRegistryError(f"model {model_id} references unknown provider {model['provider']}")
        for group_id, group in data["model_groups"].items():
            if not isinstance(group, dict) or not group.get("models"):
                raise ModelRegistryError(f"model group {group_id} must contain models")
            if group.get('provider') and group['provider'] not in providers:
                raise ModelRegistryError(f'model group {group_id} references unknown provider')
            for model_id in group["models"]:
                model = data["models"].get(model_id) or {}
                if not model:
                    raise ModelRegistryError(f"model group {group_id} references unknown model {model_id}")
                if group.get('provider') and model.get('provider') != group['provider']:
                    raise ModelRegistryError(f'model {model_id} does not belong to provider group {group_id}')
                if group.get("purpose", "agent") == "agent" and model.get("auxiliary_only"):
                    raise ModelRegistryError(f"auxiliary-only model {model_id} cannot join agent group {group_id}")
        if data["default_model_group"] not in data["model_groups"]:
            raise ModelRegistryError("default_model_group does not exist")


model_registry = ModelRegistry()
