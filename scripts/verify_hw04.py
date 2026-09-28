import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import warnings

warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, "code", "web_application")

SID4 = 6491
PORT_BASE = 8000 + (SID4 % 900)
PREFIX = f"s{SID4}"
SEED = SID4
VERIFY_SEED = 260000 + SID4
DOMAIN_ID = SID4 % 8
BASE = f"http://127.0.0.1:{PORT_BASE}"

DEMO_EMAIL = "admin@s6491.com"
DEMO_PASSWORD = "Recall@6491"
COOKIE_NAME = "s6491_sid"

checks = []


def check(name, passed, detail=""):
    checks.append({"name": name, "passed": bool(passed), "detail": str(detail)})
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def path(*parts):
    return os.path.join(ROOT, *parts)


def git(*args):
    try:
        out = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, timeout=10)
        return out.stdout.strip()
    except Exception:
        return ""


def port_open(port):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def check_deliverables():
    for rel in [
        "code/web_application/database.py",
        "code/web_application/models.py",
        "code/web_application/routers/api_auth.py",
        "code/web_application/.env",
        "code/web_application/frontend/package.json",
        "code/web_application/frontend/src/App.jsx",
        "code/web_application/frontend/src/pages/Login.jsx",
        "code/web_application/frontend/src/pages/Home.jsx",
        "code/web_application/frontend/src/pages/CreateRecord.jsx",
        "code/web_application/frontend/src/pages/UpdateRecord.jsx",
        "code/web_application/frontend/src/pages/DeleteRecord.jsx",
    ]:
        check(f"deliverable present: {rel}", os.path.isfile(path(rel)))


