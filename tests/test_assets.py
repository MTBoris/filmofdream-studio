import assets

PAGE = '''<html><head><title>Pumice Raft | NASA Earth Observatory</title>
<meta property="og:image" content="https://eoimages.gsfc.nasa.gov/images/imagerecords/78000/78863/gavre_amo_2012219_tmb.jpg">
</head><body>
<a href="https://eoimages.gsfc.nasa.gov/images/imagerecords/78000/78863/gavre_amo_2012219.jpg">web</a>
<a href="https://eoimages.gsfc.nasa.gov/images/imagerecords/78000/78863/gavre_amo_2012219_lrg.jpg">large</a>
<a href="https://eoimages.gsfc.nasa.gov/images/imagerecords/12000/12345/other_lrg.jpg">other image</a>
</body></html>'''


def test_find_large_image_prefers_lrg_for_this_image_id():
    url = assets.find_large_image(PAGE, "https://earthobservatory.nasa.gov/images/78863")
    assert url.endswith("/78863/gavre_amo_2012219_lrg.jpg")


def test_find_large_image_none():
    assert assets.find_large_image("<html></html>", "https://earthobservatory.nasa.gov/images/1") is None


def test_host_whitelist():
    assert assets.host_ok("https://eoimages.gsfc.nasa.gov/images/x.jpg")
    assert not assets.host_ok("https://evil.example.com/x.jpg")
    assert not assets.host_ok("http://eoimages.gsfc.nasa.gov/x.jpg")
