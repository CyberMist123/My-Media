"""arr-cli: Fable's command-line door into the media stack (replaces arr-mcp).

Read-only by default; the only write is creating a Seerr request.
There are deliberately no delete/remove commands (task book §13).
Config comes from env vars, falling back to D:\\My Media\\.env. Output is JSON.
"""
import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

ENV_FILE = r"D:\My Media\.env"


def load_env():
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"'))


def cfg(name, default=None):
    v = os.environ.get(name, default)
    if v is None:
        die(f"missing config {name} (env or {ENV_FILE})")
    return v


class CliError(Exception):
    pass


def die(msg):
    raise CliError(msg)


def call(base, path, key=None, method="GET", body=None, headers=None, opener=None, form=False):
    url = base.rstrip("/") + path
    h = dict(headers or {})
    if key:
        h["X-Api-Key"] = key
    data = None
    if body is not None:
        if form:
            data = urllib.parse.urlencode(body).encode()
            h["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with (opener or urllib.request.build_opener()).open(req, timeout=20) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        die(f"{method} {url} -> HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    except urllib.error.URLError as e:
        die(f"{method} {url} -> {e.reason}")
    try:
        return json.loads(raw)
    except ValueError:
        return raw


# --- services -------------------------------------------------------------

def seerr(path, method="GET", body=None):
    # Requests run as the dedicated non-admin Fable user via X-Api-User.
    hdr = {"X-Api-User": cfg("SEERR_FABLE_USER_ID")} if method != "GET" else None
    return call(cfg("SEERR_URL", "http://localhost:5055"), "/api/v1" + path,
                cfg("SEERR_API_KEY"), method, body, hdr)


def arr(app, path, method="GET", body=None):
    port = {"sonarr": 8989, "radarr": 7878, "prowlarr": 9696}[app]
    ver = "v1" if app == "prowlarr" else "v3"
    up = app.upper()
    return call(cfg(f"{up}_URL", f"http://localhost:{port}"), f"/api/{ver}{path}",
                cfg(f"{up}_API_KEY"), method, body)


def qb(path):
    base = cfg("QB_URL", "http://localhost:8090")
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    user = os.environ.get("QB_USER")
    if user:
        res = call(base, "/api/v2/auth/login", method="POST", form=True, opener=opener,
                   body={"username": user, "password": cfg("QB_PASS")},
                   headers={"Referer": base})
        if res != "Ok.":
            die(f"qBittorrent login failed: {res}")
    return call(base, "/api/v2" + path, opener=opener)


# --- commands ------------------------------------------------------------

def cmd_status(a):
    out = {}
    for name, fn in [("seerr", lambda: seerr("/status")),
                     ("sonarr", lambda: arr("sonarr", "/system/status")),
                     ("radarr", lambda: arr("radarr", "/system/status")),
                     ("prowlarr", lambda: arr("prowlarr", "/system/status")),
                     ("qbittorrent", lambda: qb("/app/version"))]:
        try:
            r = fn()
            out[name] = {"ok": True, "version": r.get("version") if isinstance(r, dict) else r}
        except CliError as e:
            out[name] = {"ok": False, "error": str(e)}
    return out


def cmd_search(a):
    q = urllib.parse.quote(a.query, safe="")
    res = seerr(f"/search?query={q}&page=1&language=zh")
    return [{"mediaType": r.get("mediaType"), "tmdbId": r.get("id"),
             "title": r.get("title") or r.get("name"),
             "original": r.get("originalTitle") or r.get("originalName"),
             "year": (r.get("releaseDate") or r.get("firstAirDate") or "")[:4],
             "inLibrary": (r.get("mediaInfo") or {}).get("status")}
            for r in res.get("results", []) if r.get("mediaType") in ("movie", "tv")]


def cmd_request(a):
    body = {"mediaType": a.type, "mediaId": a.tmdb_id}
    if a.type == "tv":
        body["seasons"] = "all" if a.seasons == "all" else [int(s) for s in a.seasons.split(",")]
    if a.dry_run:
        return {"dryRun": True, "wouldPost": body}
    r = seerr("/request", "POST", body)
    return {"requestId": r.get("id"), "status": r.get("status"), "media": r.get("media", {}).get("tmdbId")}


def cmd_requests(a):
    r = seerr(f"/request?take={a.take}&sort=added")
    return [{"id": x.get("id"), "type": x.get("type"), "status": x.get("status"),
             "tmdbId": (x.get("media") or {}).get("tmdbId"),
             "mediaStatus": (x.get("media") or {}).get("status")} for x in r.get("results", [])]


def cmd_queue(a):
    out = []
    for app in ("sonarr", "radarr"):
        for x in arr(app, "/queue?pageSize=50").get("records", []):
            out.append({"app": app, "title": x.get("title"), "status": x.get("status"),
                        "trackedState": x.get("trackedDownloadState"),
                        "left": x.get("sizeleft"), "size": x.get("size"),
                        "messages": [m.get("title") for m in x.get("statusMessages", [])]})
    return out


def cmd_torrents(a):
    return [{"name": t["name"], "state": t["state"], "progress": round(t["progress"], 3),
             "size": t["size"], "savePath": t["save_path"]} for t in qb("/torrents/info")]


def cmd_space(a):
    root = cfg("MEDIA_ROOT", "M:\\")
    u = shutil.disk_usage(root)
    return {"root": root, "total": u.total, "used": u.used, "free": u.free}


def main():
    # PowerShell 5.1 / cmd default to the ANSI code page; force UTF-8 so
    # Chinese titles never raise UnicodeEncodeError and JSON stays valid.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    load_env()
    p = argparse.ArgumentParser(prog="arr", description="Fable media-stack CLI (no delete commands)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="health/version of every service")
    s = sub.add_parser("search", help="search movies/TV via Seerr")
    s.add_argument("query")
    r = sub.add_parser("request", help="request a movie/TV show via Seerr as the Fable user")
    r.add_argument("type", choices=["movie", "tv"])
    r.add_argument("tmdb_id", type=int)
    r.add_argument("--seasons", default="all", help="'all' or e.g. 1,2 (tv only)")
    r.add_argument("--dry-run", action="store_true", help="show what would be posted")
    q = sub.add_parser("requests", help="recent Seerr requests")
    q.add_argument("--take", type=int, default=20)
    sub.add_parser("queue", help="Sonarr/Radarr download queue")
    sub.add_parser("torrents", help="qBittorrent torrents (read-only)")
    sub.add_parser("space", help="media volume capacity")
    a = p.parse_args()
    try:
        result = globals()["cmd_" + a.cmd](a)
    except CliError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(2)
    print(json.dumps({"ok": True, "data": result}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
