"""Lumio — Custom CSS injection (Apple / Asana inspired dark theme)."""

import streamlit as st


@st.cache_resource
def _get_css() -> str:
    """Build CSS string once, cache forever (static content)."""
    return """
<style>
/* ===== GLOBAL ===== */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --c-bg: #0a0a1a;
    --c-surface: rgba(255,255,255,0.035);
    --c-surface-solid: #1a1a30;
    --c-border: rgba(255,255,255,0.07);
    --c-border-subtle: rgba(255,255,255,0.05);
    --c-border-hover: rgba(255,255,255,0.16);
    --c-text: #eeeef5;
    --c-text-secondary: #a0a0b8;
    --c-text-muted: #6b6b82;
    --c-text-tertiary: #8b8ba0;
    --c-accent: #84cc16;
    --c-accent-light: rgba(132,204,22,0.10);
    --c-success: #4ade80;
    --c-success-light: rgba(74,222,128,0.10);
    --c-danger: #f87171;
    --c-danger-light: rgba(248,113,113,0.10);
    --c-warn: #fbbf24;
    --c-warn-light: rgba(251,191,36,0.10);
    --c-highlight: #fbbf24;
    --c-highlight-bg: rgba(251,191,36,0.10);
    --c-ring-low: #4a4a5e;
    --c-praxis: #059669;
    --c-praxis-text: #a0e8b8;
    --c-alert-text: #d70015;
    --radius: 14px;
    --radius-sm: 10px;
    --shadow-sm: 0 2px 8px rgba(0,0,0,0.25);
    --shadow-md: 0 8px 32px rgba(0,0,0,0.35);
    --glass-blur: blur(16px);
    --transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

html, body, [class*="css"],
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] p,
[data-testid="stAppViewContainer"] div,
[data-testid="stAppViewContainer"] label,
[data-testid="stAppViewContainer"] button,
[data-testid="stAppViewContainer"] input,
[data-testid="stAppViewContainer"] select,
[data-testid="stAppViewContainer"] textarea,
[data-testid="stSidebar"],
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] label,
.stMarkdown, .stMarkdown p, .stMarkdown span {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    -webkit-font-smoothing: antialiased;
}
/* Restore Material Symbols font for Streamlit icons.
   Uses multiple selectors for robustness across Streamlit versions:
   - data-testid selectors (stable API)
   - Attribute selectors matching common icon font patterns
   - Class substring selectors as fallback */
[data-testid="stIconMaterial"],
[data-testid="stIcon"],
[data-testid="stExpanderToggleIcon"] span,
[data-testid="stSidebar"] [role="button"] span[aria-hidden],
span[style*="Material"],
span[class*="e1t4gh3"],
span[class*="ejhh0er"],
span[class*="icon"],
.material-symbols-rounded {
    font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
}

.main .block-container {
    padding: 2rem 3rem 3rem 3rem;
    max-width: 1100px;
}

.stApp {
    background-color: var(--c-bg);
    color: var(--c-text);
}

/* ===== SIDEBAR ===== */
section[data-testid="stSidebar"] {
    background: #0e0e22 !important;
    border-right: 1px solid var(--c-border);
}
section[data-testid="stSidebar"] * {
    color: var(--c-text) !important;
}
section[data-testid="stSidebar"] .stMarkdown p {
    color: var(--c-text-secondary) !important;
}

/* Sidebar KPI bar */
.sidebar-kpi-bar {
    display: flex;
    gap: 0;
    border: 1px solid var(--c-border);
    border-radius: var(--radius-sm);
    overflow: hidden;
    margin: 6px 0 14px 0;
    background: rgba(255,255,255,0.02);
}
.sidebar-kpi-item {
    flex: 1;
    text-align: center;
    padding: 10px 4px;
    border-right: 1px solid var(--c-border);
}
.sidebar-kpi-item:last-child { border-right: none; }
.sidebar-kpi-num {
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1;
    color: var(--c-text) !important;
}
.sidebar-kpi-lbl {
    font-size: 0.55rem;
    font-weight: 600;
    color: var(--c-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-top: 4px;
}

/* Filter labels */
.filter-label {
    font-size: 0.62rem;
    font-weight: 600;
    color: var(--c-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 12px 0 4px 0;
}

/* Sidebar radio pills for Zeitraum */
section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] {
    gap: 6px !important;
    flex-wrap: wrap;
}
/* Hide the radio circle indicator */
section[data-testid="stSidebar"] [data-baseweb="radio"] > div:first-child {
    display: none !important;
}
/* Pill styling for each radio option */
section[data-testid="stSidebar"] [data-baseweb="radio"] {
    border: 1px solid var(--c-border) !important;
    border-radius: 20px !important;
    padding: 6px 16px !important;
    background: rgba(255,255,255,0.03) !important;
    cursor: pointer;
    transition: var(--transition);
    margin: 0 !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
}
section[data-testid="stSidebar"] [data-baseweb="radio"] p {
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1.2 !important;
    text-align: center !important;
}
section[data-testid="stSidebar"] [data-baseweb="radio"]:hover {
    border-color: var(--c-accent) !important;
}
/* Selected pill state — lime accent background */
section[data-testid="stSidebar"] [data-baseweb="radio"]:has(input:checked) {
    background: var(--c-accent) !important;
    border-color: var(--c-accent) !important;
}
section[data-testid="stSidebar"] [data-baseweb="radio"]:has(input:checked) p {
    color: #0a0a1a !important;
}

/* Favorites link */
.fav-link {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    border: 1px solid var(--c-border);
    border-radius: var(--radius-sm);
    background: rgba(255,255,255,0.02);
    transition: var(--transition);
    color: var(--c-text);
}
.fav-link:hover { border-color: var(--c-accent); }
.fav-count {
    background: var(--c-accent);
    color: #0a0a1a;
    font-size: 0.62rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 10px;
}

/* ===== TAB BAR ===== */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    background: rgba(255,255,255,0.03);
    border-radius: var(--radius);
    padding: 4px;
    border: 1px solid var(--c-border);
    margin-bottom: 1.5rem;
}

.stTabs [data-baseweb="tab"] {
    height: 38px;
    border-radius: var(--radius-sm);
    font-size: 0.82rem;
    font-weight: 500;
    color: var(--c-text-muted) !important;
    padding: 0 20px;
    background: transparent;
    border: none;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, rgba(132,204,22,0.14), rgba(34,211,238,0.08)) !important;
    color: var(--c-accent) !important;
    font-weight: 600;
    box-shadow: 0 0 12px rgba(132,204,22,0.08);
}

.stTabs [data-baseweb="tab-border"],
.stTabs [data-baseweb="tab-highlight"] {
    display: none;
}

/* ===== GENERIC CARD ===== */
.med-card {
    background: var(--c-surface);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--c-border);
    border-radius: var(--radius);
    padding: 20px 24px;
    margin-bottom: 12px;
    transition: var(--transition);
}
.med-card:hover {
    border-color: var(--c-border-hover);
    box-shadow: var(--shadow-md);
    background: rgba(255,255,255,0.05);
}

/* ===== KPI CARD ===== */
.kpi-card {
    background: var(--c-surface);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--c-border);
    border-radius: var(--radius);
    padding: 18px 20px;
    text-align: center;
    position: relative;
    overflow: hidden;
    transition: var(--transition);
    opacity: 0;
    animation: dash-enter 0.5s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}
.kpi-card:nth-child(1) { animation-delay: 0s; }
.kpi-card:nth-child(2) { animation-delay: 0.08s; }
.kpi-card:nth-child(3) { animation-delay: 0.16s; }
.kpi-card:nth-child(4) { animation-delay: 0.24s; }
.kpi-card:nth-child(5) { animation-delay: 0.32s; }
.kpi-card:hover {
    border-color: var(--c-border-hover);
    box-shadow: 0 4px 24px rgba(0,0,0,0.25);
    transform: translateY(-1px);
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg,
        var(--kpi-accent, rgba(132,204,22,0.5)),
        var(--kpi-accent-to, rgba(34,211,238,0.5)));
    opacity: 0.7;
    transition: opacity 0.2s ease;
}
.kpi-card:hover::before {
    opacity: 1;
}
.kpi-value {
    font-size: 1.8rem;
    font-weight: 800;
    color: var(--c-text);
    letter-spacing: -0.04em;
    line-height: 1;
    transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), color 0.2s ease;
}
.kpi-card:hover .kpi-value {
    transform: scale(1.06);
    color: var(--c-accent);
}
.kpi-label {
    font-size: 0.65rem;
    font-weight: 600;
    color: var(--c-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 6px;
}
.kpi-delta {
    font-size: 0.7rem;
    font-weight: 500;
    margin-top: 3px;
}
.kpi-delta-up   { color: var(--c-success); }
.kpi-delta-down { color: var(--c-danger); }
.kpi-delta-flat { color: var(--c-text-muted); }

/* ===== DASHBOARD HERO BAR ===== */
.dash-bar {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
    margin-bottom: 20px;
}
.dash-card {
    background: var(--c-surface);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--c-border);
    border-radius: var(--radius);
    padding: 16px 18px;
    position: relative;
    overflow: hidden;
    transition: var(--transition);
    opacity: 0;
    animation: dash-enter 0.5s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}
.dash-card:nth-child(1) { animation-delay: 0s; }
.dash-card:nth-child(2) { animation-delay: 0.08s; }
.dash-card:nth-child(3) { animation-delay: 0.16s; }
.dash-card:nth-child(4) { animation-delay: 0.24s; }
.dash-card:nth-child(5) { animation-delay: 0.32s; }
@keyframes dash-enter {
    from { opacity: 0; transform: translateY(16px) scale(0.97); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
}
.dash-card:hover {
    border-color: var(--c-border-hover);
    transform: translateY(-1px);
    box-shadow: 0 4px 24px rgba(0,0,0,0.25);
}
.dash-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--c-accent), rgba(34,211,238,0.5));
    opacity: 0.5;
}
.dash-card-accent {
    border-left: none;
}
.dash-card-accent::before {
    opacity: 1;
}
.dash-value {
    font-size: 1.65rem;
    font-weight: 800;
    color: var(--c-text);
    letter-spacing: -0.04em;
    line-height: 1;
    transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), color 0.2s ease;
}
.dash-card:hover .dash-value {
    transform: scale(1.06);
    color: var(--c-accent);
}
.dash-label {
    font-size: 0.65rem;
    font-weight: 600;
    color: var(--c-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 5px;
}
.dash-sub {
    font-size: 0.72rem;
    font-weight: 500;
    margin-top: 4px;
}
.sparkline-bar {
    display: inline-block;
    width: 3px;
    margin-right: 1px;
    border-radius: 1px 1px 0 0;
    vertical-align: bottom;
}

/* ===== ARTICLE CARD v3 — Dark glassmorphism ===== */
.a-card {
    background: var(--c-surface);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--c-border);
    border-radius: var(--radius);
    padding: 20px 24px;
    margin-bottom: 14px;
    transition: var(--transition);
    position: relative;
    overflow: hidden;
}
.a-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg,
        var(--card-accent, transparent),
        var(--card-accent-to, transparent));
    opacity: 0;
    transition: opacity 0.3s ease;
}
.a-card:hover {
    border-color: var(--c-border-hover);
    box-shadow: var(--shadow-md);
    background: rgba(255,255,255,0.05);
    transform: translateY(-1px);
}
.a-card:hover::before {
    opacity: 1;
}

.a-header {
    display: flex;
    align-items: flex-start;
    gap: 14px;
}

/* Score Ring — animated fitness-style ring */
.a-score-ring {
    flex-shrink: 0;
    width: 48px;
    position: relative;
    text-align: center;
}
.a-score-ring svg {
    width: 48px;
    height: 48px;
    transform: rotate(-90deg);
}
.a-score-ring .ring-bg {
    fill: none;
    stroke: rgba(255,255,255,0.06);
    stroke-width: 3;
}
.a-score-ring .ring-fill {
    fill: none;
    stroke-width: 3;
    stroke-linecap: round;
    stroke-dasharray: 125.66;  /* 2 * pi * 20 */
    animation: ring-draw 1.2s cubic-bezier(0.22, 1, 0.36, 1) forwards;
    transition: filter 0.3s ease;
}
.ring-high { stroke: var(--c-success); filter: drop-shadow(0 0 6px rgba(74,222,128,0.4)); }
.ring-mid  { stroke: var(--c-warn); filter: drop-shadow(0 0 6px rgba(251,191,36,0.3)); }
.ring-low  { stroke: var(--c-ring-low); }

@keyframes ring-draw {
    from { stroke-dashoffset: 125.66; }
}

.a-score-val {
    position: absolute;
    top: 24px;  /* center of 48px SVG, ignores badge below */
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: 1.05rem;
    font-weight: 800;
    letter-spacing: -0.04em;
    line-height: 1;
    animation: score-pop 0.5s cubic-bezier(0.22, 1, 0.36, 1) 0.3s both;
    transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.a-score-high { color: var(--c-success); text-shadow: 0 0 12px rgba(74,222,128,0.3); }
.a-score-mid  { color: var(--c-warn); text-shadow: 0 0 12px rgba(251,191,36,0.2); }
.a-score-low  { color: var(--c-text-muted); }

@keyframes score-pop {
    from { opacity: 0; transform: translate(-50%, -50%) scale(0.4); }
    to   { opacity: 1; transform: translate(-50%, -50%) scale(1); }
}

/* Top-Evidenz indicator */
.a-hq-badge {
    font-size: 0.5rem;
    font-weight: 700;
    color: var(--c-success);
    display: block;
    text-align: center;
    margin-top: 2px;
    opacity: 0.7;
    transition: var(--transition);
}

.a-title {
    font-size: 0.92rem;
    font-weight: 600;
    color: var(--c-text);
    line-height: 1.45;
    text-decoration: none;
    display: inline;
    margin-bottom: 4px;
    background-image: linear-gradient(var(--c-accent), var(--c-accent));
    background-size: 0% 2px;
    background-position: 0 100%;
    background-repeat: no-repeat;
    transition: background-size 0.3s ease, color 0.2s ease;
}
.a-title:hover { color: var(--c-accent); background-size: 100% 2px; }

.a-meta {
    font-size: 0.74rem;
    color: var(--c-text-muted);
    display: flex;
    gap: 6px;
    align-items: center;
    flex-wrap: wrap;
    line-height: 1.4;
}

/* Specialty dot-chip in meta */
.a-spec-dot {
    display: inline-flex;
    align-items: center;
    padding: 1px 8px;
    border-radius: 4px;
    font-size: 0.68rem;
    font-weight: 600;
    transition: var(--transition);
}

/* Memory badges (Redaktions-Gedaechtnis) */
.memory-badge {
    display: inline-flex;
    align-items: center;
    padding: 1px 7px;
    border-radius: 4px;
    font-size: 0.62rem;
    font-weight: 600;
    letter-spacing: 0.01em;
    margin-left: 2px;
    cursor: help;
    transition: var(--transition);
}
.memory-new {
    background: rgba(74,222,128,0.10);
    color: #4ade80;
}
.memory-recent {
    background: rgba(251,191,36,0.10);
    color: #fbbf24;
}
.memory-followup {
    background: rgba(96,165,250,0.10);
    color: #60a5fa;
}
.memory-stale {
    background: rgba(248,113,113,0.10);
    color: #f87171;
}

/* Inline tags */
.a-tags-inline {
    display: flex;
    gap: 5px;
    flex-wrap: wrap;
    margin-top: 6px;
}

.a-tag {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.62rem;
    font-weight: 600;
    background: var(--c-highlight-bg);
    color: var(--c-highlight);
    letter-spacing: 0.01em;
    transition: var(--transition);
}

/* Summary — compact */
.a-summary {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid rgba(255,255,255,0.06);
}

.a-summary-core {
    font-size: 0.82rem;
    font-weight: 500;
    color: var(--c-text);
    line-height: 1.5;
    margin-bottom: 4px;
}

.a-summary-detail {
    font-size: 0.78rem;
    color: var(--c-text-secondary);
    line-height: 1.5;
}

/* Status badge top-right */
.a-status-indicator {
    position: absolute;
    top: 14px;
    right: 16px;
}

/* Specialty pill (still used in favorites/search) */
.a-spec {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.65rem;
    font-weight: 600;
}

/* ===== SCORE PILL (compact, for search/stats) ===== */
.score-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 22px;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 700;
    transition: transform 0.15s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.score-high { background: var(--c-success); color: var(--c-bg); }
.score-mid  { background: var(--c-warn); color: var(--c-bg); }
.score-low  { background: var(--c-ring-low); color: var(--c-text-secondary); }

/* ===== HEATMAP GRID (animated column reveal) ===== */
.hm-grid {
    display: grid;
    gap: 3px;
    margin-top: 12px;
}
.hm-label {
    font-size: 0.78rem;
    color: var(--c-text-tertiary);
    display: flex;
    align-items: center;
    padding-right: 8px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.hm-col-header {
    font-size: 0.72rem;
    color: var(--c-text-tertiary);
    text-align: center;
    padding-bottom: 4px;
    font-weight: 600;
}
.hm-cell {
    border-radius: 4px;
    min-height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.68rem;
    font-weight: 600;
    color: rgba(255,255,255,0.7);
    opacity: 0;
    transform: scaleY(0.3);
    animation: hm-reveal 0.4s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}
@keyframes hm-reveal {
    to { opacity: 1; transform: scaleY(1); }
}

/* ===== ALERT BANNER ===== */
.alert-banner {
    background: var(--c-danger-light);
    border: 1px solid rgba(248,113,113,0.2);
    border-radius: var(--radius);
    padding: 14px 20px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 12px;
}
.alert-dot {
    width: 8px; height: 8px;
    background: var(--c-danger);
    border-radius: 50%;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}

/* ===== SECTION / PAGE HEADERS ===== */
.section-header {
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--c-text);
    letter-spacing: -0.02em;
    margin-bottom: 2px;
    display: inline-block;
    position: relative;
    padding-bottom: 6px;
}
.section-header::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0;
    width: 40px;
    height: 2px;
    background: linear-gradient(90deg, var(--c-accent), transparent);
    border-radius: 1px;
}
.section-sub {
    font-size: 0.75rem;
    color: var(--c-text-muted);
    margin-bottom: 14px;
}
.page-header {
    font-size: 1.4rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    margin-bottom: 2px;
    background: linear-gradient(135deg, var(--c-text) 0%, var(--c-accent) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.page-sub {
    font-size: 0.82rem;
    color: var(--c-text-secondary);
    margin-bottom: 24px;
}

/* Section divider with label */
.section-divider {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 28px 0 18px 0;
}
.section-divider::after {
    content: '';
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, var(--c-accent), rgba(34,211,238,0.3), transparent);
    opacity: 0.4;
}
.section-divider-label {
    font-size: 0.68rem;
    font-weight: 700;
    color: var(--c-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    white-space: nowrap;
}

/* ===== FORM CONTROLS ===== */
.stTextInput input {
    border-radius: var(--radius-sm) !important;
    border: 1px solid var(--c-border) !important;
    font-size: 0.84rem !important;
    padding: 10px 14px !important;
    transition: var(--transition);
    background: rgba(255,255,255,0.03) !important;
    color: var(--c-text) !important;
}
.stTextInput input:focus {
    border-color: var(--c-accent) !important;
    box-shadow: 0 0 0 3px rgba(132,204,22,0.12) !important;
}
.stSelectbox > div > div, .stMultiSelect > div > div {
    border-radius: var(--radius-sm) !important;
    background: rgba(255,255,255,0.03) !important;
}

/* ===== BUTTONS ===== */
.stButton > button {
    border-radius: var(--radius-sm);
    font-weight: 500;
    font-size: 0.82rem;
    padding: 6px 14px;
    border: 1px solid var(--c-border);
    background: rgba(255,255,255,0.04);
    color: var(--c-text);
    transition: var(--transition);
    min-height: 34px;
}
.stButton > button:hover {
    background: rgba(255,255,255,0.08);
    border-color: var(--c-border-hover);
}

/* Secondary buttons — subtle default look */
.stButton > button[kind="secondary"] {
    opacity: 0.85;
    transition: var(--transition);
}
.stButton > button[kind="secondary"]:hover {
    opacity: 1;
    background: rgba(255,255,255,0.06) !important;
    border-color: var(--c-border-hover) !important;
}

/* Load-more button gets default primary styling — no override needed */

/* ===== METRICS ===== */
[data-testid="stMetric"] {
    background: var(--c-surface);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--c-border);
    border-radius: var(--radius);
    padding: 14px 16px;
}
[data-testid="stMetricLabel"] {
    font-size: 0.68rem !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--c-text-muted) !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.4rem !important;
    font-weight: 800 !important;
    color: var(--c-text) !important;
}

/* ===== MISC ===== */
hr { border-color: rgba(255,255,255,0.06) !important; margin: 20px 0 !important; }
.stDataFrame { border-radius: var(--radius); overflow: hidden; }
.stDownloadButton > button { border-radius: var(--radius-sm) !important; background: rgba(255,255,255,0.04) !important; color: var(--c-text) !important; border: 1px solid var(--c-border) !important; }
.stDownloadButton > button:hover { background: rgba(255,255,255,0.08) !important; border-color: var(--c-border-hover) !important; }
.stSlider [data-testid="stThumbValue"] { font-size: 0.72rem; }

/* ===== MICRO-INTERACTIONS ===== */
/* Tags — lift + glow */
.a-tag:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(251,191,36,0.2);
    filter: brightness(1.15);
}
/* Badges — lift + brighten */
.status-badge:hover,
.momentum-badge:hover,
.evidence-badge:hover,
.cross-spec-badge:hover {
    transform: translateY(-1px);
    filter: brightness(1.25);
    box-shadow: 0 2px 8px rgba(255,255,255,0.06);
}
/* Score Ring — glow on hover */
.a-score-ring:hover .ring-fill {
    filter: drop-shadow(0 0 10px currentColor) brightness(1.2);
}
.a-score-ring:hover .a-score-val {
    transform: translate(-50%, -50%) scale(1.12);
}
/* Score-Breakdown — grow items */
.sb-item:hover {
    transform: scale(1.08);
}
.sb-item:hover .sb-bar-fill {
    filter: brightness(1.3);
    box-shadow: 0 0 6px currentColor;
}
/* Praxis-Box — border slide */
.a-summary-praxis:hover {
    border-left-width: 5px;
    padding-left: 12px;
    background: rgba(74,222,128,0.12);
}
/* Score-Pill — pop + tooltip */
.score-pill:hover {
    transform: scale(1.15);
}
.score-pill[data-tip]:hover::after {
    content: attr(data-tip);
    position: absolute;
    bottom: calc(100% + 8px);
    left: 50%;
    transform: translateX(-50%);
    background: rgba(14,14,34,0.97);
    color: #e8e8f0;
    font-size: 0.7rem;
    font-weight: 400;
    line-height: 1.5;
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid rgba(132,204,22,0.15);
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    white-space: nowrap;
    z-index: 1000;
    pointer-events: none;
    animation: sb-tip-in 0.15s ease-out;
}
/* HQ-Badge — pop */
.a-hq-badge:hover {
    opacity: 1;
    transform: scale(1.08);
}
/* Specialty-Dot — glow */
.a-spec-dot:hover {
    filter: brightness(1.3);
    box-shadow: 0 0 6px rgba(255,255,255,0.12);
}
/* Progress-Bar — glow pulse */
.progress-track:hover .progress-fill {
    box-shadow: 0 0 12px rgba(132,204,22,0.4), 0 0 4px rgba(132,204,22,0.6);
}

.status-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.62rem;
    font-weight: 600;
    transition: var(--transition);
}
.status-new       { color: #8b8ba0; background: rgba(255,255,255,0.06); }
.status-approved  { color: #4ade80; background: rgba(74,222,128,0.10); }
.status-rejected  { color: #f87171; background: rgba(248,113,113,0.10); }
.status-saved     { color: #84cc16; background: rgba(132,204,22,0.10); }
.status-alert     { color: #fb923c; background: rgba(251,146,60,0.10); }

.progress-track {
    background: rgba(255,255,255,0.06);
    border-radius: 6px;
    height: 5px;
    overflow: hidden;
}
.progress-fill {
    height: 5px;
    border-radius: 6px;
    background: linear-gradient(90deg, var(--c-accent), #22d3ee);
    transition: width 0.5s ease, box-shadow 0.3s ease;
    box-shadow: 0 0 8px rgba(132,204,22,0.25);
}

.empty-state {
    text-align: center;
    padding: 48px 24px;
    color: var(--c-text-muted);
}
.empty-state-icon { font-size: 2.2rem; margin-bottom: 10px; opacity: 0.35; }
.empty-state-text { font-size: 0.88rem; font-weight: 500; color: var(--c-text-secondary); }

.a-summary-praxis {
    font-size: 0.78rem;
    color: var(--c-praxis-text);
    margin-top: 4px;
    padding: 5px 10px;
    background: rgba(74,222,128,0.08);
    border-radius: 4px;
    border-left: 3px solid var(--c-success);
    transition: var(--transition);
}

.score-breakdown {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 8px;
    padding: 8px 10px;
    background: rgba(255,255,255,0.02);
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.05);
}
.sb-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 58px;
    transition: transform 0.2s ease;
    position: relative;
    cursor: help;
}
/* Custom tooltip for score breakdown items (data-tip avoids native browser tooltip) */
.sb-item[data-tip]:hover::after {
    content: attr(data-tip);
    position: absolute;
    bottom: calc(100% + 8px);
    left: 50%;
    transform: translateX(-50%);
    background: rgba(14,14,34,0.97);
    color: #e8e8f0;
    font-size: 0.7rem;
    font-weight: 400;
    line-height: 1.55;
    padding: 10px 14px;
    border-radius: 8px;
    border: 1px solid rgba(132,204,22,0.15);
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    white-space: pre-line;
    width: max-content;
    max-width: 240px;
    z-index: 1000;
    pointer-events: none;
    animation: sb-tip-in 0.15s ease-out;
}
.sb-item[data-tip]:hover::before {
    content: '';
    position: absolute;
    bottom: calc(100% + 2px);
    left: 50%;
    transform: translateX(-50%);
    border: 5px solid transparent;
    border-top-color: rgba(14,14,34,0.97);
    z-index: 1001;
    pointer-events: none;
}
.sb-item[data-tip] { pointer-events: auto; }
@keyframes sb-tip-in {
    0% { opacity: 0; transform: translateX(-50%) translateY(4px); }
    100% { opacity: 1; transform: translateX(-50%) translateY(0); }
}
.sb-bar-track {
    width: 100%;
    height: 4px;
    background: rgba(255,255,255,0.08);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 3px;
}
.sb-bar-fill {
    height: 4px;
    border-radius: 2px;
    transition: width 0.3s ease, filter 0.2s ease, box-shadow 0.2s ease;
}
.sb-value {
    font-size: 0.68rem;
    font-weight: 600;
    color: var(--c-text);
}
.sb-label {
    font-size: 0.6rem;
    color: var(--c-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.03em;
}

/* Sidebar dividers */
section[data-testid="stSidebar"] hr {
    margin: 12px 0 !important;
    border-color: rgba(255,255,255,0.06) !important;
}

/* Expander styling — more compact in sidebar */
section[data-testid="stSidebar"] details summary {
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    color: var(--c-text-secondary) !important;
}

/* ===== THEMEN-RADAR 2.0 ===== */
.radar-overview {
    background: linear-gradient(135deg, rgba(132,204,22,0.06) 0%, rgba(34,211,238,0.06) 100%);
    border: 1px solid rgba(132,204,22,0.12);
    border-radius: var(--radius);
    padding: 14px 20px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 10px;
    position: relative;
    overflow: hidden;
}
.radar-overview::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--c-accent), #22d3ee, transparent);
    opacity: 0.5;
}
.radar-overview-icon {
    font-size: 1.1rem;
    flex-shrink: 0;
}
.radar-overview-text {
    font-size: 0.82rem;
    font-weight: 500;
    color: var(--c-text);
    line-height: 1.5;
}

/* Hero Card — Trend #1 */
.trend-hero {
    background: var(--c-surface);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--c-border);
    border-radius: var(--radius);
    overflow: hidden;
    margin-bottom: 16px;
    transition: var(--transition);
}
.trend-hero:hover {
    border-color: var(--c-border-hover);
    box-shadow: var(--shadow-md), 0 0 20px rgba(132,204,22,0.06);
    transform: translateY(-1px);
}
.trend-hero-accent {
    height: 3px;
    background: linear-gradient(90deg, var(--accent-from, #84cc16), var(--accent-to, #22d3ee));
    box-shadow: 0 2px 12px rgba(132,204,22,0.15);
}
.trend-hero-body {
    padding: 18px 24px 16px 24px;
}
.trend-hero-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 8px;
}
.trend-hero-label {
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--c-text);
    letter-spacing: -0.02em;
    line-height: 1.3;
}
.trend-hero-sublabel {
    font-size: 0.78rem;
    color: var(--c-text-secondary);
    line-height: 1.5;
    margin-bottom: 6px;
}
.trend-hero-summary {
    font-size: 0.78rem;
    color: var(--c-text-secondary);
    line-height: 1.5;
    margin-bottom: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
.trend-hero-stats {
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
}
.trend-hero-stat {
    display: flex;
    flex-direction: column;
    align-items: center;
}
.trend-hero-stat-value {
    font-size: 1rem;
    font-weight: 700;
    color: var(--c-text);
    line-height: 1;
}
.trend-hero-stat-label {
    font-size: 0.6rem;
    font-weight: 600;
    color: var(--c-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-top: 3px;
}

/* Trend Cards — #2+ */
.trend-card {
    background: var(--c-surface);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--c-border);
    border-radius: var(--radius);
    padding: 14px 16px 14px 19px;
    margin-bottom: 10px;
    transition: var(--transition);
    position: relative;
    overflow: hidden;
}
.trend-card:hover {
    border-color: var(--c-border-hover);
    box-shadow: var(--shadow-md);
    background: rgba(255,255,255,0.05);
    transform: translateY(-1px);
}
.trend-card::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
    background: var(--spec-color, #8b8ba0);
    box-shadow: 2px 0 10px color-mix(in srgb, var(--spec-color, #8b8ba0) 30%, transparent);
}
.trend-card-label {
    font-size: 0.88rem;
    font-weight: 700;
    color: var(--c-text);
    margin-bottom: 4px;
    line-height: 1.3;
}
.trend-card-why {
    font-size: 0.72rem;
    color: var(--c-text-secondary);
    line-height: 1.4;
    margin-bottom: 8px;
}
.trend-card-badges {
    display: flex;
    gap: 5px;
    flex-wrap: wrap;
    align-items: center;
}
.trend-card-meta {
    font-size: 0.62rem;
    color: var(--c-text-muted);
    margin-left: auto;
}

/* Momentum badges */
.momentum-badge {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.01em;
    transition: var(--transition);
}
.momentum-exploding {
    background: rgba(248,113,113,0.12);
    color: #f87171;
}
.momentum-rising {
    background: rgba(74,222,128,0.12);
    color: #4ade80;
}
.momentum-stable {
    background: rgba(255,255,255,0.06);
    color: #8b8ba0;
}
.momentum-falling {
    background: rgba(251,191,36,0.12);
    color: #fbbf24;
}

/* Evidence badge */
.evidence-badge {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 0.6rem;
    font-weight: 600;
    transition: var(--transition);
}
.evidence-badge-default {
    background: rgba(167,139,250,0.12);
    color: #a78bfa;
}
.evidence-badge-rising {
    background: rgba(74,222,128,0.12);
    color: #4ade80;
}

/* Cross-specialty badge */
.cross-spec-badge {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 0.6rem;
    font-weight: 600;
    background: rgba(96,165,250,0.12);
    color: #60a5fa;
    transition: var(--transition);
}

/* Empty state for Themen-Radar */
.trend-empty {
    border: 2px dashed var(--c-border);
    border-radius: var(--radius);
    padding: 40px 24px;
    text-align: center;
}
.trend-empty-icon {
    font-size: 2rem;
    opacity: 0.25;
    margin-bottom: 8px;
}
.trend-empty-text {
    font-size: 0.82rem;
    font-weight: 500;
    color: var(--c-text-secondary);
}
.trend-empty-sub {
    font-size: 0.72rem;
    color: var(--c-text-muted);
    margin-top: 4px;
}

/* Detail panel in expanders */
.trend-detail-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 12px;
    margin-bottom: 12px;
}
.trend-detail-col {
    padding: 10px 12px;
    background: rgba(255,255,255,0.02);
    border-radius: var(--radius-sm);
    border: 1px solid rgba(255,255,255,0.05);
}
.trend-detail-col-title {
    font-size: 0.6rem;
    font-weight: 700;
    color: var(--c-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 6px;
}
.trend-detail-col-item {
    font-size: 0.74rem;
    color: var(--c-text);
    padding: 2px 0;
    display: flex;
    justify-content: space-between;
}
.trend-detail-col-value {
    font-weight: 600;
    color: var(--c-text-secondary);
}

/* ===== KONGRESSPLAN ===== */
.kongress-hero {
    background: var(--c-surface);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--c-border);
    border-radius: var(--radius);
    overflow: hidden;
    margin-bottom: 16px;
    transition: var(--transition);
}
.kongress-hero:hover {
    border-color: var(--c-border-hover);
    box-shadow: var(--shadow-md), 0 0 24px color-mix(in srgb, var(--hero-accent, #84cc16) 12%, transparent);
    transform: translateY(-1px);
}
.kongress-hero-accent {
    height: 3px;
    box-shadow: 0 2px 12px rgba(132,204,22,0.15);
}
.kongress-hero-body {
    padding: 20px 24px 18px 24px;
}

.kongress-card {
    background: var(--c-surface);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--c-border);
    border-radius: var(--radius);
    padding: 14px 18px 14px 21px;
    margin-bottom: 8px;
    transition: var(--transition);
    position: relative;
    overflow: hidden;
}
.kongress-card::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    background: var(--spec-color, #8b8ba0);
    box-shadow: 2px 0 10px color-mix(in srgb, var(--spec-color, #8b8ba0) 30%, transparent);
}
.kongress-card:hover {
    border-color: var(--c-border-hover);
    box-shadow: var(--shadow-md);
    background: rgba(255,255,255,0.05);
    transform: translateY(-1px);
}

.kongress-badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.01em;
    transition: var(--transition);
}
.kongress-badge:hover {
    transform: translateY(-1px);
    filter: brightness(1.2);
}
.kongress-badge-national {
    background: rgba(59,130,246,0.12);
    color: #3b82f6;
}
.kongress-badge-intl {
    background: rgba(167,139,250,0.12);
    color: #a78bfa;
}
.kongress-badge-cme {
    background: rgba(74,222,128,0.12);
    color: #4ade80;
}
.kongress-badge-articles {
    background: rgba(59,130,246,0.12);
    color: #3b82f6;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
/* Sidebar-Toggle sichtbar halten auch wenn header versteckt */
[data-testid="stExpandSidebarButton"] { visibility: visible !important; }

/* ===== DARK MODE GLOBAL OVERRIDES ===== */
/* Streamlit native elements */
.stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown span {
    color: var(--c-text);
}
[data-testid="stExpander"] {
    background: var(--c-surface);
    border: 1px solid var(--c-border) !important;
    border-radius: var(--radius) !important;
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
}
[data-testid="stExpander"] summary {
    color: var(--c-text) !important;
}
[data-testid="stExpander"] summary:hover {
    color: var(--c-accent) !important;
}
/* Watchlist delete button — small red X */
[data-testid="stSidebar"] [data-testid="stExpander"] .stButton button {
    background: transparent !important;
    border: 1px solid rgba(248,113,113,0.25) !important;
    color: #f87171 !important;
    border-radius: 6px !important;
    padding: 2px 0 !important;
    min-height: unset !important;
    height: 26px !important;
    width: 26px !important;
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: all 0.15s ease !important;
    margin-top: 6px !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] .stButton button:hover {
    background: rgba(248,113,113,0.12) !important;
    border-color: #f87171 !important;
    transform: scale(1.08);
}
/* Selectbox / Multiselect dropdown */
[data-baseweb="select"] {
    background: rgba(255,255,255,0.03) !important;
}
[data-baseweb="popover"] [role="listbox"] {
    background: var(--c-surface-solid) !important;
    border: 1px solid var(--c-border) !important;
}
[data-baseweb="popover"] [role="option"] {
    color: var(--c-text) !important;
}
[data-baseweb="popover"] [role="option"]:hover {
    background: rgba(132,204,22,0.08) !important;
}
/* Popover panels (legend etc.) */
[data-testid="stPopover"] [data-testid="stPopoverBody"] {
    background: var(--c-surface-solid) !important;
    border: 1px solid var(--c-border) !important;
}
/* Number input */
.stNumberInput input {
    background: rgba(255,255,255,0.03) !important;
    color: var(--c-text) !important;
    border-color: var(--c-border) !important;
}
/* Spinner */
.stSpinner > div {
    border-top-color: var(--c-accent) !important;
}
/* Primary button override for lime */
.stButton > button[kind="primary"],
button[data-testid="stBaseButton-primary"] {
    background: var(--c-accent) !important;
    color: #0a0a1a !important;
    border: none !important;
    font-weight: 500;
}
.stButton > button[kind="primary"]:hover,
button[data-testid="stBaseButton-primary"]:hover {
    background: #a3e635 !important;
    box-shadow: 0 0 16px rgba(132,204,22,0.20) !important;
}
/* Slider */
.stSlider [data-baseweb="slider"] [role="slider"] {
    background: var(--c-accent) !important;
}
/* Caption text */
.stCaption, .stCaption p {
    color: var(--c-text-muted) !important;
}
/* Toast / success / warning / error */
[data-testid="stNotification"] {
    background: var(--c-surface-solid) !important;
    border: 1px solid var(--c-border) !important;
    color: var(--c-text) !important;
}
/* Links */
a { color: var(--c-accent); }
a:hover { color: #bef264; }

</style>
"""


def inject_css():
    """Inject the full custom CSS into the Streamlit app."""
    st.markdown(_get_css(), unsafe_allow_html=True)
