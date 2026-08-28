from .orchestration.system import OrionSystem


class LocalOrionWorkflow(OrionSystem):
    """Backward-compatible local workflow entry point backed by the canonical system."""

    def __init__(self) -> None:
        super().__init__()
