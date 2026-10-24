#!/usr/bin/env python3
"""sitedoor CLI test: a local http.server stub stands in for the editor door.

Covers the bearer header, the token never appearing in output or argv on every
path, plan/apply/revert/history/whoami/photo/enroll wire shapes, request ids
(including the shared vector the door's TypeScript test also asserts), --json
mode, exit codes, and the Keychain lookup order with fake `security` and
`secret-tool` programs on PATH. No network beyond 127.0.0.1, no real keychain:
every run gets PATH = a temp shim dir only, so the machine's own keychain tools
are never reached.

Run: python3 tests/test_sitedoor.py   (exit 0 = pass)
"""
import hashlib
import http.server
import importlib.util
import json
import os
import secrets
import shutil
import ssl
import stat
import subprocess
import sys
import tempfile
import threading
import urllib.error

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(REPO, "claude", "skills", "sitedoor", "tools", "sitedoor.py")
SERVICE = "next-phil-editor"

# Shared request-id vector (the door's TypeScript test asserts the same hex).
VECTOR = {
    "account": "phil-sim",
    "slug": "anthony-test",
    "op": "testimonial_add",
    "payload_json": "{\"content\":\"Victoria’s team was great — café visits & all \U0001F642\","
                    "\"rating\":5,\"reviewer_name\":\"Dana R.\"}",
    "plan_id": "0" * 64,
    "request_id": "40621c02e004f583913e51e14711500e8991c619ffc49d59d0fb9f6c6dcda1be",
}

FAILS = []


def check(cond, label):
    if cond:
        print("ok   " + label)
    else:
        print("FAIL " + label)
        FAILS.append(label)


# ---------------------------------------------------------------- stub door
class Stub:
    def __init__(self):
        self.requests = []
        self.responder = None  # fn(path, headers, body_bytes) -> (status, bytes)
        stub = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n)
                stub.requests.append({"path": self.path, "headers": dict(self.headers), "body": body})
                status, out = stub.responder(self.path, dict(self.headers), body)
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self):
        return "http://127.0.0.1:%d/editor/v1" % self.port

    def bodies(self):
        out = []
        for r in self.requests:
            if r["path"] == "/editor/v1":
                out.append(json.loads(r["body"].decode("utf-8")))
        return out


def j(obj):
    return json.dumps(obj).encode("utf-8")


def default_responder(stub):
    def respond(path, headers, body):
        if path.startswith("/upload"):
            return 200, j({"storageId": "kg2abc"})
        req = json.loads(body.decode("utf-8"))
        op = req.get("op")
        if op == "whoami":
            return 200, j({"ok": True, "account": "phil-sim", "person": "Test Phil", "scope": "test_only"})
        if op == "get":
            return 200, j({"ok": True, "slug": req.get("slug"), "fields": {"title": "Realtor"}})
        if op == "plan":
            return 200, j({"ok": True, "action": req.get("action"), "slug": req.get("slug"), "plan_id": "a" * 64,
                           "request_id": "b" * 64, "changed": 1, "skipped_duplicate": [],
                           "diff": [{"path": "title", "before": "Realtor", "after": "Broker"}]})
        if op == "apply":
            return 200, j({"ok": True, "changed": 1, "request_id": req.get("request_id"), "write_ids": ["w1"]})
        if op == "revert":
            return 200, j({"ok": True, "changed": 1, "request_id": "r2", "write_ids": ["w2"], "reverted": ["w1"]})
        if op == "history":
            return 200, j({"ok": True, "slug": req.get("slug"),
                           "writes": [{"write_id": "w1", "request_id": "r1", "field_path": "title", "table": "realtor",
                                       "before": "Realtor", "after": "Broker", "at": 1, "account": "phil-sim",
                                       "person": "Test Phil", "revert_of": None, "reverted_at": None}]})
        if op == "photo_upload_url":
            return 200, j({"ok": True, "upload_url": "http://127.0.0.1:%d/upload/xyz" % stub.port})
        if op == "photo_finalize":
            return 200, j({"ok": True, "storage_id": "kg2abc", "content_type": "image/jpeg", "size": 2004,
                           "url": "https://next-snake-35.convex.cloud/api/storage/"
                                  "0f8fad5b-d9cb-469f-a165-70867728950e"})
        return 400, j({"ok": False, "code": "invalid", "reason_code": "unknown_op", "reason": "unknown op"})
    return respond


