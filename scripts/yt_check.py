"""Check that the YouTube credentials in GitHub secrets work. Prints only the channel name and counts."""
import json, os, urllib.parse, urllib.request

def token():
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data) as r:
        return json.load(r)["access_token"]

req = urllib.request.Request(
    "https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics,status&mine=true",
    headers={"Authorization": "Bearer " + token()},
)
with urllib.request.urlopen(req) as r:
    for c in json.load(r).get("items", []):
        print(c["snippet"]["title"], c["statistics"]["subscriberCount"], "subs,",
              c["statistics"]["videoCount"], "videos, long uploads:", c["status"].get("longUploadsStatus"))
