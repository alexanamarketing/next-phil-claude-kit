#!/usr/bin/env python3
"""adsdoor: check whether an agent's Facebook ads connection works, through the ads status door.

The ads status door is one read-only web address on the ads engine. For each agent
it reports whether NEXT's system user holds the agent's Facebook Page with the Ads
and Content permissions, whether the agent's record carries that Page id, whether
the agent is on the open-house text list, and whether the ads engine last turned
the agent down. This script is the only way the adsdoor skill talks to it. It never
writes anything anywhere.

Usage:
  adsdoor.py --agent <slug>        one agent
  adsdoor.py --all                 every agent on the roster (test accounts left out)
  adsdoor.py --all --tests         every agent, test accounts included and marked
  add --json to print the door's answer as exactly one JSON object

Output: one verdict line per agent, then for each problem a line in plain words
saying what is missing, what to do and who does it (Phil or Anthony).

Token: read inside this process from the macOS Keychain (item next-phil-ads-status,
account phil by default), else the Linux secret store, else ADSDOOR_TOKEN (tests
only). It is never printed, logged, or passed on a command line, any copy of it in
a door answer is printed as [redacted], and the tool never follows a redirect. A
token from the Keychain or the secret store goes only to the live door over https;
ADSDOOR_URL is honoured only with an ADSDOOR_TOKEN test token.

Every answer is checked against the frozen schema (schema.json beside this file,
byte-identical to the ads engine's) and a leak scan before anything prints; an
answer that fails either is not shown.

Exit codes: 0 every agent shown is working, 1 something is missing (or could not
be read), 2 no token on this computer, 3 the door could not be reached or refused
the request (or a local check refused it).
Environment: ADSDOOR_ACCOUNT (default phil); ADSDOOR_URL, ADSDOOR_TOKEN and
ADSDOOR_TIMEOUT are for tests only. Standard library only, Python 3.8+.
"""
import argparse
import builtins
import datetime
import http.client
import json
import math
import os
import re
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

SERVICE = "next-phil-ads-status"
DEFAULT_URL = "https://meta.nextrealestate.team/ads/status/v1"
DEFAULT_ACCOUNT = "phil"
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.json")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-.~+/=]{20,}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

EXIT_OK, EXIT_MISSING, EXIT_NO_TOKEN, EXIT_REFUSED = 0, 1, 2, 3

# Every token value this process has read; print() below replaces each with [redacted].
_SECRETS = []
_TOKEN_SOURCE = {"source": None}


def _redact(text):
    for t in _SECRETS:
        if t:
            text = text.replace(t, "[redacted]")
    return text


def print(*args, **kwargs):  # noqa: A001  (module-wide redacting print)
    if _SECRETS:
        args = tuple(_redact(a if isinstance(a, str) else str(a)) for a in args)
    builtins.print(*args, **kwargs)


# ------------------------------------------------------------------ the words (approved copy, 2026-10-29)
SKIP_NOTE = "Skip the first paragraph if the Page already shows under Accounts > Pages."
CLICK_PATH = [
    "First get the Page into NEXT's business. Go to business.facebook.com/settings and pick the NEXT business. "
    "Left menu Accounts > Pages > Add > Request access to a Page. Paste the agent's Page name or link, turn on "
    "Content and Ads only, and send. The agent approves it on their Page under Settings > Page access.",
    "Then give it to NEXTOSADMIN. In the same settings, left menu Users > System users > NEXTOSADMIN > Assign "
    "assets. Pick Pages, tick the agent's Page, then under Partial access turn on Content and Ads and leave "
    "everything else off, including Full control. Save changes.",
]
NOT_ASSIGNED = "The Facebook Page is not assigned to NEXT yet. Phil: "
MISSING_TASK = ("NEXT can see the Page but is missing %s. Phil: open the Page under NEXTOSADMIN in Business "
                "Settings and turn on %s.")
NO_ID = ("NEXT has the Page but the agent's record has no Page id. Anthony stores it. The Page that looks like "
         "theirs is %s, id %s.")