# ---------------------------------------------------------------- harness
def make_shims(d, security=None, secret_tool=None):
    """Write fake keychain programs. Each records its argv (one line per call).
    PATH holds only the shim dir, so shim bodies use shell builtins only."""
    os.makedirs(d, exist_ok=True)
    for name, body in (("security", security), ("secret-tool", secret_tool)):
        p = os.path.join(d, name)
        if os.path.exists(p):
            os.remove(p)
        if body is None:
            continue
        with open(p, "w") as f:
            f.write("#!/bin/sh\n" + 'echo "$0 $*" >> "%s/argv.log"\n' % d + body + "\n")
        os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def run(args, token=None, shims=None, url=None, account=None, extra_env=None, cwd=None):
    env = {"HOME": os.environ.get("HOME", "/tmp"), "LANG": "C.UTF-8", "PYTHONIOENCODING": "utf-8"}
    env["PATH"] = shims or tempfile.mkdtemp(prefix="sitedoor-empty-")
    if token is not None:
        env["SITEDOOR_TOKEN"] = token
    if url:
        env["SITEDOOR_URL"] = url
    if account:
        env["SITEDOOR_ACCOUNT"] = account
    if extra_env:
        env.update(extra_env)
    r = subprocess.run([sys.executable, CLI] + args, capture_output=True, env=env, cwd=cwd, timeout=60)
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


def fake_token():
    return "sdt" + "_" + secrets.token_hex(20)


def write_json(d, name, obj):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    return p


def one_json(out):
    """stdout must be exactly one JSON object."""
    try:
        obj = json.loads(out)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def load_module():
    spec = importlib.util.spec_from_file_location("sitedoor", CLI)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- tests
