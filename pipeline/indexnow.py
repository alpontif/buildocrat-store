#!/usr/bin/env python3
"""Tell Bing, Yandex and other IndexNow engines about every URL in the sitemap."""
import json
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = "04de6a9626389d0a16b71f8a9fd41e8a"
HOST = "www.buildocrat.store"

urls = re.findall(r"<loc>([^<]+)</loc>", open(os.path.join(ROOT, "docs", "sitemap.xml"), encoding="utf-8").read())
for i in range(0, len(urls), 9000):
    body = json.dumps({"host": HOST, "key": KEY, "keyLocation": f"https://{HOST}/{KEY}.txt", "urlList": urls[i:i + 9000]}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        print("IndexNow", urllib.request.urlopen(req, timeout=60).status, len(urls[i:i + 9000]), "urls")
    except Exception as ex:  # a ping failure must never fail the refresh
        print("IndexNow failed:", ex)
