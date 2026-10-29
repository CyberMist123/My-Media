"""Idempotent Seerr wiring (task book §13): Sonarr/Radarr servers inside Seerr,
Sonarr anime root, and the dedicated non-admin Fable user (REQUEST + AUTO_APPROVE).
Writes SEERR_FABLE_USER_ID to D:\\My Media\\.env. Run after the Seerr setup wizard."""
import json
import os
import secrets
import urllib.request

ENV = r"D:\My Media\.env"
for line in open(ENV, encoding="utf-8"):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ.setdefault(k, v)

PERM_REQUEST, PERM_AUTO_APPROVE = 32, 128  # Seerr dist/lib/permissions.js
QUALITY_PROFILE = "Any"  # interim; §8.1 quality tuning replaces this


def call(base, path, key, method="GET", body=None):
    req = urllib.request.Request(base + path, method=method,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"X-Api-Key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


SEERR = ("http://localhost:5055/api/v1", os.environ["SEERR_API_KEY"])
seerr = lambda p, m="GET", b=None: call(*SEERR[:1], p, SEERR[1], m, b)
arr = lambda app, port, p, m="GET", b=None: call(f"http://localhost:{port}/api/v3", p,
                                                   os.environ[f"{app.upper()}_API_KEY"], m, b)

# Sonarr also needs the anime root folder.
if not any(r["path"].rstrip("/") == "/data/media/anime" for r in arr("sonarr", 8989, "/rootfolder")):
    arr("sonarr", 8989, "/rootfolder", "POST", {"path": "/data/media/anime"})
    print("sonarr: root folder /data/media/anime")

for app, port, root in (("sonarr", 8989, "/data/media/tv"), ("radarr", 7878, "/data/media/movies")):
    if seerr(f"/settings/{app}"):
        continue
    prof = next(p for p in arr(app, port, "/qualityprofile") if p["name"] == QUALITY_PROFILE)
    body = dict(name=app.capitalize(), hostname=app, port=port, apiKey=os.environ[f"{app.upper()}_API_KEY"],
                useSsl=False, baseUrl="", activeProfileId=prof["id"], activeProfileName=prof["name"],
                activeDirectory=root, is4k=False, isDefault=True, externalUrl=f"http://localhost:{port}",
                syncEnabled=True, preventSearch=False, tags=[])
    if app == "sonarr":
        body.update(activeAnimeProfileId=prof["id"], activeAnimeProfileName=prof["name"],
                    activeAnimeDirectory="/data/media/anime", animeTags=[], enableSeasonFolders=True)
    else:
        body.update(minimumAvailability="released")
    seerr(f"/settings/{app}", "POST", body)
    print(f"seerr: {app} server ({root}, profile {prof['name']})")

users = seerr("/user?take=100")["results"]
fable = next((u for u in users if (u.get("username") or u.get("displayName")) == "fable"), None)
if not fable:
    fable = seerr("/user", "POST", {"email": "fable@ler.local", "username": "fable",
                                    "password": secrets.token_urlsafe(24),  # never used: Fable acts via X-Api-User
                                    "permissions": PERM_REQUEST | PERM_AUTO_APPROVE})
    print(f"seerr: created user fable id={fable['id']}")
want = PERM_REQUEST | PERM_AUTO_APPROVE
if fable.get("permissions") != want:
    seerr(f"/user/{fable['id']}", "PUT", {"permissions": want})
    print(f"seerr: fable permissions -> {want}")

lines = [l for l in open(ENV, encoding="utf-8").read().splitlines() if not l.startswith("SEERR_FABLE_USER_ID=")]
lines.append(f"SEERR_FABLE_USER_ID={fable['id']}")
open(ENV, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("done")
