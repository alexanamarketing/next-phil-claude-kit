#!/usr/bin/env python3
"""sitedoor: change an agent's record on the website database through the editor door.

The editor door is one web address on the website's database server. It accepts
a short list of agent-record changes (bio, title, testimonials, past sales,
service areas, social links, license number, office address, headshot, homepage
SEO text), shows the change before writing it, logs every write in the MLS log,
and can undo any write. This script is the only way the sitedoor skill talks to it.

Subcommands:
  whoami                                  which token this machine holds (account, scope)
  get <slug>                              the editable fields of one agent
  plan <slug> --payload <file>            show the change a payload would make (writes nothing)
  apply <slug> --payload <file> --plan <plan_id> [--apply]
                                          without --apply: shows the plan again, writes nothing
                                          with --apply: writes the change the plan showed
  revert <slug> (--request <id> | --write <id>) [--apply]
                                          undo one change (dry without --apply)
  history <slug> [--limit N]              recent changes for one agent, newest first
  photo <slug> <file> [--apply]           check a photo locally; --apply uploads it and
                                          prints the storage URL to use in a change
  enroll [--replace]                      make a new token on this machine, store it in the
                                          Keychain, print only its fingerprint (sha256)

A payload file is a JSON object with an "op" key (the kind of change, for example
"testimonial_add") and the change's own fields. --op names the kind when the file
has no "op" key. Add --json to any subcommand to print exactly one JSON object.

Token: read inside this process from the macOS Keychain (item next-phil-editor,
account phil by default), else the Linux secret store, else SITEDOOR_TOKEN (tests
only). It is never printed, logged, or passed on a command line, any copy of it in
a door answer is printed as [redacted], and the tool never follows a redirect.
A token from the Keychain or the secret store goes only to the live door over
https; SITEDOOR_URL is honoured only with a SITEDOOR_TOKEN test token.

Exit codes: 0 ok, 2 usage, 3 network or certificate problem, 4 refused (by the
door or by a local check), 5 no token on this machine.
Environment: SITEDOOR_ACCOUNT (default phil); SITEDOOR_URL and SITEDOOR_TOKEN are for
tests only. Standard library only, Python 3.8+.
"""
import argparse
import builtins
import hashlib
import http.client
import json
import os
import re
import secrets
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

SERVICE = "next-phil-editor"
DEFAULT_URL = "https://next-snake-35.convex.site/editor/v1"
DEFAULT_ACCOUNT = "phil"
MAX_PHOTO_BYTES = 8 * 1024 * 1024
MIN_PHOTO_BYTES = 1024
TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-.~+/=]{20,}$")

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
TIMEOUT = 60

EXIT_OK, EXIT_USAGE, EXIT_NETWORK, EXIT_REFUSED, EXIT_NO_TOKEN = 0, 2, 3, 4, 5

TLS_HINT = (
    "Python could not check the website's security certificate. On a Mac, open "
    "Finder, then Applications, then the Python 3 folder, and double-click "
    "'Install Certificates.command'. Then try again."
)


class Fail(Exception):
    """A finished run that is not ok: carries the exit code and the JSON body to print."""

    def __init__(self, exit_code, body):
        super().__init__(body.get("reason", ""))
        self.exit_code = exit_code
        self.body = body


def local_refusal(reason_code, reason):
    return Fail(EXIT_REFUSED, {"ok": False, "code": "invalid", "reason_code": reason_code, "reason": reason})


# ------------------------------------------------------------------ request ids
def canonical_payload(payload):
    """The exact string sent as payload_json and hashed into the request id."""
    try:
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)
        text.encode("utf-8")
    except (ValueError, UnicodeEncodeError) as e:
        raise local_refusal("payload_not_json", "The payload cannot be sent as JSON (%s). Remove NaN, "
                                                "Infinity or broken characters and try again." % type(e).__name__)
    return text


def request_id(account, slug, op, payload_json, plan_id):
    """sha256 over the UTF-8 bytes of account|slug|op|payload_json|plan_id."""
    data = "|".join([account, slug, op, payload_json, plan_id]).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------ token
def account_name():
    return os.environ.get("SITEDOOR_ACCOUNT") or DEFAULT_ACCOUNT


