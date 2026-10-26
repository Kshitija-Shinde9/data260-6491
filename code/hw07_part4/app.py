from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import run_agent

HTML = """<!doctype html><html><head><meta charset=utf-8><title>Capital Bikeshare Advisor</title><style>body{font:15px system-ui;max-width:1180px;margin:30px auto;padding:0 20px;background:#f6f8fb;color:#172033}button{background:#1769aa;color:white;border:0;padding:10px 18px;border-radius:7px}input{padding:9px;width:70%}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.card{background:white;padding:18px;border-radius:10px;box-shadow:0 1px 5px #ccd}pre{white-space:pre-wrap}.ok{color:#067647}</style></head><body><h1>Capital Bikeshare membership advisor</h1><p>Upload a trip CSV with <code>started_at,duration_minutes,ride_id</code>.</p><form id=f><input type=file name=csv accept=.csv required><br><br><input name=url value="https://help.capitalbikeshare.com/hc/en-us/articles/360039401111-30-Day-Membership"><button>Run agent</button></form><div id=o></div><script>f.onsubmit=async e=>{e.preventDefault();o.innerHTML='<p>Running...</p>';let r=await fetch('/run',{method:'POST',body:new FormData(f)});let x=await r.json();o.innerHTML='<div class=grid><section class=card><h2>'+x.decision+'</h2><p>'+x.justification+'</p><h3>Costs</h3><pre>'+JSON.stringify(x.costs,null,2)+'</pre><p><b>Steps:</b> '+x.metrics.step_count+' &nbsp; <b>Time:</b> '+x.metrics.total_time_ms+' ms &nbsp; <b>Stop:</b> '+x.metrics.stop_reason+'</p></section><section class=card><h2>Tool timeline</h2><pre>'+x.timeline.map(t=>t.tool+' '+JSON.stringify(t.inputs)+'\\n'+JSON.stringify(t.observation)).join('\\n\\n')+'</pre></section></div><section class=card><h2>Weekly breakdown</h2><pre>'+JSON.stringify(x.weekly,null,2)+'</pre><h2>Citations</h2><pre>'+JSON.stringify(x.citations,null,2)+'</pre><h2>Evidence metadata</h2><pre>'+JSON.stringify(x.policy_metadata,null,2)+'</pre></section>'}</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(HTML.encode())

    def do_POST(self):
        if self.path != "/run":
            self.send_error(404)
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        ctype = self.headers.get("Content-Type", "")
        boundary = ctype.split("boundary=", 1)[-1].encode()
        fields = {}
        for part in body.split(b"--" + boundary):
            if b"\r\n\r\n" not in part:
                continue
            head, value = part.split(b"\r\n\r\n", 1)
            value = value.rstrip(b"\r\n-")
            import re

            m = re.search(rb'name="([^"]+)"', head)
            if m:
                fields[m.group(1).decode()] = value
        try:
            result = run_agent(
                fields.get("csv", b"").decode("utf-8", "replace"),
                fields.get("url", b"").decode() or None,
            )
            payload = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)
        except Exception as exc:
            self.send_error(400, str(exc))


if __name__ == "__main__":
    print("Open http://127.0.0.1:8787")
    ThreadingHTTPServer(("127.0.0.1", 8787), Handler).serve_forever()
