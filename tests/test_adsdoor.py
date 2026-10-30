#!/usr/bin/env python3
"""adsdoor CLI test: a local http.server stub stands in for the ads status door.

Every fixture here is synthetic (sample-agent, sample-two, fake 15-digit Page ids,
fake names, an act id of zeros) and is built in code, so no real agent, Page or
account ever sits in this public repo.

Covers: the GET request shape (bearer header, ?agent= and ?all=1), the verdict line
and the plain-words problem lines for every gap the door can report, test accounts
hidden unless --all --tests, a partial answer when a source is down, every error
answer (401, 404, 429, 503, no answer, a timeout, a redirect), the Keychain lookup
order with fake `security` and `secret-tool` programs on PATH, --json passing the
vendored validator, and a closing sweep that the token never appears in stdout,
stderr or anywhere in the stub's request log except the Authorization header.

Run: python3 tests/test_adsdoor.py   (exit 0 = pass)
"""
import copy
import http.server
import importlib.util
import json
import os
import secrets
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "claude", "skills", "adsdoor", "tools")
CLI = os.path.join(TOOLS, "adsdoor.py")
SCHEMA = os.path.join(TOOLS, "schema.json")
SERVICE = "next-phil-ads-status"

FAILS = []


def check(cond, label):
    if cond:
        print("ok   " + label)
    else:
        print("FAIL " + label)
        FAILS.append(label)


# ---------------------------------------------------------------- synthetic documents
T_CHECK = "2026-10-29T18:00:00.000Z"
T_BOOT = "2026-10-29T12:00:00.000Z"
T_REFUSED = "2026-10-29T15:00:00.000Z"   # 8:00 AM in Arizona (UTC-7, no daylight saving)
T_STORED = "2026-10-20T10:00:00.000Z"
PAGE_A = "100000000000001"
PAGE_B = "100000000000002"
PAGE_C = "100000000000003"


def no_request():
    return {"requested_at": None, "requested_by": None, "approved_at": None, "assigned_at": None, "page_id": None}


def agent(slug, name, stored=PAGE_A, assigned=True, tasks=("ADVERTISE", "CREATE_CONTENT"), candidates=(),
          sms=True, refusal=None, test=False, fallback=False, state=None, request=None, allowed=False):
    assigned = bool(assigned and stored)
    tasks = list(tasks) if assigned else None
    page = {
        "stored_id": stored,
        "stored_updated_at": T_STORED if stored else None,
        "assigned": assigned,
        "assigned_name": (name + " Realty") if assigned else None,
        "has_advertise": bool(assigned and "ADVERTISE" in tasks),
        "has_create_content": bool(assigned and "CREATE_CONTENT" in tasks),
        "stored_matches_assigned": assigned,
        "tasks": tasks,
        "candidates": [dict(c) for c in candidates],
        "fallback": fallback,
    }
    connected = bool(assigned and page["has_advertise"] and page["has_create_content"] and sms)
    ok = bool(connected and (refusal is None or refusal["stale"]))
    return {
        "slug": slug, "name": name, "has_secrets_row": True, "test_identity": test, "page": page,
        "sms_map": sms, "engine_refusal": refusal, "ok": ok,
        "request_state": "connected" if connected else (state or "not_requested"),
        "request": request or no_request(), "request_allowed": allowed,
    }


def refusal(code="agent_page_not_connected", stale=False, reason=None):
    return {"code": code, "at": T_REFUSED, "stale": stale, "stale_reason": reason}


def document(agents, onboard_present=False):
    ok_src = {"ok": True, "read_at": T_CHECK}
    return {
        "schema_version": "ads-status/v1",
        "checked_at": T_CHECK,
        "meta_read_at": T_CHECK,
        "engine": {"sha": "a" * 40, "booted_at": T_BOOT, "billing_mode": "brokerage",
                   "billing_account_id": "act_" + "0" * 15, "scan_minutes": 15, "sms_mode": "live"},
        "sources": {"meta": dict(ok_src), "convex": dict(ok_src), "map": dict(ok_src), "ledger": dict(ok_src),
                    "onboard": {"ok": True, "read_at": T_CHECK, "present": onboard_present}},
        "agents": sorted(copy.deepcopy(agents), key=lambda a: a["slug"]),
    }


