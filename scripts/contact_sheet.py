import json, sys
from PIL import Image
d = sys.argv[1]; fr = json.load(open(f"{d}/frames.json"))
paths = [p for v in fr.values() for p in v]
cols, tw, th = 5, 384, 216
rows = -(-len(paths) // cols)
sheet = Image.new("RGB", (cols * tw, rows * th), "black")
for i, p in enumerate(paths):
    im = Image.open(p).convert("RGB").resize((tw, th))
    sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
sheet.save(sys.argv[2], quality=85)
print(len(paths), "frames")
