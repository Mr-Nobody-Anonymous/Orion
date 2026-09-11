from pathlib import Path

from orion.infrastructure.source_repositories import source_repository_inventory


def test_source_repository_inventory_is_honest_about_runtime_use() -> None:
    root = Path(__file__).resolve().parents[2]
    inventory = source_repository_inventory(root)
    assert inventory["total"] == 30
    assert inventory["present"] == 30
    assert inventory["direct_runtime_imports"] == 0
    assert inventory["by_integration_mode"]["reference"] > 0
