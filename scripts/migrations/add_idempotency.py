from pathlib import Path

p = Path(r"C:/Users/hp/Desktop/Orion/src/orion/mission/persistence.py")
raw = p.read_text(encoding="utf-8-sig")
lines = raw.split("\n")
needle = 'if mission.version == 1:'
idx = next(
    (i for i, l in enumerate(lines) if needle in l),
    None,
)
assert idx is not None, "version branch not found"
old_block = lines[idx:idx + 9]
new_block = [
    "        if mission.version == 1:",
    "            inserted = self._store.insert_if_absent(",
    "                \"missions\", payload, id=mission.mission_id, version_id=\"1\"",
    "            )",
    "            if not inserted:",
    "                # idempotent replay: the row already exists with the same",
    "                # version (e.g. crash after insert, before event)",
    "                existing = self.load_mission(mission.mission_id)",
    "                if existing == mission:",
    "                    return",
    "                raise ConcurrentUpdateError(",
    "                    f\"mission {mission.mission_id!r} already exists\"",
    "                )",
    "            return",
]
lines[idx:idx + 9] = new_block
p.write_text("\n".join(lines), encoding="utf-8-sig")
print("SAVE IDEMPOTENCY OK")