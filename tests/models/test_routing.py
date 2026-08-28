from orion.infrastructure.configuration import AIMode
from orion.models.cloud import CloudProviderUnavailable, NullCloudProvider
from orion.models.routing import HardwareProfile, LocalModelRouter, ProviderRouter


def test_local_router_selects_tier_by_hardware() -> None:
    small = LocalModelRouter(HardwareProfile(ram_gb=16)).select()
    large = LocalModelRouter(HardwareProfile(ram_gb=128, vram_gb=24, cuda_available=True)).select("complex")
    assert small.name == "small"
    assert large.name == "large"


def test_provider_router_uses_cloud_in_hybrid_mode_for_complex_tasks() -> None:
    local = NullCloudProvider(provider_name="local")
    cloud = NullCloudProvider(provider_name="cloud")
    router = ProviderRouter(AIMode.HYBRID, local=local, cloud=cloud)
    assert router.provider_for("complex") is cloud
    assert router.provider_for("routine") is local


def test_null_cloud_provider_fails_with_clear_message() -> None:
    provider = NullCloudProvider(provider_name="demo-cloud")
    try:
        provider.generate("hello")
    except CloudProviderUnavailable as error:
        assert "demo-cloud" in str(error)
    else:
        raise AssertionError("expected cloud provider to be unavailable")
