#!/usr/bin/env python3
"""In-memory stand-in for the Hetzner Cloud API, used by molecule mock-api.

Only what the role's modules call is modelled, with the conflict rules that
matter for ordering (assigned IPs and in-use firewalls cannot be deleted).
Every request is logged; the test harness reads and resets state through:

  GET  /__mock/log    -> {"requests": ["METHOD /path?query", ...]}
  GET  /__mock/state  -> {"<collection>": [{...}, ...]}
  POST /__mock/reset  -> body {"seed": {"<collection>": [{...}, ...]}}

Usage: mock_hcloud.py <port>   (binds 127.0.0.1 only)
"""

import copy
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

TS = "2026-01-01T00:00:00+00:00"
LOCATIONS = [
    {"id": i, "name": n, "description": n, "country": "DE", "city": n,
     "latitude": 0.0, "longitude": 0.0, "network_zone": "eu-central"}
    for i, n in enumerate(["fsn1", "nbg1", "hel1"], start=1)
]
SERVER_TYPES = [
    {"id": i, "name": n, "description": n, "cores": 2, "memory": 4.0,
     "disk": 40, "prices": [], "storage_type": "local", "cpu_type": "shared",
     "architecture": "x86", "deprecated": False, "deprecation": None,
     "locations": [{"id": loc["id"], "name": loc["name"], "deprecation": None,
                    "available": True, "recommended": True}
                   for loc in LOCATIONS]}
    for i, n in enumerate(["cx23", "cx33", "cx43"], start=1)
]
IMAGES = [{"id": 1, "type": "system", "status": "available", "name": "debian-12",
           "description": "Debian 12", "os_flavor": "debian", "os_version": "12",
           "architecture": "x86", "rapid_deploy": True, "deprecated": None,
           "deprecation": None, "protection": {"delete": False}, "labels": {},
           "created": TS, "disk_size": 5, "image_size": None,
           "created_from": None, "bound_to": None}]
LB_TYPES = [{"id": 1, "name": "lb11", "description": "LB11", "max_connections": 10000,
             "max_services": 5, "max_targets": 25, "max_assigned_certificates": 10,
             "prices": [], "deprecated": None}]
STATIC = {"locations": LOCATIONS, "server_types": SERVER_TYPES,
          "images": IMAGES, "load_balancer_types": LB_TYPES}
SINGULAR = {"ssh_keys": "ssh_key", "networks": "network", "firewalls": "firewall",
            "placement_groups": "placement_group", "servers": "server",
            "primary_ips": "primary_ip", "floating_ips": "floating_ip",
            "volumes": "volume", "load_balancers": "load_balancer"}

STATE = {"next_id": 100, "log": [], "res": {k: [] for k in SINGULAR}}


def new_id():
    STATE["next_id"] += 1
    return STATE["next_id"]


def action(command="mock"):
    return {"id": new_id(), "command": command, "status": "success", "progress": 100,
            "started": TS, "finished": TS, "resources": [], "error": None}


def by_name(collection, name):
    pool = STATIC.get(collection) or STATE["res"][collection]
    for obj in pool:
        if obj["name"] == name or str(obj["id"]) == str(name):
            return obj
    return None


def by_id(collection, oid):
    pool = STATIC.get(collection) or STATE["res"][collection]
    return next((o for o in pool if str(o["id"]) == str(oid)), None)


def ref(collection, value):
    """Resolve a create-body reference (id, name or {"id"/"name": ...})."""
    if isinstance(value, dict):
        value = value.get("id", value.get("name"))
    return by_name(collection, value)


def ipv4():
    return "203.0.113.%d" % (STATE["next_id"] % 250 + 1)