WRONG_ID = ("The Page id on the agent's record is not one of the Pages NEXT has. Anthony and Phil check which "
            "Page is right.")
OFF_MAP = ("The agent is not on the open-house text list yet, so they will not get the ad texts. "
           "Anthony adds them.")
REFUSED_NOT_CONNECTED = ("The ads engine last turned %s down at %s because no Page was connected. If the Page id "
                         "went on the record after that, the next scan picks it up within %d minutes. "
                         "No restart needed.")
REFUSED_OTHER = "The ads engine last turned %s down at %s because %s. Anthony looks at it."
REASON_WORDS = {
    "agent_page_not_connected": "no Page was connected",
    "agent_page_revoked": "the Page permissions were pulled",
    "agent_page_unverifiable": "Facebook did not answer when it checked the Page",
    "agent_page_changed": "the Page changed between the ask and the approval",
    "unknown": "the engine gave a reason this check does not know yet",
}
FALLBACK = "%s's ads post from NEXT's own Page on purpose, so the Page lines above don't apply to them."
REQUEST_LINES = {
    "requested_pending": ("Waiting on %(name)s to approve NEXT's request on their Facebook Page. They find it "
                          "under Settings > Page access > Pending requests. Sent %(date)s."),
    "approved_unassigned": "%(name)s approved the request. NEXT is finishing the setup, which takes up to 5 minutes.",
    "expired": "The request to %(name)s expired before they approved it. Send it again from NEXT Tools.",
    "error": "The request to %(name)s hit a problem on Facebook's side. Anthony looks at it.",
}
NOT_REQUESTED = "NEXT has not sent %s a Page request yet."
SOURCE_WORDS = {"meta": "Facebook", "convex": "The website database", "map": "The text list",
                "ledger": "The ads engine's log", "engine": "The ads engine"}
PARTIAL = "could not check everything. %s did not answer, so this is partial."
SOURCE_NOT_ANSWERING = "%s did not answer right now. Try again in a few minutes. If it keeps failing, tell Anthony."
UNNAMED_NOT_ANSWERING = ("Part of the ads check did not answer right now, and it did not say which part. Try "
                         "again in a few minutes. If it keeps failing, tell Anthony.")

NO_TOKEN = "There is no ads check token in your Keychain. Run the Keychain step from the setup message again."
TOKEN_REFUSED = "The ads check did not accept your token. Ask Anthony for a new one."
UNKNOWN_AGENT = "There is no agent called %s on the roster. Run adsdoor --all to see everyone."
RATE_LIMITED = "You hit the limit of 60 checks an hour or 600 a day. Try again in %s."
NOT_ANSWERING = ("The ads check is not answering right now. Try again in a few minutes. If it keeps failing, "
                 "tell Anthony.")
TLS_HINT = (
    "Python could not check the ads check's security certificate. On a Mac, open "
    "Finder, then Applications, then the Python 3 folder, and double-click "
    "'Install Certificates.command'. Then try again."
)


class Fail(Exception):
    """A finished run that is not ok: carries the exit code and the JSON body to print."""

    def __init__(self, exit_code, reason_code, reason):
        super().__init__(reason)
        self.exit_code = exit_code
        self.body = {"ok": False, "reason_code": reason_code, "reason": reason}


# ------------------------------------------------------------------ the schema subset and leak scan
# A twin of the ads engine's lib/ads/status/validate.ts: the same JSON Schema subset,
# the same leak rules, the same cross-field invariants. Any schema keyword outside
# the subset is refused when the schema loads.
KNOWN_KEYWORDS = {
    "$schema", "$id", "$ref", "$defs", "title", "description",
    "type", "required", "properties", "additionalProperties", "enum", "const",
    "items", "pattern", "minimum", "maxLength", "propertyNames", "x-free-text",
}


