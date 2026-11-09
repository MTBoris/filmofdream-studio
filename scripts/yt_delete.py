"""Delete a YouTube video of the channel. python scripts/yt_delete.py VIDEO_ID"""
import sys, urllib.request
sys.path.insert(0, "scripts")
from yt_upload import token
req = urllib.request.Request(f"https://www.googleapis.com/youtube/v3/videos?id={sys.argv[1]}", method="DELETE",
                             headers={"Authorization": "Bearer " + token()})
urllib.request.urlopen(req)
print("deleted", sys.argv[1])