def build(col, body):
    """Return a full API object for a create body (also used for seeds)."""
    oid = body.get("id") or new_id()
    base = {"id": oid, "name": body.get("name"), "labels": body.get("labels") or {},
            "created": TS, "protection": {"delete": False}}
    loc = ref("locations", body.get("location") or body.get("home_location") or "fsn1")
    if col == "ssh_keys":
        base.update(public_key=body.get("public_key"), fingerprint="00:11:%d" % oid)
    elif col == "networks":
        base.update(ip_range=body.get("ip_range"), subnets=body.get("subnets") or [],
                    routes=[], servers=[], load_balancers=[],
                    expose_routes_to_vswitch=bool(body.get("expose_routes_to_vswitch")))
    elif col == "firewalls":
        base.update(rules=body.get("rules") or [], applied_to=[])
        for res in body.get("apply_to") or []:
            base["applied_to"].append(res)
    elif col == "placement_groups":
        base.update(type=body.get("type", "spread"), servers=[])
    elif col == "servers":
        net = body.get("public_net") or {}
        st = ref("server_types", body.get("server_type") or "cx23")
        pg = ref("placement_groups", body.get("placement_group")) if body.get("placement_group") else None
        base.update(status="running", server_type=st, location=loc, image=IMAGES[0], iso=None,
                    rescue_enabled=False, locked=False, backup_window=None,
                    outgoing_traffic=0, ingoing_traffic=0, included_traffic=0,
                    protection={"delete": False, "rebuild": False}, volumes=[],
                    private_net=[], primary_disk_size=40, load_balancers=[],
                    placement_group=pg,
                    public_net={"ipv4": ({"id": new_id(), "ip": ipv4(), "blocked": False,
                                          "dns_ptr": "static.example"}
                                         if net.get("enable_ipv4", True) else None),
                                "ipv6": None, "floating_ips": [], "firewalls": []})
        if pg:
            pg["servers"].append(oid)
        for fw in body.get("firewalls") or []:
            fobj = ref("firewalls", fw.get("firewall") if isinstance(fw, dict) else fw)
            base["public_net"]["firewalls"].append({"id": fobj["id"], "status": "applied"})
            fobj["applied_to"].append({"type": "server", "server": {"id": oid}})
        for name in body.get("networks") or []:
            attach_network(base, ref("networks", name), None, [])
    elif col == "primary_ips":
        base.update(ip=ipv4(), type=body.get("type", "ipv4"), assignee_id=body.get("assignee_id"),
                    assignee_type="server", auto_delete=bool(body.get("auto_delete")),
                    blocked=False, dns_ptr=[], location=loc)
    elif col == "floating_ips":
        base.update(description=body.get("description"), ip=ipv4(), type=body.get("type", "ipv4"),
                    server=body.get("server"), dns_ptr=[], home_location=loc, blocked=False)
    elif col == "volumes":
        base.update(size=body.get("size"), server=body.get("server"), location=loc,
                    linux_device="/dev/disk/by-id/scsi-0HC_Volume_%d" % oid,
                    status="available", format=body.get("format"))
    elif col == "load_balancers":
        base.update(public_net={"enabled": True, "ipv4": {"ip": ipv4(), "dns_ptr": None},
                                "ipv6": {"ip": None, "dns_ptr": None}},
                    private_net=[], location=loc,
                    load_balancer_type=ref("load_balancer_types", body.get("load_balancer_type") or "lb11"),
                    targets=body.get("targets") or [], services=body.get("services") or [],
                    algorithm=body.get("algorithm") or {"type": "round_robin"},
                    outgoing_traffic=0, ingoing_traffic=0, included_traffic=0)
    for key, value in (body.get("set") or {}).items():
        base[key] = value
    if col == "load_balancers":
        base["services"] = [lb_service(svc) for svc in base["services"]]
    return base


def lb_service(svc):
    port = svc.get("destination_port") or svc.get("listen_port")
    full = {"protocol": "tcp", "listen_port": port, "destination_port": port,
            "proxyprotocol": False, "http": None,
            "health_check": {"protocol": "tcp", "port": port, "interval": 15,
                             "timeout": 10, "retries": 3, "http": None}}
    full.update(svc)
    return full


def attach_network(server, network, ip, alias_ips):
    ip = ip or "10.0.1.%d" % (len(network["servers"]) + 10)
    server["private_net"].append({"network": network["id"], "ip": ip,
                                  "alias_ips": alias_ips or [], "mac_address": "86:00:00:00:00:01"})
    network["servers"].append(server["id"])


def run_action(col, obj, name, body):
    """Apply the state change of POST /<col>/<id>/actions/<name>."""
    if col == "floating_ips" and name == "assign":
        obj["server"] = body.get("server")
    elif col == "floating_ips" and name == "unassign":
        obj["server"] = None
    elif col == "networks" and name == "add_subnet":
        sub = dict(body, gateway=body["ip_range"].split("/")[0])
        obj["subnets"].append(sub)
    elif col == "networks" and name == "delete_subnet":
        obj["subnets"] = [s for s in obj["subnets"] if s["ip_range"] != body.get("ip_range")]
    elif col == "servers" and name == "attach_to_network":
        attach_network(obj, by_id("networks", body["network"]), body.get("ip"), body.get("alias_ips"))
    elif col == "servers" and name == "detach_from_network":
        obj["private_net"] = [p for p in obj["private_net"] if p["network"] != body["network"]]
        net = by_id("networks", body["network"])
        if net:
            net["servers"] = [s for s in net["servers"] if s != obj["id"]]
    elif col == "firewalls" and name == "apply_to_resources":
        obj["applied_to"].extend(body.get("apply_to") or [])
        return {"actions": [action(name)]}
    elif col == "firewalls" and name == "remove_from_resources":
        gone = body.get("remove_from") or []
        obj["applied_to"] = [a for a in obj["applied_to"] if a not in gone]
        for srv in STATE["res"]["servers"]:
            srv["public_net"]["firewalls"] = [f for f in srv["public_net"]["firewalls"]
                                              if f["id"] != obj["id"] or
                                              {"type": "server", "server": {"id": srv["id"]}} not in gone]
        return {"actions": [action(name)]}
    elif col == "firewalls" and name == "set_rules":
        obj["rules"] = body.get("rules") or []
        return {"actions": [action(name)]}
    elif col == "volumes" and name == "attach":
        obj["server"] = body.get("server")
    elif col == "volumes" and name == "detach":
        obj["server"] = None
    elif col == "load_balancers" and name == "attach_to_network":
        obj["private_net"].append({"network": body["network"], "ip": body.get("ip") or "10.0.1.250"})
    elif col == "load_balancers" and name == "add_service":
        obj["services"].append(lb_service(body))
    elif col == "load_balancers" and name == "delete_service":
        obj["services"] = [s for s in obj["services"] if s.get("listen_port") != body.get("listen_port")]
    elif col == "load_balancers" and name == "add_target":
        obj["targets"].append(body)
    return {"action": action(name)}