def meta_down(doc):
    d = copy.deepcopy(doc)
    d["sources"]["meta"] = {"ok": False, "read_at": None}
    d["meta_read_at"] = None
    d["kind"] = "source_unavailable"
    d["source"] = "meta"
    for a in d["agents"]:
        for f in ("assigned", "assigned_name", "has_advertise", "has_create_content", "stored_matches_assigned",
                  "tasks"):
            a["page"][f] = None
        a["page"]["candidates"] = []
        a["ok"] = None
    return d


GOOD = agent("sample-agent", "Sample Agent")
UNASSIGNED = agent("sample-two", "Sample Two", stored=None, assigned=False)
NO_ID = agent("sample-two", "Sample Two", stored=None, assigned=False,
              candidates=[{"id": PAGE_B, "name": "Sample Two Homes"}])
WRONG_ID = agent("sample-two", "Sample Two", stored=PAGE_C, assigned=False)
NO_CONTENT = agent("sample-two", "Sample Two", tasks=("ADVERTISE",))
NO_ADS = agent("sample-two", "Sample Two", tasks=("CREATE_CONTENT", "MANAGE"))
OFF_MAP = agent("sample-two", "Sample Two", sms=False)
REFUSED = agent("sample-two", "Sample Two", refusal=refusal())
REVOKED = agent("sample-two", "Sample Two", refusal=refusal("agent_page_revoked"))
STALE = agent("sample-two", "Sample Two", refusal=refusal(stale=True, reason="verified_after"))
DEMO = agent("next-demo", "Test Phil", stored=None, assigned=False, test=True, fallback=True)
PENDING = agent("sample-two", "Sample Two", stored=None, assigned=False, state="requested_pending",
                allowed=True, request={"requested_at": T_REFUSED, "requested_by": "admin:phil",
                                       "approved_at": None, "assigned_at": None, "page_id": PAGE_B})

# The click path from the approved copy (Block C, Anthony's Q4 answer, 2026-10-29), each paragraph in full.
SKIP_NOTE = "Skip the first paragraph if the Page already shows under Accounts > Pages."
CLICK_PATH_FULL = [
    "First get the Page into NEXT's business. Go to business.facebook.com/settings and pick the NEXT business. "
    "Left menu Accounts > Pages > Add > Request access to a Page. Paste the agent's Page name or link, turn on "
    "Content and Ads only, and send. The agent approves it on their Page under Settings > Page access.",
    "Then give it to NEXTOSADMIN. In the same settings, left menu Users > System users > NEXTOSADMIN > Assign "
    "assets. Pick Pages, tick the agent's Page, then under Partial access turn on Content and Ads and leave "
    "everything else off, including Full control. Save changes.",
]


def convex_down_empty():
    """The door's answer when the website database is down: no roster, so no agents at all."""
    d = document([])
    d["sources"]["convex"] = {"ok": False, "read_at": None}
    d["kind"] = "source_unavailable"
    d["source"] = "convex"
    return d


# ---------------------------------------------------------------- stub door
class Stub:
    def __init__(self, tls_context=None):
        self.requests = []
        self.responder = None  # fn(path) -> (status, bytes or None, extra headers)
        stub = self

        class H(http.server.BaseHTTPRequestHandler):
            def _answer(self):
                stub.requests.append({"method": self.command, "path": self.path, "headers": dict(self.headers)})
                status, out, extra = stub.responder(self.path)
                out = out or b""
                self.send_response(status)
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

            def do_GET(self):
                self._answer()

            def do_POST(self):
                self._answer()

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        if tls_context is not None:
            self.server.socket = tls_context.wrap_socket(self.server.socket, server_side=True)
        self.port = self.server.server_address[1]
        self.scheme = "https" if tls_context is not None else "http"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self):
        return "%s://127.0.0.1:%d/ads/status/v1" % (self.scheme, self.port)


