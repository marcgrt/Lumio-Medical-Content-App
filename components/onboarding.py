"""Lumio — Interactive Spotlight Onboarding Tour (PromptLab-style).

Full-screen JS overlay with spotlight cutout on real UI elements.
Everything runs in JavaScript — no Streamlit reruns needed.
Improved: shorter texts, responsive width, quick-skip option.
"""

import streamlit as st


def inject_onboarding_tour():
    """Inject the onboarding tour JS. Call once in app.py."""
    st.components.v1.html(_TOUR_HTML, height=0)


_TOUR_HTML = r"""
<style>
@keyframes ltPulse{
  0%,100%{box-shadow:0 0 0 9999px rgba(0,0,0,0.72),0 0 0 3px rgba(132,204,22,0.30)}
  50%{box-shadow:0 0 0 9999px rgba(0,0,0,0.72),0 0 0 7px rgba(132,204,22,0.08)}
}
@keyframes ltSlideIn{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
@keyframes ltFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}
</style>
<script>
(function(){
var pd=window.parent.document, pw=window.parent;
if(pw.__ltInit) return;
pw.__ltInit=true;

/* ------------------------------------------------------------------ */
/* Element finders                                                    */
/* ------------------------------------------------------------------ */
function qSidebar(){return pd.querySelector('[data-testid="stSidebar"]')}
function qKPI(){return pd.querySelector('.sidebar-kpi-bar')}
function qTabBar(){return pd.querySelector('[data-testid="stTabs"] [role="tablist"]')}
function qFirstCard(){return pd.querySelector('.a-card')}
function qScoreRing(){return pd.querySelector('.a-score-ring')}
function qWatchlists(){
  var sb=qSidebar();
  if(!sb) return null;
  var exps=sb.querySelectorAll('[data-testid="stExpander"]');
  for(var i=0;i<exps.length;i++){
    if(exps[i].textContent.indexOf('Watchlist')!==-1) return exps[i];
  }
  return null;
}

/* ------------------------------------------------------------------ */
/* Tour Steps — concise, scannable                                    */
/* ------------------------------------------------------------------ */
var STEPS=[
  {
    title:"Willkommen bei Lumio!",
    text:"Lumio durchsucht t\u00e4glich <b>11 medizinische Quellen</b> \u2014 PubMed, Cochrane, \u00c4rzteblatt, WHO und mehr. Jeder Artikel wird automatisch nach Evidenz bewertet und per KI zusammengefasst.<br><br><span style='color:#84cc16'>\u23f1 Ca. 1 Minute</span> \u2014 oder klicke unten auf \u00bbSchnellstart\u00ab.",
    getEl:null, placement:"center", icon:"\u2728", showQuickStart:true
  },
  {
    title:"Sidebar: Deine Filter",
    text:"\u2022 <b>Zeitraum</b> \u2014 Heute / 7d / 30d / Alle<br>\u2022 <b>Fachgebiet</b> \u2014 Kardiologie, Onkologie \u2026<br>\u2022 <b>Mindest-Score</b> \u2014 Schieberegler<br>\u2022 <b>Sprache</b> \u2014 DE / EN / Alle<br><br>Unter \u00bbWeitere Filter\u00ab: Quellen, Studientyp, Open Access.",
    getEl:qSidebar, placement:"right", icon:"\u2699\ufe0f"
  },
  {
    title:"KPI-Leiste",
    text:"Drei Kennzahlen auf einen Blick:<br><br>\u2022 <b>Gesamt</b> \u2014 Alle Artikel in der DB<br>\u2022 <b>Top-Evidenz</b> \u2014 Score \u2265 65 (Meta-Analysen, RCTs, Leitlinien)<br>\u2022 <b>Alerts</b> \u2014 Offene Sicherheitsmeldungen",
    getEl:qKPI, placement:"right", icon:"\ud83d\udcca"
  },
  {
    title:"Sieben Arbeitsbereiche",
    text:"\u2022 <b>Feed</b> \u2014 Dashboard + Artikel-Feed + Themen-Radar<br>\u2022 <b>Suche</b> \u2014 Volltextsuche + Artikel-Werkbank<br>\u2022 <b>Insights</b> \u2014 Heatmap, Score-Verteilung, Quellen-Analyse<br>\u2022 <b>Redaktion</b> \u2014 L\u00fccken-Detektor + Konkurrenz-Radar<br>\u2022 <b>Versand</b> \u2014 Digest-Vorschau + Themen-Pakete<br>\u2022 <b>Kongresse</b> \u2014 Alle Aerztekongresse 2026 + Deadlines<br>\u2022 <b>Kalender</b> \u2014 Redaktionskalender",
    getEl:qTabBar, placement:"bottom", icon:"\ud83d\uddc2\ufe0f"
  },
  {
    title:"Artikel-Karte lesen",
    text:"<b>Links:</b> Score-Ring (0\u2013100) \u2014 <b>Mitte:</b> Titel, Journal, Datum, Fachgebiet \u2014 <b>Darunter:</b> KI-Zusammenfassung mit Kernbefund + Praxis-Tipp.<br><br>Aktionen: <b>\u2606</b> Merken \u2022 <b>\u2717</b> Ausblenden \u2022 <b>\u270d\ufe0f</b> KI-Entwurf generieren.",
    getEl:qFirstCard, placement:"top", icon:"\ud83d\udcf0"
  },
  {
    title:"Score-System",
    text:"<div style='display:grid;grid-template-columns:1fr 1fr;gap:4px 16px;font-size:12px'><span>Journal-Prestige</span><span style='color:#6b6b82'>30\u00a0%</span><span>Studiendesign</span><span style='color:#6b6b82'>25\u00a0%</span><span>Aktualit\u00e4t</span><span style='color:#6b6b82'>20\u00a0%</span><span>Keywords</span><span style='color:#6b6b82'>15\u00a0%</span><span>Arztrelevanz</span><span style='color:#6b6b82'>10\u00a0%</span></div><br>Farben: <b style='color:#4ade80'>\u2265 65 Top</b> \u2022 <b style='color:#eab308'>40\u201364 Solide</b> \u2022 <b style='color:#6b7280'>&lt; 40 News</b><br><br>\u00bbScore-Details\u00ab unter jeder Karte zeigt die Einzelwerte.",
    getEl:qScoreRing, placement:"right", icon:"\ud83c\udfaf"
  },
  {
    title:"Watchlists",
    text:"Verfolge Themen automatisch: Lege Keywords fest (z.\u00a0B. \u00bbSGLT2, Herzinsuffizienz\u00ab). Lumio pr\u00fcft bei jeder Pipeline, ob neue Treffer vorliegen.<br><br>Klicke auf \u00bbFiltern\u00ab neben einer Watchlist, um nur deren Treffer im Feed zu sehen.",
    getEl:qWatchlists, placement:"right", icon:"\ud83c\udfaf"
  },
  {
    title:"Los geht\u2019s!",
    text:"\u2022 <b>Artikel ausw\u00e4hlen</b> \u2192 \u00bbF\u00fcr PromptLab kopieren\u00ab<br>\u2022 <b>Versand-Tab</b> \u2192 Digest kopieren/herunterladen<br>\u2022 <b>Redaktion-Tab</b> \u2192 L\u00fccken + Konkurrenz analysieren<br>\u2022 <b>Tour wiederholen</b> \u2192 Klick auf <b>?</b> oben rechts<br><br><span style='color:#84cc16;font-weight:600'>Viel Spa\u00df mit Lumio!</span>",
    getEl:null, placement:"center", icon:"\ud83d\ude80"
  }
];

var TOTAL=STEPS.length, TW=440, GAP=16, KEY="lumio_onboarding_done";
var step=-1, overlay, spot, tip;

function done(){try{return localStorage.getItem(KEY)==="1"}catch(e){return false}}
function save(){try{localStorage.setItem(KEY,"1")}catch(e){}}
function clear(){try{localStorage.removeItem(KEY)}catch(e){}}

pw.__lumioRestartTour=function(){clear();pw.__ltInit=false;start()};

/* ------------------------------------------------------------------ */
/* DOM                                                                */
/* ------------------------------------------------------------------ */
function mkOverlay(){
  overlay=pd.createElement("div");
  overlay.id="lt-overlay";
  overlay.style.cssText="position:fixed;inset:0;z-index:20000;";
  overlay.addEventListener("click",function(e){if(e.target===overlay)finish()});

  spot=pd.createElement("div");
  spot.id="lt-spot";
  spot.style.cssText="position:fixed;border-radius:12px;pointer-events:none;z-index:20000;transition:all .4s cubic-bezier(.4,0,.2,1);";

  tip=pd.createElement("div");
  tip.id="lt-tip";
  tip.style.cssText="position:fixed;z-index:20001;width:"+TW+"px;max-width:calc(100vw - 32px);font-family:'Inter',system-ui,sans-serif;";

  pd.body.appendChild(overlay);
  pd.body.appendChild(spot);
  pd.body.appendChild(tip);
}
function rmOverlay(){
  if(overlay){overlay.remove();overlay=null}
  if(spot){spot.remove();spot=null}
  if(tip){tip.remove();tip=null}
}

/* ------------------------------------------------------------------ */
/* Render                                                             */
/* ------------------------------------------------------------------ */
function render(){
  if(step<0||step>=TOTAL){finish();return}
  var s=STEPS[step];
  var el=s.getEl?s.getEl():null;
  var centered=!el;

  // Spotlight
  if(centered){
    spot.style.cssText="display:none";
    overlay.style.background="rgba(0,0,0,0.78)";
  } else {
    overlay.style.background="transparent";
    el.scrollIntoView({behavior:"smooth",block:"center"});
    requestAnimationFrame(function(){requestAnimationFrame(function(){
      var r=el.getBoundingClientRect();
      var pad=12;
      spot.style.cssText="position:fixed;border-radius:12px;pointer-events:none;z-index:20000;"+
        "top:"+(r.top-pad)+"px;left:"+(r.left-pad)+"px;"+
        "width:"+(r.width+pad*2)+"px;height:"+(r.height+pad*2)+"px;"+
        "animation:ltPulse 2s ease-in-out infinite;"+
        "transition:all .4s cubic-bezier(.4,0,.2,1);";
      posTip(s,r);
    })});
    var r=el.getBoundingClientRect();
    posTip(s,r);
  }

  // Dots — clickable step indicators
  var dots="";
  for(var i=0;i<TOTAL;i++){
    var w=i===step?20:6;
    var bg=i<=step?"#84cc16":"rgba(255,255,255,0.1)";
    dots+='<div data-step="'+i+'" style="width:'+w+'px;height:6px;border-radius:3px;background:'+bg+';transition:all .3s;cursor:pointer"></div>';
  }

  var isFirst=step===0, isLast=step===TOTAL-1;

  // Quick start button (only on first step)
  var quickStartBtn = s.showQuickStart
    ? '<button id="lt-quick" style="background:none;border:1px solid rgba(255,255,255,0.10);color:#84cc16;font-size:11px;padding:6px 14px;border-radius:7px;cursor:pointer;font-family:inherit;margin-left:6px">Schnellstart \u2192</button>'
    : '';

  tip.innerHTML=
    '<div style="background:rgba(12,12,28,0.96);backdrop-filter:blur(30px);-webkit-backdrop-filter:blur(30px);'+
    'border:1px solid rgba(255,255,255,0.10);border-radius:14px;padding:22px 26px;'+
    'box-shadow:0 20px 60px rgba(0,0,0,0.6),0 0 0 1px rgba(132,204,22,0.06);'+
    'animation:ltSlideIn .3s ease-out;'+(centered?'max-width:500px;width:92%;margin:0 auto;':'')+'">'+

    // Title
    '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">'+
      '<div style="width:32px;height:32px;border-radius:9px;background:linear-gradient(135deg,#84cc16,#22d3ee);'+
      'display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:16px;animation:ltFloat 2.5s ease-in-out infinite">'+
        s.icon+'</div>'+
      '<span style="font-size:15px;font-weight:700;color:#fff;flex:1">'+s.title+'</span>'+
      '<span style="font-size:10px;color:#6b6b82;flex-shrink:0">'+(step+1)+' / '+TOTAL+'</span>'+
    '</div>'+

    // Text
    '<div style="font-size:13px;color:#b8b8cc;line-height:1.7;margin:0 0 16px">'+s.text+'</div>'+

    // Dots
    '<div id="lt-dots" style="display:flex;gap:4px;justify-content:center;margin-bottom:16px">'+dots+'</div>'+

    // Buttons
    '<div style="display:flex;align-items:center;justify-content:space-between">'+
      '<div style="display:flex;gap:8px;align-items:center">'+
        (isLast?'':'<button id="lt-skip" style="background:none;border:none;color:#6b6b82;font-size:11px;cursor:pointer;font-family:inherit">\u00dcberspringen</button>')+
        (step>0?'<button id="lt-prev" style="background:none;border:1px solid rgba(255,255,255,0.10);color:#b8b8cc;font-size:11px;padding:6px 14px;border-radius:7px;cursor:pointer;font-family:inherit">Zur\u00fcck</button>':'')+
        quickStartBtn+
      '</div>'+
      '<button id="lt-next" style="display:flex;align-items:center;gap:6px;padding:9px 22px;border-radius:8px;border:none;cursor:pointer;'+
      'background:linear-gradient(135deg,#84cc16,#22d3ee);color:#0a0a1a;font-size:12px;font-weight:700;font-family:inherit;transition:all .15s">'+
        (isLast?"Los geht\u2019s!":"Weiter \u2192")+
      '</button>'+
    '</div>'+
  '</div>';

  // Center tooltip
  if(centered){
    tip.style.cssText="position:fixed;z-index:20001;width:"+TW+"px;max-width:calc(100vw - 32px);font-family:'Inter',sans-serif;"+
      "top:50%;left:50%;transform:translate(-50%,-50%);";
  }

  // Bind buttons
  var sk=pd.getElementById("lt-skip");
  var pv=pd.getElementById("lt-prev");
  var nx=pd.getElementById("lt-next");
  var qs=pd.getElementById("lt-quick");
  if(sk)sk.onclick=finish;
  if(pv)pv.onclick=function(){step--;render()};
  if(nx)nx.onclick=function(){if(isLast)finish();else{step++;render()}};
  if(qs)qs.onclick=function(){step=TOTAL-1;render()};  // Jump to last step

  // Clickable dots for direct navigation
  var dotsEl=pd.getElementById("lt-dots");
  if(dotsEl) dotsEl.addEventListener("click",function(e){
    var target=e.target.closest("[data-step]");
    if(target){step=parseInt(target.dataset.step);render()}
  });
}

function posTip(s,rect){
  var pad=12;
  var r={top:rect.top-pad,left:rect.left-pad,width:rect.width+pad*2,height:rect.height+pad*2,
         cx:rect.left+rect.width/2,cy:rect.top+rect.height/2};
  var vh=pw.innerHeight,vw=pw.innerWidth,th=300;
  var t,l,p=s.placement||"bottom";

  if(p==="bottom"){t=r.top+r.height+GAP;l=r.cx-TW/2}
  else if(p==="top"){t=r.top-th-GAP;l=r.cx-TW/2}
  else if(p==="right"){t=r.cy-th/2;l=r.left+r.width+GAP}
  else{t=r.cy-th/2;l=r.left-TW-GAP}

  if(p==="bottom"&&t+th>vh-12){t=r.top-th-GAP}
  if(p==="top"&&t<12){t=r.top+r.height+GAP}
  if(p==="right"&&l+TW>vw-12){l=r.left-TW-GAP}

  l=Math.max(12,Math.min(l,vw-TW-12));
  t=Math.max(12,Math.min(t,vh-th-12));

  tip.style.cssText="position:fixed;z-index:20001;width:"+TW+"px;max-width:calc(100vw - 32px);font-family:'Inter',sans-serif;"+
    "top:"+t+"px;left:"+l+"px;animation:ltSlideIn .3s ease-out;";
}

/* ------------------------------------------------------------------ */
/* Lifecycle                                                          */
/* ------------------------------------------------------------------ */
function start(){step=0;mkOverlay();render();pd.addEventListener("keydown",keys)}
function finish(){step=-1;save();rmOverlay();pd.removeEventListener("keydown",keys)}
function keys(e){
  if(e.key==="ArrowRight"||e.key==="Enter"){e.preventDefault();if(step>=TOTAL-1)finish();else{step++;render()}}
  else if(e.key==="ArrowLeft"){e.preventDefault();if(step>0){step--;render()}}
  else if(e.key==="Escape"){e.preventDefault();finish()}
}

// Auto-start after Streamlit renders
if(!done()) setTimeout(start,1200);

})();
</script>
""".strip()