def main():
    check(os.path.isfile(CLI), "sitedoor.py exists")
    if not os.path.isfile(CLI):
        return 1

    tmp = tempfile.mkdtemp(prefix="sitedoor-test-")
    stub = Stub()
    stub.responder = default_responder(stub)
    tok = fake_token()
    seen = []  # every (stdout, stderr) pair, scanned for the token at the end

    def go(args, **kw):
        kw.setdefault("token", tok)
        kw.setdefault("url", stub.url)
        rc, out, err = run(args, **kw)
        seen.append((out, err))
        return rc, out, err

    # whoami: bearer header, op whoami without slug, human output
    stub.requests.clear()
    rc, out, err = go(["whoami"])
    check(rc == 0, "whoami exit 0")
    b = stub.bodies()
    check(len(b) == 1 and b[0] == {"op": "whoami"}, "whoami sends exactly {op: whoami}")
    hdr = stub.requests[0]["headers"]
    check(hdr.get("Authorization") == "Bearer " + tok, "bearer header carries the token")
    check("phil-sim" in out and "test_only" in out, "whoami prints account and scope")

    # whoami --json: exactly one object, the door body verbatim
    rc, out, err = go(["whoami", "--json"])
    obj = one_json(out)
    check(rc == 0 and obj == {"ok": True, "account": "phil-sim", "person": "Test Phil", "scope": "test_only"},
          "whoami --json prints the door body as one JSON object")

    # get
    stub.requests.clear()
    rc, out, err = go(["get", "anthony-test"])
    check(rc == 0 and stub.bodies() == [{"op": "get", "slug": "anthony-test"}], "get sends op get with slug")

    # plan sends op plan with write_op and payload_json (canonical string)
    pf = write_json(tmp, "p.json", {"op": "realtor_set", "set": {"title": "Broker"}})
    stub.requests.clear()
    rc, out, err = go(["plan", "anthony-test", "--payload", pf])
    b = stub.bodies()
    check(rc == 0 and len(b) == 1 and b[0].get("op") == "plan", "plan sends op plan")
    check(b and b[0].get("action") == "realtor_set" and b[0].get("slug") == "anthony-test",
          "plan carries action and slug")
    check(b and set(b[0]) == {"op", "slug", "action", "payload_json"}, "plan sends no extra keys")
    check(b and b[0].get("payload_json") == '{"set":{"title":"Broker"}}', "payload_json is the canonical string")
    check(b and isinstance(b[0].get("payload_json"), str) and "payload" not in b[0],
          "payload travels only as the payload_json string")
    check("title: Realtor -> Broker" in out, "plan prints the diff line")
    check("a" * 64 in out, "plan prints the plan id")

    # plan --payload f.json --json: exactly one JSON object
    rc, out, err = go(["plan", "anthony-test", "--payload", pf, "--json"])
    obj = one_json(out)
    check(rc == 0 and obj is not None and obj.get("ok") is True and obj.get("plan_id") == "a" * 64,
          "plan --payload --json prints exactly one JSON object")

    # apply requires --plan (usage error, nothing sent)
    stub.requests.clear()
    rc, out, err = go(["apply", "anthony-test", "--payload", pf, "--apply"])
    check(rc == 2 and stub.requests == [], "apply without --plan is a usage error and sends nothing")

    # apply without --apply sends plan only
    stub.requests.clear()
    rc, out, err = go(["apply", "anthony-test", "--payload", pf, "--plan", "a" * 64])
    b = stub.bodies()
    check(rc == 0 and [x.get("op") for x in b] == ["plan"], "apply without --apply sends only a plan")
    check("--apply" in out, "apply without --apply tells how to write")

    # apply --apply sends apply with expect_before_sha256 and the deterministic request id
    stub.requests.clear()
    rc, out, err = go(["apply", "anthony-test", "--payload", pf, "--plan", "a" * 64, "--apply"],
                      account="phil")
    b = stub.bodies()
    check(rc == 0 and [x.get("op") for x in b] == ["apply"], "apply --apply sends op apply")
    pj = '{"set":{"title":"Broker"}}'
    want = hashlib.sha256(("phil|anthony-test|realtor_set|" + pj + "|" + "a" * 64).encode("utf-8")).hexdigest()
    check(b and b[0].get("request_id") == want, "request_id = sha256(account|slug|op|payload_json|plan_id)")
    check(b and b[0].get("expect_before_sha256") == "a" * 64, "apply sends the plan id as expect_before_sha256")
    check(b and set(b[0]) == {"op", "slug", "action", "payload_json", "expect_before_sha256", "request_id"},
          "apply sends exactly the contract keys")
    check("w1" in out, "apply prints the write id")
    # determinism: a second identical apply sends the same id
    stub.requests.clear()
    go(["apply", "anthony-test", "--payload", pf, "--plan", "a" * 64, "--apply"], account="phil")
    b2 = stub.bodies()
    check(b2 and b2[0].get("request_id") == want, "request_id is deterministic across runs")

    # shared vector, end to end through the CLI and through the module function
    vf = os.path.join(tmp, "vector.json")
    vp = json.loads(VECTOR["payload_json"])
    vp["op"] = VECTOR["op"]
    with open(vf, "w", encoding="utf-8") as f:
        json.dump(vp, f, ensure_ascii=False, indent=2)
    stub.requests.clear()
    rc, out, err = go(["apply", VECTOR["slug"], "--payload", vf, "--plan", VECTOR["plan_id"], "--apply"],
                      account=VECTOR["account"])
    b = stub.bodies()
    check(b and b[0].get("payload_json") == VECTOR["payload_json"], "shared vector: payload_json string matches")
    check(b and b[0].get("request_id") == VECTOR["request_id"], "shared vector: request_id hex matches")
    mod = load_module()
    rid = mod.request_id(VECTOR["account"], VECTOR["slug"], VECTOR["op"], VECTOR["payload_json"], VECTOR["plan_id"])
    check(rid == VECTOR["request_id"], "shared vector: request_id() function matches")
    check(mod.canonical_payload(json.loads(VECTOR["payload_json"])) == VECTOR["payload_json"],
          "shared vector: canonical_payload() reproduces the string")

    # history and revert shapes
    stub.requests.clear()
    rc, out, err = go(["history", "anthony-test"])
    b = stub.bodies()
    check(rc == 0 and b and b[0].get("op") == "history" and b[0].get("slug") == "anthony-test",
          "history sends op history with slug")
    check("write w1" in out and "request r1" in out, "history prints write and request ids")
    rc, out, err = go(["history", "anthony-test", "--limit", "51"])
    check(rc == 2, "history --limit above 50 is a usage error")
    stub.requests.clear()
    rc, out, err = go(["revert", "anthony-test", "--request", "r1"])
    b = stub.bodies()
    check(rc == 0 and "revert" not in [x.get("op") for x in b], "revert without --apply writes nothing")
    check("title" in out and "1 logged change" in out, "revert dry run lists the matching change")
    check("--apply" in out, "revert without --apply tells how to write")
    stub.requests.clear()
    rc, out, err = go(["revert", "anthony-test", "--request", "r1", "--apply"])
    b = stub.bodies()
    check(rc == 0 and b == [{"op": "revert", "slug": "anthony-test", "target_request_id": "r1"}],
          "revert --request --apply sends target_request_id")
    stub.requests.clear()
    rc, out, err = go(["revert", "anthony-test", "--write", "w1", "--apply"])
    b = stub.bodies()
    check(rc == 0 and b == [{"op": "revert", "slug": "anthony-test", "write_id": "w1"}],
          "revert --write --apply sends write_id")
    rc, out, err = go(["revert", "anthony-test", "--apply"])
    check(rc == 2, "revert needs --request or --write")

    # door refusal: exit 4, human prints code and reason; --json prints the body
    refusal = {"ok": False, "code": "refused", "reason_code": "scope", "reason": "this token is for test agents only"}
    stub.responder = lambda p, h, body: (403, j(refusal))
    rc, out, err = go(["get", "victoria-kulszan"])
    check(rc == 4 and "refused" in (out + err) and "test agents only" in (out + err),
          "door refusal exits 4 and names code and reason")
    rc, out, err = go(["get", "victoria-kulszan", "--json"])
    check(rc == 4 and one_json(out) == refusal, "door refusal --json prints the body as one object")
    stub.responder = lambda p, h, body: (401, j({"ok": False, "code": "unauthorized",
                                                 "reason_code": "unauthorized", "reason": "token not accepted"}))
    rc, out, err = go(["whoami"])
    check(rc == 4, "401 exits 4")
    stub.responder = lambda p, h, body: (502, b"<html>bad gateway</html>")
    rc, out, err = go(["whoami", "--json"])
    obj = one_json(out)
    check(rc == 3 and obj is not None and obj.get("ok") is False, "non-JSON answer exits 3 with one JSON object")
    stub.responder = default_responder(stub)

    # local refusals (--json): SVG and oversize photos never reach the door
    svg = os.path.join(tmp, "x.svg")
    with open(svg, "w") as f:
        f.write('<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>')
    stub.requests.clear()
    rc, out, err = go(["photo", "anthony-test", svg, "--json"])
    obj = one_json(out)
    check(rc == 4 and obj is not None and obj.get("ok") is False and obj.get("code") == "invalid"
          and obj.get("reason_code") == "bad_image_type" and obj.get("reason"),
          "SVG photo is a local refusal {ok:false, code:invalid, reason_code:bad_image_type}")
    rc, out, err = go(["photo", "anthony-test", svg, "--apply"])
    check(rc == 4 and stub.requests == [], "SVG photo with --apply still sends nothing")
    big = os.path.join(tmp, "big.jpg")
    with open(big, "wb") as f:
        f.write(b"\xff\xd8\xff\xe0" + b"\0" * (8 * 1024 * 1024 + 10))
    rc, out, err = go(["photo", "anthony-test", big, "--json"])
    obj = one_json(out)
    check(rc == 4 and obj and obj.get("reason_code") == "file_too_large", "oversize photo is a local refusal")

    # photo dry run and apply
    jpg = os.path.join(tmp, "p.jpg")
    jbytes = b"\xff\xd8\xff\xe0" + os.urandom(2000)
    with open(jpg, "wb") as f:
        f.write(jbytes)
    stub.requests.clear()
    rc, out, err = go(["photo", "anthony-test", jpg])
    check(rc == 0 and stub.requests == [] and "image/jpeg" in out, "photo dry run checks locally and sends nothing")
    png = os.path.join(tmp, "p.png")
    with open(png, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + os.urandom(100))
    webp = os.path.join(tmp, "p.webp")
    with open(webp, "wb") as f:
        f.write(b"RIFF\x10\x00\x00\x00WEBPVP8 " + os.urandom(100))
    rc1, o1, _ = go(["photo", "anthony-test", png])
    rc2, o2, _ = go(["photo", "anthony-test", webp])
    check(rc1 == 0 and "image/png" in o1 and rc2 == 0 and "image/webp" in o2, "png and webp sniffed")
    stub.requests.clear()
    rc, out, err = go(["photo", "anthony-test", jpg, "--apply"])
    paths = [r["path"] for r in stub.requests]
    ops = [json.loads(r["body"])["op"] for r in stub.requests if r["path"] == "/editor/v1"]
    check(rc == 0 and ops == ["photo_upload_url", "photo_finalize"] and any(p.startswith("/upload") for p in paths),
          "photo --apply: upload url, upload, finalize")
    up = [r for r in stub.requests if r["path"].startswith("/upload")]
    check(up and up[0]["body"] == jbytes and up[0]["headers"].get("Content-Type") == "image/jpeg",
          "upload sends the bytes with the sniffed content type")
    check(up and "Authorization" not in up[0]["headers"], "upload never carries the token")
    fin = [json.loads(r["body"]) for r in stub.requests if r["path"] == "/editor/v1"][-1]
    check(fin.get("storage_id") == "kg2abc", "finalize sends the storage id")
    check("https://next-snake-35.convex.cloud/api/storage/" in out, "photo --apply prints the storage URL")

    # payload file problems
    rc, out, err = go(["plan", "anthony-test", "--payload", os.path.join(tmp, "missing.json")])
    check(rc == 2, "missing payload file is a usage error")
    nop = write_json(tmp, "noop.json", {"set": {"title": "x"}})
    rc, out, err = go(["plan", "anthony-test", "--payload", nop, "--json"])
    obj = one_json(out)
    check(rc == 4 and obj and obj.get("reason_code") == "missing_op", "payload without op is a local refusal")
    rc, out, err = go(["plan", "anthony-test", "--payload", nop, "--op", "realtor_set"])
    check(rc == 0, "--op supplies the write op")

    # network errors: exit 3
    rc, out, err = go(["whoami"], url="http://127.0.0.1:9/editor/v1")
    check(rc == 3, "connection refused exits 3")
    rc, out, err = go(["whoami", "--json"], url="http://127.0.0.1:9/editor/v1")
    obj = one_json(out)
    check(rc == 3 and obj and obj.get("ok") is False, "network error --json prints one object")
    rc, out, err = go(["whoami"], url="http://example.com/editor/v1")
    check(rc == 2, "a plain-http door URL off this machine is refused")
    check(mod.network_code(urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed")))
          == "tls_certs", "certificate failure maps to tls_certs")

    # usage
    rc, out, err = go([])
    check(rc == 2, "no subcommand exits 2")

    # ---------------- token sources and order
    shim = os.path.join(tmp, "shim")
    sec_tok, st_tok = fake_token(), fake_token()
    # security present with an item: used first, even with env set
    make_shims(shim, security='[ "$1" = find-generic-password ] && { echo "%s"; exit 0; }; exit 44' % sec_tok,
               secret_tool='echo "%s"' % st_tok)
    stub.requests.clear()
    rc, out, err = go(["whoami"], shims=shim, token=tok)
    check(rc == 0 and stub.requests[-1]["headers"].get("Authorization") == "Bearer " + sec_tok,
          "Keychain (security) is read first")
    seen.append((out, err))
    argv = open(os.path.join(shim, "argv.log")).read()
    check("-s %s" % SERVICE in argv and "-a phil" in argv and "-w" in argv,
          "security is asked for service next-phil-editor, account phil")
    check(sec_tok not in argv and tok not in argv, "no token value in any program argv")
    # account override
    open(os.path.join(shim, "argv.log"), "w").close()
    go(["whoami"], shims=shim, account="phil-sim")
    check("-a phil-sim" in open(os.path.join(shim, "argv.log")).read(), "SITEDOOR_ACCOUNT picks the account")
    # security has no item: fall to secret-tool
    make_shims(shim, security="exit 44", secret_tool='[ "$1" = lookup ] && { echo "%s"; exit 0; }; exit 1' % st_tok)
    stub.requests.clear()
    rc, out, err = go(["whoami"], shims=shim, token=tok)
    check(rc == 0 and stub.requests[-1]["headers"].get("Authorization") == "Bearer " + st_tok,
          "secret-tool is read when the Keychain has no item")
    argv = open(os.path.join(shim, "argv.log")).read()
    check("lookup service %s account phil" % SERVICE in argv, "secret-tool lookup uses service and account")
    # neither has it: env
    make_shims(shim, security="exit 44", secret_tool="exit 1")
    stub.requests.clear()
    rc, out, err = go(["whoami"], shims=shim, token=tok)
    check(rc == 0 and stub.requests[-1]["headers"].get("Authorization") == "Bearer " + tok,
          "SITEDOOR_TOKEN is the last source")
    # nothing anywhere: exit 5 naming the Keychain item
    stub.requests.clear()
    rc, out, err = go(["whoami"], shims=shim, token=None)
    check(rc == 5 and stub.requests == [], "no token exits 5 and sends nothing")
    check(SERVICE in (out + err) and "phil" in (out + err) and "add-generic-password" in (out + err),
          "no-token message names the Keychain item to create")
    rc, out, err = go(["whoami", "--json"], shims=shim, token=None)
    obj = one_json(out)
    check(rc == 5 and obj and obj.get("code") == "no_token", "no token --json prints code no_token")
    # empty output from security counts as no item
    make_shims(shim, security="exit 0", secret_tool=None)
    rc, out, err = go(["whoami"], shims=shim, token=None)
    check(rc == 5, "an empty Keychain answer counts as no token")

    # ---------------- enroll with a fake security shim
    store = os.path.join(shim, "stored.txt")
    make_shims(shim,
               security=('case "$1" in find-generic-password) [ -s "%s" ] && { IFS= read -r t < "%s"; printf "%%s\\n" "$t"; exit 0; }; exit 44;; '
                         'add-generic-password) IFS= read -r a; IFS= read -r b; [ "$a" = "$b" ] || exit 9; '
                         'printf %%s "$a" > "%s"; exit 0;; esac; exit 1') % (store, store, store),
               secret_tool=None)
    open(os.path.join(shim, "argv.log"), "w").close()
    rc, out, err = go(["enroll"], shims=shim, token=None)
    stored = open(store).read() if os.path.exists(store) else ""
    check(rc == 0 and len(stored) >= 32, "enroll stores a generated token through the prompt")
    check(stored and hashlib.sha256(stored.encode()).hexdigest() in out, "enroll prints the token's sha256")
    check(stored and stored not in out and stored not in err, "enroll never prints the token")
    argv = open(os.path.join(shim, "argv.log")).read()
    check("add-generic-password -U -s %s -a phil -w" % SERVICE in argv, "enroll calls security add-generic-password -U ... -w")
    check(stored and stored not in argv, "enroll never puts the token in argv")
    seen.append((out, err))
    # a second enroll refuses to overwrite without --replace
    rc, out, err = go(["enroll"], shims=shim, token=None)
    check(rc != 0 and open(store).read() == stored, "enroll refuses to replace an existing token")
    rc, out, err = go(["enroll", "--replace"], shims=shim, token=None)
    check(rc == 0 and open(store).read() != stored, "enroll --replace makes a new token")
    seen.append((out, err))
    final = open(store).read()
    # Linux path: secret-tool store with the token on stdin
    shim2 = os.path.join(tmp, "shim2")
    store2 = os.path.join(shim2, "stored.txt")
    make_shims(shim2, security=None,
               secret_tool=('case "$1" in lookup) [ -s "%s" ] && { IFS= read -r t < "%s"; printf "%%s" "$t"; exit 0; }; exit 1;; '
                            'store) IFS= read -r t; printf "%%s" "$t" > "%s"; exit 0;; esac; exit 1') % (store2, store2, store2))
    rc, out, err = go(["enroll"], shims=shim2, token=None)
    st = open(store2).read().strip() if os.path.exists(store2) else ""
    check(rc == 0 and st and hashlib.sha256(st.encode()).hexdigest() in out and st not in out,
          "enroll on Linux stores through secret-tool stdin and prints only the sha256")
    check("store --label" in open(os.path.join(shim2, "argv.log")).read(), "secret-tool store has a label")

    # ---------------- the token never appears anywhere we printed
    for t in (tok, sec_tok, st_tok, stored, final, st):
        if not t:
            continue
        hit = any(t in o or t in e for o, e in seen)
        check(not hit, "token %s... absent from every stdout/stderr" % t[:6])

    stub.server.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    print("%d failure(s)" % len(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