def _run_quiet(argv, stdin_text=None):
    """Run a keychain program. Its output is returned to this process only."""
    try:
        r = subprocess.run(argv, input=stdin_text, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r


def _accept(token, source):
    _SECRETS.append(token)
    if not TOKEN_RE.match(token):
        raise Fail(EXIT_NO_TOKEN, {
            "ok": False, "code": "no_token", "reason_code": "bad_token_format",
            "reason": ("The editor token on this computer has spaces, line breaks or other characters a "
                       "token never has, so it was not used. Add it again in Terminal: security "
                       "add-generic-password -U -s %s -a %s -w" % (SERVICE, account_name())),
        })
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
    env = os.environ.get("SITEDOOR_TOKEN", "").strip()
    if env:
        return _accept(env, "env")
    raise Fail(EXIT_NO_TOKEN, {
        "ok": False, "code": "no_token", "reason_code": "no_token",
        "reason": ("No editor token on this computer for account '%s'. Add it once in Terminal "
                   "(not in Claude): security add-generic-password -U -s %s -a %s -w "
                   "and paste the token when it asks." % (account, SERVICE, account)),
    })


# ------------------------------------------------------------------ http
def _check_url(url, what):
    u = urllib.parse.urlparse(url)
    local = u.hostname in ("127.0.0.1", "localhost", "::1")
    if u.scheme == "https" or (u.scheme == "http" and local):
        return url
    raise Fail(EXIT_USAGE, {"ok": False, "code": "invalid", "reason_code": "bad_url",
                            "reason": "%s must be an https address" % what})


def door_url():
    return _check_url(os.environ.get("SITEDOOR_URL") or DEFAULT_URL, "SITEDOOR_URL")


def token_may_go_to(url, source):
    """A Keychain token goes only to the live door's host over https; a test token anywhere _check_url allows."""
    if source == "env":
        return True
    u, d = urllib.parse.urlparse(url), urllib.parse.urlparse(DEFAULT_URL)
    return u.scheme == "https" and u.hostname == d.hostname and u.port in (None, 443)


def network_code(exc):
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, ssl.SSLCertVerificationError) or isinstance(exc, ssl.SSLCertVerificationError):
        return "tls_certs"
    return "network"


def _network_fail(exc):
    code = network_code(exc)
    reason = TLS_HINT if code == "tls_certs" else (
        "Could not reach the editor door (%s). Check the internet connection and try again."
        % type(getattr(exc, "reason", exc)).__name__)
    return Fail(EXIT_NETWORK, {"ok": False, "code": code, "reason_code": code, "reason": reason})


