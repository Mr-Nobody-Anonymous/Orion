from orion.memory import LayeredMemory, MemoryLayer


def test_working_memory_compresses_oldest_entry_into_episodic_memory() -> None:
    memory = LayeredMemory(working_limit=1)
    memory.remember(MemoryLayer.WORKING, {"id": 1}, summary="first market observation", tags={"market"})
    memory.remember(MemoryLayer.WORKING, {"id": 2}, summary="second market observation", tags={"market"})
    assert memory.counts()["working"] == 1
    assert memory.counts()["episodic"] == 1


def test_memory_retrieval_prefers_relevant_summary() -> None:
    memory = LayeredMemory()
    memory.remember(MemoryLayer.RESEARCH, {"id": 1}, summary="inflation evidence", tags={"macro"})
    memory.remember(MemoryLayer.TRADING, {"id": 2}, summary="bitcoin momentum", tags={"crypto"})
    assert memory.retrieve("inflation")[0].content["id"] == 1
