"""Lumio — Interactive Spotlight Onboarding Tour.

Full-screen JS overlay with spotlight cutout on real UI elements.
Navigates between ALL tabs, explaining each workspace.
Background music with mute button. Keyboard navigation.
"""

import streamlit as st


def inject_onboarding_tour():
    """Inject the onboarding tour JS. Call once in app.py."""
    st.components.v1.html(_TOUR_HTML, height=0)


_TOUR_HTML = r"""
<style>
@keyframes ltPulse{
  0%,100%{box-shadow:0 0 0 9999px rgba(0,0,0,0.8),0 0 0 4px rgba(132,204,22,0.5),0 0 30px rgba(132,204,22,0.2),0 0 60px rgba(132,204,22,0.08)}
  50%{box-shadow:0 0 0 9999px rgba(0,0,0,0.8),0 0 0 10px rgba(132,204,22,0.15),0 0 50px rgba(132,204,22,0.1),0 0 100px rgba(132,204,22,0.04)}
}
@keyframes ltSlideIn{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
@keyframes ltFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}
@keyframes ltEq{0%,100%{height:3px}50%{height:12px}}
</style>
<script>
(function(){
var pd=window.parent.document, pw=window.parent;
["lt-overlay","lt-spot","lt-tip"].forEach(function(id){
  var el=pd.getElementById(id); if(el) el.remove();
});
if(pw.__ltInit) return;
pw.__ltInit=true;

/* ------------------------------------------------------------------ */
/* Audio removed — no music in onboarding */
function startAudio(){}
function stopAudio(){}
function toggleMute(){}

/* ------------------------------------------------------------------ */
/* Tab navigation helper                                               */
/* ------------------------------------------------------------------ */
function clickTab(tabName){
  var tabs=pd.querySelectorAll('[data-testid="stTabs"] [role="tab"]');
  for(var i=0;i<tabs.length;i++){
    if(tabs[i].textContent.trim().indexOf(tabName)!==-1){
      tabs[i].click();
      return true;
    }
  }
  return false;
}

/* ------------------------------------------------------------------ */
/* Element finders                                                     */
/* ------------------------------------------------------------------ */
function qSidebar(){return pd.querySelector('[data-testid="stSidebar"]')}
function qKPI(){return pd.querySelector('.sidebar-kpi-bar')}
function qTabBar(){return pd.querySelector('[data-testid="stTabs"] [role="tablist"]')}
function qFirstCard(){return pd.querySelector('.a-card')}
function qScoreRing(){return pd.querySelector('.a-score-ring')}
function qDashBar(){return pd.querySelector('.dash-bar')}
function qSortLabel(){
  var sb=qSidebar(); if(!sb) return null;
  var els=sb.querySelectorAll('.filter-label');
  for(var i=0;i<els.length;i++){if(els[i].textContent.indexOf('Sortierung')!==-1) return els[i].nextElementSibling||els[i]}
  return null;
}
function qMainContent(){return pd.querySelector('[data-testid="stTabs"]')}
function qWatchlists(){
  var sb=qSidebar(); if(!sb) return null;
  var exps=sb.querySelectorAll('[data-testid="stExpander"]');
  for(var i=0;i<exps.length;i++){if(exps[i].textContent.indexOf('Watchlist')!==-1) return exps[i]}
  return null;
}

/* ------------------------------------------------------------------ */
/* Tour Steps                                                          */
/* ------------------------------------------------------------------ */
var STEPS=[
  /* --- 0: Welcome + Schnellauswahl-Hub (centered) --- */
  {
    title:"Willkommen bei Lumio!",
    text:"Lumio ist dein t\u00e4gliches Recherche-Dashboard. Es durchsucht <b>30+ medizinische Quellen</b>, bewertet jeden Artikel per KI und fasst ihn zusammen."+
      "<br><br>W\u00e4hle einen Bereich oder starte die vollst\u00e4ndige Tour:"+
      "<div id='lt-hub' style='display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:14px 0 4px'>"+
        "<div data-goto='1' class='lt-hb' style='padding:8px 10px;border-radius:8px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);cursor:pointer;font-size:11px;transition:all .15s'>\ud83d\udcf0 <b>Feed</b> \u2013 Artikel sichten</div>"+
        "<div data-goto='9' class='lt-hb' style='padding:8px 10px;border-radius:8px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);cursor:pointer;font-size:11px;transition:all .15s'>\ud83d\udce1 <b>Themen-Radar</b></div>"+
        "<div data-goto='10' class='lt-hb' style='padding:8px 10px;border-radius:8px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);cursor:pointer;font-size:11px;transition:all .15s'>\ud83d\udd0d <b>Suche & Insights</b></div>"+
        "<div data-goto='11' class='lt-hb' style='padding:8px 10px;border-radius:8px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);cursor:pointer;font-size:11px;transition:all .15s'>\ud83c\udf3f <b>Saisonale Themen</b></div>"+
        "<div data-goto='12' class='lt-hb' style='padding:8px 10px;border-radius:8px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);cursor:pointer;font-size:11px;transition:all .15s'>\ud83c\udfe5 <b>Kongresse</b></div>"+
        "<div data-goto='13' class='lt-hb' style='padding:8px 10px;border-radius:8px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);cursor:pointer;font-size:11px;transition:all .15s'>\ud83e\udd1d <b>Redaktion</b></div>"+
        "<div data-goto='14' class='lt-hb' style='padding:8px 10px;border-radius:8px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);cursor:pointer;font-size:11px;transition:all .15s'>\ud83d\udce8 <b>Versand</b></div>"+
        "<div data-goto='14' class='lt-hb' style='padding:8px 10px;border-radius:8px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);cursor:pointer;font-size:11px;transition:all .15s'>\ud83d\udcda <b>Scoring & mehr</b></div>"+
      "</div>"+
      "<span style='color:#84cc16;font-size:11px'>\u23f1 Tour: ca. 3 Minuten \u2022 Oder klicke direkt auf einen Bereich</span>",
    getEl:null, placement:"center", icon:"\u2728"
  },

  /* --- 1: Feed Tab: Sidebar --- */
  {
    title:"Deine Filter in der Sidebar",
    text:"Hier steuerst du, welche Artikel im Feed erscheinen:<br><br>\u2022 <b>Zeitraum</b> \u2013 von 1 Tag bis zur Gesamtansicht<br>\u2022 <b>Fachgebiet</b> \u2013 Kardiologie, Onkologie, etc.<br>\u2022 <b>Quellen</b> \u2013 einzelne Journals oder alle<br>\u2022 <b>Sprache</b> \u2013 Deutsch, Englisch oder beide<br>\u2022 <b>Sortierung</b> \u2013 6 verschiedene Modi (siehe n\u00e4chster Schritt)<br>\u2022 <b>Status</b> \u2013 Neu, Gemerkt oder Warnungen",
    getEl:qSidebar, placement:"right", icon:"\ud83d\udcdd",
    beforeStep:function(){clickTab("Feed")}
  },

  /* --- 2: KPI-Bar --- */
  {
    title:"Drei Kennzahlen auf einen Blick",
    text:"\u2022 <b>Gesamt</b> \u2013 Artikel insgesamt in der Datenbank<br>\u2022 <b>Score \u226570</b> \u2013 besonders relevante Artikel<br>\u2022 <b>Alerts</b> \u2013 offene Arzneimittelwarnungen",
    getEl:qKPI, placement:"right", icon:"\ud83d\udcca"
  },

  /* --- 3: Dashboard --- */
  {
    title:"Das Dashboard",
    text:"Die wichtigsten Zahlen der Woche:<br><br>\u2022 <b>Letzte 7 Tage</b> mit Vergleich zur Vorwoche<br>\u2022 <b>\u00d8 Score</b> als Qualit\u00e4tsindikator<br>\u2022 <b>Ungesichtete Artikel</b> (Score \u226570), die noch warten<br>\u2022 <b>Top-Quelle</b> + 30-Tage-Sparkline",
    getEl:qDashBar, placement:"bottom", icon:"\ud83d\udcc8"
  },

  /* --- 4: Artikel-Karte --- */
  {
    title:"So liest du eine Artikel-Karte",
    text:"\u2022 <b>Score-Ring</b> links \u2013 je gr\u00fcner, desto relevanter<br>\u2022 <b>Titel + Quelle</b> \u2013 mit Fachgebiet und Tags<br>\u2022 <b>KI-Zusammenfassung</b> \u2013 Kernbefund auf Deutsch<br><br>Buttons: <b>\u2606 Merken</b> (pers\u00f6nlich) \u2022 <b>\u2717 Ausblenden</b> (f\u00fcr alle) \u2022 <b>\ud83d\udcc1 Sammlung</b><br><br>Mehrere Artikel ausw\u00e4hlen? Nutze die <b>Checkboxen</b> links \u2013 unten erscheint eine Aktionsleiste.",
    getEl:qFirstCard, placement:"top", icon:"\ud83d\udcf0"
  },

  /* --- 5: Scoring --- */
  {
    title:"Das Scoring-System",
    text:"Jeder Artikel wird auf einer Skala von 0\u2013100 bewertet:<br><br><div style='display:grid;grid-template-columns:1fr auto;gap:2px 12px;font-size:12px'><span>Klinische Handlungsrelevanz</span><span style='color:#a0a0b8'>max. 20</span><span>Evidenz und Recherchetiefe</span><span style='color:#a0a0b8'>max. 20</span><span>Thematische Zugkraft</span><span style='color:#a0a0b8'>max. 20</span><span>Neuigkeitswert</span><span style='color:#a0a0b8'>max. 16</span><span>Quellenansehen</span><span style='color:#a0a0b8'>max. 12</span><span>Aufbereitungsqualit\u00e4t</span><span style='color:#a0a0b8'>max. 12</span></div><br><b style='color:#4ade80'>\u226570 = TOP</b> \u2022 <b style='color:#eab308'>45\u201369 = RELEVANT</b> \u2022 <b style='color:#6b7280'>unter 45 = MONITOR</b>",
    getEl:qScoreRing, placement:"right", icon:"\ud83c\udfaf"
  },

  /* --- 6: Sortierung --- */
  {
    title:"Sortierung f\u00fcr jeden Workflow",
    text:"In der Sidebar findest du unter <b>Sortierung</b> diese Modi:<br><br>\u2022 \ud83d\udd25 <b>Trending</b> \u2013 Score \u00d7 Aktualit\u00e4t \u00d7 Momentum<br>\u2022 \ud83c\udfaf <b>High Score</b> \u2013 reiner Score, h\u00f6chste zuerst<br>\u2022 \u2728 <b>Redaktions-Tipp</b> \u2013 Top-Quellen + Praxisrelevanz<br>\u2022 \ud83d\udc8e <b>Unentdeckte Perlen</b> \u2013 gute Artikel aus weniger bekannten Quellen<br>\u2022 \ud83e\ude7a <b>Klinische Dringlichkeit</b> \u2013 sofort handlungsrelevant<br>\u2022 \ud83d\udcda <b>Quelle A\u2013Z</b> \u2013 gruppiert nach Journal",
    getEl:null, placement:"center", icon:"\ud83d\udd00"
  },

  /* --- 7: Watchlists --- */
  {
    title:"Themen per Watchlist verfolgen",
    text:"Lege Stichw\u00f6rter an (z.\u202fB. \u00abSGLT2, Herzinsuffizienz\u00bb) und Lumio zeigt dir automatisch neue Treffer. \u00dcber <b>Filtern</b> kannst du den Feed auf eine Watchlist eingrenzen.<br><br>Unter <b>Versand</b> werden daraus automatisch <b>Themen-Pakete</b> f\u00fcr deinen Newsletter generiert.",
    getEl:qWatchlists, placement:"right", icon:"\ud83c\udfaf"
  },

  /* --- 8: Sammlungen — centered overlay, navigiert zu Cowork im Hintergrund --- */
  {
    title:"Sammlungen \u2013 gemeinsam recherchieren",
    text:"Im <b>Redaktion</b>-Tab (jetzt im Hintergrund) verwaltest du Sammlungen:<br><br>\u2022 <b>Neue Sammlung</b> erstellen \u2013 Name, Beschreibung, Zuweisung<br>\u2022 Im Feed: Artikel per <b>Checkbox</b> ausw\u00e4hlen \u2192 \u00abZur Sammlung\u00bb<br>\u2022 <b>Kommentare</b> schreiben zur Abstimmung im Team<br>\u2022 Aus einer fertigen Sammlung per KI einen <b>Entwurf</b> generieren<br><br>Im <b>Redaktions-Feed</b> siehst du, woran das Team gerade arbeitet.",
    getEl:null, placement:"center", icon:"\ud83d\udcc1",
    beforeStep:function(){clickTab("Redaktion")}
  },

  /* --- 9: Themen-Radar Tab --- */
  {
    title:"Der Themen-Radar",
    text:"Welche Themen nehmen diese Woche Fahrt auf?<br><br>\u2022 Die <b>Hero-Kachel</b> oben zeigt den wichtigsten Trend<br>\u2022 Darunter: <b>weitere Trend-Cluster</b> mit Momentum-Anzeige<br>\u2022 Jeder Cluster enth\u00e4lt eine <b>Handlungsempfehlung</b><br>\u2022 <b>Storyline-Vorschl\u00e4ge</b> liefern konkrete Artikel-Ideen<br><br>Die KI erkennt Trends automatisch anhand von Artikelzahlen, Quellen und Studientypen.",
    getEl:null, placement:"center", icon:"\ud83d\udce1",
    beforeStep:function(){clickTab("Themen-Radar")}
  },

  /* --- 10: Suche & Insights Tab --- */
  {
    title:"Suche & Insights",
    text:"<b>Suche:</b> Volltextsuche \u00fcber Titel, Abstract, Zusammenfassung und Tags.<br><br><b>Insights:</b><br>\u2022 Fachgebiet-Verteilung und Score-Trends<br>\u2022 Quellen-Qualit\u00e4t \u2013 welche Journals liefern die besten Inhalte?<br>\u2022 Abdeckungs-Check \u2013 fehlen Artikel in bestimmten Fachgebieten?<br>\u2022 CSV-Export aller Daten f\u00fcr eigene Analysen",
    getEl:null, placement:"center", icon:"\ud83d\udd0d",
    beforeStep:function(){clickTab("Suche")}
  },

  /* --- 11: Saisonale Themen Tab --- */
  {
    title:"Saisonale Themen",
    text:"Welche Gesundheitsthemen sind gerade saisonal aktuell?<br><br>\u2022 <b>4-Wochen-Vorausschau</b> \u2013 was wird bald relevant?<br>\u2022 <b>Themen-Cluster</b> \u2013 z.\u202fB. Pollenflug, Grippe-Saison, Sonnenschutz<br>\u2022 <b>Awareness-Tage</b> \u2013 Weltkrebstag, Welt-Parkinson-Tag etc.<br>\u2022 <b>Regulatorische Stichtage</b> \u2013 EBM-Fristen, Quartalsabschl\u00fcsse<br><br>Klicke auf ein Cluster, um passende Artikel zu sehen.",
    getEl:null, placement:"center", icon:"\ud83c\udf3f",
    beforeStep:function(){clickTab("Saisonale Themen")}
  },

  /* --- 12: Kongresse Tab --- */
  {
    title:"Kongresse im \u00dcberblick",
    text:"Alle wichtigen Medizin-Kongresse auf einen Blick:<br><br>\u2022 <b>Monatskalender</b> mit farblicher Kennzeichnung<br>\u2022 <b>Details</b> \u2013 Ort, CME-Punkte, Fristen, verwandte Artikel<br>\u2022 <b>Favoriten</b> f\u00fcr deine Redaktionsplanung<br>\u2022 <b>KI-Briefing</b> \u2013 automatisches 1-Seiten-Briefing vor dem Kongress<br>\u2022 <b>Watchlist</b> \u2013 beobachte ein Thema rund um den Kongress",
    getEl:null, placement:"center", icon:"\ud83c\udfe5",
    beforeStep:function(){clickTab("Kongresse")}
  },

  /* --- 13: Cowork Tab --- */
  {
    title:"Redaktion \u2013 im Team arbeiten",
    text:"Hier koordiniert die Redaktion ihre Arbeit:<br><br>\u2022 <b>Redaktions-Feed</b> \u2013 was wurde zuletzt geplant und ver\u00f6ffentlicht?<br>\u2022 <b>Meine Sammlungen</b> \u2013 deine Themenmappen mit Artikeln<br>\u2022 <b>Neue Sammlung</b> \u2013 Recherche starten und Kollegen zuweisen<br>\u2022 <b>Kommentare</b> \u2013 direkt an der Sammlung abstimmen<br>\u2022 <b>KI-Entwurf</b> \u2013 aus einer Sammlung einen Artikel-Entwurf generieren (Claude Sonnet)",
    getEl:null, placement:"center", icon:"\ud83e\udd1d",
    beforeStep:function(){clickTab("Redaktion")}
  },

  /* --- 14: Versand Tab --- */
  {
    title:"Versand an deine Leser",
    text:"Fertige Inhalte exportieren und versenden:<br><br>\u2022 <b>W\u00f6chentlicher Digest</b> \u2013 automatisch aus den Top-Artikeln erstellt<br>\u2022 <b>Themen-Pakete</b> \u2013 kuratierte Zusammenstellungen pro Watchlist<br>\u2022 Export als <b>HTML</b> oder <b>Clipboard</b> f\u00fcr den Newsletter<br><br>Die Vorlagen sind bereits an das esanum-Design angepasst.",
    getEl:null, placement:"center", icon:"\ud83d\udce8",
    beforeStep:function(){clickTab("Versand")}
  },

  /* --- 15: Abschluss (centered) --- */
  {
    title:"Bereit f\u00fcr den Start!",
    text:"Deine wichtigsten Anlaufstellen:<br><br>"+
      "<div style='display:grid;grid-template-columns:auto 1fr;gap:3px 10px;font-size:12px;line-height:1.8'>"+
        "<b>\ud83d\udcf0 Feed</b><span>Artikel sichten, merken, sammeln</span>"+
        "<b>\ud83d\udce1 Radar</b><span>Aufkommende Trends erkennen</span>"+
        "<b>\ud83c\udf3f Saisonal</b><span>Vorausplanen, was bald kommt</span>"+
        "<b>\ud83c\udfe5 Kongresse</b><span>Termine, Briefings, Watchlists</span>"+
        "<b>\ud83e\udd1d Redaktion</b><span>Sammlungen, Zuweisung, Entw\u00fcrfe</span>"+
        "<b>\ud83d\udce8 Versand</b><span>Newsletter und Themen-Pakete</span>"+
      "</div><br>"+
      "Du kannst diese Tour jederzeit \u00fcber das <b>?</b> oben rechts neu starten.<br><br><span style='color:#84cc16;font-weight:700'>Viel Spa\u00df mit Lumio!</span>",
    getEl:null, placement:"center", icon:"\ud83d\ude80",
    beforeStep:function(){clickTab("Feed")}
  }
];

var TOTAL=STEPS.length, TW=440, GAP=16, KEY="lumio_onboarding_done";
var step=-1, overlay, spot, tip, prevTargetEl=null;

/* 3D lift: make the target element pop dramatically out of the page */
var LIFT_STYLE="transform:scale(1.06) perspective(800px) rotateX(1deg) translateZ(0);"+
  "box-shadow:0 35px 80px rgba(0,0,0,0.6), 0 0 50px rgba(132,204,22,0.2), 0 0 100px rgba(132,204,22,0.08), inset 0 1px 0 rgba(255,255,255,0.08);"+
  "border:2px solid rgba(132,204,22,0.35);"+
  "border-radius:14px;position:relative;z-index:1100000;"+
  "transition:transform 0.5s cubic-bezier(.22,1,.36,1), box-shadow 0.5s ease, border 0.5s ease;"+
  "filter:brightness(1.08);";

function liftTarget(el){
  unliftTarget();
  if(!el) return;
  el._origStyle=el.getAttribute("style")||"";
  el.setAttribute("style", el._origStyle+";"+LIFT_STYLE);
  prevTargetEl=el;
}
function unliftTarget(){
  if(prevTargetEl){
    prevTargetEl.setAttribute("style", prevTargetEl._origStyle||"");
    delete prevTargetEl._origStyle;
    prevTargetEl=null;
  }
}

function done(){try{return localStorage.getItem(KEY)==="1"}catch(e){return false}}
function save(){try{localStorage.setItem(KEY,"1")}catch(e){}}
function clear(){try{localStorage.removeItem(KEY)}catch(e){}}
pw.__lumioRestartTour=function(){clear();pw.__ltInit=false;start()};

/* ------------------------------------------------------------------ */
/* DOM — z-index higher than sidebar (sidebar is ~1000100)             */
/* ------------------------------------------------------------------ */
function mkOverlay(){
  overlay=pd.createElement("div");
  overlay.id="lt-overlay";
  overlay.style.cssText="position:fixed;inset:0;z-index:1100000;";
  overlay.addEventListener("click",function(e){if(e.target===overlay)finish()});

  spot=pd.createElement("div");
  spot.id="lt-spot";
  spot.style.cssText="position:fixed;border-radius:12px;pointer-events:none;z-index:1100000;transition:all .4s cubic-bezier(.4,0,.2,1);";

  tip=pd.createElement("div");
  tip.id="lt-tip";
  tip.style.cssText="position:fixed;z-index:1100001;width:"+TW+"px;max-width:calc(100vw - 32px);font-family:'Inter',system-ui,sans-serif;";

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
/* Render                                                              */
/* ------------------------------------------------------------------ */
function render(){
  if(step<0||step>=TOTAL){finish();return}
  var s=STEPS[step];

  /* Execute beforeStep hook (e.g. navigate to tab) */
  if(s.beforeStep) s.beforeStep();

  /* Wait for tab content to render before measuring */
  setTimeout(function(){ _renderInner(s) }, s.beforeStep ? 600 : 50);
}

function _renderInner(s){
  var el=s.getEl?s.getEl():null;
  var centered=!el;

  /* Reset previous 3D lift */
  unliftTarget();

  if(centered){
    spot.style.cssText="display:none";
    overlay.style.background="rgba(0,0,0,0.78)";
  } else {
    overlay.style.background="transparent";
    /* Apply 3D lift to the target element */
    liftTarget(el);
    el.scrollIntoView({behavior:"smooth",block:"center"});
    requestAnimationFrame(function(){requestAnimationFrame(function(){
      var r=el.getBoundingClientRect();
      var pad=14;
      spot.style.cssText="position:fixed;border-radius:14px;pointer-events:none;z-index:1100000;"+
        "top:"+(r.top-pad)+"px;left:"+(r.left-pad)+"px;"+
        "width:"+(r.width+pad*2)+"px;height:"+(r.height+pad*2)+"px;"+
        "animation:ltPulse 2s ease-in-out infinite;"+
        "transition:all .4s cubic-bezier(.4,0,.2,1);";
      posTip(s,r);
    })});
    var r=el.getBoundingClientRect();
    posTip(s,r);
  }

  /* Dots */
  var dots="";
  for(var i=0;i<TOTAL;i++){
    var w=i===step?20:6;
    var bg=i<=step?"#84cc16":"rgba(255,255,255,0.1)";
    dots+='<div data-step="'+i+'" style="width:'+w+'px;height:6px;border-radius:3px;background:'+bg+';transition:all .3s;cursor:pointer"></div>';
  }

  var isFirst=step===0, isLast=step===TOTAL-1;

  var quickStartBtn='';

  /* Mute button removed */
  var muteBtn='';

  tip.innerHTML=
    '<div style="background:rgba(12,12,28,0.98);backdrop-filter:blur(30px);-webkit-backdrop-filter:blur(30px);'+
    'border:1px solid rgba(255,255,255,0.15);border-radius:14px;padding:22px 26px;'+
    'box-shadow:0 20px 60px rgba(0,0,0,0.6),0 0 0 1px rgba(132,204,22,0.06);'+
    'animation:ltSlideIn .3s ease-out;'+(centered?'max-width:520px;width:92%;margin:0 auto;':'')+'">'+

    '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">'+
      '<div style="width:32px;height:32px;border-radius:9px;background:linear-gradient(135deg,#84cc16,#22d3ee);'+
      'display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:16px;animation:ltFloat 2.5s ease-in-out infinite">'+
        s.icon+'</div>'+
      '<span style="font-size:15px;font-weight:700;color:#fff;flex:1">'+s.title+'</span>'+
      '<span style="font-size:10px;color:#a0a0b8;flex-shrink:0">'+(step+1)+'/'+TOTAL+'</span>'+
    '</div>'+

    '<div style="font-size:13px;color:#e0e0ee;line-height:1.7;margin:0 0 16px">'+s.text+'</div>'+

    '<div id="lt-dots" style="display:flex;gap:4px;justify-content:center;margin-bottom:16px">'+dots+'</div>'+

    '<div style="display:flex;align-items:center;justify-content:space-between">'+
      '<div style="display:flex;gap:8px;align-items:center">'+
        (isLast?'':'<button id="lt-skip" style="background:none;border:none;color:#a0a0b8;font-size:11px;cursor:pointer;font-family:inherit">\u00dcberspringen</button>')+
        (step>0?'<button id="lt-prev" style="background:none;border:1px solid rgba(255,255,255,0.15);color:#e0e0ee;font-size:11px;padding:6px 14px;border-radius:7px;cursor:pointer;font-family:inherit">Zur\u00fcck</button>':'')+
        quickStartBtn+
        muteBtn+
      '</div>'+
      '<button id="lt-next" style="display:flex;align-items:center;gap:6px;padding:9px 22px;border-radius:8px;border:none;cursor:pointer;'+
      'background:linear-gradient(135deg,#84cc16,#22d3ee);color:#0a0a1a;font-size:12px;font-weight:700;font-family:inherit;transition:all .15s">'+
        (isLast?"Los geht\u2019s!":"Weiter \u2192")+
      '</button>'+
    '</div>'+
  '</div>';

  if(centered){
    tip.style.cssText="position:fixed;z-index:1100001;width:"+TW+"px;max-width:calc(100vw - 32px);font-family:'Inter',sans-serif;"+
      "top:50%;left:50%;transform:translate(-50%,-50%);";
  }

  /* Bind buttons */
  var sk=pd.getElementById("lt-skip");
  var pv=pd.getElementById("lt-prev");
  var nx=pd.getElementById("lt-next");
  var qs=pd.getElementById("lt-quick");
  var mt=pd.getElementById("lt-mute");
  if(sk)sk.onclick=finish;
  if(pv)pv.onclick=function(){step--;render()};
  if(nx)nx.onclick=function(){if(isLast)finish();else{step++;render()}};
  if(qs)qs.onclick=function(){finish()};
  if(mt)mt.onclick=toggleMute;

  var dotsEl=pd.getElementById("lt-dots");
  if(dotsEl)dotsEl.addEventListener("click",function(e){
    var t=e.target.closest("[data-step]");
    if(t){step=parseInt(t.dataset.step);render()}
  });

  /* Hub quick-jump buttons */
  var hub=pd.getElementById("lt-hub");
  if(hub)hub.addEventListener("click",function(e){
    var t=e.target.closest("[data-goto]");
    if(t){step=parseInt(t.dataset.goto);render()}
  });
}

function posTip(s,rect){
  var pad=12;
  var r={top:rect.top-pad,left:rect.left-pad,width:rect.width+pad*2,height:rect.height+pad*2,
         cx:rect.left+rect.width/2,cy:rect.top+rect.height/2};
  var vh=pw.innerHeight,vw=pw.innerWidth,th=320;
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

  tip.style.cssText="position:fixed;z-index:1100001;width:"+TW+"px;max-width:calc(100vw - 32px);font-family:'Inter',sans-serif;"+
    "top:"+t+"px;left:"+l+"px;animation:ltSlideIn .3s ease-out;";
}

/* ------------------------------------------------------------------ */
/* Lifecycle                                                           */
/* ------------------------------------------------------------------ */
function start(){step=0;mkOverlay();startAudio();render();pd.addEventListener("keydown",keys)}
function finish(){step=-1;save();unliftTarget();rmOverlay();stopAudio();pd.removeEventListener("keydown",keys);pw.__ltInit=false}
function keys(e){
  if(e.key==="ArrowRight"||e.key==="Enter"){e.preventDefault();if(step>=TOTAL-1)finish();else{step++;render()}}
  else if(e.key==="ArrowLeft"){e.preventDefault();if(step>0){step--;render()}}
  else if(e.key==="Escape"){e.preventDefault();finish()}
  /* m key removed — no audio */
}

if(!done()) setTimeout(start,1500);

})();
</script>
""".strip()