class _Redirected(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect: urllib would re-send the Authorization header to the new address."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise _Redirected(code)


_OPENER = urllib.request.build_opener(_NoRedirect)


def _send(url, data, headers):
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with _OPENER.open(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read()
    except _Redirected as e:
        raise Fail(EXIT_NETWORK, {"ok": False, "code": "bad_response", "reason_code": "redirect",
                                  "reason": "The editor door answered with a redirect (HTTP %s); the tool does "
                                            "not follow redirects. Nothing was sent onward." % e})
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read()
        except (http.client.HTTPException, OSError) as e2:
            raise _network_fail(e2)
    except (urllib.error.URLError, OSError, ssl.SSLError, http.client.HTTPException) as e:
        raise _network_fail(e)


def call_door(token, body):
    """POST one request to the door. Returns (status, raw_text, parsed_dict)."""
    url = door_url()
    if not token_may_go_to(url, _TOKEN_SOURCE["source"]):
        raise Fail(EXIT_NETWORK, {"ok": False, "code": "invalid", "reason_code": "url_override_needs_test_token",
                                  "reason": "SITEDOOR_URL points somewhere other than the live editor door, and "
                                            "a Keychain token only ever goes to the live door. Unset SITEDOOR_URL."})
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    status, raw = _send(url, data, headers)
    text = raw.decode("utf-8", "replace").strip()
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None
    if not isinstance(parsed, dict):
        raise Fail(EXIT_NETWORK, {"ok": False, "code": "bad_response", "reason_code": "bad_response",
                                  "reason": "The editor door answered with something that is not JSON "
                                            "(HTTP %d). Try again in a minute." % status})
    if parsed.get("ok") is not True:
        parsed.setdefault("ok", False)
        raise Fail(EXIT_REFUSED, parsed)
    return status, text, parsed


# ------------------------------------------------------------------ payload files
def load_payload(path, op_flag):
    try:
        with open(path, encoding="utf-8") as f:
            obj = json.load(f)
    except OSError as e:
        raise Fail(EXIT_USAGE, {"ok": False, "code": "invalid", "reason_code": "payload_unreadable",
                                "reason": "Cannot read the payload file %s (%s)." % (path, e.strerror)})
    except ValueError as e:
        raise local_refusal("payload_not_json", "The payload file is not valid JSON: %s" % e)
    if not isinstance(obj, dict):
        raise local_refusal("payload_not_object", "The payload file must hold one JSON object.")
    op = op_flag or obj.get("op")
    obj.pop("op", None)
    if not isinstance(op, str) or not op:
        raise local_refusal("missing_op", "The payload file needs an \"op\" key (for example "
                                          "\"testimonial_add\"), or pass --op.")
    return op, obj


# ------------------------------------------------------------------ photos
def sniff_image(head):
    if head[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def check_photo(path):
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            head = f.read(16)
    except OSError as e:
        raise Fail(EXIT_USAGE, {"ok": False, "code": "invalid", "reason_code": "file_unreadable",
                                "reason": "Cannot read %s (%s)." % (path, e.strerror)})
    kind = sniff_image(head)
    if kind is None:
        raise local_refusal("bad_image_type", "Only JPEG, PNG or WEBP photos can be used (SVG and other "
                                              "files are refused). Export the photo as a JPEG and try again.")
    if size > MAX_PHOTO_BYTES:
        raise local_refusal("file_too_large", "The photo is %.1f MB; the limit is 8 MB. Export a smaller "
                                              "copy and try again." % (size / 1048576.0))
    if size < MIN_PHOTO_BYTES or not _photo_complete(path, kind, size, head):
        raise local_refusal("bad_image_type", "The photo file looks cut off or damaged. Export it again "
                                              "as a JPEG and try again.")
    return kind, size


def _photo_complete(path, kind, size, head):
    with open(path, "rb") as f:
        f.seek(max(0, size - 64))
        tail = f.read()
    if kind == "image/jpeg":
        return b"\xff\xd9" in tail
    if kind == "image/png":
        return b"IEND" in tail
    if kind == "image/webp":
        return int.from_bytes(head[4:8], "little") + 8 <= size
    return False


# ------------------------------------------------------------------ output
def _full(v):
    """A value printed whole: text as is, anything else as compact JSON."""
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def show_diff(body):
    """Every before and after value printed whole, so the user approves exactly what is written."""
    lines = []
    for d in body.get("diff") or []:
        if isinstance(d, dict):
            before, after = d.get("before"), d.get("after")
            lines.append("  %s: %s -> %s" % (d.get("path", "?"), _full(before), _full(after)))
            if isinstance(before, str) and isinstance(after, str) and len(after) < len(before):
                lines.append("  %s: %d characters -> %d characters (the new text is shorter)"
                             % (d.get("path", "?"), len(before), len(after)))
    return lines


def _short(v, n=200):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + "..."


class Out:
    def __init__(self, as_json):
        self.as_json = as_json
        self.printed_json = False

    def json_once(self, text_or_obj):
        if self.printed_json:
            return
        self.printed_json = True
        if isinstance(text_or_obj, str):
            print(text_or_obj)
        else:
            print(json.dumps(text_or_obj, ensure_ascii=False))

    def say(self, line=""):
        if not self.as_json:
            print(line)


# ------------------------------------------------------------------ commands
def cmd_whoami(a, out):
    _, text, body = call_door(read_token(account_name()), {"op": "whoami"})
    out.json_once(text) if out.as_json else None
    out.say("This computer's token: account %s (%s), scope %s." % (
        body.get("account"), body.get("person"), body.get("scope")))


def _flat(prefix, value, lines):
    if isinstance(value, dict):
        for k in sorted(value):
            _flat("%s.%s" % (prefix, k) if prefix else k, value[k], lines)
    else:
        lines.append("  %s: %s" % (prefix, _full(value)))


def cmd_get(a, out):
    _, text, body = call_door(read_token(account_name()), {"op": "get", "slug": a.slug})
    if out.as_json:
        out.json_once(text)
        return
    print("Agent %s (token %s, scope %s)" % (body.get("slug", a.slug), body.get("account"), body.get("scope")))
    lines = []
    _flat("", body.get("realtor") or {}, lines)
    print("Record fields:")
    print("\n".join(lines) if lines else "  (none)")
    tests = body.get("testimonials") or []
    print("Testimonials (%d):" % len(tests))
    for t in tests:
        tid = t.get("id") or {}
        print("  %s | content_sha256 %s | rating %s | %s" % (
            tid.get("reviewer_name", t.get("reviewer_name")), tid.get("content_sha256"), t.get("rating"),
            _full(t.get("content"))))
    sales = body.get("sales")
    if not sales:
        print("Past sales: no sales record for this agent (past sales live in the homepage layout file in git).")
    else:
        entries = list(sales.get("entries") or [])
        entries.sort(key=lambda e: str(e.get("close_date") or ""), reverse=True)
        n = len(entries)
        show = entries if a.sales == "all" else entries[:a.sales]
        print("Past sales: %d sales on file (source %s, stats %s)." % (
            n, sales.get("source") or "hand", _short(sales.get("stats"), 120)))
        if len(show) < n:
            print("  Showing the %d newest; add --sales all to see every sale and its id." % len(show))
        for e in show:
            print("  id %s | %s | %s, %s | %s | photo %s" % (
                e.get("id"), e.get("close_date") or "no date", e.get("address"), e.get("city"),
                e.get("price"), "yes" if e.get("photo") else "no"))
    draft = body.get("draft")
    if not draft:
        print("Homepage draft: none.")
    else:
        lines = []
        _flat("", draft, lines)
        print("Homepage draft fields:")
        print("\n".join(lines))


def cmd_history(a, out):
    _, text, body = call_door(read_token(account_name()), {"op": "history", "slug": a.slug, "limit": a.limit})
    if out.as_json:
        out.json_once(text)
        return
    rows = body.get("writes") or []
    if not rows:
        print("0 changes logged for %s." % a.slug)
    for r in rows:
        print("write %s  request %s  %s: %s -> %s%s" % (
            r.get("write_id"), r.get("request_id"), r.get("field_path"), _short(r.get("before"), 80),
            _short(r.get("after"), 80), "  (undone)" if r.get("reverted_at") else ""))


def _plan(a, token, op, payload_json, out):
    _, text, body = call_door(token, {"op": "plan", "slug": a.slug, "action": op, "payload_json": payload_json})
    if out.as_json:
        out.json_once(text)
    else:
        lines = show_diff(body)
        print("Planned change for %s (%s), nothing written yet:" % (a.slug, op))
        print("\n".join(lines) if lines else "  (no field would change)")
        for n in body.get("skipped_duplicate") or []:
            print("  already there, skipped: %s" % _short(n))
        for n in body.get("photo_check") or []:
            print("  photo check: %s" % _short(n))
        print("plan_id: %s" % body.get("plan_id"))
    return body


def cmd_plan(a, out):
    op, payload = load_payload(a.payload, a.op)
    pj = canonical_payload(payload)
    body = _plan(a, read_token(account_name()), op, pj, out)
    out.say("To write it after the user says yes: apply %s --payload %s --plan %s --apply"
            % (a.slug, a.payload, body.get("plan_id")))


def cmd_apply(a, out):
    op, payload = load_payload(a.payload, a.op)
    pj = canonical_payload(payload)
    account = account_name()
    token = read_token(account)
    if not a.apply:
        body = _plan(a, token, op, pj, out)
        expected = body.get("request_id")
        if expected and body.get("plan_id") == a.plan and expected != request_id(account, a.slug, op, pj, a.plan):
            out.say("Note: this computer's account name (%s) does not match the token's account, so the "
                    "door would refuse the write. Run whoami and set SITEDOOR_ACCOUNT to the account it shows."
                    % account)
        if body.get("plan_id") != a.plan:
            out.say("Note: the plan_id is now %s (the record changed since plan %s). Show this plan to "
                    "the user again before writing." % (body.get("plan_id"), a.plan))
        out.say("Nothing written. Add --apply to write this change.")
        return
    rid = request_id(account, a.slug, op, pj, a.plan)
    _, text, body = call_door(token, {"op": "apply", "slug": a.slug, "action": op, "payload_json": pj,
                                      "expect_before_sha256": a.plan, "request_id": rid})
    if out.as_json:
        out.json_once(text)
        return
    if body.get("replay_of"):
        print("Already written earlier (same change, same plan); nothing new was written.")
    else:
        print("Written: %s field change(s) on %s." % (body.get("changed"), a.slug))
    print("request_id: %s" % (body.get("request_id") or rid))
    ids = body.get("write_ids") or []
    if ids:
        print("write ids: %s" % ", ".join(str(i) for i in ids))
    print("To undo: revert %s --request %s --apply" % (a.slug, body.get("request_id") or rid))


def cmd_revert(a, out):
    token = read_token(account_name())
    if not a.apply:
        _, text, body = call_door(token, {"op": "history", "slug": a.slug, "limit": 50})
        rows = [r for r in body.get("writes") or []
                if (a.request and r.get("request_id") == a.request) or (a.write and r.get("write_id") == a.write)]
        if out.as_json:
            out.json_once({"ok": True, "dry_run": True, "would_revert": rows})
            return
        if not rows:
            print("That change is not in the last 50 changes for %s. --apply will still look it up by "
                  "its id and undo it if nothing changed it since." % a.slug)
            print("Nothing written. Add --apply to undo it.")
            return
        print("Would undo %d logged change(s) on %s:" % (len(rows), a.slug))
        for r in rows:
            print("  %s: %s -> back to %s" % (r.get("field_path"), _short(r.get("after"), 80),
                                              _short(r.get("before"), 80)))
        print("Nothing written. Add --apply to undo it.")
        return
    req = {"op": "revert", "slug": a.slug}
    if a.request:
        req["target_request_id"] = a.request
    else:
        req["write_id"] = a.write
    _, text, body = call_door(token, req)
    if out.as_json:
        out.json_once(text)
        return
    print("Undone: %s field change(s) on %s." % (body.get("changed"), a.slug))
    ids = body.get("write_ids") or []
    if ids:
        print("write ids: %s" % ", ".join(str(i) for i in ids))


def cmd_photo(a, out):
    kind, size = check_photo(a.file)
    if not a.apply:
        if out.as_json:
            out.json_once({"ok": True, "dry_run": True, "content_type": kind, "bytes": size})
        out.say("Photo looks fine: %s, %d bytes. Add --apply to upload it." % (kind, size))
        return
    token = read_token(account_name())
    _, _, issued = call_door(token, {"op": "photo_upload_url", "slug": a.slug})
    upload_url = issued.get("upload_url")
    if not isinstance(upload_url, str):
        raise Fail(EXIT_NETWORK, {"ok": False, "code": "bad_response", "reason_code": "bad_response",
                                  "reason": "The editor door did not return an upload address."})
    _check_url(upload_url, "the upload address")
    with open(a.file, "rb") as f:
        data = f.read()
    status, raw = _send(upload_url, data, {"Content-Type": kind})  # no token on this request
    try:
        storage_id = json.loads(raw.decode("utf-8")).get("storageId")
    except (ValueError, AttributeError):
        storage_id = None
    if status >= 300 or not storage_id:
        raise Fail(EXIT_NETWORK, {"ok": False, "code": "upload_failed", "reason_code": "upload_failed",
                                  "reason": "The photo upload did not go through (HTTP %d)." % status})
    _, text, body = call_door(token, {"op": "photo_finalize", "slug": a.slug, "storage_id": storage_id})
    if out.as_json:
        out.json_once(text)
        return
    print("Uploaded. Use this photo address in the change:")
    print(body.get("url"))


def cmd_enroll(a, out):
    account = account_name()
    has_security = bool(shutil.which("security"))
    has_secret_tool = bool(shutil.which("secret-tool"))
    if not (has_security or has_secret_tool):
        raise Fail(EXIT_NO_TOKEN, {"ok": False, "code": "no_token", "reason_code": "no_keychain",
                                   "reason": "No Keychain program found on this computer."})
    if not a.replace:
        try:
            read_existing = read_token_keychain_only(account)
        except Fail:
            read_existing = None
        if read_existing:
            raise local_refusal("token_exists", "A token for account '%s' is already in the Keychain. "
                                                "Use enroll --replace only if Anthony asked for a new one." % account)
    tok = secrets.token_urlsafe(32)
    _SECRETS.append(tok)
    if has_security:
        # security -i reads its command from stdin, so the token never reaches argv or a terminal prompt.
        r = _run_quiet(["security", "-i"],
                       stdin_text="add-generic-password -U -s %s -a %s -w %s\n" % (SERVICE, account, tok))
    else:
        r = _run_quiet(["secret-tool", "store", "--label", "%s %s" % (SERVICE, account),
                        "service", SERVICE, "account", account], stdin_text=tok)
    if r is None or r.returncode != 0:
        raise Fail(EXIT_NO_TOKEN, {"ok": False, "code": "no_token", "reason_code": "store_failed",
                                   "reason": "Could not save the new token in the Keychain."})
    if read_token_keychain_only(account) != tok:
        raise Fail(EXIT_NO_TOKEN, {"ok": False, "code": "no_token", "reason_code": "store_unverified",
                                   "reason": "Saved the token but could not read it back from the Keychain."})
    sha = hashlib.sha256(tok.encode("utf-8")).hexdigest()
    del tok
    if out.as_json:
        out.json_once({"ok": True, "account": account, "token_sha256": sha})
        return
    print("New token saved in the Keychain (item %s, account %s)." % (SERVICE, account))
    print("Send Anthony this fingerprint so he can switch it on (it is not the token):")
    print(sha)


def read_token_keychain_only(account):
    saved = os.environ.pop("SITEDOOR_TOKEN", None)
    try:
        return read_token(account)
    except Fail:
        return None
    finally:
        if saved is not None:
            os.environ["SITEDOOR_TOKEN"] = saved


# ------------------------------------------------------------------ main
def _sales_count(v):
    if v == "all":
        return "all"
    try:
        n = int(v)
    except ValueError:
        n = 0
    if n < 1:
        raise argparse.ArgumentTypeError("--sales takes a number or all")
    return n


def _limit(v):
    try:
        n = int(v)
    except ValueError:
        n = 0
    if not 1 <= n <= 50:
        raise argparse.ArgumentTypeError("--limit must be 1 to 50")
    return n


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print("sitedoor: %s" % message, file=sys.stderr)
        if "--json" in sys.argv[1:]:
            print(json.dumps({"ok": False, "code": "invalid", "reason_code": "usage", "reason": message}))
        sys.exit(EXIT_USAGE)


def build_parser():
    p = Parser(prog="sitedoor.py", description="Change an agent's website record through the editor door.")
    sub = p.add_subparsers(dest="cmd", parser_class=Parser)

    def add(name, help_text):
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("--json", action="store_true", help="print exactly one JSON object")
        return sp

    add("whoami", "show which token this computer holds")
    sp = add("get", "show an agent's editable fields")
    sp.add_argument("slug")
    sp.add_argument("--sales", type=_sales_count, default=20, metavar="N|all",
                    help="how many of the newest past sales to list (default 20, or all)")
    sp = add("history", "list recent changes for an agent")
    sp.add_argument("slug")
    sp.add_argument("--limit", type=_limit, default=20, help="1 to 50, default 20")
    sp = add("plan", "show what a change would do (writes nothing)")
    sp.add_argument("slug")
    sp.add_argument("--payload", required=True, metavar="FILE")
    sp.add_argument("--op", help="kind of change, when the payload file has no op key")
    sp = add("apply", "write a planned change (needs --apply)")
    sp.add_argument("slug")
    sp.add_argument("--payload", required=True, metavar="FILE")
    sp.add_argument("--op")
    sp.add_argument("--plan", required=True, metavar="PLAN_ID", help="the plan_id the user saw")
    sp.add_argument("--apply", action="store_true", help="actually write")
    sp = add("revert", "undo a change (needs --apply)")
    sp.add_argument("slug")
    which = sp.add_mutually_exclusive_group(required=True)
    which.add_argument("--request", metavar="REQUEST_ID")
    which.add_argument("--write", metavar="WRITE_ID")
    sp.add_argument("--apply", action="store_true")
    sp = add("photo", "check a photo, and upload it with --apply")
    sp.add_argument("slug")
    sp.add_argument("file")
    sp.add_argument("--apply", action="store_true")
    sp = add("enroll", "make a new token on this computer and store it in the Keychain")
    sp.add_argument("--replace", action="store_true")
    return p


COMMANDS = {"whoami": cmd_whoami, "get": cmd_get, "history": cmd_history, "plan": cmd_plan,
            "apply": cmd_apply, "revert": cmd_revert, "photo": cmd_photo, "enroll": cmd_enroll}


def main(argv=None):
    parser = build_parser()
    a = parser.parse_args(argv)
    if not a.cmd:
        parser.print_help(sys.stderr)
        return EXIT_USAGE
    out = Out(getattr(a, "json", False))
    try:
        COMMANDS[a.cmd](a, out)
        return EXIT_OK
    except Fail as f:
        if out.as_json:
            out.json_once(f.body)
        else:
            body = f.body
            print("sitedoor: %s (%s%s)" % (body.get("reason") or "refused", body.get("code"),
                                           "/" + body["reason_code"] if body.get("reason_code")
                                           and body.get("reason_code") != body.get("code") else ""),
                  file=sys.stderr)
        return f.exit_code
    except KeyboardInterrupt:
        return 130
    except Exception as e:  # never a traceback: it could carry request details
        body = {"ok": False, "code": "error", "reason_code": type(e).__name__,
                "reason": "sitedoor stopped on an unexpected %s." % type(e).__name__}
        if out.as_json:
            out.json_once(body)
        else:
            print("sitedoor: %s" % body["reason"], file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