def delete(col, obj):
    """Hetzner refuses to delete assigned IPs and firewalls still in use."""
    if col in ("floating_ips", "primary_ips") and (obj.get("server") or obj.get("assignee_id")):
        return 422, {"error": {"code": "must_be_unassigned", "message": "IP is still assigned", "details": {}}}
    if col == "firewalls" and obj["applied_to"]:
        return 422, {"error": {"code": "resource_in_use", "message": "firewall is still in use", "details": {}}}
    STATE["res"][col].remove(obj)
    if col == "servers":
        for fw in STATE["res"]["firewalls"]:
            fw["applied_to"] = [a for a in fw["applied_to"] if a.get("server", {}).get("id") != obj["id"]]
        for net in STATE["res"]["networks"]:
            net["servers"] = [s for s in net["servers"] if s != obj["id"]]
        for pg in STATE["res"]["placement_groups"]:
            pg["servers"] = [s for s in pg["servers"] if s != obj["id"]]
        for fip in STATE["res"]["floating_ips"]:
            if fip["server"] == obj["id"]:
                fip["server"] = None
        return 200, {"action": action("delete_server")}
    if col == "load_balancers":
        return 200, {"action": action("delete_load_balancer")}
    return 204, None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body=None):
        data = json.dumps(body).encode() if body is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def not_found(self):
        self.send(404, {"error": {"code": "not_found", "message": "not found", "details": {}}})

    def handle_any(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}") if length else {}
        url = urlparse(self.path)
        parts = url.path.strip("/").split("/")
        if parts[0] == "__mock":
            if parts[1] == "reset":
                STATE["res"] = {k: [] for k in SINGULAR}
                STATE["log"] = []
                for col, items in (body.get("seed") or {}).items():
                    for item in items:
                        STATE["res"][col].append(build(col, item))
                return self.send(200, {"ok": True})
            if parts[1] == "state":
                return self.send(200, STATE["res"])
            return self.send(200, {"requests": STATE["log"]})
        STATE["log"].append("%s %s" % (method, self.path))
        col = parts[0]
        meta = {"pagination": {"page": 1, "per_page": 50, "previous_page": None,
                               "next_page": None, "last_page": 1, "total_entries": 0}}
        if col == "actions":
            return self.send(200, {"action": action()})
        if col not in SINGULAR and col not in STATIC:
            return self.not_found()
        pool = STATIC.get(col) or STATE["res"][col]
        single = SINGULAR.get(col, col[:-1])
        if len(parts) == 1 and method == "GET":
            query = parse_qs(url.query)
            items = [o for o in pool if "name" not in query or o["name"] == query["name"][0]]
            return self.send(200, {col: copy.deepcopy(items), "meta": meta})
        if len(parts) == 1 and method == "POST":
            obj = build(col, body)
            STATE["res"][col].append(obj)
            resp = {single: obj, "action": action("create"), "next_actions": [],
                    "actions": [], "root_password": None}
            return self.send(201, resp)
        obj = by_id(col, parts[1])
        if obj is None:
            return self.not_found()
        if len(parts) == 2 and method == "GET":
            return self.send(200, {single: obj})
        if len(parts) == 2 and method == "PUT":
            obj.update({k: v for k, v in body.items() if k in ("name", "labels", "description")})
            return self.send(200, {single: obj})
        if len(parts) == 2 and method == "DELETE":
            code, resp = delete(col, obj)
            return self.send(code, resp)
        if len(parts) == 4 and parts[2] == "actions" and method == "POST":
            return self.send(201, run_action(col, obj, parts[3], body))
        if len(parts) == 4 and parts[2] == "actions" and method == "GET":
            return self.send(200, {"action": action()})
        return self.not_found()

    def do_GET(self):
        self.handle_any("GET")

    def do_POST(self):
        self.handle_any("POST")

    def do_PUT(self):
        self.handle_any("PUT")

    def do_DELETE(self):
        self.handle_any("DELETE")


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
