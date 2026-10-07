#!/usr/bin/env python3
"""Load a list of classes into the class database through the local sign-up service (iits-portal-reg).

Goes through the same /classes/save call the portal's admin screen uses, so every class is validated,
gets its own join code and is written to the audit log under the named admin.
Classes that already exist (same start date + name) are reported and skipped.

usage: python3 tools/seed_classes.py data/classes-2026-autumn-hkbuas.json --as bernard [--port 8794]
"""
import argparse, json, urllib.error, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("file")
ap.add_argument("--as", dest="admin", required=True, help="an admin teacher's username (recorded in the audit log)")
ap.add_argument("--port", type=int, default=8794)
a = ap.parse_args()


def call(method, path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{a.port}{path}", method=method,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"X-Portal-Realm": "teacher", "X-Auth-User": a.admin,
                                          "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=15)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


s, j = call("GET", "/classes")
if s != 200 or not j.get("me", {}).get("admin"):
    raise SystemExit(f"{a.admin} is not an admin teacher ({s}: {j.get('error')})")
have = {(c["start_date"], c["name"]) for c in j["classes"]}
for c in json.load(open(a.file))["classes"]:
    start = c["sessions"][0]["date"] if c.get("sessions") else c.get("start_date")
    if (start, c["name"]) in have:
        print(f"  skip    {start} · {c['name']} (already there)")
        continue
    s, j = call("POST", "/classes/save", c)
    print(f"  {'added' if s == 200 else 'FAILED':7} {start} · {c['name']}  {j.get('id') or j.get('error')}")
