"""Idempotent stage-B wiring (task book §8.1, §7.7): root folders, native
qBittorrent download client + remote path mapping, recycle bin / unmonitor
settings in Sonarr and Radarr, and Sonarr/Radarr apps in Prowlarr.
Keys come from D:\\My Media\\.env. Prints only what it changed."""
import json
import os
import urllib.request

ENV = r"D:\My Media\.env"
for line in open(ENV, encoding="utf-8"):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ.setdefault(k, v)

QB_HOST, QB_PORT = "host.docker.internal", 8090
REMOTE, LOCAL = "Z:\\LER-MEDIA\\downloads\\", "/data/downloads/"
APPS = {
    "sonarr": dict(port=8989, root="/data/media/tv", category="tv-sonarr", catfield="tvCategory",
                   media_cfg="/config/mediamanagement"),
    "radarr": dict(port=7878, root="/data/media/movies", category="radarr", catfield="movieCategory",
                   media_cfg="/config/mediamanagement"),
}


def api(app, port, path, method="GET", body=None, ver="v3"):
    req = urllib.request.Request(
        f"http://localhost:{port}/api/{ver}{path}", method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"X-Api-Key": os.environ[f"{app.upper()}_API_KEY"], "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


def setfield(fields, name, value):
    for f in fields:
        if f["name"] == name:
            f["value"] = value


for app, c in APPS.items():
    p = c["port"]
    if not any(r["path"].rstrip("/") == c["root"] for r in api(app, p, "/rootfolder")):
        api(app, p, "/rootfolder", "POST", {"path": c["root"]})
        print(f"{app}: root folder {c['root']}")

    if not any(d["implementation"] == "QBittorrent" for d in api(app, p, "/downloadclient")):
        schema = next(s for s in api(app, p, "/downloadclient/schema") if s["implementation"] == "QBittorrent")
        setfield(schema["fields"], "host", QB_HOST)
        setfield(schema["fields"], "port", QB_PORT)
        setfield(schema["fields"], c["catfield"], c["category"])
        schema.update(name="qBittorrent (native)", enable=True, priority=1,
                      removeCompletedDownloads=False, removeFailedDownloads=False)
        api(app, p, "/downloadclient", "POST", schema)
        print(f"{app}: download client qBittorrent {QB_HOST}:{QB_PORT} category={c['category']}")

    if not any(m["remotePath"] == REMOTE for m in api(app, p, "/remotepathmapping")):
        api(app, p, "/remotepathmapping", "POST", {"host": QB_HOST, "remotePath": REMOTE, "localPath": LOCAL})
        print(f"{app}: remote path mapping {REMOTE} -> {LOCAL}")

    mm = api(app, p, c["media_cfg"])
    want = {"recycleBin": "/data/.recycle", "recycleBinCleanupDays": 0}
    want["autoUnmonitorPreviouslyDownloadedEpisodes" if app == "sonarr" else "autoUnmonitorPreviouslyDownloadedMovies"] = True
    if any(mm.get(k) != v for k, v in want.items()):
        mm.update(want)
        api(app, p, c["media_cfg"], "PUT", mm)
        print(f"{app}: media management {want}")

# Prowlarr -> Sonarr/Radarr (full sync), addressed by compose service name.
existing = {a["implementation"] for a in api("prowlarr", 9696, "/applications", ver="v1")}
for app, c in APPS.items():
    impl = app.capitalize()
    if impl in existing:
        continue
    schema = next(s for s in api("prowlarr", 9696, "/applications/schema", ver="v1") if s["implementation"] == impl)
    setfield(schema["fields"], "prowlarrUrl", "http://prowlarr:9696")
    setfield(schema["fields"], "baseUrl", f"http://{app}:{c['port']}")
    setfield(schema["fields"], "apiKey", os.environ[f"{app.upper()}_API_KEY"])
    schema.update(name=impl, syncLevel="fullSync")
    api("prowlarr", 9696, "/applications", "POST", schema, ver="v1")
    print(f"prowlarr: app {impl} (fullSync)")

print("done")
