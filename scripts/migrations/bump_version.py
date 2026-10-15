from pathlib import Path

p = Path(r"C:/Users/hp/Desktop/Orion/src/orion/mission/engine.py")
raw = p.read_text(encoding="utf-8-sig")
lines = raw.split("\n")
needle = "self._missions[mission_id] = replace(mission, budget=budget)"
idx = next(
    (i for i, l in enumerate(lines) if needle in l),
    None,
)
assert idx is not None, "budget replace not found"
new = "self._missions[mission_id] = replace(mission, budget=budget, version=mission.version + 1)"
lines[idx] = new
p.write_text("\n".join(lines), encoding="utf-8-sig")
print("BUDGET VERSION BUMP OK")