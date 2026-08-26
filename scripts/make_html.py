"""Write a self-contained interactive page from data.json (no network needed to view)."""
import argparse
import json
import os

# Files are read and written relative to the current directory, so run the
# scripts from wherever you want the output to land.
HERE = os.getcwd()

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="data.json")
ap.add_argument("--out", default="citation_map.html")
ap.add_argument("--heading", default="Who cites Santosh Ganji's four most-cited papers")
ARGS = ap.parse_args()
D = json.load(open(os.path.join(HERE, ARGS.data)))

TPL = """<!doctype html>
<meta charset="utf-8">
<title>Citation map - Santosh Ganji</title>
<style>
 :root { --bg:#0f1216; --panel:#171b21; --line:#2a313b; --text:#e6e9ee; --muted:#9aa4b2; }
 * { box-sizing:border-box; }
 body { margin:0; background:var(--bg); color:var(--text);
        font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }
 header { padding:20px 24px 12px; border-bottom:1px solid var(--line); }
 h1 { font-size:19px; margin:0 0 4px; font-weight:600; }
 .sub { color:var(--muted); font-size:13px; }
 .wrap { display:grid; grid-template-columns:1fr 380px; gap:0; height:calc(100vh - 74px); }
 #cv { display:block; width:100%; height:100%; cursor:grab; }
 .side { border-left:1px solid var(--line); overflow-y:auto; padding:16px; background:var(--panel); }
 .chips { padding:12px 24px; display:flex; gap:8px; flex-wrap:wrap; border-bottom:1px solid var(--line); }
 .chip { border:1px solid var(--line); background:transparent; color:var(--text); cursor:pointer;
         border-radius:999px; padding:5px 12px; font-size:12.5px; display:flex; align-items:center; gap:7px; }
 .chip.off { opacity:.38; }
 .dot { width:9px; height:9px; border-radius:50%; }
 .mode { margin-left:auto; display:flex; gap:6px; }
 h2 { font-size:12px; letter-spacing:.06em; text-transform:uppercase; color:var(--muted);
      margin:18px 0 8px; font-weight:600; }
 h2:first-child { margin-top:0; }
 table { width:100%; border-collapse:collapse; font-size:12.5px; }
 td { padding:4px 6px; border-bottom:1px solid var(--line); vertical-align:top; }
 td.n { text-align:right; color:var(--muted); width:34px; white-space:nowrap; }
 .cc { color:var(--muted); font-size:11px; }
 #tip { position:fixed; pointer-events:none; max-width:340px; background:#000d; color:#fff;
        border:1px solid var(--line); border-radius:6px; padding:8px 10px; font-size:12px;
        display:none; z-index:9; }
 a { color:#7cc0ff; }
</style>
<header>
 <h1>__HEAD__</h1>
 <div class="sub">__SUB__</div>
</header>
<div class="chips" id="chips"></div>
<div class="wrap">
  <canvas id="cv"></canvas>
  <div class="side" id="side"></div>
</div>
<div id="tip"></div>
<script>
const DATA = __DATA__;
let MODE = "paper";
const active = new Set(DATA.targets.map(t => t.key));

// ---------- chips
const chips = document.getElementById("chips");
DATA.targets.forEach(t => {
  const b = document.createElement("button");
  b.className = "chip";
  b.innerHTML = `<span class="dot" style="background:${t.color}"></span>${t.label}
                 <span class="cc">${t.collected}/${t.scholar_citations}</span>`;
  b.onclick = () => { active.has(t.key) ? active.delete(t.key) : active.add(t.key);
                      b.classList.toggle("off"); rebuild(); };
  chips.appendChild(b);
});
const mode = document.createElement("div");
mode.className = "mode";
[["paper","Papers"],["author","Authors"],["inst","Institutions"]].forEach(([k,lbl]) => {
  const b = document.createElement("button");
  b.className = "chip" + (k === MODE ? "" : " off");
  b.textContent = lbl;
  b.onclick = () => { MODE = k;
    [...mode.children].forEach(c => c.classList.add("off")); b.classList.remove("off"); rebuild(); };
  mode.appendChild(b);
});
chips.appendChild(mode);

// ---------- graph build
let nodes = [], links = [];
function rebuild() {
  const recs = DATA.records.filter(r => active.has(r.target));
  const byId = new Map();
  const add = (id, o) => { if (!byId.has(id)) byId.set(id, Object.assign({id, x:0, y:0, vx:0, vy:0}, o));
                           return byId.get(id); };
  links = [];
  DATA.targets.filter(t => active.has(t.key)).forEach(t =>
    add("T:"+t.key, {label:t.label, kind:"target", color:t.color, r:15, meta:`${t.collected} citing papers collected of ${t.scholar_citations} on Google Scholar`}));

  recs.forEach(r => {
    if (MODE === "paper") {
      const n = add("P:"+r.title.toLowerCase().slice(0,80),
        {label:r.title, kind:"paper", color:r.self_citation ? "#d98880" : "#8b95a3", r:4.5,
         meta:`${r.venue||"—"} ${r.year||""}<br>${r.authors.join(", ")}<br>${r.institutions.join("; ")||"no affiliation in OpenAlex"}${r.doi?"<br>doi:"+r.doi:""}`});
      links.push({s:n.id, t:"T:"+r.target});
    } else if (MODE === "author") {
      r.authors.forEach(a => {
        const n = add("A:"+a, {label:a, kind:"author", color:"#16a085", r:4.5, count:0, meta:""});
        n.count++; n.r = 4 + Math.min(9, n.count * 1.6);
        links.push({s:n.id, t:"T:"+r.target});
      });
    } else {
      r.institutions.forEach(i => {
        const n = add("I:"+i, {label:i, kind:"inst", color:"#8e44ad", r:5, count:0, meta:""});
        n.count++; n.r = 4.5 + Math.min(11, n.count * 2.2);
        links.push({s:n.id, t:"T:"+r.target});
      });
    }
  });
  // dedupe links
  const seen = new Set();
  links = links.filter(l => { const k = l.s+">"+l.t; if (seen.has(k)) return false; seen.add(k); return true; });
  nodes = [...byId.values()];
  nodes.forEach((n,i) => { const a = i * 2.399; n.x = Math.cos(a)*Math.sqrt(i)*24; n.y = Math.sin(a)*Math.sqrt(i)*24; });
  nodes.forEach(n => { if (n.kind !== "target") n.meta = n.meta || `${n.count} citing paper(s)`; });
  alpha = 1;
  sidebar(recs);
}

// ---------- force layout
let alpha = 1;
function step() {
  const idx = new Map(nodes.map((n,i)=>[n.id,i]));
  for (const l of links) {
    const a = nodes[idx.get(l.s)], b = nodes[idx.get(l.t)];
    if (!a || !b) continue;
    let dx = b.x-a.x, dy = b.y-a.y, d = Math.hypot(dx,dy) || 0.01;
    const f = (d - 70) / d * 0.035 * alpha;
    a.vx += dx*f; a.vy += dy*f; b.vx -= dx*f; b.vy -= dy*f;
  }
  for (let i=0;i<nodes.length;i++) {
    const a = nodes[i];
    for (let j=i+1;j<nodes.length;j++) {
      const b = nodes[j];
      let dx = b.x-a.x, dy = b.y-a.y, d2 = dx*dx+dy*dy;
      if (d2 > 90000 || d2 === 0) continue;
      const d = Math.sqrt(d2), f = 260/d2 * alpha;
      a.vx -= dx/d*f; a.vy -= dy/d*f; b.vx += dx/d*f; b.vy += dy/d*f;
    }
    a.vx -= a.x*0.0022*alpha; a.vy -= a.y*0.0022*alpha;
    a.x += a.vx; a.y += a.vy; a.vx *= 0.82; a.vy *= 0.82;
  }
  alpha *= 0.997;
}

// ---------- render
const cv = document.getElementById("cv"), ctx = cv.getContext("2d");
let tx = 0, ty = 0, scale = 1;
function resize(){ cv.width = cv.clientWidth*devicePixelRatio; cv.height = cv.clientHeight*devicePixelRatio; }
addEventListener("resize", resize); resize();

function draw() {
  step();
  ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
  ctx.clearRect(0,0,cv.clientWidth,cv.clientHeight);
  ctx.save();
  ctx.translate(cv.clientWidth/2 + tx, cv.clientHeight/2 + ty); ctx.scale(scale, scale);
  const idx = new Map(nodes.map((n,i)=>[n.id,i]));
  ctx.strokeStyle = "rgba(150,160,175,.22)"; ctx.lineWidth = 1/scale;
  ctx.beginPath();
  for (const l of links) {
    const a = nodes[idx.get(l.s)], b = nodes[idx.get(l.t)];
    if (a && b) { ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); }
  }
  ctx.stroke();
  for (const n of nodes) {
    ctx.beginPath(); ctx.arc(n.x,n.y,n.r,0,6.2832);
    ctx.fillStyle = n.color; ctx.fill();
    ctx.lineWidth = 1/scale; ctx.strokeStyle = "rgba(15,18,22,.9)"; ctx.stroke();
  }
  ctx.fillStyle = "#e6e9ee"; ctx.font = `${12/scale}px -apple-system,sans-serif`;
  ctx.textAlign = "center";
  for (const n of nodes) {
    if (n.kind === "target") { ctx.fillText(n.label, n.x, n.y - n.r - 6/scale); }
    else if (n.r > 9) { ctx.fillText(n.label.slice(0,34), n.x, n.y - n.r - 4/scale); }
  }
  ctx.restore();
  requestAnimationFrame(draw);
}

// ---------- interaction
let drag = null;
cv.onmousedown = e => drag = {x:e.clientX, y:e.clientY, tx, ty};
addEventListener("mouseup", () => drag = null);
cv.onwheel = e => { e.preventDefault(); scale = Math.max(0.15, Math.min(6, scale * (e.deltaY<0?1.1:0.9))); };
const tip = document.getElementById("tip");
cv.onmousemove = e => {
  if (drag) { tx = drag.tx + e.clientX-drag.x; ty = drag.ty + e.clientY-drag.y; return; }
  const r = cv.getBoundingClientRect();
  const mx = (e.clientX-r.left - cv.clientWidth/2 - tx)/scale;
  const my = (e.clientY-r.top - cv.clientHeight/2 - ty)/scale;
  let hit = null;
  for (const n of nodes) if ((n.x-mx)**2 + (n.y-my)**2 < (n.r+4)**2) hit = n;
  if (hit) { tip.style.display="block"; tip.style.left=(e.clientX+14)+"px"; tip.style.top=(e.clientY+12)+"px";
             tip.innerHTML = `<b>${hit.label}</b><br>${hit.meta}`; }
  else tip.style.display = "none";
};

// ---------- sidebar
function sidebar(recs) {
  // counts are distinct citing papers, so a paper citing two targets is not double-counted
  const cnt = (get) => { const m = new Map();
    recs.forEach(r => get(r).forEach(v => {
      if (!m.has(v)) m.set(v, new Set());
      m.get(v).add(r.title.toLowerCase().slice(0,80));
    }));
    return [...m].map(([k,s])=>[k,s.size]).sort((a,b)=> b[1]-a[1] || a[0].localeCompare(b[0])); };
  const authors = cnt(r => [...new Set(r.authors)]);
  const insts = cnt(r => r.institutions);
  const countries = cnt(r => r.countries);
  const years = cnt(r => r.year ? [String(r.year)] : []).sort((a,b)=> a[0].localeCompare(b[0]));
  const tbl = (rows, n) => "<table>" + rows.slice(0,n).map(([k,v]) =>
      `<tr><td class="n">${v}</td><td>${k}</td></tr>`).join("") + "</table>";
  document.getElementById("side").innerHTML =
    `<h2>Totals</h2><table>
      <tr><td class="n">${new Set(recs.map(r=>r.title.toLowerCase().slice(0,80))).size}</td><td>citing papers shown</td></tr>
      <tr><td class="n">${authors.length}</td><td>distinct citing authors</td></tr>
      <tr><td class="n">${insts.length}</td><td>distinct institutions</td></tr>
      <tr><td class="n">${countries.length}</td><td>countries</td></tr>
      <tr><td class="n">${recs.filter(r=>r.self_citation).length}</td><td>self-citations</td></tr></table>
     <h2>Institutions</h2>${tbl(insts, 40)}
     <h2>Authors</h2>${tbl(authors, 60)}
     <h2>Countries</h2>${tbl(countries, 20)}
     <h2>Citing papers by year</h2>${tbl(years, 20)}`;
}

rebuild();
draw();
</script>
"""

sub = " &middot; ".join(
    f"{t['label']}: {t['collected']} of {t['scholar_citations']}" for t in D["targets"])
html = (TPL.replace("__DATA__", json.dumps(D))
           .replace("__SUB__", "Citing papers collected from Semantic Scholar, OpenAlex and "
                    "OpenCitations; affiliations from OpenAlex. " + sub))
html = html.replace("__HEAD__", ARGS.heading)
out = os.path.join(HERE, ARGS.out)
open(out, "w").write(html)
print("wrote", out, os.path.getsize(out), "bytes")
