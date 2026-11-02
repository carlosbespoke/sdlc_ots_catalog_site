"""livesvc grader library: observe live platform services (Vault, PostgreSQL) behaviourally, run Terraform as an
unprivileged user, static gates over HCL, and comparison of observations. Generic over tasks of the livesvc family:
nothing here knows a task's model; the spec (spec.json) and the reference solution define what is expected.

An observation is a flat dict {check_id: {fact: value}}: every fact of one object lives under one check id
("vault.policy:prod-api", "pg.table:medlink_prod.billing.invoices", ...). Two observations are compared check by
check; a check passes when all its facts are equal. Facts are behavioural where the services allow it (capabilities
of a policy on concrete paths, a real AppRole login, real dynamic database credentials and their effective
privileges, privileges of a table created by the schema owner) and never contain run-specific values (ids,
accessors, generated user names, timestamps).
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

VAULT = "http://127.0.0.1:8200"
PG_HOST, PG_PORT = "127.0.0.1", 5432
DYNAMIC_ROLE = re.compile(r"^v-")          # roles Vault's postgresql plugin creates for dynamic credentials
SYSTEM_MOUNTS = {"sys/", "cubbyhole/", "identity/"}


def log(msg):
    print(f"[grade] {msg}", flush=True)


class ObserveError(Exception):
    """An observation query failed: a grader or infrastructure problem, never a property of the submission."""


# ---- Vault HTTP -------------------------------------------------------------------------------------------------------
def vault(method, path, body=None, token=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{VAULT}/v1/{path.lstrip('/')}", data=data, method=method)
    if token:
        req.add_header("X-Vault-Token", token)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, (json.loads(raw) if raw.strip() else {})
        except ValueError:
            return e.code, {"errors": [raw.decode(errors="replace")[:300]]}
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        return 0, {"errors": [str(e)[:300]]}


class Vault:
    def __init__(self, token):
        self.token = token

    def get(self, path, ok=(200,)):
        code, body = vault("GET", path, token=self.token)
        return body if code in ok else None

    def strict(self, path):
        """GET that must succeed (the object was just listed or is a system endpoint)."""
        code, body = vault("GET", path, token=self.token)
        if code != 200:
            raise ObserveError(f"vault GET {path} -> {code}: {str(body)[:300]}")
        return body

    def list(self, path):
        code, body = vault("LIST", path, token=self.token)
        return sorted((body.get("data") or {}).get("keys") or []) if code == 200 else []

    def write(self, method, path, body=None):
        return vault(method, path, body, token=self.token)


# ---- Grafana HTTP -----------------------------------------------------------------------------------------------------
GRAFANA = "http://127.0.0.1:3000"


def grafana(method, path, body=None, user="admin", password=None, timeout=30):
    import base64
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{GRAFANA}/{path.lstrip('/')}", data=data, method=method)
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode())
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, (json.loads(raw) if raw.strip() else {})
        except ValueError:
            return e.code, {"message": raw.decode(errors="replace")[:300]}
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        return 0, {"message": str(e)[:300]}


DURATION = re.compile(r"(\d+)(ms|s|m|h|d|w|y)")
UNIT = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "y": 31536000}


def seconds(v):
    """Alertmanager/Grafana durations ("1h30m", "5m") as seconds; None stays None."""
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return v
    return sum(int(n) * UNIT[u] for n, u in DURATION.findall(str(v)))


def matcher_ok(m, labels):
    name, op, value = m
    have = labels.get(name, "")
    if op == "=":
        return have == value
    if op == "!=":
        return have != value
    rx = re.fullmatch(f"(?:{value})", have) is not None
    return rx if op == "=~" else not rx


def route_matchers(node):
    out = [tuple(m) for m in node.get("object_matchers") or []]
    for k, v in (node.get("match") or {}).items():
        out.append((k, "=", v))
    for k, v in (node.get("match_re") or {}).items():
        out.append((k, "=~", v))
    for m in node.get("matchers") or []:
        mm = re.match(r'\s*([^=!~\s]+)\s*(=~|!~|!=|=)\s*"?(.*?)"?\s*$', m)
        if mm:
            out.append((mm.group(1), mm.group(2), mm.group(3)))
    return out


def route_alert(tree, labels):
    """Alertmanager routing: the list of matched leaves with their effective settings, in order."""
    defaults = {"group_by": tree.get("group_by") or ["grafana_folder", "alertname"],
                "group_wait": seconds(tree.get("group_wait")) or 30,
                "group_interval": seconds(tree.get("group_interval")) or 300,
                "repeat_interval": seconds(tree.get("repeat_interval")) or 14400,
                "receiver": tree.get("receiver")}

    def walk(node, parent):
        eff = {"receiver": node.get("receiver") or parent["receiver"],
               "group_by": node.get("group_by") if node.get("group_by") is not None else parent["group_by"],
               "group_wait": seconds(node.get("group_wait")) or parent["group_wait"],
               "group_interval": seconds(node.get("group_interval")) or parent["group_interval"],
               "repeat_interval": seconds(node.get("repeat_interval")) or parent["repeat_interval"]}
        found = []
        for child in node.get("routes") or []:
            if all(matcher_ok(m, labels) for m in route_matchers(child)):
                found += walk(child, eff)
                if not child.get("continue"):
                    break
        if not found:
            found = [{**eff, "group_by": sorted(eff["group_by"] or []),
                      "mute": sorted(node.get("mute_time_intervals") or []),
                      "active": sorted(node.get("active_time_intervals") or [])}]
        return found

    return walk(tree, defaults)


def expand_probes(spec_probes, inventory):
    """Route probe label sets from the spec template over the current inventory."""
    import itertools
    out = []
    for p in spec_probes or []:
        items = (inventory.get(p["each"]) or {}).items() if p.get("each") else [(None, {})]
        for key, item in sorted(items):
            base = {}
            for k, v in p.get("labels", {}).items():
                base[k] = key if v == "@key" else (str(item.get(v[1:], "")) if isinstance(v, str) and v.startswith("@") else v)
            vary = p.get("vary", {})
            names = sorted(vary)
            for combo in itertools.product(*(vary[n] for n in names)):
                out.append({**base, **dict(zip(names, combo))})
    return out


# ---- PostgreSQL -------------------------------------------------------------------------------------------------------
def qi(name):
    """A PostgreSQL identifier, quoted: names come from the submission (model-controlled), so a double quote is doubled
    and control characters are refused; never splice a raw name into SQL."""
    name = str(name)
    if any(ord(ch) < 32 for ch in name):
        raise ObserveError(f"refusing an identifier with control characters: {name!r}")
    return "\"" + name.replace("\"", "\"\"") + "\""


def ql(value):
    """A PostgreSQL string literal, quoted (single quotes doubled)."""
    return "'" + str(value).replace("'", "''") + "'"


def psql_json(sql, db="postgres", user="postgres", password=None, timeout=120):
    """Run one query returning a single json value; returns (ok, value_or_error)."""
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PGPASSWORD": password or "", "PGCONNECT_TIMEOUT": "10"}
    p = subprocess.run(["psql", "-X", "-q", "-At", "-v", "ON_ERROR_STOP=1", "-h", PG_HOST, "-p", str(PG_PORT), "-U", user,
                        "-d", db, "-c", sql], capture_output=True, text=True, env=env, timeout=timeout,
                       stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        return False, (p.stderr or p.stdout).strip()[-400:]
    out = p.stdout.strip()
    try:
        return True, (json.loads(out) if out else None)
    except ValueError:
        return False, f"unparsable psql output: {out[:200]}"


def psql_exec(sql, db="postgres", password=None, timeout=120):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PGPASSWORD": password or "", "PGCONNECT_TIMEOUT": "10"}
    p = subprocess.run(["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-h", PG_HOST, "-p", str(PG_PORT), "-U", "postgres",
                        "-d", db, "-c", sql], capture_output=True, text=True, env=env, timeout=timeout,
                       stdin=subprocess.DEVNULL)
    return p.returncode == 0, (p.stderr or "").strip()[-400:]


def pg_can_login(user, password, db):
    ok, val = psql_json("select json_build_object('u', current_user)", db=db, user=user, password=password, timeout=30)
    return ok


# ---- helpers ----------------------------------------------------------------------------------------------------------
def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]


def norm_list(v):
    return sorted(v) if isinstance(v, list) else ([] if v in (None, "") else v)


def instantiate(pattern):
    """Concrete paths that exercise one policy path pattern (Vault globs: a trailing * and + segments)."""
    p = pattern.strip()
    p = "/".join("probe" if seg == "+" else seg for seg in p.split("/"))
    if p.endswith("*"):
        stem = p[:-1]
        out = {stem + "probe", stem + "probe/deep"}
        if stem.endswith("/"):
            out.add(stem)
        return out
    return {p}


POLICY_PATH = re.compile(r'path\s+"([^"]+)"')


def policy_patterns(text):
    return set(POLICY_PATH.findall(text or ""))


# ======================================================================================================================
# Observation
# ======================================================================================================================
class Observer:
    """Reads the live services. `spec_obs` (spec["observe"]) may list extra probe paths and databases to skip."""

    def __init__(self, vault_token, pg_password, spec_obs, credentials):
        self.v = Vault(vault_token)
        self.pgpw = pg_password
        self.cfg = spec_obs or {}
        self.creds = credentials or {}
        self.obs = {}
        self.policy_texts = {}

    def put(self, check, fact, value):
        self.obs.setdefault(check, {})[fact] = value

    # ---- vault ----------------------------------------------------------------------------------------------------
    def observe_vault(self):
        mounts = (self.v.strict("sys/mounts") or {}).get("data") or {}
        self.mounts = {}
        for path, m in sorted(mounts.items()):
            if path in SYSTEM_MOUNTS:
                continue
            opts = m.get("options") or {}
            kind = m.get("type")
            version = str(opts.get("version", "1")) if kind in ("kv", "generic") else None
            self.mounts[path.rstrip("/")] = {"type": kind, "version": version}
            self.put(f"vault.mount:{path.rstrip('/')}", "type", kind if version is None else f"{kind}-v{version}")
        auths = (self.v.strict("sys/auth") or {}).get("data") or {}
        self.auths = {p.rstrip("/"): a.get("type") for p, a in auths.items()}
        for p, t in sorted(self.auths.items()):
            if p != "token":
                self.put(f"vault.auth:{p}", "type", t)
        audits = (self.v.strict("sys/audit") or {}).get("data") or {}
        for p, a in sorted(audits.items()):
            opts = a.get("options") or {}
            self.put(f"vault.audit:{p.rstrip('/')}", "device", {"type": a.get("type"), "file_path": opts.get("file_path"),
                                                               "log_raw": str(opts.get("log_raw", "false")).lower()})
        self._policies()
        self._kv()
        self._transit()
        self._identity()
        for path, t in sorted(self.auths.items()):
            if t == "approle":
                self._approle(path)
            elif t == "userpass":
                self._userpass(path)
        for path, m in sorted(self.mounts.items()):
            if m["type"] == "database":
                self._database(path)

    def _policies(self):
        names = [n for n in self.v.list("sys/policies/acl") if n != "root"]
        for n in names:
            text = ((self.v.strict(f"sys/policies/acl/{n}") or {}).get("data") or {}).get("policy", "")
            self.policy_texts[n] = text
            self.put(f"vault.policy:{n}", "exists", True)

    def _kv(self):
        for mount, m in self.mounts.items():
            if m["type"] not in ("kv", "generic"):
                continue
            if m["version"] == "2":
                cfg = (self.v.strict(f"{mount}/config") or {}).get("data") or {}
                self.put(f"vault.kvconfig:{mount}", "config", {k: cfg.get(k) for k in
                                                               ("max_versions", "cas_required", "delete_version_after")})
            data = {}
            stack = [""]
            while stack:
                prefix = stack.pop()
                listing = self.v.list(f"{mount}/metadata/{prefix}" if m["version"] == "2" else f"{mount}/{prefix}")
                for k in listing:
                    if k.endswith("/"):
                        stack.append(prefix + k)
                        continue
                    key = prefix + k
                    if m["version"] == "2":
                        body = (self.v.strict(f"{mount}/data/{key}") or {}).get("data") or {}
                        meta = (self.v.strict(f"{mount}/metadata/{key}") or {}).get("data") or {}
                        data[key] = {"current": meta.get("current_version"), "oldest": meta.get("oldest_version"),
                                     "data": digest(body.get("data"))}
                    else:
                        data[key] = {"data": digest((self.v.get(f"{mount}/{key}") or {}).get("data"))}
            self.put("vault.kvdata", mount, digest(data))
            self.put("vault.kvdata", f"{mount}#keys", len(data))

    def _transit(self):
        for mount, m in self.mounts.items():
            if m["type"] != "transit":
                continue
            keys = {}
            for k in self.v.list(f"{mount}/keys"):
                d = (self.v.strict(f"{mount}/keys/{k}") or {}).get("data") or {}
                keys[k] = {f: d.get(f) for f in ("type", "latest_version", "min_decryption_version",
                                                 "min_encryption_version", "deletion_allowed", "exportable")}
            self.put(f"vault.transit:{mount}", "keys", keys)

    def _identity(self):
        self.entity_name = {}
        for n in self.v.list("identity/entity/name"):
            d = (self.v.strict(f"identity/entity/name/{n}") or {}).get("data") or {}
            self.entity_name[d.get("id")] = n
            self.put("vault.entities", n, {"metadata": d.get("metadata") or {}, "policies": norm_list(d.get("policies")),
                                           "disabled": bool(d.get("disabled")),
                                           "aliases": sorted((a.get("mount_path"), a.get("name")) for a in d.get("aliases") or [])})
        groups = {}
        for n in self.v.list("identity/group/name"):
            groups[n] = (self.v.strict(f"identity/group/name/{n}") or {}).get("data") or {}
        gname = {g.get("id"): n for n, g in groups.items()}
        for n, d in sorted(groups.items()):
            self.put(f"vault.group:{n}", "group", {
                "type": d.get("type"), "policies": norm_list(d.get("policies")),
                "members": sorted(self.entity_name.get(i, "?unknown-entity") for i in d.get("member_entity_ids") or []),
                "member_groups": sorted(gname.get(i, "?unknown-group") for i in d.get("member_group_ids") or [])})

    def _approle(self, path):
        build = {c["role"]: c for c in self.creds.get("approle", []) if c.get("mount", "approle") == path}
        roles = self.v.list(f"auth/{path}/role")
        fields = ("token_policies", "token_ttl", "token_max_ttl", "token_explicit_max_ttl", "token_period",
                  "token_num_uses", "token_no_default_policy", "token_type", "token_bound_cidrs", "secret_id_ttl",
                  "secret_id_num_uses", "secret_id_bound_cidrs", "bind_secret_id", "local_secret_ids")
        for r in roles:
            d = (self.v.strict(f"auth/{path}/role/{r}") or {}).get("data") or {}
            cfg = {f: (norm_list(d.get(f)) if isinstance(d.get(f), list) else d.get(f)) for f in fields}
            self.put(f"vault.approle:{r}", "config", cfg)
        # production clients: the credentials they hold today
        for r, c in sorted(build.items()):
            check = f"vault.client:{r}"
            rid = ((self.v.get(f"auth/{path}/role/{r}/role-id") or {}).get("data") or {}).get("role_id")
            self.put(check, "role_id_unchanged", rid == c["role_id"])
            code, body = vault("POST", f"auth/{path}/login", {"role_id": c["role_id"], "secret_id": c["secret_id"]})
            auth = body.get("auth") or {}
            # core (when the model keeps the role): the client still gets in with what it holds
            self.put(check, "login_ok", code == 200)
            # regular: what its token is (follows from the role's settings)
            if code == 200:
                self.put(f"vault.login:{r}", "token", {"policies": norm_list(auth.get("token_policies")),
                                                      "ttl": auth.get("lease_duration"), "type": auth.get("token_type"),
                                                      "num_uses": auth.get("num_uses")})
            if code == 200 and auth.get("token_type") != "batch":
                vault("POST", "auth/token/revoke-self", {}, token=auth.get("client_token"))

    def _userpass(self, path):
        build = {c["user"]: c["password"] for c in self.creds.get("userpass", []) if c.get("mount", "userpass") == path}
        for u in self.v.list(f"auth/{path}/users"):
            d = (self.v.strict(f"auth/{path}/users/{u}") or {}).get("data") or {}
            self.put(f"vault.user:{u}", "config", {f: (norm_list(d.get(f)) if isinstance(d.get(f), list) else d.get(f))
                                                   for f in ("token_ttl", "token_max_ttl", "token_policies",
                                                             "token_bound_cidrs", "token_type")})
        for u, pw in sorted(build.items()):
            code, body = vault("POST", f"auth/{path}/login/{u}", {"password": pw})
            auth = body.get("auth") or {}
            self.put(f"vault.human:{u}", "login", {"ok": code == 200, "token_policies": norm_list(auth.get("token_policies")),
                                                   "identity_policies": norm_list(auth.get("identity_policies"))}
                     if code == 200 else {"ok": False})
            if code == 200:
                vault("POST", "auth/token/revoke-self", {}, token=auth.get("client_token"))

    def _database(self, mount):
        self.db_conns = getattr(self, "db_conns", {})
        for c in self.v.list(f"{mount}/config"):
            d = (self.v.strict(f"{mount}/config/{c}") or {}).get("data") or {}
            det = d.get("connection_details") or {}
            url = det.get("connection_url") or ""
            m = re.search(r"/([^/?]+)(\?|$)", url.split("@")[-1]) if "@" in url else None
            self.db_conns[f"{mount}/{c}"] = m.group(1) if m else None
            self.put(f"vault.dbconn:{c}", "config", {
                "plugin": d.get("plugin_name"), "connection_url": url, "username": det.get("username"),
                "allowed_roles": norm_list(d.get("allowed_roles")), "password_policy": d.get("password_policy") or "",
                "root_rotation_statements": d.get("root_credentials_rotate_statements") or []})
        for r in self.v.list(f"{mount}/roles"):
            d = (self.v.strict(f"{mount}/roles/{r}") or {}).get("data") or {}
            check = f"vault.dbrole:{r}"
            self.put(check, "config", {"db_name": d.get("db_name"), "default_ttl": d.get("default_ttl"),
                                       "max_ttl": d.get("max_ttl"), "credential_type": d.get("credential_type")})
            self.put(check, "credentials", self._creds(mount, r, self.db_conns.get(f"{mount}/{d.get('db_name')}")))

    def _creds(self, mount, role, database):
        code, body = self.v.write("GET", f"{mount}/creds/{role}")
        if code != 200:
            return {"issued": False}
        user, pw = (body.get("data") or {}).get("username"), (body.get("data") or {}).get("password")
        out = {"issued": True, "lease": body.get("lease_duration")}
        if database:
            ok, val = psql_json(PRIV_SELF_SQL, db=database, user=user, password=pw, timeout=30)
            out["connect"] = ok
            if ok:
                out.update(val)
            others = []
            for db in self.databases:
                if db != database and db not in ("postgres",):
                    if pg_can_login(user, pw, db):
                        others.append(db)
            out["other_databases"] = sorted(others)
        self.v.write("PUT", "sys/leases/revoke", {"lease_id": body.get("lease_id")})
        ok, val = psql_json(f"select json_build_object('n', count(*)) from pg_roles where rolname = {ql(user)}")
        out["revoked"] = bool(ok and val and val.get("n") == 0)
        return out

    # ---- policy capabilities (needs the reference texts, so it runs at comparison time) -------------------------------
    def capabilities(self, texts_by_name, extra_paths):
        """{name: {path: caps}} for each policy text on its own instantiated paths plus extra_paths."""
        out = {}
        for name, (text, paths) in texts_by_name.items():
            shadow = f"zz-grader-{digest(text)}"
            if text is None:
                out[name] = None
                continue
            self.v.write("PUT", f"sys/policies/acl/{shadow}", {"policy": text})
            code, body = self.v.write("POST", "auth/token/create-orphan", {"policies": [shadow], "no_default_policy": True,
                                                                          "ttl": "10m", "display_name": "grader"})
            tok = (body.get("auth") or {}).get("client_token")
            plist = sorted(paths | set(extra_paths))
            code, caps = vault("POST", "sys/capabilities", {"token": tok, "paths": plist}, token=self.v.token)
            res = {}
            for p in plist:
                c = caps.get(p) if isinstance(caps, dict) else None
                if c is None and len(plist) == 1:
                    c = caps.get("capabilities")
                res[p] = sorted(c or [])
            out[name] = res
            vault("POST", "auth/token/revoke-orphan", {"token": tok}, token=self.v.token)
            self.v.write("DELETE", f"sys/policies/acl/{shadow}")
        return out

    # ---- postgres -------------------------------------------------------------------------------------------------
    def observe_pg(self):
        skip = set(self.cfg.get("skip_databases", []))
        ok, dbs = psql_json("select coalesce(json_agg(datname order by datname), '[]') from pg_database "
                            "where not datistemplate", password=self.pgpw)
        if not ok:
            raise ObserveError(f"listing databases failed: {dbs}")
        self.databases = [d for d in (dbs or []) if d not in skip]
        ok, roles = psql_json(ROLES_SQL, password=self.pgpw)
        if not ok:
            raise ObserveError(f"reading roles failed: {roles}")
        for r in roles or []:
            if DYNAMIC_ROLE.match(r["name"]):
                continue
            check = f"pg.role:{r['name']}"
            self.put(check, "attributes", {k: r[k] for k in ("super", "inherit", "createrole", "createdb", "login",
                                                            "replication", "bypassrls", "connlimit", "validuntil")})
            self.put(check, "member_of", r["member_of"])
        for db in self.databases:
            ok, val = psql_json(DB_SQL, db=db, password=self.pgpw)
            if not ok:
                raise ObserveError(f"reading database {db} failed: {val}")
            self.put(f"pg.db:{db}", "database", val["database"])
            self.put(f"pg.extensions:{db}", "names", val["extensions"])
            for s in val["schemas"]:
                self.put(f"pg.schema:{db}.{s['name']}", "schema", {"owner": s["owner"], "privileges": s["privileges"]})
            for t in val["relations"]:
                kind = "table" if t["kind"] in ("r", "p", "v", "m", "f") else "sequence"
                self.put(f"pg.{kind}:{db}.{t['schema']}.{t['name']}", "privileges", t["privileges"])
            self.put("pg.data", db, val["data"])
            self._default_privileges(db, [s for s in val["schemas"] if s["name"] != "public"])
        for c in self.creds.get("pg_logins", []):
            self.put(f"pg.login:{c['role']}", "login", pg_can_login(c["role"], c["password"], c.get("database", "postgres")))

    def _default_privileges(self, db, schemas):
        for s in schemas:
            q = (f"set role {qi(s['owner'])}; create table {qi(s['name'])}.zz_grader_probe (id bigserial primary key); "
                 f"reset role;")
            ok, err = psql_exec(q, db=db, password=self.pgpw)
            check = f"pg.defaults:{db}.{s['name']}"
            if not ok:
                self.put(check, "probe", {"error": "the schema owner cannot create a table"})
                continue
            ok, val = psql_json(PROBE_PRIVS_SQL.replace("@SCHEMA@", s["name"].replace("'", "''")), db=db, password=self.pgpw)
            if not ok:
                raise ObserveError(f"reading the default-privilege probe in {db}.{s['name']} failed: {val}")
            self.put(check, "probe", val)
            psql_exec(f"drop table {qi(s['name'])}.zz_grader_probe", db=db, password=self.pgpw)

    # ---- grafana --------------------------------------------------------------------------------------------------
    def g(self, path, user="admin", password=None, strict=True):
        code, body = grafana("GET", path, user=user, password=password or self.grafana_pw)
        if strict and code != 200:
            raise ObserveError(f"grafana GET {path} -> {code}: {str(body)[:300]}")
        return code, body

    def observe_grafana(self, inventory):
        _, dss = self.g("api/datasources")
        ds_uids = {d["uid"]: d["type"] for d in dss}
        for d in dss:
            jd = {k: v for k, v in sorted((d.get("jsonData") or {}).items()) if k in self.cfg.get("datasource_json_fields",
                  ["httpMethod", "timeInterval", "maxLines", "derivedFields", "defaultProject", "tlsSkipVerify"])}
            self.put(f"grafana.datasource:{d['uid']}", "datasource", {
                "name": d["name"], "type": d["type"], "url": d.get("url", ""), "access": d.get("access"),
                "default": bool(d.get("isDefault")), "database": d.get("database", ""), "json": jd})
        _, folders = self.g("api/search?type=dash-folder&limit=5000")
        self.folder_uids = sorted(f["uid"] for f in folders)
        for f in folders:
            _, meta = self.g(f"api/folders/{f['uid']}")
            _, perms = self.g(f"api/folders/{f['uid']}/permissions")
            self.put(f"grafana.folder:{f['uid']}", "folder", {"title": meta.get("title"),
                                                              "parent": meta.get("parentUid") or ""})
            self.put(f"grafana.folder:{f['uid']}", "permissions", sorted(
                f"{x.get('role') or ('team:' + x['team'] if x.get('team') else 'user:' + str(x.get('userLogin')))}="
                f"{x.get('permissionName') or x.get('permission')}" for x in perms if not x.get("inherited")))
        _, dashes = self.g("api/search?type=dash-db&limit=5000")
        for d in dashes:
            _, body = self.g(f"api/dashboards/uid/{d['uid']}")
            self.put(f"grafana.dashboard:{d['uid']}", "dashboard", normalize_dashboard(body, ds_uids))
        _, teams = self.g("api/teams/search?perpage=1000")
        for t in teams.get("teams", []):
            _, members = self.g(f"api/teams/{t['id']}/members")
            self.put(f"grafana.team:{t['name']}", "team", {"email": t.get("email") or "",
                                                          "members": sorted(m["login"] for m in members)})
        _, users = self.g("api/org/users")
        for u in users:
            if u["login"] == "admin":
                continue
            self.put(f"grafana.user:{u['login']}", "org_role", u.get("role"))
        # alerting
        _, cps = self.g("api/v1/provisioning/contact-points")
        byname = {}
        for c in cps:
            settings = {k: v for k, v in sorted((c.get("settings") or {}).items()) if v != "[REDACTED]"}
            byname.setdefault(c["name"], []).append({"type": c["type"], "settings": settings,
                                                     "disable_resolve": bool(c.get("disableResolveMessage"))})
        for n, integ in byname.items():
            self.put(f"grafana.contactpoint:{n}", "integrations", sorted(integ, key=lambda x: json.dumps(x, sort_keys=True)))
        _, mutes = self.g("api/v1/provisioning/mute-timings")
        for m in mutes or []:
            self.put(f"grafana.mute:{m['name']}", "intervals", normalize_intervals(m.get("time_intervals")))
        _, tmpls = self.g("api/v1/provisioning/templates")
        for t in tmpls or []:
            self.put(f"grafana.template:{t['name']}", "template", digest((t.get("template") or "").strip()))
        _, tree = self.g("api/v1/provisioning/policies")
        for labels in expand_probes(self.cfg.get("route_probes"), inventory) + self.cfg.get("route_extra", []):
            key = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            self.put(f"grafana.route:{key}", "routing", route_alert(tree, labels))
        _, rules = self.g("api/v1/provisioning/alert-rules")
        groups = {}
        for r in rules or []:
            self.put(f"grafana.rule:{r['folderUID']}/{r['ruleGroup']}/{r['title']}", "rule", normalize_rule(r, ds_uids))
            groups.setdefault((r["folderUID"], r["ruleGroup"]), 0)
        for (fu, gname) in sorted(groups):
            _, gr = self.g(f"api/v1/provisioning/folder/{fu}/rule-groups/{urllib.request.quote(gname)}")
            self.put(f"grafana.rulegroup:{fu}/{gname}", "interval", seconds(gr.get("interval")))
        # what people can do: real logins
        for c in self.creds.get("grafana_users", []):
            access = {}
            code, _ = grafana("GET", "api/user", user=c["login"], password=c["password"])
            if code != 200:
                self.put(f"grafana.access:{c['login']}", "login", False)
                continue
            for fu in self.folder_uids:
                code, meta = grafana("GET", f"api/folders/{fu}", user=c["login"], password=c["password"])
                access[fu] = "none" if code != 200 else ("admin" if meta.get("canAdmin") else
                                                         "edit" if meta.get("canEdit") else "view")
            self.put(f"grafana.access:{c['login']}", "login", True)
            self.put(f"grafana.access:{c['login']}", "folders", access)

    def observe(self, inventory=None):
        if self.pgpw is not None:
            self.observe_pg()
        if self.v.token is not None:
            self.observe_vault()
        if getattr(self, "grafana_pw", None):
            self.observe_grafana(inventory or {})
        return self.obs


ROLES_SQL = r"""
select coalesce(json_agg(json_build_object(
  'name', r.rolname, 'super', r.rolsuper, 'inherit', r.rolinherit, 'createrole', r.rolcreaterole,
  'createdb', r.rolcreatedb, 'login', r.rolcanlogin, 'replication', r.rolreplication, 'bypassrls', r.rolbypassrls,
  'connlimit', r.rolconnlimit,
  'validuntil', case when r.rolvaliduntil is null or r.rolvaliduntil = 'infinity' then 'never' else 'set' end,
  'member_of', coalesce((select json_agg(json_build_object('role', g.rolname, 'admin', m.admin_option,
                                                           'inherit', m.inherit_option, 'set', m.set_option)
                                         order by g.rolname)
                         from pg_auth_members m join pg_roles g on g.oid = m.roleid
                         where m.member = r.oid), '[]'::json)
) order by r.rolname), '[]'::json)
from pg_roles r where r.rolname !~ '^pg_'
"""

# Privileges of every non-superuser, non-dynamic role (and PUBLIC) on the database, its schemas and relations.
DB_SQL = r"""
with roles as (
  select oid, rolname from pg_roles where rolname !~ '^pg_' and rolname !~ '^v-' and not rolsuper
), nsp as (
  select n.oid, n.nspname, n.nspowner, n.nspacl from pg_namespace n
  where n.nspname not in ('pg_catalog', 'information_schema', 'pg_toast') and n.nspname !~ '^pg_(toast|temp)'
), rel as (
  select c.oid, c.relname, c.relkind, c.relacl, c.relowner, n.nspname from pg_class c join nsp n on n.oid = c.relnamespace
  where c.relkind in ('r', 'p', 'v', 'm', 'f', 'S') and c.relname <> 'zz_grader_probe'
), pubrel as (
  select r.oid, string_agg(distinct a.privilege_type, ',' order by a.privilege_type) as privs
  from rel r, aclexplode(coalesce(r.relacl, acldefault((case when r.relkind = 'S' then 's' else 'r' end)::"char", r.relowner))) a
  where a.grantee = 0 group by r.oid
), pubnsp as (
  select n.oid, string_agg(distinct a.privilege_type, ',' order by a.privilege_type) as privs
  from nsp n, aclexplode(coalesce(n.nspacl, acldefault('n'::"char", n.nspowner))) a where a.grantee = 0 group by n.oid
), pubdb as (
  select string_agg(distinct a.privilege_type, ',' order by a.privilege_type) as privs
  from pg_database d, aclexplode(coalesce(d.datacl, acldefault('d'::"char", d.datdba))) a
  where d.datname = current_database() and a.grantee = 0
)
select json_build_object(
  'database', json_build_object(
     'owner', (select pg_get_userbyid(datdba) from pg_database where datname = current_database()),
     'public', coalesce((select privs from pubdb), ''),
     'privileges', coalesce((select json_object_agg(rolname, p order by rolname) from (
        select rolname, concat_ws(',',
          case when has_database_privilege(oid, current_database(), 'CONNECT') then 'CONNECT' end,
          case when has_database_privilege(oid, current_database(), 'CREATE') then 'CREATE' end,
          case when has_database_privilege(oid, current_database(), 'TEMP') then 'TEMP' end) as p
        from roles) x where p <> ''), '{}'::json)),
  'extensions', (select coalesce(json_agg(extname order by extname), '[]'::json) from pg_extension),
  'schemas', coalesce((select json_agg(json_build_object(
     'name', n.nspname, 'owner', pg_get_userbyid(n.nspowner),
     'privileges', coalesce((select json_object_agg(rolname, p order by rolname) from (
        select rolname, concat_ws(',',
          case when has_schema_privilege(roles.oid, n.oid, 'USAGE') then 'USAGE' end,
          case when has_schema_privilege(roles.oid, n.oid, 'CREATE') then 'CREATE' end) as p
        from roles) x where p <> ''), '{}'::json)
       ::jsonb || jsonb_build_object('PUBLIC', coalesce((select privs from pubnsp where pubnsp.oid = n.oid), ''))
     ) order by n.nspname) from nsp n), '[]'::json),
  'relations', coalesce((select json_agg(json_build_object(
     'schema', r.nspname, 'name', r.relname, 'kind', r.relkind,
     'privileges', (coalesce((select jsonb_object_agg(rolname, p) from (
        select rolname, case when r.relkind = 'S' then concat_ws(',',
            case when has_sequence_privilege(roles.oid, r.oid, 'USAGE') then 'USAGE' end,
            case when has_sequence_privilege(roles.oid, r.oid, 'SELECT') then 'SELECT' end,
            case when has_sequence_privilege(roles.oid, r.oid, 'UPDATE') then 'UPDATE' end)
          else concat_ws(',',
            case when has_table_privilege(roles.oid, r.oid, 'SELECT') then 'SELECT' end,
            case when has_table_privilege(roles.oid, r.oid, 'INSERT') then 'INSERT' end,
            case when has_table_privilege(roles.oid, r.oid, 'UPDATE') then 'UPDATE' end,
            case when has_table_privilege(roles.oid, r.oid, 'DELETE') then 'DELETE' end,
            case when has_table_privilege(roles.oid, r.oid, 'TRUNCATE') then 'TRUNCATE' end,
            case when has_table_privilege(roles.oid, r.oid, 'REFERENCES') then 'REFERENCES' end,
            case when has_table_privilege(roles.oid, r.oid, 'TRIGGER') then 'TRIGGER' end) end as p
        from roles where roles.oid <> r.relowner) x where p <> ''), '{}'::jsonb)
       || jsonb_build_object('PUBLIC', coalesce((select privs from pubrel where pubrel.oid = r.oid), '')))
     ) order by r.nspname, r.relname) from rel r), '[]'::json),
  'data', coalesce((select json_object_agg(nspname || '.' || relname, n) from (
     select r.nspname, r.relname, (xpath('/row/c/text()', query_to_xml(format(
       'select count(*) || '':'' || coalesce(md5(string_agg(t::text, ''|'' order by t::text)), '''') as c from %I.%I t',
       r.nspname, r.relname), false, true, '')))[1]::text as n
     from rel r where r.relkind in ('r', 'p')) d), '{}'::json)
)
"""

PROBE_PRIVS_SQL = r"""
with roles as (select oid, rolname from pg_roles where rolname !~ '^pg_' and rolname !~ '^v-' and not rolsuper),
t as (select c.oid, c.relkind, c.relowner from pg_class c join pg_namespace n on n.oid = c.relnamespace
      where n.nspname = '@SCHEMA@' and c.relname in ('zz_grader_probe', 'zz_grader_probe_id_seq'))
select json_build_object(
 'table', (select coalesce(json_object_agg(rolname, p order by rolname), '{}'::json) from (
   select rolname, concat_ws(',',
     case when has_table_privilege(roles.oid, t.oid, 'SELECT') then 'SELECT' end,
     case when has_table_privilege(roles.oid, t.oid, 'INSERT') then 'INSERT' end,
     case when has_table_privilege(roles.oid, t.oid, 'UPDATE') then 'UPDATE' end,
     case when has_table_privilege(roles.oid, t.oid, 'DELETE') then 'DELETE' end,
     case when has_table_privilege(roles.oid, t.oid, 'TRUNCATE') then 'TRUNCATE' end,
     case when has_table_privilege(roles.oid, t.oid, 'REFERENCES') then 'REFERENCES' end,
     case when has_table_privilege(roles.oid, t.oid, 'TRIGGER') then 'TRIGGER' end) as p
   from roles, t where t.relkind = 'r' and roles.oid <> t.relowner) x where p <> ''),
 'sequence', (select coalesce(json_object_agg(rolname, p order by rolname), '{}'::json) from (
   select rolname, concat_ws(',',
     case when has_sequence_privilege(roles.oid, t.oid, 'USAGE') then 'USAGE' end,
     case when has_sequence_privilege(roles.oid, t.oid, 'SELECT') then 'SELECT' end,
     case when has_sequence_privilege(roles.oid, t.oid, 'UPDATE') then 'UPDATE' end) as p
   from roles, t where t.relkind = 'S' and roles.oid <> t.relowner) x where p <> ''))
"""

# What a dynamic credential is, seen from inside the database it was issued for.
PRIV_SELF_SQL = r"""
select json_build_object(
 'member_of', (select coalesce(json_agg(g.rolname order by g.rolname), '[]'::json) from pg_auth_members m
               join pg_roles g on g.oid = m.roleid where m.member = (select oid from pg_roles where rolname = current_user)),
 'expires', (select rolvaliduntil is not null and rolvaliduntil <> 'infinity' from pg_roles where rolname = current_user),
 'attributes', (select json_build_object('super', rolsuper, 'createrole', rolcreaterole, 'createdb', rolcreatedb,
                                         'inherit', rolinherit) from pg_roles where rolname = current_user),
 'privileges', (select coalesce(json_object_agg(n.nspname || '.' || c.relname, concat_ws(',',
     case when c.relkind = 'S' then case when has_sequence_privilege(c.oid, 'USAGE') then 'USAGE' end
          else case when has_table_privilege(c.oid, 'SELECT') then 'SELECT' end end,
     case when c.relkind <> 'S' and has_table_privilege(c.oid, 'INSERT') then 'INSERT' end,
     case when c.relkind <> 'S' and has_table_privilege(c.oid, 'UPDATE') then 'UPDATE' end,
     case when c.relkind <> 'S' and has_table_privilege(c.oid, 'DELETE') then 'DELETE' end,
     case when c.relkind <> 'S' and has_table_privilege(c.oid, 'TRUNCATE') then 'TRUNCATE' end)
     order by n.nspname, c.relname), '{}'::json)
   from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where c.relkind in ('r', 'p', 'S') and n.nspname not in ('pg_catalog', 'information_schema') and n.nspname !~ '^pg_'),
 'schemas', (select coalesce(json_agg(nspname order by nspname), '[]'::json) from pg_namespace
             where has_schema_privilege(oid, 'USAGE') and nspname not in ('pg_catalog', 'information_schema')
             and nspname !~ '^pg_'))
"""


def squash(q):
    """Queries compare as text with whitespace collapsed (no backend evaluates them)."""
    return re.sub(r"\s+", " ", str(q)).strip()


def normalize_dashboard(body, ds_uids):
    d = body.get("dashboard") or {}
    meta = body.get("meta") or {}
    panels = []

    def ds_ref(x):
        if isinstance(x, dict):
            return x.get("uid")
        return x if isinstance(x, str) else None

    def visit(ps):
        for p in ps or []:
            if p.get("type") == "row":
                visit(p.get("panels"))
                continue
            targets = []
            for t in p.get("targets") or []:
                ref = ds_ref(t.get("datasource")) or ds_ref(p.get("datasource"))
                targets.append({"ref": t.get("refId"), "datasource": ref,
                                "resolves": ref in ds_uids or (isinstance(ref, str) and ref.startswith("$")),
                                "query": squash(t.get("expr") or t.get("rawSql") or t.get("query") or t.get("target") or "")})
            th = ((p.get("fieldConfig") or {}).get("defaults") or {}).get("thresholds") or {}
            panels.append({"title": p.get("title"), "type": p.get("type"), "targets": targets,
                           "unit": ((p.get("fieldConfig") or {}).get("defaults") or {}).get("unit"),
                           "thresholds": [s.get("value") for s in th.get("steps") or []]})
        return panels

    visit(d.get("panels"))
    return {"title": d.get("title"), "folder": meta.get("folderUid") or "", "tags": sorted(d.get("tags") or []),
            "variables": sorted(v.get("name") for v in (d.get("templating") or {}).get("list") or []),
            "panels": sorted(panels, key=lambda x: (x["title"] or "", x["type"] or ""))}


def normalize_intervals(intervals):
    out = []
    for i in intervals or []:
        out.append({k: (sorted(json.dumps(x, sort_keys=True) for x in v) if isinstance(v, list) else v)
                    for k, v in sorted(i.items()) if v not in (None, [], "")})
    return sorted(out, key=lambda x: json.dumps(x, sort_keys=True))


def normalize_rule(r, ds_uids):
    data = []
    for q in r.get("data") or []:
        m = q.get("model") or {}
        if q.get("datasourceUid") == "__expr__":
            data.append({"ref": q.get("refId"), "expr_type": m.get("type"), "expression": m.get("expression", ""),
                         "reducer": m.get("reducer"),
                         "conditions": [{"type": (c.get("evaluator") or {}).get("type"),
                                         "params": (c.get("evaluator") or {}).get("params")}
                                        for c in m.get("conditions") or []]})
        else:
            data.append({"ref": q.get("refId"), "datasource": q.get("datasourceUid"),
                         "resolves": q.get("datasourceUid") in ds_uids, "query": squash(m.get("expr") or m.get("rawSql") or ""),
                         "range": (q.get("relativeTimeRange") or {}).get("from")})
    ns = r.get("notification_settings") or {}
    return {"condition": r.get("condition"), "for": seconds(r.get("for")), "labels": r.get("labels") or {},
            "annotations": r.get("annotations") or {}, "paused": bool(r.get("isPaused")),
            "no_data": r.get("noDataState"), "exec_err": r.get("execErrState"),
            "data": sorted(data, key=lambda x: x["ref"] or ""),
            "notification": {k: ns.get(k) for k in sorted(ns)} if ns else {}}


# ======================================================================================================================
# Comparison
# ======================================================================================================================
def policy_check_facts(observer, ref, sub, extra_paths):
    """Capability maps of every policy name in either observation, evaluated in the live (submission) Vault."""
    names = sorted(set(ref.get("_policy_texts", {})) | set(sub.get("_policy_texts", {})))
    rt, st = ref.get("_policy_texts", {}), sub.get("_policy_texts", {})
    ref_caps, sub_caps = {}, {}
    for n in names:
        paths = set()
        for t in (rt.get(n), st.get(n)):
            for pat in policy_patterns(t):
                paths |= instantiate(pat)
        if n in rt:
            ref_caps[n] = observer.capabilities({n: (rt[n], paths)}, extra_paths)[n]
        if n in st:
            sub_caps[n] = observer.capabilities({n: (st[n], paths)}, extra_paths)[n]
    return ref_caps, sub_caps


def compare(ref, sub):
    """{check: (ok, detail)} over the union of check ids (facts compared one by one)."""
    out = {}
    for check in sorted(set(ref) | set(sub)):
        if check.startswith("_"):
            continue
        r, s = ref.get(check), sub.get(check)
        if r is None:
            out[check] = (False, "exists but the model does not define it")
            continue
        if s is None:
            out[check] = (False, "missing")
            continue
        bad = []
        for fact in sorted(set(r) | set(s)):
            if r.get(fact) != s.get(fact):
                bad.append(f"{fact}: expected {short(r.get(fact))}, found {short(s.get(fact))}")
        out[check] = (not bad, "; ".join(bad)[:600])
    return out


def short(v, n=160):
    text = json.dumps(v, sort_keys=True) if not isinstance(v, str) else v
    return text if len(text) <= n else text[:n] + "..."


def diff_detail(r, s):
    """A readable diff of two dict facts (only differing keys)."""
    if isinstance(r, dict) and isinstance(s, dict):
        keys = sorted(set(r) | set(s))
        return {k: [r.get(k), s.get(k)] for k in keys if r.get(k) != s.get(k)}
    return [r, s]
