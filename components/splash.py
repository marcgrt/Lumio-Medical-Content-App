"""Lumio — Morphing Data Stream Splash Screen.

Plays the data-stream intro video once on first visit, then fades to dashboard.
Full-screen overlay injected into Streamlit parent document.
Falls back to a CSS particle animation if autoplay is blocked.
"""

from pathlib import Path

import streamlit as st

_VIDEO_PATH = Path(__file__).parent.parent / "static" / "morphing-data-stream.mp4"


def inject_splash():
    """Inject the splash video overlay. Auto-skips on repeat visits."""
    if not _VIDEO_PATH.exists():
        return

    st.components.v1.html(_SPLASH_HTML, height=0)


_SPLASH_HTML = r"""
<script>
(function(){
var pd = window.parent.document;
var pw = window.parent;
var KEY = "lumio_splash_seen";

try { if(pw.localStorage.getItem(KEY)==="1") return; } catch(e){ return; }

var style = pd.createElement("style");
style.id = "lumio-splash-style";
style.textContent = [
  "@keyframes splashGlow{0%{transform:scale(0.2);opacity:0}40%{transform:scale(1.2);opacity:1}60%{transform:scale(1);opacity:1}100%{transform:scale(1);opacity:1}}",
  "@keyframes splashText{0%{opacity:0;transform:translateY(20px)}100%{opacity:1;transform:translateY(0)}}",
  "@keyframes splashParticle{0%{opacity:0;transform:translate(var(--sx),var(--sy)) scale(0.5)}60%{opacity:0.6}100%{opacity:0;transform:translate(0,0) scale(0.2)}}",
  "@keyframes splashPulse{from{opacity:0.2}to{opacity:0.5}}"
].join("\n");
pd.head.appendChild(style);

var ov = pd.createElement("div");
ov.id = "lumio-splash";
ov.style.cssText = "position:fixed;inset:0;z-index:99999;background:#0a0a0f;display:flex;align-items:center;justify-content:center;flex-direction:column;cursor:pointer;transition:opacity 0.8s ease-out;overflow:hidden";

var videoURL = "./app/static/morphing-data-stream.mp4";
var vid = pd.createElement("video");
vid.style.cssText = "max-height:80vh;max-width:90vw;object-fit:contain;position:absolute;top:50%;left:50%;transform:translate(-50%,-50%)";
vid.autoplay = true;
vid.muted = true;
vid.playsInline = true;
vid.preload = "none";
vid.src = videoURL;
ov.appendChild(vid);

// CSS fallback
var fallback = pd.createElement("div");
fallback.style.cssText = "position:absolute;inset:0;display:none;align-items:center;justify-content:center";
var TERMS = ["RCT","n=1204","p<0.001","NEJM","Lancet","Phase III","HR 0.72","Cochrane","BMJ","Meta-Analyse","PubMed","JAMA","Biomarker","PFS","ORR 42%","BRCA1","EGFR","PD-L1","CI 95%","NNT=12"];
var particleHTML = "";
for(var i=0;i<20;i++){
  var angle = (i/20)*Math.PI*2;
  var dist = 300+Math.random()*400;
  var sx = Math.round(Math.cos(angle)*dist);
  var sy = Math.round(Math.sin(angle)*dist);
  var delay = (Math.random()*1.5).toFixed(2);
  particleHTML += '<div style="position:absolute;top:50%;left:50%;font-family:monospace;font-size:'+(10+Math.random()*4)+'px;color:#84cc16;opacity:0;--sx:'+sx+'px;--sy:'+sy+'px;animation:splashParticle 3s '+delay+'s ease-in forwards">'+TERMS[i]+'</div>';
}
fallback.innerHTML = particleHTML
  + '<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:160px;height:160px;border-radius:50%;background:radial-gradient(circle,rgba(132,204,22,0.9),rgba(34,211,238,0.6) 40%,transparent 70%);filter:blur(40px);animation:splashGlow 3s 1.5s ease-out both"></div>'
  + '<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-55%);text-align:center;animation:splashText 1s 3.5s ease-out both;opacity:0"><div style="font-size:72px;font-weight:800;background:linear-gradient(135deg,#84cc16,#22d3ee);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-family:system-ui">L</div><div style="font-family:monospace;font-size:36px;color:#84cc16;letter-spacing:8px;margin-top:8px;animation:splashText 1s 4s ease-out both;opacity:0">lumio</div><div style="font-family:monospace;font-size:11px;color:rgba(132,204,22,0.4);letter-spacing:4px;margin-top:12px;text-transform:uppercase;animation:splashText 1s 4.5s ease-out both;opacity:0">Raw Data \u2192 Filtered Insight</div></div>';
ov.appendChild(fallback);

var hint = pd.createElement("div");
hint.style.cssText = "position:absolute;bottom:40px;left:50%;transform:translateX(-50%);font-family:monospace;font-size:12px;color:rgba(132,204,22,0.4);letter-spacing:3px;text-transform:uppercase;opacity:0;transition:opacity 1s;z-index:1";
hint.textContent = "Klicken zum \u00dcberspringen";
ov.appendChild(hint);
pd.body.appendChild(ov);

setTimeout(function(){ hint.style.opacity="1"; hint.style.animation="splashPulse 2s ease-in-out infinite alternate"; }, 1500);

var dismissed = false;
function dismiss(){
  if(dismissed) return;
  dismissed = true;
  try { pw.localStorage.setItem(KEY, "1"); } catch(e){}
  ov.style.opacity = "0";
  vid.pause();
  setTimeout(function(){
    ov.remove();
    var s = pd.getElementById("lumio-splash-style");
    if(s) s.remove();
  }, 800);
}

vid.addEventListener("ended", function(){ setTimeout(dismiss, 400); });
vid.addEventListener("canplay", function(){
  fallback.style.display = "none";
  vid.style.display = "block";
});

vid.play().then(function(){
  fallback.style.display = "none";
}).catch(function(){
  vid.style.display = "none";
  fallback.style.display = "flex";
  setTimeout(dismiss, 6000);
});

ov.addEventListener("click", dismiss);
setTimeout(dismiss, 8000);

})();
</script>
""".strip()
