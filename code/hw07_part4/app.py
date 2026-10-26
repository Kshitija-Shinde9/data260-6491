from __future__ import annotations

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import run_agent

HTML = """<!doctype html><html><head><meta charset=utf-8><title>Capital Bikeshare Advisor</title><style>
body{font:15px system-ui;max-width:1180px;margin:30px auto;padding:0 20px;background:#f6f8fb;color:#172033}
button{background:#1769aa;color:white;border:0;padding:10px 18px;border-radius:7px}input,select{padding:9px}
label{display:block;margin:14px 0}input[name=url]{width:100%;box-sizing:border-box}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.card{background:white;padding:18px;border-radius:10px;box-shadow:0 1px 5px #ccd;margin-top:18px}pre{white-space:pre-wrap}
</style></head><body>
<h1>Capital Bikeshare membership advisor</h1>
<p>Upload a trip CSV with <code>started_at,duration_minutes,ride_id</code>. Part 5 uses this same agent.</p>
<form id=f>
<input type=file name=csv accept=.csv required><br><br>
<label>Pricing page <input name=url value="https://help.capitalbikeshare.com/hc/en-us/articles/360039401111-30-Day-Membership"></label><br><br>
<label>Defense <select name=defense>
<option value=both selected>Prompt + tool defense</option>
<option value=prompt>Prompt defense only</option>
<option value=before>Before defenses</option>
</select></label>
<button>Run agent</button>
</form>
<p>For the Part 5 fixture, set the pricing page to <code>reports/hw07/part4/scenarios/hostile_pricing.html</code> and upload <code>reports/hw07/part4/scenarios/injection_membership.csv</code>. Run it once in each defense mode.</p>
<div id=o></div>
<script>
function esc(s){return String(s==null?'':s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function outcome(ok){return ok?'succeeded':'blocked';}
f.onsubmit=async e=>{
e.preventDefault();
o.innerHTML='<p>Running...</p>';
let r=await fetch('/run',{method:'POST',body:new FormData(f)});
let x=await r.json();
let security='';
if(x.injection_present){
  let a=x.attacks||{};
  security='<section class=card><h2>Part 5 attacks</h2><p>Prompt defense: '+x.prompt_defense+' &nbsp; Tool defense: '+x.tool_defense+'</p><p>Recommendation override: '+outcome(a.recommendation_override)+'<br>Non-SELECT tool misuse: '+outcome(a.non_select)+'<br>Data exfiltration: '+outcome(a.data_exfiltration)+'</p><h3>Prompt</h3><pre>'+esc(x.prompt)+'</pre><h3>Answer</h3><pre>'+esc(x.answer)+'</pre></section>';
}
let gap=String.fromCharCode(10);
let timeline=esc(x.timeline.map(t=>t.tool+' '+JSON.stringify(t.inputs)+gap+JSON.stringify(t.observation)).join(gap+gap));
o.innerHTML='<div class=grid><section class=card><h2>'+esc(x.decision)+'</h2><p>'+esc(x.justification)+'</p><h3>Costs</h3><pre>'+esc(JSON.stringify(x.costs,null,2))+'</pre><p><b>Steps:</b> '+esc(x.metrics.step_count)+' &nbsp; <b>Time:</b> '+esc(x.metrics.total_time_ms)+' ms &nbsp; <b>Stop:</b> '+esc(x.metrics.stop_reason)+'</p></section><section class=card><h2>Tool timeline</h2><pre>'+timeline+'</pre></section></div><section class=card><h2>Weekly breakdown</h2><pre>'+esc(JSON.stringify(x.weekly,null,2))+'</pre><h2>Citations</h2><pre>'+esc(JSON.stringify(x.citations,null,2))+'</pre><h2>Evidence metadata</h2><pre>'+esc(JSON.stringify(x.policy_metadata,null,2))+'</pre></section>'+security;
};
</script></body></html>"""


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
            m = re.search(rb'name="([^"]+)"', head)
            if m:
                fields[m.group(1).decode()] = value
        try:
            mode = fields.get("defense", b"both").decode() or "both"
            result = run_agent(
                fields.get("csv", b"").decode("utf-8", "replace"),
                fields.get("url", b"").decode() or None,
                prompt_defense=mode != "before",
                tool_defense=mode == "both",
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