def _canon(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"))


def _type_of(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "integer" if v.is_integer() else "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return "unknown"


class Validator:
    def __init__(self, schema):
        self.root = schema
        self._assert_known(schema, "#")

    def _assert_known(self, node, path, in_map=False):
        if not isinstance(node, dict):
            return
        for k, v in node.items():
            if in_map:
                self._assert_known(v, "%s/%s" % (path, k))
                continue
            if k not in KNOWN_KEYWORDS:
                raise ValueError("schema: unsupported keyword %s at %s" % (k, path))
            if k in ("$defs", "properties"):
                self._assert_known(v, "%s/%s" % (path, k), True)
            elif k in ("items", "additionalProperties", "propertyNames"):
                self._assert_known(v, "%s/%s" % (path, k))

    def _resolve(self, ref):
        m = re.match(r"^#/\$defs/([A-Za-z0-9_]+)$", ref)
        defs = self.root.get("$defs") or {}
        if not m or m.group(1) not in defs:
            raise ValueError("schema: unresolvable $ref %s" % ref)
        return defs[m.group(1)]

    def check(self, def_name, value):
        errors, free = [], []
        self._check({"$ref": "#/$defs/" + def_name}, value, "$", errors, free)
        return errors, free

    def _check(self, schema, value, path, errors, free):
        if isinstance(schema.get("$ref"), str):
            self._check(self._resolve(schema["$ref"]), value, path, errors, free)
            return
        actual = _type_of(value)
        if "type" in schema:
            want = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            if not any(actual == t or (t == "number" and actual == "integer") for t in want):
                errors.append("%s: expected %s, got %s" % (path, "|".join(want), actual))
                return
        if "const" in schema and _canon(schema["const"]) != _canon(value):
            errors.append("%s: expected const %s" % (path, _canon(schema["const"])))
        if isinstance(schema.get("enum"), list) and not any(_canon(e) == _canon(value) for e in schema["enum"]):
            errors.append("%s: value not in enum" % path)
        if isinstance(value, str):
            if isinstance(schema.get("pattern"), str) and not re.search(schema["pattern"], value):
                errors.append("%s: does not match %s" % (path, schema["pattern"]))
            if isinstance(schema.get("maxLength"), int) and len(value) > schema["maxLength"]:
                errors.append("%s: longer than %d" % (path, schema["maxLength"]))
            if schema.get("x-free-text") is True:
                free.append((path, value))
        if actual in ("integer", "number") and isinstance(schema.get("minimum"), (int, float)) \
                and value < schema["minimum"]:
            errors.append("%s: below minimum %s" % (path, schema["minimum"]))
        if isinstance(value, list) and isinstance(schema.get("items"), dict):
            for i, item in enumerate(value):
                self._check(schema["items"], item, "%s[%d]" % (path, i), errors, free)
        if isinstance(value, dict):
            props = schema.get("properties") or {}
            for req in schema.get("required") or []:
                if req not in value:
                    errors.append("%s: missing required %s" % (path, req))
            ap = schema.get("additionalProperties")
            for k, v in value.items():
                if k in props:
                    self._check(props[k], v, "%s.%s" % (path, k), errors, free)
                elif ap is False:
                    errors.append("%s: unknown key %s" % (path, k))
                elif isinstance(ap, dict):
                    self._check(ap, v, "%s.%s" % (path, k), errors, free)
            pn = schema.get("propertyNames")
            if isinstance(pn, dict) and isinstance(pn.get("pattern"), str):
                for k in value:
                    if not re.search(pn["pattern"], k):
                        errors.append("%s: bad key %s" % (path, k))


EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{8,}\d", re.A)
PIT_RE = re.compile(r"\bpit-[0-9a-f-]{8,}", re.I)
LONG_RE = re.compile(r"[A-Za-z0-9_-]{32,}")
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$")
META_TOKEN_RE = re.compile(r"\bEAA[A-Za-z0-9]{10,}")
RAW_RULES = [
    ("e164 phone", re.compile(r"\+1[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", re.A)),
    ("meta token", re.compile(r"EAA[A-Za-z0-9]{20,}")),
    ("access_token", re.compile(r"access_token", re.I)),
    ("ghl pit", re.compile(r"pit-[0-9a-f]{8}", re.I)),
    ("secret path", re.compile(r"/secrets/")),
]


def _free_text_problem(v):
    if EMAIL_RE.search(v):
        return "email"
    if PHONE_RE.search(v):
        return "phone"
    if PIT_RE.search(v):
        return "ghl pit"
    if META_TOKEN_RE.search(v):
        return "meta token"
    if any(not ENV_NAME_RE.match(t) for t in LONG_RE.findall(v)):
        return "key-like run"
    return None


def _leaks(doc, free, secrets):
    out = ["leak: %s at %s" % (p, path) for path, p in ((path, _free_text_problem(v)) for path, v in free) if p]
    raw = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    out += ["leak: %s in the serialized document" % label for label, rx in RAW_RULES if rx.search(raw)]
    if any(s and s in raw for s in secrets or []):
        out.append("leak: literal secret in the serialized document")
    return out


TEST_IDENTITIES = {"next-demo", "anthony-test", "bri-test", "bri-admin", "phil-sexton", "jim-sexton"}
OK_SOURCES = ("meta", "convex", "map", "ledger")


def _ms(iso):
    if iso is None:
        return float("nan")
    return datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
        tzinfo=datetime.timezone.utc).timestamp() * 1000


def check_invariants(doc):
    out = []

    def bad(path, why):
        out.append("invariant: %s: %s" % (path, why))

    src = doc["sources"]
    down = [k for k in OK_SOURCES if src[k]["ok"] is False]
    if down:
        if doc.get("kind") != "source_unavailable" or doc.get("source") != down[0]:
            bad("$", "source %s is down but kind/source do not say so" % down[0])
    elif "kind" in doc or "source" in doc:
        bad("$", "kind/source present with every source up")
    if (doc["meta_read_at"] is None) != (src["meta"]["ok"] is False):
        bad("$.meta_read_at", "must be null exactly when meta is down")
    for k in OK_SOURCES + ("onboard",):
        if src[k]["ok"] and src[k]["read_at"] is None:
            bad("$.sources." + k, "ok without read_at")
    meta_down, convex_down = src["meta"]["ok"] is False, src["convex"]["ok"] is False
    map_down, ledger_down = src["map"]["ok"] is False, src["ledger"]["ok"] is False
    slugs = [a["slug"] for a in doc["agents"]]
    if slugs != sorted(slugs):
        bad("$.agents", "not sorted by slug")
    if len(set(slugs)) != len(slugs):
        bad("$.agents", "duplicate slug")
    for i, a in enumerate(doc["agents"]):
        p = "$.agents[%d]" % i
        pg = a["page"]
        if a["test_identity"] != (a["slug"] in TEST_IDENTITIES):
            bad(p + ".test_identity", "does not match the test identity list")
        meta_fields = ("assigned", "assigned_name", "has_advertise", "has_create_content",
                       "stored_matches_assigned", "tasks")
        if meta_down or convex_down:
            for f in meta_fields:
                if pg[f] is not None:
                    bad("%s.page.%s" % (p, f), "must be null while meta or convex is down")
            if pg["candidates"]:
                bad(p + ".page.candidates", "must be empty while meta or convex is down")
        else:
            for f in ("assigned", "has_advertise", "has_create_content", "stored_matches_assigned"):
                if pg[f] is None:
                    bad("%s.page.%s" % (p, f), "null while meta is up")
            if pg["stored_id"] is None and (pg["assigned"] or pg["stored_matches_assigned"]):
                bad(p + ".page", "assigned with no stored id")
            if pg["assigned"] != pg["stored_matches_assigned"]:
                bad(p + ".page", "assigned and stored_matches_assigned disagree")
            if not pg["assigned"] and (pg["has_advertise"] or pg["has_create_content"]
                                       or pg["assigned_name"] is not None or pg["tasks"] is not None):
                bad(p + ".page", "task or name fields set on an unassigned Page")
            if pg["assigned"] and isinstance(pg["tasks"], list):
                if pg["has_advertise"] != ("ADVERTISE" in pg["tasks"]):
                    bad(p + ".page.has_advertise", "disagrees with tasks")
                if pg["has_create_content"] != ("CREATE_CONTENT" in pg["tasks"]):
                    bad(p + ".page.has_create_content", "disagrees with tasks")
            for c in pg["candidates"]:
                if c["id"] == pg["stored_id"]:
                    bad(p + ".page.candidates", "lists the stored Page")
            ids = [c["id"] for c in pg["candidates"]]
            if ids != sorted(ids):
                bad(p + ".page.candidates", "not sorted by id")
        if convex_down and (pg["stored_id"] is not None or pg["stored_updated_at"] is not None
                            or a["has_secrets_row"] is not None):
            bad(p + ".page", "stored fields must be null while convex is down")
        if not convex_down and a["has_secrets_row"] is None:
            bad(p + ".has_secrets_row", "null while convex is up")
        if not convex_down and a["has_secrets_row"] is False and (pg["stored_id"] is not None
                                                                   or pg["stored_updated_at"] is not None):
            bad(p + ".page", "stored fields without a secrets row")
        if (a["sms_map"] is None) != map_down:
            bad(p + ".sms_map", "must be null exactly when map is down")
        r = a["engine_refusal"]
        if ledger_down and r is not None:
            bad(p + ".engine_refusal", "must be null while the ledger is down")
        if r:
            if r["stale"] != (r["stale_reason"] is not None):
                bad(p + ".engine_refusal", "stale and stale_reason disagree")
            at, stored = _ms(r["at"]), _ms(pg["stored_updated_at"])
            stored_after = pg["stored_id"] is not None and stored > at
            if r["stale_reason"] == "restart_after_store":
                if not (stored_after and stored < _ms(doc["engine"]["booted_at"])):
                    bad(p + ".engine_refusal", "restart_after_store needs a stored id written after the refusal "
                                               "and before the boot")
            if r["stale_reason"] == "stored_after":
                scan = doc["engine"]["scan_minutes"] * 60000
                if not (r["code"] == "agent_page_not_connected" and stored_after
                        and _ms(doc["checked_at"]) >= stored + scan):
                    bad(p + ".engine_refusal", "stored_after needs agent_page_not_connected, a stored id after "
                                               "the refusal and one scan since the store")
        connected = bool(pg["assigned"] and pg["has_advertise"] and pg["has_create_content"]
                         and pg["stored_matches_assigned"] and a["sms_map"])
        if down:
            if a["ok"] is not None:
                bad(p + ".ok", "must be null while a source is down")
        else:
            want = bool(connected and (r is None or r["stale"]))
            if a["ok"] != want:
                bad(p + ".ok", "should be %s" % want)
        if not meta_down and not convex_down and not map_down:
            if (a["request_state"] == "connected") != connected:
                bad(p + ".request_state", "connected must equal the derivation (%s)" % connected)
        if a["request_state"] == "not_requested" and any(v is not None for v in a["request"].values()):
            bad(p + ".request", "fields set while not_requested")
        unread = src["onboard"]["present"] is False or src["onboard"]["ok"] is False
        if unread and (a["request_allowed"] or a["request_state"] not in ("not_requested", "connected")):
            bad(p, "request fields beyond not_requested without a readable onboard state file")
    return out


_VALIDATOR = {}


def validator():
    if "v" not in _VALIDATOR:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            _VALIDATOR["v"] = Validator(json.load(f))
    return _VALIDATOR["v"]


def validate_status_document(doc, secrets=None):
    """Every problem with a status document (shape, leaks, invariants). Empty means it may be shown."""
    errors, free = validator().check("status_document", doc)
    leaks = _leaks(doc, free, secrets)
    if errors:
        return errors + leaks
    try:
        inv = check_invariants(doc)
    except (KeyError, TypeError, ValueError) as e:
        inv = ["invariant: could not be checked (%s)" % type(e).__name__]
    return leaks + inv


def validate_def(def_name, value, secrets=None):
    """Shape and leak check of any $def (error_document, ...). Empty means valid."""
    errors, free = validator().check(def_name, value)
    return errors + _leaks(value, free, secrets)


# ------------------------------------------------------------------ token
def account_name():
    return os.environ.get("ADSDOOR_ACCOUNT") or DEFAULT_ACCOUNT


def _run_quiet(argv):
    """Run a keychain program. Its output is returned to this process only."""
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _accept(token, source):
    _SECRETS.append(token)
    if not TOKEN_RE.match(token):
        raise Fail(EXIT_NO_TOKEN, "bad_token_format", NO_TOKEN)
    _TOKEN_SOURCE["source"] = source
    return token


def read_token(account):
    if shutil.which("security"):
        r = _run_quiet(["security", "find-generic-password", "-s", SERVICE, "-a", account, "-w"])
        if r is not None and r.returncode == 0 and r.stdout.strip():
            return _accept(r.stdout.strip(), "keychain")
    if shutil.which("secret-tool"):
        r = _run_quiet(["secret-tool", "lookup", "service", SERVICE, "account", account])
        if r is not None and r.returncode == 0 and r.stdout.strip():
            return _accept(r.stdout.strip(), "keychain")
    env = os.environ.get("ADSDOOR_TOKEN", "").strip()
    if env:
        return _accept(env, "env")
    raise Fail(EXIT_NO_TOKEN, "no_token", NO_TOKEN)


# ------------------------------------------------------------------ http
def door_url():
    url = os.environ.get("ADSDOOR_URL") or DEFAULT_URL
    u = urllib.parse.urlparse(url)
    local = u.hostname in ("127.0.0.1", "localhost", "::1")
    if u.scheme == "https" or (u.scheme == "http" and local):
        return url
    raise Fail(EXIT_REFUSED, "bad_url", "ADSDOOR_URL must be an https address.")


def token_may_go_to(url, source):
    """A Keychain token goes only to the live door's host over https; a test token anywhere door_url allows."""
    if source == "env":
        return True
    u, d = urllib.parse.urlparse(url), urllib.parse.urlparse(DEFAULT_URL)
    return u.scheme == "https" and u.hostname == d.hostname and u.port in (None, 443)


class _Redirected(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect: urllib would re-send the Authorization header to the new address."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise _Redirected(code)


_OPENER = urllib.request.build_opener(_NoRedirect)


def _timeout():
    try:
        return max(1, min(120, int(os.environ.get("ADSDOOR_TIMEOUT") or 30)))
    except ValueError:
        return 30


def _is_tls(exc):
    reason = getattr(exc, "reason", exc)
    return isinstance(reason, ssl.SSLCertVerificationError) or isinstance(exc, ssl.SSLCertVerificationError)


def call_door(token, query):
    """GET the door. Returns (status, parsed JSON or None)."""
    base = door_url()
    if not token_may_go_to(base, _TOKEN_SOURCE["source"]):
        raise Fail(EXIT_REFUSED, "url_override_needs_test_token",
                   "ADSDOOR_URL points somewhere other than the live ads check, and a Keychain token only ever "
                   "goes there. Unset ADSDOOR_URL.")
    req = urllib.request.Request(base + "?" + urllib.parse.urlencode(query),
                                 headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
                                 method="GET")
    try:
        with _OPENER.open(req, timeout=_timeout()) as resp:
            status, raw = resp.status, resp.read()
    except _Redirected:
        raise Fail(EXIT_REFUSED, "redirect", NOT_ANSWERING)
    except urllib.error.HTTPError as e:
        try:
            status, raw = e.code, e.read()
        except (http.client.HTTPException, OSError):
            raise Fail(EXIT_REFUSED, "network", NOT_ANSWERING)
    except (urllib.error.URLError, OSError, ssl.SSLError, http.client.HTTPException) as e:
        if _is_tls(e):
            raise Fail(EXIT_REFUSED, "tls_certs", TLS_HINT)
        raise Fail(EXIT_REFUSED, "network", NOT_ANSWERING)
    try:
        parsed = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        parsed = None
    return status, parsed


def _minutes(seconds):
    n = max(1, int(math.ceil(seconds / 60.0)))
    return "1 minute" if n == 1 else "%d minutes" % n


def fetch(token, query, slug):
    """The door's status document, checked, or a Fail with the right next step."""
    status, body = call_door(token, query)
    if status in (200, 503) and isinstance(body, dict) and "schema_version" in body:
        if validate_status_document(body, secrets=[token]):
            raise Fail(EXIT_REFUSED, "answer_failed_checks", NOT_ANSWERING)
        return body
    kind = body.get("kind") if isinstance(body, dict) else None
    if status == 401:
        raise Fail(EXIT_REFUSED, "unauthorized", TOKEN_REFUSED)
    if status == 404 and kind == "unknown_agent":
        raise Fail(EXIT_REFUSED, "unknown_agent", UNKNOWN_AGENT % slug)
    if status == 400 and kind == "bad_query" and slug:
        raise Fail(EXIT_REFUSED, "bad_query", UNKNOWN_AGENT % slug)
    if status == 429 and kind == "rate_limited":
        retry = body.get("retry_after_s")
        retry = retry if isinstance(retry, int) and not isinstance(retry, bool) and retry > 0 else 3600
        raise Fail(EXIT_REFUSED, "rate_limited", RATE_LIMITED % _minutes(retry))
    if status == 503 and kind == "source_unavailable":
        source = body.get("source")
        if isinstance(source, str) and source in SOURCE_WORDS:
            raise Fail(EXIT_REFUSED, "source_unavailable", SOURCE_NOT_ANSWERING % SOURCE_WORDS[source])
        raise Fail(EXIT_REFUSED, "source_unavailable", UNNAMED_NOT_ANSWERING)
    code = kind if kind == "method_not_allowed" else "http_%d" % status
    raise Fail(EXIT_REFUSED, code, NOT_ANSWERING)


# ------------------------------------------------------------------ the report
def arizona(iso, with_time=True):
    """An ISO time as Phil reads it: Arizona time (UTC-7 all year)."""
    t = datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S.%fZ") - datetime.timedelta(hours=7)
    day = "%s %d" % (t.strftime("%b"), t.day)
    if not with_time:
        return day
    hour = t.hour % 12 or 12
    return "%s at %d:%02d %s Arizona time" % (day, hour, t.minute, "AM" if t.hour < 12 else "PM")


def problems(doc, a):
    """The plain-words lines for one agent, in the fixed order. Each is (text, extra lines)."""
    name = a["name"] or a["slug"]
    pg = a["page"]
    out = []
    if pg["assigned"] is not None:
        if pg["stored_id"] is None and not pg["assigned"]:
            if pg["candidates"]:
                c = pg["candidates"][0]
                out.append((NO_ID % (c["name"], c["id"]), []))
            else:
                out.append((NOT_ASSIGNED + SKIP_NOTE, CLICK_PATH))
        elif not pg["assigned"]:
            out.append((WRONG_ID, []))
        else:
            missing, turn_on = [], []
            if pg["has_create_content"] is False:
                missing.append("Create content")
                turn_on.append("Content")
            if pg["has_advertise"] is False:
                missing.append("Advertise")
                turn_on.append("Ads")
            if missing:
                out.append((MISSING_TASK % (" and ".join(missing), " and ".join(turn_on)), []))
    if a["sms_map"] is False:
        out.append((OFF_MAP, []))
    r = a["engine_refusal"]
    if r and not r["stale"]:
        when = arizona(r["at"])
        if r["code"] == "agent_page_not_connected":
            out.append((REFUSED_NOT_CONNECTED % (name, when, doc["engine"]["scan_minutes"]), []))
        else:
            out.append((REFUSED_OTHER % (name, when, REASON_WORDS.get(r["code"], REASON_WORDS["unknown"])), []))
    state = a["request_state"]
    if state in REQUEST_LINES:
        sent = a["request"]["requested_at"]
        out.append((REQUEST_LINES[state] % {"name": name, "date": arizona(sent, False) if sent else "earlier"}, []))
    elif state == "not_requested" and a["request_allowed"] and a["ok"] is False and pg["assigned"] is False:
        out.append((NOT_REQUESTED % name, []))
    return out


def any_down(doc):
    return doc.get("kind") == "source_unavailable" or any(doc["sources"][k]["ok"] is False for k in OK_SOURCES)


def first_down(doc):
    if doc.get("source") in SOURCE_WORDS:
        return doc["source"]
    for k in OK_SOURCES:
        if doc["sources"][k]["ok"] is False:
            return k
    return "meta"


def report(doc, show_tests):
    agents = [a for a in doc["agents"] if show_tests or not a["test_identity"]]
    if not agents:
        if any_down(doc):
            partial = PARTIAL % SOURCE_WORDS[first_down(doc)]
            print(partial[0].upper() + partial[1:])
            return EXIT_MISSING
        print("No agents on the roster.")
        return EXIT_OK
    rc = EXIT_OK
    for a in agents:
        name = a["name"] or a["slug"]
        lines = problems(doc, a)
        if a["ok"] is True:
            verdict = "ads connection working."
        elif a["ok"] is None:
            verdict = PARTIAL % SOURCE_WORDS[first_down(doc)]
            rc = EXIT_MISSING
        else:
            n = len(lines)
            verdict = "ads connection not working. %d %s to fix." % (n, "thing" if n == 1 else "things")
            rc = EXIT_MISSING
        print("%s%s %s" % (name, ", test account:" if a["test_identity"] else ":", verdict))
        if a["ok"] is True:
            continue
        for text, more in lines:
            print("  " + text)
            for m in more:
                print("    " + m)
        if a["page"]["fallback"]:
            print("  " + FALLBACK % name)
    return rc


# ------------------------------------------------------------------ main
class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Fail(EXIT_REFUSED, "usage", "adsdoor: %s. Say which agent with --agent <slug>, or use --all "
                                          "(add --tests to include test accounts)." % message)


def build_parser():
    p = Parser(prog="adsdoor.py", description="Check whether an agent's Facebook ads connection works.")
    p.add_argument("--agent", metavar="SLUG", help="one agent, by the slug in their site address")
    p.add_argument("--all", action="store_true", help="every agent on the roster")
    p.add_argument("--tests", action="store_true", help="with --all, include test accounts")
    p.add_argument("--json", action="store_true", help="print the door's answer as one JSON object")
    return p


def run(argv, as_json):
    a = build_parser().parse_args(argv)
    if a.agent and a.all:
        raise Fail(EXIT_REFUSED, "usage", "adsdoor: use --agent <slug> or --all, not both.")
    if not a.agent and not a.all:
        raise Fail(EXIT_REFUSED, "usage", "adsdoor: say which agent with --agent <slug>, or use --all "
                                          "to see everyone.")
    if a.tests and not a.all:
        raise Fail(EXIT_REFUSED, "usage", "adsdoor: --tests goes with --all (adsdoor --all --tests).")
    if a.agent and (not SLUG_RE.match(a.agent) or len(a.agent) > 64):
        raise Fail(EXIT_REFUSED, "bad_slug", UNKNOWN_AGENT % a.agent[:64])
    token = read_token(account_name())
    query = {"agent": a.agent} if a.agent else {"all": "1"}
    doc = fetch(token, query, a.agent)
    if as_json:
        print(json.dumps(doc, ensure_ascii=False, indent=2))
        shown = [x for x in doc["agents"] if a.agent or a.tests or not x["test_identity"]]
        if any_down(doc):
            return EXIT_MISSING
        return EXIT_OK if all(x["ok"] is True for x in shown) else EXIT_MISSING
    return report(doc, show_tests=bool(a.tests or a.agent))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    as_json = "--json" in argv
    try:
        return run(argv, as_json)
    except Fail as f:
        if as_json:
            print(json.dumps(f.body, ensure_ascii=False))
        else:
            print("%s (%s)" % (f.body["reason"], f.body["reason_code"]), file=sys.stderr)
        return f.exit_code
    except KeyboardInterrupt:
        return 130
    except Exception as e:  # never a traceback: it could carry request details
        body = {"ok": False, "reason_code": type(e).__name__, "reason": NOT_ANSWERING}
        if as_json:
            print(json.dumps(body))
        else:
            print("%s (%s)" % (NOT_ANSWERING, type(e).__name__), file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
