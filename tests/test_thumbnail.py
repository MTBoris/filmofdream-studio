from PIL import Image

import thumbnail


def test_thumbnail_is_1280x720_with_white_bird_and_title(tmp_path):
    src = tmp_path / "bg.png"
    Image.new("RGB", (1920, 1080), (200, 70, 40)).save(src)
    out = tmp_path / "t.jpg"
    thumbnail.make({"text": ["ПТИЦЫ", "ИЗ КАМНЯ?"], "bird": "left"}, str(src), str(out))
    im = Image.open(out)
    assert im.size == (1280, 720)
    left = im.crop((100, 300, 500, 500)).convert("L")
    assert max(left.getdata()) > 230   # the white bird is on the left
