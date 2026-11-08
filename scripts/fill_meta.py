"""Fill {CHAPTERS} in meta.json from build timeline. python scripts/fill_meta.py META TIMELINE OUT"""
import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8")); tl = json.load(open(sys.argv[2]))
starts = {s["scene"]: s["start"] for s in tl["scenes"]}
rows = []
for i, (scene, title) in enumerate(m.get("chapters", [])):
    t = 0 if i == 0 else starts[scene]
    rows.append(f"{int(t // 60):02d}:{int(t % 60):02d} {title}")
m["description"] = m["description"].replace("{CHAPTERS}", "\n".join(rows))
json.dump(m, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n".join(rows))