def j(obj):
    return json.dumps(obj).encode("utf-8")


def serve(doc, status=200):
    return lambda path: (status, j(doc), None)


def hanging_server():
    """Accepts connections and never answers."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    held = []

    def loop():
        while True:
            try:
                c, _ = srv.accept()
            except OSError:
                return
            held.append(c)

    threading.Thread(target=loop, daemon=True).start()
    return srv, "http://127.0.0.1:%d/ads/status/v1" % srv.getsockname()[1]


def closed_port_url():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return "http://127.0.0.1:%d/ads/status/v1" % port


# ---------------------------------------------------------------- harness
def make_shims(d, security=None, secret_tool=None):
    """Fake keychain programs that log their argv. PATH holds only this dir."""
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


def run(args, token=None, shims=None, url=None, extra_env=None):
    env = {"HOME": os.environ.get("HOME", "/tmp"), "LANG": "C.UTF-8", "PYTHONIOENCODING": "utf-8"}
    env["PATH"] = shims or tempfile.mkdtemp(prefix="adsdoor-empty-")
    if token is not None:
        env["ADSDOOR_TOKEN"] = token
    if url:
        env["ADSDOOR_URL"] = url
    if extra_env:
        env.update(extra_env)
    r = subprocess.run([sys.executable, CLI] + args, capture_output=True, env=env, timeout=60)
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


def fake_token():
    return "adt" + "_" + secrets.token_urlsafe(30)


def one_json(out):
    try:
        obj = json.loads(out)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def load_module():
    spec = importlib.util.spec_from_file_location("adsdoor_under_test", CLI)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def flat(s):
    return " ".join(s.split())


# ---------------------------------------------------------------- tests
def main():
    check(os.path.isfile(CLI), "adsdoor.py exists")
    check(os.path.isfile(SCHEMA), "the vendored schema.json exists")
    if not (os.path.isfile(CLI) and os.path.isfile(SCHEMA)):
        print("%d failure(s)" % len(FAILS))
        return 1

    stub = Stub()
    tok = fake_token()
    seen = []  # every (stdout, stderr), swept for the token at the end

    def go(args, **kw):
        kw.setdefault("token", tok)
        kw.setdefault("url", stub.url)
        rc, out, err = run(args, **kw)
        seen.append((out, err))
        return rc, out, err

    # ---- the vendored validator: synthetic documents pass, planted defects fail
    mod = load_module()
    with open(SCHEMA, encoding="utf-8") as f:
        schema = json.load(f)
    check(schema.get("$id") == "ads-status/v1", "vendored schema is ads-status/v1")
    corpus = [document([GOOD]), document([GOOD, UNASSIGNED]), document([NO_ID]), document([WRONG_ID]),
              document([NO_CONTENT]), document([NO_ADS]), document([OFF_MAP]), document([REFUSED]),
              document([REVOKED]), document([STALE]), document([DEMO, GOOD]), meta_down(document([GOOD, OFF_MAP])),
              document([PENDING], onboard_present=True)]
    bad_corpus = [i for i, d in enumerate(corpus) if mod.validate_status_document(d)]
    check(not bad_corpus, "every synthetic document passes the vendored validator (failing: %s)" % bad_corpus)
    planted = {
        "phone": lambda d: d["agents"][0].update(name="Sample " + " ".join(["+1", "602", "555", "01" + "23"])),
        "email": lambda d: d["agents"][0]["page"].update(assigned_name="@".join(["someone", "example.com"])),
        "unknown key": lambda d: d["agents"][0].update(phone="x"),
        "meta token": lambda d: d["agents"][0].update(name="EAA" + "B" * 24),
        "numeric page id": lambda d: d["agents"][0]["page"].update(stored_id=900000000000001),
        "ok over off-map": lambda d: d["agents"][0].update(sms_map=False),
        "act id not a pattern": lambda d: d["engine"].update(billing_account_id="act_x"),
    }
    for label, plant in planted.items():
        d = document([GOOD])
        plant(d)
        check(bool(mod.validate_status_document(d)), "validator refuses a planted %s" % label)
    d = document([GOOD])
    d["agents"][0]["name"] = "Sample " + tok
    check(bool(mod.validate_status_document(d, secrets=[tok])), "validator refuses a document carrying the token")
    check(mod.validate_def("error_document", {"kind": "rate_limited", "retry_after_s": 30}) == [],
          "an error document validates")
    check(mod.validate_def("error_document", {"kind": "unauthorized", "slugs": ["a"]}) != [],
          "an error document with extra data is refused")
    odd = copy.deepcopy(schema)
    odd["$defs"]["slug"]["format"] = "hostname"
    try:
        mod.Validator(odd)
        refused_kw = False
    except ValueError:
        refused_kw = True
    check(refused_kw, "a schema keyword the validator does not know is refused at load")

    # ---- request shape
    stub.responder = serve(document([GOOD]))
    stub.requests.clear()
    rc, out, err = go(["--agent", "sample-agent"])
    check(rc == 0, "a working agent exits 0 (rc=%s err=%s)" % (rc, err.strip()[:120]))
    r0 = stub.requests[0] if stub.requests else {}
    check(r0.get("method") == "GET", "the door is called with GET")
    check(r0.get("path") == "/ads/status/v1?agent=sample-agent", "--agent sends ?agent=<slug>")
    check(r0.get("headers", {}).get("Authorization") == "Bearer " + tok, "the bearer header carries the token")
    check(out.strip() == "Sample Agent: ads connection working.", "the verdict line for a working agent")

    stub.requests.clear()
    stub.responder = serve(document([GOOD, UNASSIGNED]))
    rc, out, err = go(["--all"])
    check(stub.requests and stub.requests[0]["path"] == "/ads/status/v1?all=1", "--all sends ?all=1")
    check(rc == 1, "a missing piece exits 1")
    check("Sample Agent: ads connection working." in out, "--all prints a line for the working agent")
    check("Sample Two: ads connection not working. 1 thing to fix." in out,
          "--all prints the not-working verdict with the count")

    # ---- each gap in plain words, with who fixes it
    stub.responder = serve(document([UNASSIGNED]))
    rc, out, err = go(["--agent", "sample-two"])
    f = flat(out)
    check("The Facebook Page is not assigned to NEXT yet. Phil:" in f, "an unassigned Page says it is Phil's to do")
    check(all(b in f for b in CLICK_PATH_FULL) and SKIP_NOTE in f,
          "the unassigned line carries both approved click path paragraphs and the skip note in full")
    at = [f.find(x) for x in [SKIP_NOTE] + CLICK_PATH_FULL]
    check(min(at) >= 0 and at == sorted(at), "the skip note prints before the first click path paragraph")
    check("Send Meta request" not in out and "NEXT Tools" not in out and "has not sent" not in out,
          "an unconnected Page gets the manual click path, never a request button or an automatic request")

    stub.responder = serve(document([NO_ID]))
    rc, out, err = go(["--agent", "sample-two"])
    check("NEXT has the Page but the agent's record has no Page id. Anthony stores it. The Page that looks like "
          "theirs is Sample Two Homes, id %s." % PAGE_B in flat(out), "an assigned Page with no stored id names the candidate")
    check("Phil:" not in out, "no click path when the Page is already with NEXT")

    stub.responder = serve(document([WRONG_ID]))
    rc, out, err = go(["--agent", "sample-two"])
    check("The Page id on the agent's record is not one of the Pages NEXT has. Anthony and Phil check which "
          "Page is right." in flat(out), "a stored id that is not an assigned Page")

    stub.responder = serve(document([NO_CONTENT]))
    rc, out, err = go(["--agent", "sample-two"])
    check("NEXT can see the Page but is missing Create content. Phil: open the Page under NEXTOSADMIN in Business "
          "Settings and turn on Content." in flat(out), "a Page missing Create content")
    stub.responder = serve(document([NO_ADS]))
    rc, out, err = go(["--agent", "sample-two"])
    check("NEXT can see the Page but is missing Advertise. Phil: open the Page under NEXTOSADMIN in Business "
          "Settings and turn on Ads." in flat(out), "a Page missing Advertise (an extra MANAGE task is not a problem)")
    check("MANAGE" not in out, "an extra task is never raised")

    stub.responder = serve(document([OFF_MAP]))
    rc, out, err = go(["--agent", "sample-two"])
    check("The agent is not on the open-house text list yet, so they will not get the ad texts. Anthony adds "
          "them." in flat(out), "an agent off the text list")
    check(rc == 1, "off the text list exits 1")

    stub.responder = serve(document([REFUSED]))
    rc, out, err = go(["--agent", "sample-two"])
    check("The ads engine last turned Sample Two down at Oct 29 at 8:00 AM Arizona time because no Page was "
          "connected. If the Page id went on the record after that, the next scan picks it up within 15 minutes. "
          "No restart needed." in flat(out), "a live not-connected refusal, in Arizona time")
    stub.responder = serve(document([REVOKED]))
    rc, out, err = go(["--agent", "sample-two"])
    check("The ads engine last turned Sample Two down at Oct 29 at 8:00 AM Arizona time because the Page "
          "permissions were pulled. Anthony looks at it." in flat(out), "a revoked refusal is Anthony's")
    stub.responder = serve(document([STALE]))
    rc, out, err = go(["--agent", "sample-two"])
    check(rc == 0 and "turned" not in out and "ads connection working." in out,
          "a refusal the engine has moved past is not shown and does not count")

    # ---- request states the onboarding unit will report later
    stub.responder = serve(document([PENDING], onboard_present=True))
    rc, out, err = go(["--agent", "sample-two"])
    check("Waiting on Sample Two to approve NEXT's request on their Facebook Page. They find it under Settings > "
          "Page access > Pending requests. Sent Oct 29." in flat(out), "a pending request says where the agent approves it")

    # while requests are not open (no readable onboard state file) a request line is never shown
    stub.responder = serve(document([PENDING], onboard_present=False))
    rc, out, err = go(["--agent", "sample-two"])
    check(rc == 3 and "Waiting on" not in out and "Waiting on" not in err,
          "a request state with no onboard state file is refused and prints no request line")

    # ---- test accounts and the fallback Page
    stub.responder = serve(document([DEMO, GOOD]))
    rc, out, err = go(["--all"])
    check("Test Phil" not in out and rc == 0, "--all leaves test accounts out")
    rc, out, err = go(["--all", "--tests"])
    check("Test Phil, test account: ads connection not working." in out, "--all --tests marks a test account")
    check("Test Phil's ads post from NEXT's own Page on purpose, so the Page lines above don't apply to them."
          in flat(out), "a fallback slug says its ads post from NEXT's own Page on purpose")
    rc, out, err = go(["--tests"])
    check(rc == 3 and "--all" in (out + err), "--tests without --all is refused with a next step")

    # ---- a partial answer
    stub.responder = serve(meta_down(document([GOOD, OFF_MAP])), status=503)
    rc, out, err = go(["--all"])
    check("Sample Agent: could not check everything. Facebook did not answer, so this is partial." in out,
          "a 503 with a document names the source that did not answer")
    check("not on the open-house text list" in flat(out), "a partial answer still shows what it could read")
    check(rc == 1, "a partial answer exits 1")

    # the website database down: the door has no roster to send, so the answer is partial, never "all fine"
    stub.responder = serve(convex_down_empty(), status=503)
    rc, out, err = go(["--all"])
    check("No agents on the roster." not in out, "a down website database never reads as an empty roster")
    check("Could not check everything. The website database did not answer, so this is partial." in flat(out),
          "a down website database with no agents names the source and says the answer is partial")
    check(rc == 1, "a down website database with no agents exits 1 (rc=%s)" % rc)
    rc, out, err = go(["--all", "--json"])
    check(rc == 1 and one_json(out) == convex_down_empty(), "--json keeps exit 1 when a source is down and no agents")

    # ---- --json
    doc = document([GOOD, UNASSIGNED])
    stub.responder = serve(doc)
    rc, out, err = go(["--all", "--json"])
    obj = one_json(out)
    check(obj == doc, "--json prints the door's document as one JSON object")
    check(obj is not None and mod.validate_status_document(obj) == [], "--json output passes the vendored validator")
    check(rc == 1, "--json keeps the exit code")

    # ---- answers that are refused before anything prints
    leaky = document([GOOD])
    leaky["agents"][0]["name"] = "Sample " + tok
    stub.responder = serve(leaky)
    rc, out, err = go(["--agent", "sample-agent"])
    check(rc == 3 and "Sample" not in out, "an answer carrying the token is not printed")
    bad = document([GOOD])
    bad["agents"][0]["phone"] = "x"
    stub.responder = serve(bad)
    rc, out, err = go(["--agent", "sample-agent"])
    check(rc == 3 and "ads connection" not in out, "an answer outside the schema is not printed")
    stub.responder = lambda p: (200, b"<html>hi</html>", None)
    rc, out, err = go(["--all"])
    check(rc == 3, "a non-JSON answer exits 3")

    # ---- errors, each with a one-line next step
    cases = [
        (401, {"kind": "unauthorized"}, "The ads check did not accept your token. Ask Anthony for a new one."),
        (404, {"kind": "unknown_agent"},
         "There is no agent called sample-nobody on the roster. Run adsdoor --all to see everyone."),
        (429, {"kind": "rate_limited", "retry_after_s": 600},
         "You hit the limit of 60 checks an hour or 600 a day. Try again in 10 minutes."),
        (503, {"kind": "source_unavailable", "source": "engine"},
         "The ads engine did not answer right now. Try again in a few minutes. If it keeps failing, tell Anthony."),
        (503, {"kind": "source_unavailable", "source": "convex"},
         "The website database did not answer right now. Try again in a few minutes. If it keeps failing, "
         "tell Anthony."),
        (503, {"kind": "source_unavailable", "source": "elsewhere"},
         "Part of the ads check did not answer right now, and it did not say which part. Try again in a few "
         "minutes. If it keeps failing, tell Anthony."),
        (503, {"kind": "source_unavailable"},
         "Part of the ads check did not answer right now, and it did not say which part. Try again in a few "
         "minutes. If it keeps failing, tell Anthony."),
    ]
    for status, body, line in cases:
        stub.responder = serve(body, status=status)
        rc, out, err = go(["--agent", "sample-nobody"])
        check(rc == 3 and line in flat(out + err), "HTTP %d %s prints its next step" % (status, body))
    stub.responder = lambda p: (404, b"", None)
    rc, out, err = go(["--agent", "sample-agent"])
    check(rc == 3 and "not answering right now" in (out + err), "a door that is switched off reads as not answering")
    rc, out, err = go(["--agent", "sample-agent", "--json"])
    obj = one_json(out)
    check(rc == 3 and obj is not None and obj.get("ok") is False, "--json errors print one JSON object")

    hang, hang_url = hanging_server()
    t0 = time.time()
    rc, out, err = go(["--all"], url=hang_url, extra_env={"ADSDOOR_TIMEOUT": "2"})
    check(rc == 3 and "not answering right now" in (out + err) and time.time() - t0 < 30,
          "a door that never answers times out with the next step")
    hang.close()
    rc, out, err = go(["--all"], url=closed_port_url())
    check(rc == 3 and "not answering right now" in (out + err), "a closed port reads as not answering")

    stub.requests.clear()
    rc, out, err = go(["--agent", "Not_A_Slug"])
    check(rc == 3 and stub.requests == [], "a malformed slug is refused before any request")
    rc, out, err = go([])
    check(rc == 3 and stub.requests == [], "no --agent and no --all is refused with a next step")

    # a redirect is not followed (the Authorization header would go with it)
    other = Stub()
    other.responder = serve(document([GOOD]))
    stub.responder = lambda p: (302, b"", {"Location": other.url + "?all=1"})
    rc, out, err = go(["--all"])
    check(rc == 3 and other.requests == [], "a redirect is not followed")

    # ---- no token, Keychain order
    shim = tempfile.mkdtemp(prefix="adsdoor-shim-")
    make_shims(shim, security="exit 44", secret_tool="exit 1")
    stub.requests.clear()
    rc, out, err = go(["--all"], shims=shim, token=None)
    check(rc == 2 and stub.requests == [], "no token exits 2 and calls nothing")
    check("There is no ads check token in your Keychain. Run the Keychain step from the setup message again."
          in flat(out + err), "no token prints the Keychain next step")

    kc = fake_token()
    make_shims(shim, security='[ "$1" = find-generic-password ] && { echo "%s"; exit 0; }; exit 44' % kc)
    if os.path.exists(os.path.join(shim, "argv.log")):
        os.remove(os.path.join(shim, "argv.log"))
    stub.requests.clear()
    rc, out, err = go(["--all"], shims=shim, token=None)
    check(rc == 3 and stub.requests == [], "a Keychain token never goes to an address other than the live door")
    with open(os.path.join(shim, "argv.log")) as f:
        argv = f.read()
    check("find-generic-password -s %s -a phil -w" % SERVICE in argv, "security is asked for %s, account phil" % SERVICE)
    seen.append((out, err))
    check(kc not in out + err, "the Keychain token is not printed")
    check(not mod.token_may_go_to("https://example.com/ads/status/v1", "keychain"),
          "a Keychain token may not go to another https host")
    check(mod.token_may_go_to(mod.DEFAULT_URL, "keychain"), "a Keychain token may go to the live door")
    check(mod.DEFAULT_URL.startswith("https://"), "the live door is https")

    st = fake_token()
    make_shims(shim, security="exit 44", secret_tool='[ "$1" = lookup ] && { echo "%s"; exit 0; }; exit 1' % st)
    stub.requests.clear()
    rc, out, err = go(["--all"], shims=shim, token=None)
    check(rc == 3 and stub.requests == [] and st not in out + err, "secret-tool is the fallback, same rule")
    with open(os.path.join(shim, "argv.log")) as f:
        argv = f.read()
    check("lookup service %s account phil" % SERVICE in argv, "secret-tool is asked for the same item")

    # ---- https with a certificate the machine does not trust, then one it does
    if shutil.which("openssl"):
        d = tempfile.mkdtemp(prefix="adsdoor-tls-")
        cert, key = os.path.join(d, "c.pem"), os.path.join(d, "k.pem")
        r = subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                            "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1",
                            "-keyout", key, "-out", cert], capture_output=True, timeout=60)
        if r.returncode == 0:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(cert, key)
            tls = Stub(tls_context=ctx)
            tls.responder = serve(document([GOOD]))
            rc, out, err = go(["--all"], url=tls.url, extra_env={"SSL_CERT_FILE": cert})
            check(rc == 0 and "ads connection working." in out, "https to a trusted certificate works")
            rc, out, err = go(["--all"], url=tls.url, extra_env={"SSL_CERT_FILE": os.path.join(d, "none.pem")})
            check(rc == 3 and "Install Certificates" in (out + err), "an untrusted certificate prints the Mac fix")
        else:
            print("skip https case: openssl could not make a certificate")
    else:
        print("skip https case: no openssl")

    # ---- the token never leaks
    for out, err in seen:
        if tok in out or tok in err:
            check(False, "the token appeared in output")
            break
    else:
        check(True, "the token never appears in any stdout or stderr")
    stray = 0
    for s in (stub, other):
        for r in s.requests:
            rest = dict(r["headers"])
            rest.pop("Authorization", None)
            if tok in r["path"] or tok in json.dumps(rest):
                stray += 1
    check(stray == 0, "the token travels only in the Authorization header (%d stray)" % stray)

    print("%d failure(s)" % len(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
