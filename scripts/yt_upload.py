"""Upload a video to YouTube (unlisted by default) and set its thumbnail.

python scripts/yt_upload.py VIDEO.mp4 META.json THUMB.jpg
Prints the video URL. Never prints tokens.
"""
import json, os, sys, urllib.parse, urllib.request


def token():
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data) as r:
        return json.load(r)["access_token"]


def main(video, meta_path, thumb):
    meta = json.load(open(meta_path, encoding="utf-8"))
    tok = token()
    body = {
        "snippet": {"title": meta["title"], "description": meta["description"], "tags": meta.get("tags", []),
                    "categoryId": meta.get("categoryId", "27"), "defaultLanguage": "ru", "defaultAudioLanguage": "ru"},
        "status": {"privacyStatus": meta.get("privacy", "unlisted"), "selfDeclaredMadeForKids": False,
                   "containsSyntheticMedia": True},
    }
    size = os.path.getsize(video)
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)})
    with urllib.request.urlopen(req) as r:
        upload_url = r.headers["Location"]
    with open(video, "rb") as f:
        req = urllib.request.Request(upload_url, data=f.read(), method="PUT",
                                     headers={"Authorization": "Bearer " + tok, "Content-Type": "video/mp4"})
    with urllib.request.urlopen(req, timeout=3600) as r:
        vid = json.load(r)["id"]
    with open(thumb, "rb") as f:
        req = urllib.request.Request(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}",
                                     data=f.read(), method="POST",
                                     headers={"Authorization": "Bearer " + tok, "Content-Type": "image/jpeg"})
    try:
        urllib.request.urlopen(req).read()
        print("thumbnail set")
    except Exception as e:
        print("thumbnail failed:", getattr(e, "code", e))
    print("VIDEO_URL https://youtu.be/" + vid)


if __name__ == "__main__":
    main(*sys.argv[1:4])
