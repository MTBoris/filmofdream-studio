"""Fill {CHAPTERS} (and image credits) in meta.json from the build.
python scripts/fill_meta.py META TIMELINE OUT [ASSETS_JSON]

ASSETS_JSON (from scripts/assets.py): the credit of every external image is printed into the description,
at {IMAGE_CREDITS} if the description has it, else at the end.
"""
import json
import sys

m = json.load(open(sys.argv[1], encoding="utf-8"))
tl = json.load(open(sys.argv[2]))
starts = {s["scene"]: s["start"] for s in tl["scenes"]}
rows = []
for i, (scene, title) in enumerate(m.get("chapters", [])):
    t = 0 if i == 0 else starts[scene]
    rows.append(f"{int(t // 60):02d}:{int(t % 60):02d} {title}")
m["description"] = m["description"].replace("{CHAPTERS}", "\n".join(rows))
if len(sys.argv) > 4:
    assets = json.load(open(sys.argv[4], encoding="utf-8"))
    credits = list(dict.fromkeys(a["credit"] for a in assets.values() if a.get("credit")))
    block = "\n".join(credits)
    if "{IMAGE_CREDITS}" in m["description"]:
        m["description"] = m["description"].replace("{IMAGE_CREDITS}", block)
    elif block:
        m["description"] = m["description"].rstrip() + "\n\n" + block
else:
    m["description"] = m["description"].replace("{IMAGE_CREDITS}", "")
json.dump(m, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n".join(rows))
