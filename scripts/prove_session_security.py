import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

SID4 = 6491
PORT_BASE = 8000 + (SID4 % 900)
IDLE_SECONDS = 5
BASE = f"http://127.0.0.1:{PORT_BASE}"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, "code", "web_application")

USERNAME = "kshitija"
PASSWORD = "Recall@6491"
COOKIE_NAME = "s6491_session"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def rule(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def port_open(port):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def fetch(path, data=None, cookie=None):
    req = urllib.request.Request(BASE + path, data=data,
                                 method="POST" if data else "GET")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        r = OPENER.open(req, timeout=15)
        return r.status, r.headers, r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read().decode(errors="replace")


def cookie_from(headers):
    m = re.search(rf"({COOKIE_NAME}=[^;]+)", headers.get("set-cookie", "") or "")
    return m.group(1) if m else ""


def login():
    body = f"username={USERNAME}&password={PASSWORD}".encode()
    status, headers, _ = fetch("/login", data=body)
    return status, headers, cookie_from(headers)


def main():
    if port_open(PORT_BASE):
        print(f"Port {PORT_BASE} is already in use.")
        print("Stop the running server first, then run this script again.")
        return 1

    env = dict(os.environ, SESSION_MAX_AGE=str(IDLE_SECONDS))
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app",
         "--host", "127.0.0.1", "--port", str(PORT_BASE)],
        cwd=APP_DIR, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    try:
        for _ in range(40):
            if port_open(PORT_BASE):
                break
            time.sleep(0.5)
        else:
            print("server did not start")
            return 1

        print(f"App started on {BASE}  (SESSION_MAX_AGE={IDLE_SECONDS}s)")
        results = []

        rule("CHECK 1 - the Set-Cookie header and its three attributes")

        status, headers, cookie = login()
        raw = headers.get("set-cookie", "")

        print(f"POST /login  ->  HTTP {status}")
        print(f"Location     ->  {headers.get('location')}")
        print()
        print("Set-Cookie: " + raw)
        print()

        attrs = {
            "HttpOnly": "httponly" in raw.lower(),
            "Secure": re.search(r"\bsecure\b", raw, re.I) is not None,
            "SameSite": "samesite" in raw.lower(),
        }
        for label, ok in attrs.items():
            print(f"  [{'PASS' if ok else 'FAIL'}] {label} attribute present")

        results.append(("login redirects to /dashboard", status == 303))
        for label, ok in attrs.items():
            results.append((f"{label} attribute present", ok))

        print(f"\nKeeping a raw copy of the cookie, as an attacker would:")
        print(f"  {cookie[:56]}...")

        rule("CHECK 2 - the session works while it is alive")

        status, _, page = fetch("/dashboard", cookie=cookie)
        greeted = "Welcome," in page
        ok = status == 200 and greeted
        print(f"GET /dashboard with a live session  ->  HTTP {status}")
        print(f"  page greets the user by name      ->  {'yes' if greeted else 'no'}")
        print(f"  [{'PASS' if ok else 'FAIL'}] logged-in user can reach the dashboard")
        results.append(("logged-in user reaches /dashboard", ok))

        rule("CHECK 3 - a LOGGED-OUT cookie cannot be replayed")

        status, _, _ = fetch("/logout", cookie=cookie)
        print(f"GET /logout  ->  HTTP {status}")

        status, headers, _ = fetch("/dashboard", cookie=cookie)
        loc = headers.get("location") or ""
        blocked = status == 303 and "/login" in loc
        print(f"GET /dashboard replaying the pre-logout cookie  ->  HTTP {status}")
        print(f"  Location -> {loc or '(none)'}")
        print(f"  [{'PASS' if blocked else 'FAIL'}] logged-out cookie is rejected")
        results.append(("logged-out cookie cannot reach /dashboard", blocked))

        rule(f"CHECK 4 - an IDLE session expires after {IDLE_SECONDS}s")

        status, _, cookie2 = login()
        print(f"Signed in again  ->  HTTP {status}")

        status, _, _ = fetch("/dashboard", cookie=cookie2)
        print(f"GET /dashboard immediately  ->  HTTP {status}   (expected 200)")
        results.append(("fresh session reaches /dashboard", status == 200))

        wait = IDLE_SECONDS + 3
        print(f"\nSitting idle for {wait} seconds, sending no requests at all...")
        time.sleep(wait)

        status, headers, _ = fetch("/dashboard", cookie=cookie2)
        loc = headers.get("location") or ""
        expired = status == 303 and "/login" in loc
        print(f"GET /dashboard after idling  ->  HTTP {status}")
        print(f"  Location -> {loc or '(none)'}")
        print(f"  [{'PASS' if expired else 'FAIL'}] idle-expired session is rejected")
        results.append(("idle-expired session cannot reach /dashboard", expired))

        rule("SUMMARY")

        for name, ok in results:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        passed = sum(1 for _, ok in results if ok)
        print(f"\n{passed}/{len(results)} checks passed.")
        return 0 if passed == len(results) else 1

    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        print("\ntest server stopped.")


if __name__ == "__main__":
    sys.exit(main())
