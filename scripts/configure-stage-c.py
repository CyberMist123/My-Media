"""Idempotent stage-C wiring (task book §8.3, §9.2, §9.3).
Bazarr: Sonarr/Radarr connections; default profile Chinese (either script), English-
original titles (Arr auto-tag en-orig) Chinese + English; no-account providers only.
AutoBangumi: native qBittorrent as downloader, save under Z:\\LER-MEDIA\\media\\anime.
Suwayomi: CBZ on, downloads to /data/media/comics.
Keys come from / are written to D:\\My Media\\.env; nothing secret is printed."""
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

ENV = r"D:\My Media\.env"


def load_env():
    for line in open(ENV, encoding="utf-8"):
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ[k] = v


def save_env(name, value):
    lines = [l for l in open(ENV, encoding="utf-8").read().splitlines() if not l.startswith(name + "=")]
    lines.append(f"{name}={value}")
    open(ENV, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    os.environ[name] = value


def http(url, method="GET", data=None, headers=None, form=False):
    h = dict(headers or {})
    if data is not None:
        if form:
            data = urllib.parse.urlencode(data, doseq=True).encode()
            h["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(data).encode()
            h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    with OPENER.open(req, timeout=30) as r:
        raw = r.read()
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return raw.decode("utf-8", "replace")


def sh(*args):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8").stdout


load_env()

# --- Bazarr ---------------------------------------------------------------
if "BAZARR_API_KEY" not in os.environ:
    cfg = sh("docker", "exec", "ler-media-bazarr-1", "cat", "/config/config/config.yaml")
    key = re.search(r"^auth:\s*\n(?:\s+.*\n)*?\s+apikey:\s*(\S+)", cfg, re.M).group(1).strip("'\"")
    save_env("BAZARR_API_KEY", key)
B = "http://localhost:6767/api"
BH = {"X-API-KEY": os.environ["BAZARR_API_KEY"]}

# Owner 2026-10-29: English-original titles get Chinese + English; everything else
# Chinese only, simplified or traditional either way. Sonarr/Radarr auto-tag
# English-original items "en-orig"; Bazarr maps that tag to profile 2.
EN_TAG = "en-orig"
for app, port in (("sonarr", 8989), ("radarr", 7878)):
    base, hk = f"http://localhost:{port}/api/v3", {"X-Api-Key": os.environ[f"{app.upper()}_API_KEY"]}
    tag = next((t for t in http(f"{base}/tag", headers=hk) if t["label"] == EN_TAG), None)         or http(f"{base}/tag", "POST", {"label": EN_TAG}, hk)
    if not any(r["name"] == "English original" for r in http(f"{base}/autotagging", headers=hk)):
        spec = next(x for x in http(f"{base}/autotagging/schema", headers=hk)
                    if x["implementation"] == "OriginalLanguageSpecification")
        spec.update(name="English", negate=False, required=True)
        spec["fields"][0]["value"] = 1  # English
        http(f"{base}/autotagging", "POST", {"name": "English original", "removeTagsAutomatically": True,
                                             "tags": [tag["id"]], "specifications": [spec]}, hk)
        print(f"{app}: auto-tag English-original -> {EN_TAG}")


def item(i, code):
    return {"id": i, "language": code, "audio_exclude": "False", "audio_only_include": "False",
            "hi": "False", "forced": "False"}


profile = [
    # Cutoff 65535 = "any": stop once either Chinese variant is found.
    {"profileId": 1, "name": "中文（简繁任一）", "cutoff": 65535, "mustContain": [], "mustNotContain": [],
     "originalFormat": False, "tag": None, "items": [item(1, "zh"), item(2, "zt")]},
    {"profileId": 2, "name": "中英（英语原片）", "cutoff": None, "mustContain": [], "mustNotContain": [],
     "originalFormat": False, "tag": EN_TAG, "items": [item(1, "zh"), item(2, "en")]},
]
providers = ["embeddedsubtitles", "podnapisi", "yifysubtitles", "zimuku"]  # no account needed
form = {
    "settings-general-use_sonarr": "true", "settings-general-use_radarr": "true",
    "settings-sonarr-ip": "sonarr", "settings-sonarr-port": "8989", "settings-sonarr-base_url": "/",
    "settings-sonarr-apikey": os.environ["SONARR_API_KEY"],
    "settings-radarr-ip": "radarr", "settings-radarr-port": "7878", "settings-radarr-base_url": "/",
    "settings-radarr-apikey": os.environ["RADARR_API_KEY"],
    "settings-general-serie_default_enabled": "true", "settings-general-serie_default_profile": "1",
    "settings-general-movie_default_enabled": "true", "settings-general-movie_default_profile": "1",
    "settings-general-serie_tag_enabled": "true", "settings-general-movie_tag_enabled": "true",
    "settings-general-enabled_providers": providers,
    "languages-enabled": ["zh", "zt", "en"],
    "languages-profiles": json.dumps(profile, ensure_ascii=False),
}
http(f"{B}/system/settings", "POST", form, BH, form=True)
s = http(f"{B}/system/settings", headers=BH)
print("bazarr: sonarr", s["general"]["use_sonarr"], "radarr", s["general"]["use_radarr"],
      "providers", s["general"]["enabled_providers"], "tag profiles",
      s["general"]["serie_tag_enabled"], s["general"]["movie_tag_enabled"], "default profiles",
      s["general"]["serie_default_profile"], s["general"]["movie_default_profile"])

# --- AutoBangumi ----------------------------------------------------------
A = "http://localhost:7892/api/v1"
ab_user = os.environ.get("AB_USER", "admin")
ab_pass = os.environ.get("AB_PASS", "adminadmin")  # factory default until rotated below
# 3.3.x authenticates with a session cookie set by /auth/login.
assert http(f"{A}/auth/login", "POST", {"username": ab_user, "password": ab_pass}, form=True).get("authenticated")
AH = {}
if "AB_PASS" not in os.environ:
    import secrets
    new = secrets.token_urlsafe(18)
    http(f"{A}/auth/update", "POST", {"username": "admin", "password": new}, AH)
    save_env("AB_USER", "admin")
    save_env("AB_PASS", new)
    assert http(f"{A}/auth/login", "POST", {"username": "admin", "password": new}, form=True).get("authenticated")
    print("autobangumi: default admin password rotated (stored in .env)")
conf = http(f"{A}/config/get", headers=AH)
conf["downloader"].update(type="qbittorrent", host="host.docker.internal:8090", username="", password="",
                          path="Z:/LER-MEDIA/media/anime", ssl=False)
conf["bangumi_manage"].update(enable=True, rename_method="pn", group_tag=True, eps_complete=False)
http(f"{A}/config/update", "PATCH", conf, AH)
c2 = http(f"{A}/config/get", headers=AH)
print("autobangumi: downloader", c2["downloader"]["host"], "path", c2["downloader"]["path"],
      "rename", c2["bangumi_manage"]["rename_method"])

# --- Suwayomi -------------------------------------------------------------
G = "http://localhost:4567/api/graphql"
q = """mutation { setSettings(input: { settings: { downloadAsCbz: true, downloadsPath: "/data/media/comics" } })
       { settings { downloadAsCbz downloadsPath } } }"""
for _ in range(10):
    try:
        r = http(G, "POST", {"query": q})
        break
    except Exception:
        time.sleep(5)
print("suwayomi:", r["data"]["setSettings"]["settings"])
