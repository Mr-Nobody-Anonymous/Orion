from pathlib import Path

p = Path(r"C:/Users/hp/Desktop/Orion/src/orion/mission/engine.py")
raw = p.read_text(encoding="utf-8-sig")
lines = raw.split("\n")
idx = next(
    (i for i, l in enumerate(lines) if l.strip() == "def mission(self, mission_id: str) -> Mission:"),
    None,
)
assert idx is not None, "def mission not found"
insert = [
    "    @property",
    "    def store(self) -> MissionStore | None:",
    "        \"\"\"The persistence store (public read access).)\"\"\"",
    "        return self._store",
    "",
]
lines[idx:idx] = insert
p.write_text("\n".join(lines), encoding="utf-8-sig")
print("STORE PROP ADDED")