def check_mysql_tables():
    try:
        sys.path.insert(0, APP_DIR)
        from dotenv import load_dotenv
        load_dotenv(path("code", "web_application", ".env"))
        import pymysql
        from urllib.parse import urlparse, unquote

        url = urlparse(os.environ["DATABASE_URL"].replace("mysql+pymysql", "mysql"))
        conn = pymysql.connect(
            host=url.hostname, port=url.port or 3306,
            user=url.username, password=unquote(url.password or ""),
            database=url.path.lstrip("/"),
        )
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES")
            tables = {row[0] for row in cur.fetchall()}
        conn.close()
        check("MySQL reachable with s6491_rel database", True, f"tables: {sorted(tables)}")
        for t in ("recalls", "users", "sessions"):
            check(f"table exists: {t}", t in tables)
    except Exception as error:
        check("MySQL reachable with s6491_rel database", False, error)
        for t in ("recalls", "users", "sessions"):
            check(f"table exists: {t}", False, "MySQL check failed")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def fetch(fetch_path, method="GET", body=None, cookie=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + fetch_path, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        r = OPENER.open(req, timeout=15)
        raw = r.read().decode(errors="replace")
        return r.status, r.headers, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = None
        return e.code, e.headers, parsed


def check_api():
    status, _, _ = fetch("/api/recalls")
    check("unauthenticated GET /api/recalls is rejected", status == 401, f"HTTP {status}")

    status, _, body = fetch("/api/auth/login", "POST", {"email": DEMO_EMAIL, "password": "wrong-password"})
    check("login with a wrong password is rejected", status == 401, f"HTTP {status}")

    status, headers, user = fetch("/api/auth/login", "POST", {"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    raw_cookie = headers.get("set-cookie", "") if status == 200 else ""
    check("login with the correct password succeeds", status == 200, f"HTTP {status}")
    check("Set-Cookie is HttpOnly", "httponly" in raw_cookie.lower(), raw_cookie[:40])

    token = ""
    if "=" in raw_cookie:
        token = raw_cookie.split(";")[0].split("=", 1)[1]
    check("session cookie value is an opaque token, not the account's own data",
          bool(token) and DEMO_EMAIL not in token and (not user or str(user.get("id")) != token),
          f"token length {len(token)}")
    cookie = f"{COOKIE_NAME}={token}"

    status, _, recalls = fetch("/api/recalls", cookie=cookie)
    check("authenticated GET /api/recalls returns data", status == 200 and isinstance(recalls, list) and len(recalls) >= 3,
          f"HTTP {status}, {len(recalls) if isinstance(recalls, list) else 'n/a'} rows")

    status, _, created = fetch("/api/recalls", "POST",
                                {"product_name": "Verify HW4 Product", "supplier": "Verify HW4 Supplier"},
                                cookie=cookie)
    check("POST /api/recalls creates a record", status == 201 and created and created.get("product_name") == "Verify HW4 Product",
          f"HTTP {status}")
    new_id = created["id"] if created else None

    if new_id is not None:
        status, _, fetched = fetch(f"/api/recalls/{new_id}", cookie=cookie)
        check("GET /api/recalls/{id} returns the created record", status == 200 and fetched["id"] == new_id, f"HTTP {status}")

        status, _, updated = fetch(f"/api/recalls/{new_id}", "PUT",
                                    {"product_name": "Verify HW4 Product Updated", "supplier": "Verify HW4 Supplier"},
                                    cookie=cookie)
        check("PUT /api/recalls/{id} updates the record", status == 200 and updated["product_name"] == "Verify HW4 Product Updated",
              f"HTTP {status}")

        status, _, _ = fetch(f"/api/recalls/{new_id}", "DELETE", cookie=cookie)
        check("DELETE /api/recalls/{id} removes the record", status == 204, f"HTTP {status}")

        status, _, _ = fetch(f"/api/recalls/{new_id}", cookie=cookie)
        check("deleted record is gone", status == 404, f"HTTP {status}")
    else:
        check("GET /api/recalls/{id} returns the created record", False, "no id from create step")
        check("PUT /api/recalls/{id} updates the record", False, "no id from create step")
        check("DELETE /api/recalls/{id} removes the record", False, "no id from create step")
        check("deleted record is gone", False, "no id from create step")

    status, _, _ = fetch("/api/auth/logout", "POST", cookie=cookie)
    check("logout succeeds", status == 200, f"HTTP {status}")

    status, _, _ = fetch("/api/recalls", cookie=cookie)
    check("logged-out cookie can no longer reach /api/recalls", status == 401, f"HTTP {status}")


def main():
    print(f"HW4 self-check - SID4 {SID4}, DOMAIN_ID {DOMAIN_ID}\n")
    check_deliverables(); print()
    check_mysql_tables(); print()

    if port_open(PORT_BASE):
        print(f"Port {PORT_BASE} is already in use. Stop the running server first, then run this script again.")
        return 1

    python = os.path.join(ROOT, ".venv", "bin", "python")
    server = subprocess.Popen(
        [python, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(PORT_BASE)],
        cwd=APP_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(40):
            if port_open(PORT_BASE):
                break
            time.sleep(0.5)
        else:
            check("backend starts and responds on PORT_BASE", False, "server did not start")
            return 1
        check("backend starts and responds on PORT_BASE", True, BASE)

        check_api()
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        print("\ntest server stopped.")

    passed = sum(1 for c in checks if c["passed"])
    doc = {
        "homework": "HW4",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sid4": SID4,
        "port_base": PORT_BASE,
        "prefix": PREFIX,
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "domain_id": DOMAIN_ID,
        "domain": "Grocery supply and recall notices",
        "commit_hash": git("rev-parse", "HEAD") or "not a git repository",
        "tag": git("describe", "--tags", "--abbrev=0") or "no tag",
        "configuration": {
            "model_used": "none - HW4 is a MySQL/FastAPI/React CRUD app, no LLM involved",
            "database": f"MySQL - {PREFIX}_rel",
            "password_hashing": "bcrypt",
            "session_token": "secrets.token_urlsafe(32), stored server-side in the sessions table",
        },
        "total_checks": len(checks),
        "passed": passed,
        "failed": len(checks) - passed,
        "checks": checks,
    }

    out = path("reports", "hw04", "verification.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(doc, f, indent=2)

    print(f"\n{passed}/{len(checks)} checks passed.")
    print("Written to reports/hw04/verification.json")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
