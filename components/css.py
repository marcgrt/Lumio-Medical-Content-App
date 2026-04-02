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
    --transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

/* ===== ESANUM LIGHT THEME ===== */
@import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap');

[data-theme="esanum"] {
    --c-bg: #FBFBFB;
    --c-surface: rgba(0,84,97,0.03);
    --c-surface-solid: #FFFFFF;
    --c-border: #ECECEC;
    --c-border-subtle: rgba(0,0,0,0.04);
    --c-border-hover: rgba(0,84,97,0.2);
    --c-text: #333333;
    --c-text-secondary: #555555;
    --c-text-muted: #777777;
    --c-text-tertiary: #666666;
    --c-accent: #005461;
    --c-accent-light: rgba(0,84,97,0.08);
    --c-success: #76A530;
    --c-success-light: rgba(118,165,48,0.10);
    --c-danger: #BE182D;
    --c-danger-light: rgba(190,24,45,0.10);
    --c-warn: #BAAA00;
    --c-warn-light: rgba(186,170,0,0.10);
    --c-highlight: #D6A06F;
    --c-highlight-bg: rgba(214,160,111,0.10);
    --c-ring-low: #D0D0D0;
    --c-praxis: #005461;
    --c-praxis-text: #005461;
    --c-alert-text: #BE182D;
    --radius: 8px;
    --radius-sm: 4px;
    --shadow-sm: 0px 2px 8px -2px rgba(16,24,40,0.1), 0px 4px 4px -2px rgba(16,24,40,0.06);
    --shadow-md: 0px 12px 16px -4px rgba(16,24,40,0.1), 0px 4px 6px -2px rgba(16,24,40,0.05);
    --glass-blur: none;
    --transition: background 150ms ease, border-color 150ms ease, color 150ms ease, box-shadow 150ms ease, transform 150ms ease;
}
/* esanum: Font override — scoped to specific elements, NOT universal * */
[data-theme="esanum"] .stApp,
[data-theme="esanum"] .stButton button,
[data-theme="esanum"] .stDownloadButton button,
[data-theme="esanum"] .stFormSubmitButton button,
[data-theme="esanum"] .stMarkdown,
[data-theme="esanum"] .stMarkdown p,
[data-theme="esanum"] .stMarkdown span,
[data-theme="esanum"] .stMarkdown div,
[data-theme="esanum"] .stSelectbox,
[data-theme="esanum"] .stTextInput input,
[data-theme="esanum"] .stTextArea textarea,
[data-theme="esanum"] .stTab,
[data-theme="esanum"] [role="tab"],
[data-theme="esanum"] .stExpander,
[data-theme="esanum"] .stMetric,
[data-theme="esanum"] [data-testid="stMetricValue"],
[data-theme="esanum"] [data-testid="stMetricLabel"],
[data-theme="esanum"] h1, [data-theme="esanum"] h2, [data-theme="esanum"] h3,
[data-theme="esanum"] label,
[data-theme="esanum"] .stRadio label,
[data-theme="esanum"] .stCheckbox label {
    font-family: 'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    font-feature-settings: normal !important;
}
[data-theme="esanum"] [data-testid="stIconMaterial"],
[data-theme="esanum"] [data-testid="stIcon"],
[data-theme="esanum"] .material-symbols-rounded {
    font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
}
/* esanum: App background */
[data-theme="esanum"] .stApp {
    background-color: #FBFBFB !important;
    color: #444444 !important;
}
[data-theme="esanum"] .stApp::before {
    display: none !important;
}
/* esanum: Sidebar */
[data-theme="esanum"] section[data-testid="stSidebar"] {
    background: #FFFFFF !important;
    border-right: 1px solid #ECECEC !important;
}
[data-theme="esanum"] section[data-testid="stSidebar"] label,
[data-theme="esanum"] section[data-testid="stSidebar"] span,
[data-theme="esanum"] section[data-testid="stSidebar"] p,
[data-theme="esanum"] section[data-testid="stSidebar"] div,
[data-theme="esanum"] section[data-testid="stSidebar"] button,
[data-theme="esanum"] section[data-testid="stSidebar"] a,
[data-theme="esanum"] section[data-testid="stSidebar"] input {
    color: #444444 !important;
}
[data-theme="esanum"] section[data-testid="stSidebar"] .stMarkdown p {
    color: #737373 !important;
}
/* esanum: Article cards — white with shadow */
[data-theme="esanum"] .a-card {
    background: #FFFFFF !important;
    border: 1px solid #ECECEC !important;
    box-shadow: 0px 2px 8px -2px rgba(16,24,40,0.1), 0px 4px 4px -2px rgba(16,24,40,0.06) !important;
}
[data-theme="esanum"] .a-card:hover {
    border-color: rgba(0,84,97,0.2) !important;
    box-shadow: 0px 12px 16px -4px rgba(16,24,40,0.1), 0px 4px 6px -2px rgba(16,24,40,0.05) !important;
    background: #FFFFFF !important;
}
/* esanum: Dashboard cards */
[data-theme="esanum"] .dash-card {
    background: #FFFFFF !important;
    backdrop-filter: none !important;
    border: 1px solid #ECECEC !important;
    box-shadow: 0px 2px 8px -2px rgba(16,24,40,0.1) !important;
}
/* esanum: Page header — teal gradient instead of lime */
[data-theme="esanum"] .page-header {
    background: linear-gradient(135deg, #444444 0%, #005461 80%) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
    text-shadow: none !important;
}
/* esanum: Score rings — single drop-shadow (no chained filters, no infinite animation) */
[data-theme="esanum"] .ring-high {
    stroke: #22c55e !important;
    filter: drop-shadow(0 0 10px rgba(34,197,94,0.5)) !important;
    animation: ring-draw 1.2s cubic-bezier(0.22, 1, 0.36, 1) forwards !important;
}
[data-theme="esanum"] .ring-mid {
    stroke: #eab308 !important;
    filter: drop-shadow(0 0 10px rgba(234,179,8,0.5)) !important;
    animation: ring-draw 1.2s cubic-bezier(0.22, 1, 0.36, 1) forwards !important;
}
[data-theme="esanum"] .a-score-ring .ring-bg {
    stroke: rgba(0,0,0,0.06) !important;
}
/* esanum: Button styles — handled by master block below (search "COMPLETE button reset") */
/* esanum: Input focus — teal ring */
[data-theme="esanum"] .stTextInput input,
[data-theme="esanum"] .stTextArea textarea,
[data-theme="esanum"] .stNumberInput input {
    caret-color: #005461 !important;
}
[data-theme="esanum"] .stTextInput input:focus,
[data-theme="esanum"] .stTextArea textarea:focus {
    box-shadow: 0 0 0 3px rgba(0,165,174,0.25) !important;
    border-color: #005461 !important;
    caret-color: #005461 !important;
}
/* esanum: Tabs — teal active border */
[data-theme="esanum"] [data-baseweb="tab"][aria-selected="true"] {
    color: #005461 !important;
    border-bottom-color: #00A5AE !important;
}
/* esanum: Expander */
[data-theme="esanum"] [data-testid="stExpander"] {
    background: #FFFFFF !important;
    border: 1px solid #ECECEC !important;
}
/* esanum: Metrics */
[data-theme="esanum"] [data-testid="stMetric"] {
    background: transparent !important;
}
[data-theme="esanum"] [data-testid="stMetricLabel"] {
    color: #737373 !important;
}
/* esanum: Sidebar KPI bar */
[data-theme="esanum"] .sidebar-kpi-bar {
    background: #FFFFFF !important;
    border-color: #ECECEC !important;
}
[data-theme="esanum"] .sidebar-kpi-item:hover {
    background: #E5EEEF !important;
}
/* esanum: Sort tooltip */
[data-theme="esanum"] .sort-legend-toggle .sort-tooltip {
    background: #FFFFFF !important;
    border-color: #ECECEC !important;
    color: #737373 !important;
    box-shadow: 0px 12px 16px -4px rgba(16,24,40,0.1) !important;
}
/* esanum: Specialty tag colors — keep but adjust text for readability */
[data-theme="esanum"] .spec-pill {
    opacity: 0.9;
}

/* ===== ESANUM: Sidebar deep overrides ===== */
/* Sidebar background: clean white with subtle left border */
[data-theme="esanum"] section[data-testid="stSidebar"] {
    background: #FFFFFF !important;
    border-right: 1px solid #ECECEC !important;
}
/* All sidebar text: dark (scoped, not universal) — already defined above */
/* Selectbox / Multiselect / Dropdown — light background */
[data-theme="esanum"] section[data-testid="stSidebar"] [data-baseweb="select"],
[data-theme="esanum"] section[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #F5F5F5 !important;
    border-color: #ECECEC !important;
    color: #444444 !important;
}
[data-theme="esanum"] section[data-testid="stSidebar"] [data-baseweb="select"] span,
[data-theme="esanum"] section[data-testid="stSidebar"] [data-baseweb="select"] div,
[data-theme="esanum"] section[data-testid="stSidebar"] [data-baseweb="select"] input {
    color: #444444 !important;
}
/* Dropdown menu popover */
[data-theme="esanum"] [data-baseweb="popover"],
[data-theme="esanum"] [data-baseweb="menu"],
[data-theme="esanum"] [role="listbox"] {
    background: #FFFFFF !important;
    border: 1px solid #ECECEC !important;
}
[data-theme="esanum"] [data-baseweb="menu"] li,
[data-theme="esanum"] [role="option"] {
    color: #333333 !important;
    background: transparent !important;
}
[data-theme="esanum"] [data-baseweb="menu"] li:hover,
[data-theme="esanum"] [role="option"]:hover,
[data-theme="esanum"] [role="option"][aria-selected="true"] {
    background: #E5EEEF !important;
}
/* Dropdown portals render OUTSIDE [data-theme] — need html-level selector */
html[data-theme="esanum"] [data-baseweb="popover"],
html[data-theme="esanum"] [data-baseweb="popover"] [data-baseweb="menu"],
html[data-theme="esanum"] [data-baseweb="popover"] [role="listbox"],
html[data-theme="esanum"] [data-baseweb="popover"] ul {
    background: #FFFFFF !important;
    border: 1px solid #ECECEC !important;
    color: #333333 !important;
}
html[data-theme="esanum"] [data-baseweb="popover"] li,
html[data-theme="esanum"] [data-baseweb="popover"] [role="option"] {
    color: #333333 !important;
    background: transparent !important;
}
html[data-theme="esanum"] [data-baseweb="popover"] li:hover,
html[data-theme="esanum"] [data-baseweb="popover"] [role="option"]:hover,
html[data-theme="esanum"] [data-baseweb="popover"] [role="option"][aria-selected="true"] {
    background: #E5EEEF !important;
}
/* Text inputs in sidebar */
[data-theme="esanum"] section[data-testid="stSidebar"] input,
[data-theme="esanum"] section[data-testid="stSidebar"] textarea,
[data-theme="esanum"] section[data-testid="stSidebar"] [data-baseweb="input"] input,
[data-theme="esanum"] section[data-testid="stSidebar"] [data-baseweb="base-input"] input {
    background: #F5F5F5 !important;
    border-color: #ECECEC !important;
    color: #333333 !important;
    -webkit-text-fill-color: #333333 !important;
}
[data-theme="esanum"] section[data-testid="stSidebar"] [data-baseweb="input"],
[data-theme="esanum"] section[data-testid="stSidebar"] [data-baseweb="base-input"] {
    background: #F5F5F5 !important;
    border-color: #ECECEC !important;
}
/* Slider track */
[data-theme="esanum"] section[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] [role="slider"] {
    background: #005461 !important;
}
[data-theme="esanum"] section[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] div[role="progressbar"] {
    background: #005461 !important;
}
/* Sidebar buttons: flat, no shadow, readable size */
[data-theme="esanum"] section[data-testid="stSidebar"] button {
    background: #FFFFFF !important;
    border: 1px solid #DDDDDD !important;
    color: #555555 !important;
    box-shadow: none !important;
    font-weight: 500 !important;
    font-size: 0.78rem !important;
    min-height: 36px !important;
    padding: 6px 12px !important;
    transition: background 0.15s ease !important;
}
[data-theme="esanum"] section[data-testid="stSidebar"] button:hover {
    background: #F0F0F0 !important;
    border-color: #CCCCCC !important;
    box-shadow: none !important;
}
[data-theme="esanum"] section[data-testid="stSidebar"] button:active {
    background: #E8E8E8 !important;
    box-shadow: none !important;
}
/* Number input step buttons (+/-) */
[data-theme="esanum"] section[data-testid="stSidebar"] .step-down,
[data-theme="esanum"] section[data-testid="stSidebar"] .step-up,
[data-theme="esanum"] section[data-testid="stSidebar"] [data-testid="stNumberInput"] button,
[data-theme="esanum"] section[data-testid="stSidebar"] button[kind="secondary"] {
    background: #F5F5F5 !important;
    border-color: #ECECEC !important;
    color: #333333 !important;
}
[data-theme="esanum"] section[data-testid="stSidebar"] [data-testid="stNumberInput"] button svg,
[data-theme="esanum"] section[data-testid="stSidebar"] .step-down svg,
[data-theme="esanum"] section[data-testid="stSidebar"] .step-up svg {
    fill: #333333 !important;
    stroke: #333333 !important;
    color: #333333 !important;
}
/* Also fix number input step buttons in main content */
[data-theme="esanum"] [data-testid="stNumberInput"] button {
    background: #F5F5F5 !important;
    border-color: #ECECEC !important;
    color: #333333 !important;
}
[data-theme="esanum"] [data-testid="stNumberInput"] button svg {
    fill: #333333 !important;
    stroke: #333333 !important;
    color: #333333 !important;
}
/* Radio / Segmented buttons in sidebar */
[data-theme="esanum"] section[data-testid="stSidebar"] [data-baseweb="button-group"] button,
[data-theme="esanum"] section[data-testid="stSidebar"] .stRadio label,
[data-theme="esanum"] section[data-testid="stSidebar"] [data-baseweb="radio"] {
    background: #F5F5F5 !important;
    border-color: #ECECEC !important;
    color: #333333 !important;
}
[data-theme="esanum"] section[data-testid="stSidebar"] [data-baseweb="radio"] p {
    color: #333333 !important;
}
[data-theme="esanum"] section[data-testid="stSidebar"] [data-baseweb="button-group"] button[aria-pressed="true"],
[data-theme="esanum"] section[data-testid="stSidebar"] .stRadio label[data-checked="true"],
[data-theme="esanum"] section[data-testid="stSidebar"] [data-baseweb="radio"]:has(input:checked) {
    background: #005461 !important;
    color: #FFFFFF !important;
    border-color: #005461 !important;
}
[data-theme="esanum"] section[data-testid="stSidebar"] [data-baseweb="radio"]:has(input:checked) p {
    color: #FFFFFF !important;
}
/* Sidebar buttons */
[data-theme="esanum"] section[data-testid="stSidebar"] .stButton button {
    background: #F5F5F5 !important;
    border: 1px solid #ECECEC !important;
    color: #444444 !important;
}
[data-theme="esanum"] section[data-testid="stSidebar"] .stButton button:hover {
    background: #E5EEEF !important;
    border-color: #005461 !important;
    color: #005461 !important;
}
/* Filter labels — consistent spacing */
[data-theme="esanum"] .filter-label {
    color: #444444 !important;
}
/* Sidebar KPI bar numbers — ensure dark text */
[data-theme="esanum"] .sidebar-kpi-num {
    color: #444444 !important;
}
[data-theme="esanum"] .sidebar-kpi-label {
    color: #A1A1A1 !important;
}
/* Logo in sidebar — darken for light bg */
[data-theme="esanum"] .lumio-logo {
    filter: brightness(0.3) !important;
}

/* ===== ESANUM: Force white text on ALL teal/dark backgrounds ===== */
/* Catch all inline style variants: with/without spaces, short/long hex, rgb */
[data-theme="esanum"] [style*="background:#005461"],
[data-theme="esanum"] [style*="background: #005461"],
[data-theme="esanum"] [style*="background-color:#005461"],
[data-theme="esanum"] [style*="background-color: #005461"],
[data-theme="esanum"] [style*="background:#003E48"],
[data-theme="esanum"] [style*="background: #003E48"],
[data-theme="esanum"] [style*="background-color:#003E48"],
[data-theme="esanum"] [style*="background-color: #003E48"],
[data-theme="esanum"] [style*="background:#00A5AE"],
[data-theme="esanum"] [style*="background: #00A5AE"],
[data-theme="esanum"] [style*="background-color:#00A5AE"],
[data-theme="esanum"] [style*="background-color: #00A5AE"],
[data-theme="esanum"] [style*="background:#0a0a1a"],
[data-theme="esanum"] [style*="background: #0a0a1a"],
[data-theme="esanum"] [style*="background-color:#0a0a1a"],
[data-theme="esanum"] [style*="background-color: #0a0a1a"] {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}
[data-theme="esanum"] [style*="background:#005461"] *,
[data-theme="esanum"] [style*="background: #005461"] *,
[data-theme="esanum"] [style*="background-color:#005461"] *,
[data-theme="esanum"] [style*="background-color: #005461"] *,
[data-theme="esanum"] [style*="background:#003E48"] *,
[data-theme="esanum"] [style*="background: #003E48"] *,
[data-theme="esanum"] [style*="background-color:#003E48"] *,
[data-theme="esanum"] [style*="background-color: #003E48"] *,
[data-theme="esanum"] [style*="background:#00A5AE"] *,
[data-theme="esanum"] [style*="background: #00A5AE"] *,
[data-theme="esanum"] [style*="background-color:#00A5AE"] *,
[data-theme="esanum"] [style*="background-color: #00A5AE"] *,
[data-theme="esanum"] [style*="background:#0a0a1a"] *,
[data-theme="esanum"] [style*="background: #0a0a1a"] *,
[data-theme="esanum"] [style*="background-color:#0a0a1a"] *,
[data-theme="esanum"] [style*="background-color: #0a0a1a"] *,
[data-theme="esanum"] .dark-banner *,
[data-theme="esanum"] .lumio-dark-bg,
[data-theme="esanum"] .lumio-dark-bg *,
[data-theme="esanum"] .lumio-dark-bg p,
[data-theme="esanum"] .lumio-dark-bg b,
[data-theme="esanum"] .lumio-dark-bg span,
[data-theme="esanum"] .lumio-dark-bg div,
[data-theme="esanum"] [data-testid="stAppViewContainer"] .lumio-dark-bg,
[data-theme="esanum"] [data-testid="stAppViewContainer"] .lumio-dark-bg *,
[data-theme="esanum"] [data-testid="stAppViewContainer"] .lumio-dark-bg p,
[data-theme="esanum"] [data-testid="stAppViewContainer"] .lumio-dark-bg b {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}
/* Streamlit native primary buttons — always white text on teal */
html[data-theme="esanum"] button[data-testid="stBaseButton-primary"],
html[data-theme="esanum"] button[data-testid="stBaseButton-primary"] p,
html[data-theme="esanum"] button[data-testid="stBaseButton-primary"] span,
html[data-theme="esanum"] button[data-testid="stBaseButton-primary"] div,
html[data-theme="esanum"] .stButton button[data-testid="stBaseButton-primary"],
html[data-theme="esanum"] .stButton button[data-testid="stBaseButton-primary"] p,
html[data-theme="esanum"] .stButton button[data-testid="stBaseButton-primary"] span,
html[data-theme="esanum"] .stFormSubmitButton button,
html[data-theme="esanum"] .stFormSubmitButton button p,
html[data-theme="esanum"] .stFormSubmitButton button span {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}

/* ===== ESANUM: Main content deep overrides ===== */
/* Streamlit native widgets in main area */
[data-theme="esanum"] [data-testid="stAppViewContainer"] [data-baseweb="select"],
[data-theme="esanum"] [data-testid="stAppViewContainer"] [data-baseweb="select"] > div {
    background: #FFFFFF !important;
    border-color: #ECECEC !important;
    color: #444444 !important;
}
/* Input and textarea — text, background, border, placeholder */
[data-theme="esanum"] [data-testid="stAppViewContainer"] input,
[data-theme="esanum"] [data-testid="stAppViewContainer"] textarea,
[data-theme="esanum"] [data-testid="stAppViewContainer"] [data-baseweb="input"] input,
[data-theme="esanum"] [data-testid="stAppViewContainer"] [data-baseweb="base-input"] input,
[data-theme="esanum"] [data-testid="stAppViewContainer"] [data-baseweb="textarea"] textarea {
    background: #FFFFFF !important;
    border-color: #ECECEC !important;
    color: #333333 !important;
    -webkit-text-fill-color: #333333 !important;
}
[data-theme="esanum"] [data-testid="stAppViewContainer"] [data-baseweb="input"],
[data-theme="esanum"] [data-testid="stAppViewContainer"] [data-baseweb="base-input"],
[data-theme="esanum"] [data-testid="stAppViewContainer"] [data-baseweb="textarea"] {
    background: #FFFFFF !important;
    border-color: #ECECEC !important;
}
/* Placeholder text */
[data-theme="esanum"] input::placeholder,
[data-theme="esanum"] textarea::placeholder {
    color: #AAAAAA !important;
    -webkit-text-fill-color: #AAAAAA !important;
    opacity: 1 !important;
}
/* Date input */
[data-theme="esanum"] [data-testid="stDateInput"] input {
    color: #333333 !important;
    -webkit-text-fill-color: #333333 !important;
}
/* Select/dropdown — selected value text */
[data-theme="esanum"] [data-baseweb="select"] [data-testid="stMarkdown"],
[data-theme="esanum"] [data-baseweb="select"] span,
[data-theme="esanum"] [data-baseweb="select"] div[role="option"],
[data-theme="esanum"] [data-baseweb="select"] > div > div {
    color: #333333 !important;
}
/* Form labels */
[data-theme="esanum"] [data-testid="stAppViewContainer"] label,
[data-theme="esanum"] [data-testid="stAppViewContainer"] .stTextInput label p,
[data-theme="esanum"] [data-testid="stAppViewContainer"] .stTextArea label p,
[data-theme="esanum"] [data-testid="stAppViewContainer"] .stSelectbox label p,
[data-theme="esanum"] [data-testid="stAppViewContainer"] .stDateInput label p {
    color: #333333 !important;
}
/* Form submit button */
[data-theme="esanum"] [data-testid="stAppViewContainer"] [data-testid="stFormSubmitButton"] button {
    background: #FFFFFF !important;
    color: #005461 !important;
    border: 1px solid #005461 !important;
}
[data-theme="esanum"] [data-testid="stAppViewContainer"] [data-testid="stFormSubmitButton"] button:hover {
    background: #E5EEEF !important;
    color: #003E48 !important;
}
/* Tab bar */
[data-theme="esanum"] [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid #ECECEC !important;
}
[data-theme="esanum"] [data-baseweb="tab"] {
    color: #737373 !important;
}
[data-theme="esanum"] [data-baseweb="tab"][aria-selected="true"] {
    color: #005461 !important;
}
/* Expander in main */
[data-theme="esanum"] [data-testid="stExpander"] {
    background: #FFFFFF !important;
    border: 1px solid #ECECEC !important;
}
[data-theme="esanum"] [data-testid="stExpander"] summary {
    color: #444444 !important;
}
/* Score value text */
[data-theme="esanum"] .a-score-val {
    color: #444444 !important;
}
/* Dash values */
[data-theme="esanum"] .dash-value {
    color: #444444 !important;
}
[data-theme="esanum"] .dash-card:hover .dash-value {
    color: #005461 !important;
}
[data-theme="esanum"] .dash-label {
    color: #A1A1A1 !important;
}
/* KPI delta arrows */
[data-theme="esanum"] .kpi-delta-up { color: #76A530 !important; }
[data-theme="esanum"] .kpi-delta-down { color: #BE182D !important; }
/* Sparkline bars */
[data-theme="esanum"] .sparkline-bar {
    background: #005461 !important;
}
/* Section divider */
[data-theme="esanum"] .section-divider {
    color: #444444 !important;
}
[data-theme="esanum"] .section-divider::after {
    background: #ECECEC !important;
}

/* ===== ESANUM: Status badges ===== */
[data-theme="esanum"] .status-new       { color: #737373 !important; background: rgba(0,0,0,0.04) !important; }
[data-theme="esanum"] .status-approved  { color: #49661E !important; background: rgba(118,165,48,0.12) !important; }
[data-theme="esanum"] .status-rejected  { color: #80111F !important; background: rgba(190,24,45,0.10) !important; }
[data-theme="esanum"] .status-saved     { color: #005461 !important; background: rgba(0,84,97,0.10) !important; }
[data-theme="esanum"] .status-alert     { color: #7A7000 !important; background: rgba(186,170,0,0.12) !important; }
[data-theme="esanum"] .progress-track   { background: rgba(0,0,0,0.06) !important; }

/* ===== ESANUM: Global rgba(255,255,255,...) → rgba(0,0,0,...) ===== */
/* All transparent white overlays become transparent black in light mode */
[data-theme="esanum"] .med-card,
[data-theme="esanum"] .saisonal-section-reveal {
    background: #FFFFFF !important;
    border: 1px solid #ECECEC !important;
}
[data-theme="esanum"] .med-card:hover {
    background: #FFFFFF !important;
    border-color: rgba(0,84,97,0.2) !important;
    box-shadow: 0px 12px 16px -4px rgba(16,24,40,0.1) !important;
}
/* Favorite count badge */
[data-theme="esanum"] .fav-count {
    color: #FFFFFF !important;
}
/* Card top-line accent */
[data-theme="esanum"] .a-card::before {
    background: linear-gradient(90deg, #005461, #00A5AE) !important;
}
/* Dash card accent top line */
[data-theme="esanum"] .dash-card::before {
    background: linear-gradient(90deg, #005461, #00A5AE) !important;
}
/* Memory badges */
[data-theme="esanum"] .mem-badge-related,
[data-theme="esanum"] .mem-badge-update {
    background: rgba(0,84,97,0.08) !important;
    border-color: rgba(0,84,97,0.15) !important;
    color: #005461 !important;
}
/* Highlight tags */
[data-theme="esanum"] .htag {
    background: rgba(0,0,0,0.04) !important;
    color: #444444 !important;
    border-color: rgba(0,0,0,0.08) !important;
}
/* New-theme badge */
[data-theme="esanum"] .new-theme-badge {
    background: rgba(0,84,97,0.08) !important;
    color: #005461 !important;
}
/* Score breakdown borders */
[data-theme="esanum"] .score-breakdown-row {
    border-color: rgba(0,0,0,0.06) !important;
}
/* Onboarding / Alert banner */
[data-theme="esanum"] .alert-banner {
    background: rgba(190,24,45,0.05) !important;
    border-color: rgba(190,24,45,0.15) !important;
}
/* Empty state */
[data-theme="esanum"] .empty-state {
    color: #737373 !important;
}
/* Link colors */
[data-theme="esanum"] .a-title-link {
    color: #005461 !important;
}
[data-theme="esanum"] .a-title-link:hover {
    color: #003E48 !important;
}
/* User menu background */
[data-theme="esanum"] section[data-testid="stSidebar"] .sidebar-kpi-num {
    color: #444444 !important;
}

/* ===== ESANUM: Text readability fixes ===== */
/* Sidebar labels, muted text, filter headers */
[data-theme="esanum"] section[data-testid="stSidebar"] label,
[data-theme="esanum"] section[data-testid="stSidebar"] .sidebar-section-label {
    color: #444444 !important;
}
[data-theme="esanum"] [data-testid="stAppViewContainer"] .stRadio label p,
[data-theme="esanum"] [data-testid="stAppViewContainer"] [data-baseweb="select"] span,
[data-theme="esanum"] [data-testid="stAppViewContainer"] .stSelectbox label p {
    color: #222222 !important;
}
/* Muted / secondary text */
[data-theme="esanum"] .text-muted,
[data-theme="esanum"] [style*="color:var(--c-text-muted)"],
[data-theme="esanum"] .feed-subtitle {
    color: #737373 !important;
}
/* Dashboard stat cards — labels */
[data-theme="esanum"] .dash-card .dash-label,
[data-theme="esanum"] .dash-card small,
[data-theme="esanum"] .kpi-label {
    color: #737373 !important;
}
/* Dashboard stat cards — numbers */
[data-theme="esanum"] .dash-card .dash-num,
[data-theme="esanum"] .kpi-num {
    color: #222222 !important;
}
/* Congress calendar — header text */
[data-theme="esanum"] .congress-month-title,
[data-theme="esanum"] .cal-header {
    color: #222222 !important;
}
/* Congress calendar — day labels, count text */
[data-theme="esanum"] .cal-day-label,
[data-theme="esanum"] .cal-day-num,
[data-theme="esanum"] .congress-count {
    color: #444444 !important;
}
/* Congress — filter labels */
[data-theme="esanum"] .filter-label,
[data-theme="esanum"] h4,
[data-theme="esanum"] h5 {
    color: #222222 !important;
}
/* Timeline / Kalender / Weltkarte toggle labels */
[data-theme="esanum"] .stRadio [role="radiogroup"] label p {
    color: #444444 !important;
}
/* General light-mode anchor overrides */
[data-theme="esanum"] a {
    color: #005461 !important;
}
[data-theme="esanum"] a:hover {
    color: #003E48 !important;
}
/* Sortierung info icon */
[data-theme="esanum"] .sort-info-icon {
    color: #737373 !important;
}
/* Overlap warning badge */
[data-theme="esanum"] .overlap-badge {
    color: #7A7000 !important;
    background: rgba(186,170,0,0.08) !important;
    border-color: rgba(186,170,0,0.2) !important;
}
/* Expander headers */
[data-theme="esanum"] [data-testid="stExpander"] summary span,
[data-theme="esanum"] [data-testid="stExpander"] summary p {
    color: #222222 !important;
}
/* Tab labels */
[data-theme="esanum"] [data-baseweb="tab"] button {
    color: #737373 !important;
}
[data-theme="esanum"] [data-baseweb="tab"][aria-selected="true"] button,
[data-theme="esanum"] .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
    color: #005461 !important;
}
/* Kongress favorite star */
[data-theme="esanum"] .fav-star {
    color: #BAA900 !important;
}
/* Select/dropdown text in main area */
[data-theme="esanum"] [data-testid="stAppViewContainer"] [data-baseweb="select"] div,
[data-theme="esanum"] [data-testid="stAppViewContainer"] .stSelectbox div[data-baseweb="select"] span {
    color: #222222 !important;
}
/* Checkbox labels */
[data-theme="esanum"] .stCheckbox label span {
    color: #444444 !important;
}
/* Score ring text */
[data-theme="esanum"] .score-ring-text {
    fill: #222222 !important;
}

/* ===== ESANUM: Charts, Tables, Dataframes ===== */
/* Altair/Vega charts — white background */
[data-theme="esanum"] [data-testid="stVegaLiteChart"],
[data-theme="esanum"] [data-testid="stArrowVegaLiteChart"] {
    background: #FFFFFF !important;
    border: 1px solid #ECECEC !important;
    border-radius: 10px !important;
    padding: 8px !important;
}
[data-theme="esanum"] [data-testid="stVegaLiteChart"] canvas,
[data-theme="esanum"] [data-testid="stArrowVegaLiteChart"] canvas {
    border-radius: 8px !important;
}
/* Dataframe / Table — white background, dark text */
[data-theme="esanum"] [data-testid="stDataFrame"],
[data-theme="esanum"] [data-testid="stTable"],
[data-theme="esanum"] .stDataFrame,
[data-theme="esanum"] .stTable {
    background: #FFFFFF !important;
    border: 1px solid #ECECEC !important;
    border-radius: 10px !important;
    overflow: hidden;
}
[data-theme="esanum"] [data-testid="stDataFrame"] [data-testid="glideDataEditor"],
[data-theme="esanum"] [data-testid="stDataFrame"] .dvn-scroller {
    background: #FFFFFF !important;
}
/* Dataframe header cells */
[data-theme="esanum"] [data-testid="stDataFrame"] [data-testid="glideDataEditor"] th,
[data-theme="esanum"] [data-testid="stDataFrame"] .header-cell {
    background: #F5F5F5 !important;
    color: #333333 !important;
}
/* Dataframe body cells */
[data-theme="esanum"] [data-testid="stDataFrame"] td,
[data-theme="esanum"] [data-testid="stDataFrame"] .cell {
    color: #333333 !important;
}
/* Iframe-embedded charts (Altair renders in iframe) */
[data-theme="esanum"] [data-testid="stAppViewContainer"] iframe[title*="vega"],
[data-theme="esanum"] [data-testid="stAppViewContainer"] iframe[title*="altair"] {
    border-radius: 10px !important;
    border: 1px solid #ECECEC !important;
}
/* Metric containers */
[data-theme="esanum"] [data-testid="stMetric"] {
    background: #FFFFFF !important;
    border: 1px solid #ECECEC !important;
    border-radius: 10px !important;
    padding: 12px !important;
}

/* ===== ESANUM: Minimal inline-style fallbacks ===== */
/* Most colors now use CSS vars in Python code. These catch edge cases. */

/* Altair charts — hardcoded blue accent */
[data-theme="esanum"] [style*="color:#60a5fa"] {
    color: #005461 !important;
}

/* Onboarding / tooltip text on dark backgrounds */
[data-theme="esanum"] [style*="color:#0a0a1a"] {
    color: #FFFFFF !important;
}

/* Lime accent colors used in versand.py glass buttons */
[data-theme="esanum"] [style*="color:#d9f99d"],
[data-theme="esanum"] [style*="color:#ecfccb"],
[data-theme="esanum"] [style*="color:#bbf7d0"] {
    color: #555555 !important;
}

/* Expander headers in esanum — dark background header bars */
[data-theme="esanum"] [data-testid="stExpander"] details {
    background: #FFFFFF !important;
    border: 1px solid #ECECEC !important;
}
[data-theme="esanum"] [data-testid="stExpander"] summary {
    background: #F5F5F5 !important;
    color: #333333 !important;
}
[data-theme="esanum"] [data-testid="stExpander"] summary svg {
    color: #555555 !important;
    fill: #555555 !important;
}

/* Cowork — all card backgrounds and text */
[data-theme="esanum"] .cowork-card,
[data-theme="esanum"] [style*="border-left:3px solid"] {
    background: #FFFFFF !important;
}

/* Saisonal section cards */
[data-theme="esanum"] .saisonal-card {
    background: #FFFFFF !important;
    border: 1px solid #ECECEC !important;
}

/* Markdown content inside Streamlit */
[data-theme="esanum"] [data-testid="stAppViewContainer"] [data-testid="stMarkdown"] p,
[data-theme="esanum"] [data-testid="stAppViewContainer"] [data-testid="stMarkdown"] span,
[data-theme="esanum"] [data-testid="stAppViewContainer"] [data-testid="stMarkdown"] div,
[data-theme="esanum"] [data-testid="stAppViewContainer"] [data-testid="stMarkdown"] li {
    color: #333333;
}

/* Force all Streamlit text widgets to be readable — scoped selectors */
[data-theme="esanum"] [data-testid="stAppViewContainer"] p,
[data-theme="esanum"] [data-testid="stAppViewContainer"] .stMarkdown span,
[data-theme="esanum"] [data-testid="stAppViewContainer"] .stMetric span {
    color: #333333;
}
/* Code blocks: force light text on dark background for readability */
[data-theme="esanum"] [data-testid="stCode"] code,
[data-theme="esanum"] [data-testid="stCode"] pre,
[data-theme="esanum"] .stCodeBlock code,
[data-theme="esanum"] .stCodeBlock pre {
    color: #e8e8e8 !important;
}
[data-theme="esanum"] [data-testid="stCode"] span,
[data-theme="esanum"] .stCodeBlock span {
    color: #d4d4d4 !important;
}
/* Dark bg elements always get white text */
[data-theme="esanum"] .lumio-dark-bg,
[data-theme="esanum"] .lumio-dark-bg span,
[data-theme="esanum"] .lumio-dark-bg p,
[data-theme="esanum"] .lumio-dark-bg div,
[data-theme="esanum"] .lumio-dark-bg a {
    color: #FFFFFF !important;
}
/* But keep functional colors (green/red/amber status indicators, specialty colors) */
[data-theme="esanum"] [style*="color:#4ade80"] { color: #49661E !important; }
[data-theme="esanum"] [style*="color:#f87171"] { color: #BE182D !important; }
[data-theme="esanum"] [style*="color:#fbbf24"],
[data-theme="esanum"] [style*="color:#f59e0b"] { color: #7A7000 !important; }
[data-theme="esanum"] [style*="color:#84cc16"] { color: #49661E !important; }
[data-theme="esanum"] [style*="color:#fb923c"] { color: #9A4B00 !important; }
[data-theme="esanum"] [style*="color:#d4a017"] { color: #8B7000 !important; }

/* Tabs — ensure active/inactive are readable */
[data-theme="esanum"] .stTabs [data-baseweb="tab-list"] button {
    color: #777777 !important;
}
[data-theme="esanum"] .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
    color: #005461 !important;
    border-bottom-color: #005461 !important;
}

/* Metric values */
[data-theme="esanum"] [data-testid="stMetric"] label,
[data-theme="esanum"] [data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #333333 !important;
}

/* Download buttons */
[data-theme="esanum"] .stDownloadButton button {
    background: #005461 !important;
    color: #FFFFFF !important;
    border-color: #005461 !important;
}
[data-theme="esanum"] .stDownloadButton button:hover {
    background: #003E48 !important;
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
    font-feature-settings: 'ss01', 'cv01';
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

/* ===== SUBTLE AMBIENT GRADIENT ===== */
.stApp::before {
    content: '';
    position: fixed;
    inset: 0;
    z-index: -1;
    background:
        radial-gradient(ellipse 80% 50% at 15% 5%, rgba(132,204,22,0.025), transparent 50%),
        radial-gradient(ellipse 60% 40% at 85% 85%, rgba(132,204,22,0.015), transparent 50%),
        var(--c-bg);
    pointer-events: none;
}
/* Force Inter on ALL button elements — catch-all for Streamlit overrides */
.stApp button,
[data-testid="stAppViewContainer"] button,
[data-testid="stSidebar"] button,
button[data-testid*="stBaseButton"],
[data-baseweb="tab"] button {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

/* ===== SIDEBAR ===== */
section[data-testid="stSidebar"] {
    background: #0e0e22 !important;
    border-right: 1px solid var(--c-border);
}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] button,
section[data-testid="stSidebar"] a,
section[data-testid="stSidebar"] input {
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
    transition: background 0.2s ease;
    cursor: default;
}
.sidebar-kpi-item:last-child { border-right: none; }
.sidebar-kpi-item:hover { background: rgba(255,255,255,0.04); }
.sidebar-kpi-item:hover .sidebar-kpi-num { color: var(--c-accent) !important; }
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
    background: var(--c-surface, rgba(255,255,255,0.03)) !important;
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
    color: #FFFFFF !important;
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
    /* clean surface — no noise texture */
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--c-border);
    border-radius: var(--radius);
    padding: 16px 18px;
    position: relative;
    overflow: hidden;
    transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1),
                box-shadow 0.3s ease,
                border-color 0.2s ease;
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
    transform-origin: bottom;
    animation: sparkline-grow 0.6s cubic-bezier(0.22, 1, 0.36, 1) forwards;
    opacity: 0;
    transform: scaleY(0);
}
@keyframes sparkline-grow {
    to { opacity: 1; transform: scaleY(1); }
}

/* ===== ARTICLE CARD v3 — Dark glassmorphism ===== */
/* NOTE: backdrop-filter removed from cards for scroll performance.
   Cards use solid surface color instead — visual difference is negligible
   on dark backgrounds but saves ~30 composite layers during scroll. */
.a-card {
    background: var(--c-surface-solid, #14142a);
    /* clean surface — no noise texture */
    border: 1px solid var(--c-border);
    border-radius: var(--radius);
    padding: 20px 24px;
    margin-bottom: 14px;
    transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1),
                box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                border-color 0.2s ease,
                background 0.2s ease;
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
/* Subtle accent glow on hover — monochrome, premium */
.a-card:hover {
    border-color: rgba(132,204,22,0.15);
    box-shadow: 0 4px 24px rgba(0,0,0,0.3), 0 0 0 1px rgba(132,204,22,0.08);
    background: rgba(255,255,255,0.045);
    transform: translateY(-1px);
}
.a-card:hover::before {
    opacity: 1;
}

/* ===== Collection status badges — top-right corner of card ===== */
.coll-badge {
    position: absolute;
    top: 10px;
    right: 12px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 10px 3px 8px;
    border-radius: 20px;
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    z-index: 2;
    pointer-events: none;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    transition: opacity 0.2s ease;
}
/* In Arbeit — warm amber with breathing pulse */
.coll-badge-wip {
    background: rgba(245,158,11,0.12);
    color: #f59e0b;
    border: 1px solid rgba(245,158,11,0.2);
    animation: coll-pulse 2.5s ease-in-out infinite;
}
.coll-badge-wip::before {
    content: '';
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #f59e0b;
    animation: coll-dot-pulse 2.5s ease-in-out infinite;
}
/* Veröffentlicht — calm green */
.coll-badge-pub {
    background: rgba(74,222,128,0.10);
    color: #4ade80;
    border: 1px solid rgba(74,222,128,0.18);
}
.coll-badge-pub::before {
    content: '\\2713';
    font-size: 0.7rem;
    line-height: 1;
}
@keyframes coll-pulse {
    0%, 100% { opacity: 0.85; }
    50% { opacity: 1; }
}
@keyframes coll-dot-pulse {
    0%, 100% { transform: scale(1); opacity: 0.7; }
    50% { transform: scale(1.4); opacity: 1; }
}
/* esanum light mode overrides */
[data-theme="esanum"] .coll-badge-wip {
    background: rgba(245,158,11,0.08);
    color: #b45309;
    border-color: rgba(245,158,11,0.25);
}
[data-theme="esanum"] .coll-badge-wip::before {
    background: #f59e0b;
}
[data-theme="esanum"] .coll-badge-pub {
    background: rgba(118,165,48,0.08);
    color: #49661E;
    border-color: rgba(118,165,48,0.2);
}
/* Collection name tooltip on hover */
.coll-badge[title] {
    pointer-events: auto;
    cursor: help;
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
    background: transparent !important;
    border: none !important;
    outline: none !important;
    box-shadow: none !important;
}
.a-score-ring svg {
    width: 48px;
    height: 48px;
    transform: rotate(-90deg);
    background: transparent !important;
    overflow: visible;
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
.ring-high {
    stroke: var(--c-success);
    filter: drop-shadow(0 0 6px rgba(74,222,128,0.4));
    animation: ring-draw 1.2s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}
.ring-mid {
    stroke: var(--c-warn);
    filter: drop-shadow(0 0 6px rgba(251,191,36,0.3));
    animation: ring-draw 1.2s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}
.ring-low  { stroke: var(--c-ring-low); }

@keyframes ring-draw {
    from { stroke-dashoffset: 125.66; }
}
/* Hover amplifies the glow — single drop-shadow only */
.a-card:hover .ring-high { filter: drop-shadow(0 0 14px rgba(74,222,128,0.6)); }
.a-card:hover .ring-mid  { filter: drop-shadow(0 0 12px rgba(251,191,36,0.5)); }
[data-theme="esanum"] .a-card:hover .ring-high { filter: drop-shadow(0 0 16px rgba(34,197,94,0.7)) !important; }
[data-theme="esanum"] .a-card:hover .ring-mid  { filter: drop-shadow(0 0 14px rgba(234,179,8,0.7)) !important; }

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
    font-size: 1.6rem;
    font-weight: 800;
    letter-spacing: -0.04em;
    margin-bottom: 2px;
    background: linear-gradient(135deg, var(--c-text) 0%, var(--c-accent) 80%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    text-shadow: 0 0 40px rgba(132,204,22,0.15);
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

/* ===== BUTTONS — Glass Morphism ===== */
/* Hidden trigger buttons (zero-width-space text) — must stay invisible */
.st-key-export_promptlab,
.st-key-deselect_all,
.st-key-close_export {
    position: absolute !important;
    width: 0 !important;
    height: 0 !important;
    overflow: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
/* Base glass style for ALL buttons */
.stButton button[data-testid],
.stDownloadButton button[data-testid],
.stFormSubmitButton button[data-testid] {
    position: relative !important;
    overflow: hidden !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    border-radius: 9999px !important;
    font-weight: 500 !important;
    font-size: 0.82rem !important;
    padding: 6px 14px !important;
    white-space: nowrap !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    background: linear-gradient(
        135deg,
        rgba(255,255,255,0.07) 0%,
        rgba(255,255,255,0.02) 50%,
        rgba(255,255,255,0.05) 100%
    ) !important;
    backdrop-filter: blur(6px) !important;
    -webkit-backdrop-filter: blur(6px) !important;
    color: var(--c-text) !important;
    min-height: 34px !important;
    cursor: pointer !important;
    transition:
        transform 0.25s cubic-bezier(0.4, 0, 0.2, 1),
        box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1),
        border-color 0.3s ease,
        background 0.3s ease !important;
    box-shadow:
        0 2px 8px rgba(0,0,0,0.25),
        inset 0 1px 0 rgba(255,255,255,0.06) !important;
}
/* Inner highlight line */
.stButton button[data-testid]::before,
.stDownloadButton button[data-testid]::before,
.stFormSubmitButton button[data-testid]::before {
    content: '' !important;
    position: absolute !important;
    top: 0 !important;
    left: 12% !important;
    right: 12% !important;
    height: 1px !important;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.18), transparent) !important;
    pointer-events: none !important;
}
/* Glow layer (hidden, appears on hover) */
.stButton button[data-testid]::after,
.stDownloadButton button[data-testid]::after,
.stFormSubmitButton button[data-testid]::after {
    content: '' !important;
    position: absolute !important;
    inset: -1px !important;
    border-radius: 9999px !important;
    background: radial-gradient(ellipse at 50% 50%, rgba(132,204,22,0.12) 0%, transparent 70%) !important;
    opacity: 0 !important;
    pointer-events: none !important;
    transition: opacity 0.35s ease !important;
}
/* Hover — lift + glow (dark theme only) */
:root:not([data-theme="esanum"]) .stButton button[data-testid]:hover,
:root:not([data-theme="esanum"]) .stDownloadButton button[data-testid]:hover,
:root:not([data-theme="esanum"]) .stFormSubmitButton button[data-testid]:hover {
    transform: translateY(-1px) !important;
    border-color: rgba(132,204,22,0.30) !important;
    background: linear-gradient(
        135deg,
        rgba(132,204,22,0.08) 0%,
        rgba(255,255,255,0.03) 50%,
        rgba(132,204,22,0.06) 100%
    ) !important;
    box-shadow:
        0 0 20px rgba(132,204,22,0.14),
        0 4px 16px rgba(0,0,0,0.25),
        inset 0 1px 0 rgba(255,255,255,0.10) !important;
}
:root:not([data-theme="esanum"]) .stButton button[data-testid]:hover::after,
:root:not([data-theme="esanum"]) .stDownloadButton button[data-testid]:hover::after,
:root:not([data-theme="esanum"]) .stFormSubmitButton button[data-testid]:hover::after {
    opacity: 1 !important;
}
/* ============================================================
   esanum Light Theme: COMPLETE button reset
   Must override ALL dark-theme glass/glow styles.
   Using high-specificity selectors to win over later rules.
   ============================================================ */
/* Base reset for ALL buttons in esanum */
html[data-theme="esanum"] .stButton button,
html[data-theme="esanum"] .stButton button[data-testid],
html[data-theme="esanum"] .stButton button[data-testid="stBaseButton-secondary"],
html[data-theme="esanum"] .stDownloadButton button,
html[data-theme="esanum"] .stDownloadButton button[data-testid],
html[data-theme="esanum"] .stFormSubmitButton button,
html[data-theme="esanum"] .stFormSubmitButton button[data-testid] {
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
    background: #FFFFFF !important;
    border: 1px solid #ECECEC !important;
    color: #444444 !important;
    box-shadow: none !important;
    border-radius: 8px !important;
    font-family: 'Open Sans', 'Inter', -apple-system, sans-serif !important;
    font-weight: 600 !important;
    transition: background 100ms ease, border-color 100ms ease, color 100ms ease, box-shadow 100ms ease !important;
}
/* Kill ALL pseudo-elements (glow, highlight line) */
html[data-theme="esanum"] .stButton button::before,
html[data-theme="esanum"] .stButton button::after,
html[data-theme="esanum"] .stDownloadButton button::before,
html[data-theme="esanum"] .stDownloadButton button::after,
html[data-theme="esanum"] .stFormSubmitButton button::before,
html[data-theme="esanum"] .stFormSubmitButton button::after {
    display: none !important;
    content: none !important;
}
/* Primary buttons — solid teal (default state = high visibility CTA) */
html[data-theme="esanum"] .stButton button[data-testid="stBaseButton-primary"],
html[data-theme="esanum"] .stButton button[kind="primary"],
html[data-theme="esanum"] button[data-testid="stBaseButton-primary"],
html[data-theme="esanum"] .stDownloadButton button[data-testid="stBaseButton-primary"],
html[data-theme="esanum"] .stDownloadButton button[kind="primary"] {
    background: #005461 !important;
    color: #FFFFFF !important;
    border: 2px solid #005461 !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    box-shadow: 0px 2px 8px -2px rgba(0,84,97,0.18) !important;
    transition: background 100ms ease, color 100ms ease, box-shadow 100ms ease !important;
}
html[data-theme="esanum"] .stButton button[data-testid="stBaseButton-primary"] p,
html[data-theme="esanum"] .stButton button[data-testid="stBaseButton-primary"] span,
html[data-theme="esanum"] .stDownloadButton button[data-testid="stBaseButton-primary"] p,
html[data-theme="esanum"] .stDownloadButton button[data-testid="stBaseButton-primary"] span {
    background: transparent !important;
    color: #FFFFFF !important;
}
/* Hover — secondary only (exclude primary to avoid conflict) */
html[data-theme="esanum"] .stButton button[data-testid="stBaseButton-secondary"]:hover,
html[data-theme="esanum"] .stButton button:not([data-testid="stBaseButton-primary"]):hover,
html[data-theme="esanum"] .stDownloadButton button:not([data-testid="stBaseButton-primary"]):hover,
html[data-theme="esanum"] .stFormSubmitButton button:hover {
    transform: none !important;
    background: #F0F7F8 !important;
    border-color: #005461 !important;
    color: #005461 !important;
    box-shadow: 0px 2px 8px -2px rgba(0,84,97,0.12) !important;
}
/* Hover — primary: outline teal (lightens on hover = interactive feedback) */
html[data-theme="esanum"] .stButton button[data-testid="stBaseButton-primary"]:hover,
html[data-theme="esanum"] button[data-testid="stBaseButton-primary"]:hover,
html[data-theme="esanum"] .stDownloadButton button[data-testid="stBaseButton-primary"]:hover {
    background: #FFFFFF !important;
    color: #005461 !important;
    -webkit-text-fill-color: #005461 !important;
    border-color: #005461 !important;
    box-shadow: 0px 4px 12px -2px rgba(0,84,97,0.15) !important;
    transition: background 0.1s ease, color 0.1s ease, box-shadow 0.1s ease !important;
}
html[data-theme="esanum"] .stButton button[data-testid="stBaseButton-primary"]:hover p,
html[data-theme="esanum"] .stButton button[data-testid="stBaseButton-primary"]:hover span,
html[data-theme="esanum"] button[data-testid="stBaseButton-primary"]:hover p,
html[data-theme="esanum"] button[data-testid="stBaseButton-primary"]:hover span {
    color: #005461 !important;
    -webkit-text-fill-color: #005461 !important;
}
/* Active / pressed */
html[data-theme="esanum"] .stButton button:active,
html[data-theme="esanum"] .stDownloadButton button:active,
html[data-theme="esanum"] .stFormSubmitButton button:active {
    transform: none !important;
    box-shadow: inset 0 1px 3px rgba(0,0,0,0.1) !important;
}
/* Active / pressed */
.stButton button[data-testid]:active,
.stDownloadButton button[data-testid]:active,
.stFormSubmitButton button[data-testid]:active {
    transform: translateY(0px) scale(0.97) !important;
    box-shadow:
        0 0 10px rgba(132,204,22,0.08),
        0 1px 4px rgba(0,0,0,0.25),
        inset 0 2px 4px rgba(0,0,0,0.12) !important;
}

/* ===== PILLS (st.pills → renders as stButtonGroup) — MUST come after button overrides ===== */
html[data-theme="esanum"] [data-testid="stButtonGroup"] button,
html[data-theme="esanum"] [data-testid="stButtonGroup"] button[data-testid],
html[data-theme="esanum"] [data-testid="stButtonGroup"] .stButton button {
    background: rgba(0,84,97,0.03) !important;
    border: 1px solid #ECECEC !important;
    color: #444444 !important;
    border-radius: 20px !important;
    font-weight: 500 !important;
    font-size: 0.78rem !important;
    padding: 4px 14px !important;
    min-height: unset !important;
    backdrop-filter: none !important;
    box-shadow: none !important;
    transform: none !important;
}
html[data-theme="esanum"] [data-testid="stButtonGroup"] button[aria-checked="true"] {
    background: #005461 !important;
    border-color: #005461 !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
}
html[data-theme="esanum"] [data-testid="stButtonGroup"] button:hover {
    background: #E5EEEF !important;
    border-color: #005461 !important;
    color: #005461 !important;
}

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
/* Download buttons inherit glass style from base — no separate override needed */
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
/* Score Ring — glow on hover (no background box!) */
.a-score-ring:hover {
    background: transparent !important;
    outline: none !important;
    border: none !important;
    box-shadow: none !important;
}
.a-score-ring, .a-score-ring * {
    outline: none !important;
}
/* Esanum: Score ring hover */
[data-theme="esanum"] .a-score-ring:hover .ring-fill {
    filter: drop-shadow(0 0 8px rgba(0,84,97,0.4)) brightness(1.1);
}
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
    top: calc(100% + 8px);
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
/* esanum theme: lighter tooltip */
html[data-theme="esanum"] .score-pill[data-tip]:hover::after {
    background: #FFFFFF;
    color: #444444;
    border: 1px solid #ECECEC;
    box-shadow: 0px 4px 12px rgba(16,24,40,0.12);
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
    align-items: flex-start;
    gap: 10px;
    position: relative;
}
.radar-overview::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--c-accent), #22d3ee, transparent);
    opacity: 0.5;
    border-radius: var(--radius) var(--radius) 0 0;
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
.trend-hero:hover .trend-hero-accent {
    height: 3px;
    box-shadow: 0 2px 20px rgba(132,204,22,0.35);
    filter: brightness(1.3);
}
.trend-hero-accent {
    height: 3px;
    background: linear-gradient(90deg, var(--accent-from, #84cc16), var(--accent-to, #22d3ee));
    box-shadow: 0 2px 12px rgba(132,204,22,0.15);
    transition: var(--transition);
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

/* Nested expanders inside Gemerkt — compact, single-line labels */
[data-testid="stExpander"] [data-testid="stExpander"] {
    margin-bottom: 2px !important;
}
[data-testid="stExpander"] [data-testid="stExpander"] summary {
    font-size: 0.72rem !important;
    padding: 4px 8px !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
[data-testid="stExpander"] [data-testid="stExpander"] summary p {
    font-size: 0.72rem !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
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
.kongress-hero:hover .kongress-hero-accent {
    box-shadow: 0 2px 20px rgba(132,204,22,0.35);
    filter: brightness(1.3);
}
.kongress-hero-accent {
    height: 3px;
    box-shadow: 0 2px 12px rgba(132,204,22,0.15);
    transition: var(--transition);
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
    cursor: pointer;
}
.kongress-badge-articles:hover {
    background: rgba(59,130,246,0.25);
}

/* Favoriten-Stern */
.kongress-fav-btn {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 1.2rem;
    padding: 2px 4px;
    transition: var(--transition);
    filter: grayscale(100%);
    opacity: 0.4;
}
.kongress-fav-btn:hover {
    filter: grayscale(0%);
    opacity: 1;
    transform: scale(1.15);
}
.kongress-fav-btn.active {
    filter: grayscale(0%);
    opacity: 1;
}

/* Ueberlappungs-Warnung */
.kongress-overlap-warning {
    background: rgba(251,146,60,0.08);
    border: 1px solid rgba(251,146,60,0.2);
    border-radius: var(--radius);
    padding: 12px 16px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 10px;
    transition: var(--transition);
    cursor: default;
    position: relative;
    overflow: hidden;
}
.kongress-overlap-warning::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    background: linear-gradient(180deg, #fb923c, #f87171);
    opacity: 0;
    transition: opacity 0.3s ease;
}
.kongress-overlap-warning:hover {
    border-color: rgba(251,146,60,0.45);
    background: rgba(251,146,60,0.12);
    transform: translateX(4px);
    box-shadow: -3px 0 12px rgba(251,146,60,0.1);
}
.kongress-overlap-warning:hover::before {
    opacity: 1;
}

/* Monatskalender-Grid */
.kongress-cal-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 2px;
    margin-bottom: 16px;
}
.kongress-cal-header {
    text-align: center;
    font-size: 0.62rem;
    font-weight: 700;
    color: var(--c-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 4px 0;
}
.kongress-cal-day {
    min-height: 48px;
    padding: 3px 4px;
    background: rgba(255,255,255,0.02);
    border: 1px solid var(--c-border);
    border-radius: 6px;
    font-size: 0.62rem;
    transition: var(--transition);
    position: relative;
}
.kongress-cal-day:hover {
    background: rgba(255,255,255,0.06);
    border-color: var(--c-border-hover);
}
.kongress-cal-day.today {
    border-color: rgba(132,204,22,0.4);
    background: rgba(132,204,22,0.06);
}
.kongress-cal-day-num {
    font-weight: 600;
    color: var(--c-text-muted);
    font-size: 0.6rem;
    margin-bottom: 2px;
}
.kongress-cal-bar {
    display: block;
    height: 4px;
    border-radius: 2px;
    margin: 1px 0;
    opacity: 0.8;
}
.kongress-cal-bar:hover {
    opacity: 1;
    transform: scaleY(1.5);
}
.kongress-cal-day.empty {
    background: transparent;
    border-color: transparent;
}

/* Meine Kongresse Section */
.kongress-favs-section {
    background: rgba(132,204,22,0.04);
    border: 1px solid rgba(132,204,22,0.15);
    border-radius: var(--radius);
    padding: 16px 20px;
    margin-bottom: 20px;
}

/* Timeline-Monatszellen */
.kongress-tl-cell {
    text-align: center;
    padding: 8px 4px;
    border-radius: 8px;
    min-width: 0;
    transition: var(--transition);
    cursor: default;
    position: relative;
    overflow: hidden;
}
.kongress-tl-cell::before {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--c-accent), #22d3ee);
    opacity: 0;
    transition: opacity 0.3s ease;
}
.kongress-tl-cell:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
    background: rgba(255,255,255,0.06) !important;
    border-color: var(--c-border-hover) !important;
}
.kongress-tl-cell:hover::before {
    opacity: 1;
}
.kongress-tl-cell:hover .kongress-tl-count {
    transform: scale(1.12);
    color: var(--c-accent);
}
.kongress-tl-count {
    font-size: 1.1rem;
    font-weight: 800;
    color: var(--c-text);
    margin: 2px 0;
    transition: var(--transition);
}

/* Favoriten-Karte in Meine Kongresse */
.kongress-fav-card {
    background: var(--c-surface);
    border: 1px solid var(--c-border);
    border-radius: var(--radius);
    padding: 12px 14px;
    transition: var(--transition);
    cursor: default;
    position: relative;
    overflow: hidden;
}
.kongress-fav-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--c-accent), #22d3ee);
    opacity: 0;
    transition: opacity 0.3s ease;
}
.kongress-fav-card:hover {
    border-color: var(--c-border-hover);
    background: rgba(255,255,255,0.05);
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}
.kongress-fav-card:hover::before {
    opacity: 1;
}
.kongress-fav-card:hover .kongress-fav-days {
    transform: scale(1.08);
}
.kongress-fav-days {
    transition: var(--transition);
}

/* Deadline-Alert-Zeile */
.kongress-deadline-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    border: 1px solid var(--c-border);
    border-radius: 10px;
    margin-bottom: 6px;
    transition: var(--transition);
    cursor: default;
    position: relative;
    overflow: hidden;
}
.kongress-deadline-item::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    background: linear-gradient(180deg, #f87171, #fbbf24);
    opacity: 0;
    transition: opacity 0.3s ease;
}
.kongress-deadline-item:hover {
    transform: translateX(4px);
    border-color: var(--c-border-hover);
    box-shadow: var(--shadow-sm);
}
.kongress-deadline-item:hover::before {
    opacity: 1;
}
.kongress-deadline-item:hover .kongress-deadline-num {
    transform: scale(1.15);
}
.kongress-deadline-num {
    font-size: 1.3rem;
    font-weight: 800;
    min-width: 40px;
    text-align: center;
    transition: var(--transition);
}

/* Spec-Pill auf Kongress-Cards */
.kongress-spec-pill {
    padding: 2px 10px;
    border-radius: 10px;
    font-size: 0.62rem;
    font-weight: 600;
    white-space: nowrap;
    transition: var(--transition);
}
.kongress-spec-pill:hover {
    filter: brightness(1.25);
    transform: translateY(-1px);
    box-shadow: 0 2px 8px currentColor;
}

/* Hero countdown number pulse on hover */
.kongress-hero:hover .kongress-hero-countdown {
    transform: scale(1.08);
    filter: drop-shadow(0 0 12px currentColor);
}
.kongress-hero-countdown {
    transition: var(--transition);
}

/* Calendar day enhanced hover */
.kongress-cal-day:hover .kongress-cal-day-num {
    color: var(--c-accent);
    font-weight: 800;
}
.kongress-cal-day:hover .kongress-cal-bar {
    opacity: 1;
    transform: scaleY(1.5);
    filter: brightness(1.2);
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
    transition: var(--transition);
}
[data-testid="stExpander"] summary:hover {
    color: var(--c-accent) !important;
    border-color: var(--c-border-hover) !important;
}
/* Expander container gradient on open */
[data-testid="stExpander"][open] {
    border-image: linear-gradient(180deg, rgba(132,204,22,0.25), transparent 40%) 1 !important;
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
    background: var(--c-surface, rgba(255,255,255,0.03)) !important;
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
/* Popover in esanum — portals render at body level outside stApp container */
html[data-theme="esanum"] [data-testid="stPopoverBody"],
body[data-theme="esanum"] [data-testid="stPopoverBody"],
[data-theme="esanum"] [data-testid="stPopoverBody"] {
    background: #FFFFFF !important;
    border: 1px solid #ECECEC !important;
    color: #333333 !important;
}
html[data-theme="esanum"] [data-testid="stPopoverBody"] span,
html[data-theme="esanum"] [data-testid="stPopoverBody"] p,
html[data-theme="esanum"] [data-testid="stPopoverBody"] div,
html[data-theme="esanum"] [data-testid="stPopoverBody"] label,
html[data-theme="esanum"] [data-testid="stPopoverBody"] a {
    color: #333333 !important;
}
/* Popover trigger button — nuclear override */
[data-theme="esanum"] [data-testid="stPopover"] > button,
[data-theme="esanum"] button[kind="secondary"] {
    background: #FFFFFF !important;
    color: #005461 !important;
    border: 1px solid #ECECEC !important;
}
[data-theme="esanum"] [data-testid="stPopover"] > button:hover {
    background: #E5EEEF !important;
    border-color: #005461 !important;
}
/* Popover backdrop/container — nuclear override for ALL popover contexts */
html[data-theme="esanum"] [data-baseweb="popover"],
[data-theme="esanum"] [data-baseweb="popover"],
[data-theme="esanum"] [data-testid="stPopover"],
[data-theme="esanum"] [data-testid="stPopover"] > div,
[data-theme="esanum"] [data-testid="stPopoverBody"],
[data-theme="esanum"] [data-testid="stPopoverBody"] > div {
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    color: #333333 !important;
}
[data-theme="esanum"] [data-baseweb="popover"] span,
[data-theme="esanum"] [data-baseweb="popover"] p,
[data-theme="esanum"] [data-baseweb="popover"] div,
[data-theme="esanum"] [data-baseweb="popover"] li,
[data-theme="esanum"] [data-baseweb="popover"] a {
    color: #333333 !important;
}
[data-theme="esanum"] [data-testid="stPopoverBody"] code {
    background: #F5F5F5 !important;
    color: #005461 !important;
}
/* Calendar popup (date_input) — force light theme everywhere */
html[data-theme="esanum"] [data-baseweb="calendar"],
html[data-theme="esanum"] [data-baseweb="datepicker"],
html[data-theme="esanum"] [data-baseweb="calendar"] *,
html[data-theme="esanum"] [data-baseweb="datepicker"] * {
    background-color: #FFFFFF !important;
    color: #444444 !important;
}
html[data-theme="esanum"] [data-baseweb="calendar"] [role="gridcell"]:hover,
html[data-theme="esanum"] [data-baseweb="calendar"] [role="gridcell"]:hover div {
    background-color: #E5EEEF !important;
    color: #005461 !important;
}
html[data-theme="esanum"] [data-baseweb="calendar"] [aria-selected="true"],
html[data-theme="esanum"] [data-baseweb="calendar"] [aria-selected="true"] div {
    background-color: #005461 !important;
    color: #FFFFFF !important;
}
html[data-theme="esanum"] [data-baseweb="calendar"] button {
    background-color: transparent !important;
    color: #444444 !important;
}
html[data-theme="esanum"] [data-baseweb="calendar"] button:hover {
    background-color: #E5EEEF !important;
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
/* Primary button — glass with lime accent (dark theme only) */
:root:not([data-theme="esanum"]) .stButton button[data-testid="stBaseButton-primary"] {
    background: linear-gradient(
        135deg,
        rgba(132,204,22,0.25) 0%,
        rgba(132,204,22,0.12) 50%,
        rgba(132,204,22,0.20) 100%
    ) !important;
    border: 1px solid rgba(132,204,22,0.30) !important;
    color: #d9f99d !important;
    font-weight: 600 !important;
    box-shadow:
        0 0 12px rgba(132,204,22,0.10),
        0 2px 8px rgba(0,0,0,0.25),
        inset 0 1px 0 rgba(255,255,255,0.10) !important;
    transition: transform 0.15s cubic-bezier(0.34, 1.56, 0.64, 1),
                box-shadow 0.25s ease,
                background 0.2s ease,
                border-color 0.2s ease !important;
}
:root:not([data-theme="esanum"]) .stButton button[data-testid="stBaseButton-primary"]::after {
    background: radial-gradient(ellipse at 50% 50%, rgba(132,204,22,0.20) 0%, transparent 70%) !important;
}
:root:not([data-theme="esanum"]) .stButton button[data-testid="stBaseButton-primary"]:hover {
    background: linear-gradient(
        135deg,
        rgba(132,204,22,0.35) 0%,
        rgba(132,204,22,0.18) 50%,
        rgba(132,204,22,0.30) 100%
    ) !important;
    border-color: rgba(132,204,22,0.50) !important;
    color: #ecfccb !important;
    transform: scale(1.02);
    box-shadow:
        0 0 28px rgba(132,204,22,0.22),
        0 4px 16px rgba(0,0,0,0.25),
        inset 0 1px 0 rgba(255,255,255,0.12) !important;
}
/* Input focus glow ring */
.stTextInput input:focus,
.stTextArea textarea:focus,
.stSelectbox [data-baseweb="select"]:focus-within {
    box-shadow: 0 0 0 3px rgba(132,204,22,0.15) !important;
    border-color: rgba(132,204,22,0.4) !important;
    transition: box-shadow 0.25s ease, border-color 0.2s ease !important;
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

/* ===== SAISONAL — Motion-Enhanced ===== */

/* --- Keyframes --- */
@keyframes saisonal-pulse {
    0%, 100% { transform: scale(1); opacity: 0.85; }
    50% { transform: scale(1.04); opacity: 1; }
}
@keyframes saisonal-ring-draw {
    from { stroke-dashoffset: 283; }
}
@keyframes saisonal-count-up {
    from { opacity: 0; transform: translateY(10px) scale(0.9); }
    to { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes saisonal-pill-cascade {
    from { opacity: 0; transform: translateX(-10px); }
    to { opacity: 1; transform: translateX(0); }
}
@keyframes saisonal-bar-reveal {
    from { transform: scaleX(0); }
    to { transform: scaleX(1); }
}
@keyframes saisonal-live-pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(248,113,113,0.4); }
    50% { box-shadow: 0 0 0 4px rgba(248,113,113,0); }
}
@keyframes saisonal-live-pulse-amber {
    0%, 100% { box-shadow: 0 0 0 0 rgba(251,191,36,0.4); }
    50% { box-shadow: 0 0 0 4px rgba(251,191,36,0); }
}
@keyframes saisonal-progress-fill {
    from { width: 0; }
}
@keyframes saisonal-flip-in {
    0% { transform: rotateX(90deg); opacity: 0; }
    100% { transform: rotateX(0deg); opacity: 1; }
}
@keyframes saisonal-glow-slide {
    0% { left: -20%; opacity: 0; }
    50% { opacity: 0.6; }
    100% { left: 120%; opacity: 0; }
}

/* --- EFFEKT 1: Ambient Season Particles --- */
@keyframes particle-float {
    0% { transform: translateY(0) translateX(0) scale(1); opacity: 0; }
    10% { opacity: 0.6; }
    90% { opacity: 0.4; }
    100% { transform: translateY(-120px) translateX(40px) scale(0.3); opacity: 0; }
}
@keyframes particle-float-2 {
    0% { transform: translateY(0) translateX(0) rotate(0deg); opacity: 0; }
    15% { opacity: 0.5; }
    85% { opacity: 0.3; }
    100% { transform: translateY(-100px) translateX(-30px) rotate(180deg); opacity: 0; }
}
@keyframes particle-float-3 {
    0% { transform: translateY(0) translateX(0) scale(0.8); opacity: 0; }
    20% { opacity: 0.4; }
    80% { opacity: 0.2; }
    100% { transform: translateY(-90px) translateX(60px) scale(0.5); opacity: 0; }
}
.saisonal-particles {
    position: absolute;
    inset: 0;
    overflow: hidden;
    pointer-events: none;
    z-index: 0;
}
.saisonal-particles span {
    position: absolute;
    bottom: 0;
    display: block;
    border-radius: 50%;
}
.saisonal-particles span:nth-child(1) {
    width: 4px; height: 4px; left: 10%; background: var(--s-grad-from, #84cc16);
    animation: particle-float 8s ease-in-out infinite;
}
.saisonal-particles span:nth-child(2) {
    width: 3px; height: 3px; left: 30%; background: var(--s-grad-to, #22d3ee);
    animation: particle-float-2 10s ease-in-out 1s infinite;
}
.saisonal-particles span:nth-child(3) {
    width: 5px; height: 5px; left: 55%; background: var(--s-grad-from, #84cc16);
    animation: particle-float-3 7s ease-in-out 2.5s infinite;
    opacity: 0.5;
}
.saisonal-particles span:nth-child(4) {
    width: 3px; height: 3px; left: 75%; background: rgba(255,255,255,0.3);
    animation: particle-float 12s ease-in-out 0.5s infinite;
}
.saisonal-particles span:nth-child(5) {
    width: 4px; height: 4px; left: 90%; background: var(--s-grad-to, #22d3ee);
    animation: particle-float-2 9s ease-in-out 3s infinite;
    opacity: 0.4;
}
.saisonal-particles span:nth-child(6) {
    width: 2px; height: 2px; left: 45%; background: rgba(255,255,255,0.25);
    animation: particle-float-3 11s ease-in-out 1.5s infinite;
}

/* --- EFFEKT 3: Flip Countdown for Awareness --- */
@keyframes flip-tick {
    0% { transform: perspective(200px) rotateX(0deg); }
    50% { transform: perspective(200px) rotateX(-10deg); }
    100% { transform: perspective(200px) rotateX(0deg); }
}
.saisonal-flip-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 52px;
    padding: 6px 10px;
    border-radius: 8px;
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 0.82rem;
    font-weight: 800;
    letter-spacing: 0.03em;
    animation: flip-tick 2s ease-in-out infinite;
    position: relative;
    overflow: hidden;
}
.saisonal-flip-badge::after {
    content: '';
    position: absolute;
    top: 49%; left: 0; right: 0;
    height: 1px;
    background: rgba(0,0,0,0.15);
}
.saisonal-flip-badge.urgent {
    background: rgba(248,113,113,0.15);
    color: #f87171;
    box-shadow: 0 0 12px rgba(248,113,113,0.15);
}
.saisonal-flip-badge.soon {
    background: rgba(251,191,36,0.15);
    color: #fbbf24;
    box-shadow: 0 0 8px rgba(251,191,36,0.1);
}
.saisonal-flip-badge.normal {
    background: rgba(255,255,255,0.06);
    color: var(--c-text-secondary);
}

/* --- EFFEKT 4: Cluster-Card Heartbeat Glow at Peak --- */
@keyframes heartbeat-glow {
    0%, 100% { box-shadow: inset 3px 0 0 var(--cluster-color), 0 0 0 0 rgba(var(--cluster-color-rgb), 0); }
    50% { box-shadow: inset 3px 0 0 var(--cluster-color), 0 0 16px 2px rgba(var(--cluster-color-rgb), 0.12); }
}
@keyframes heartbeat-bar {
    0%, 100% { width: 3px; opacity: 1; }
    50% { width: 5px; opacity: 0.8; }
}
/* .saisonal-cluster-card — consolidated below (search "Cluster Cards (enhanced)") */

/* --- EFFEKT 5: Scroll-Triggered Section Reveals --- */
@keyframes reveal-up {
    from { opacity: 0; transform: translateY(24px); }
    to { opacity: 1; transform: translateY(0); }
}
@keyframes reveal-left {
    from { opacity: 0; transform: translateX(-16px); }
    to { opacity: 1; transform: translateX(0); }
}
.saisonal-section-reveal {
    opacity: 0;
    animation: reveal-up 0.6s cubic-bezier(0.22,1,0.36,1) forwards;
}
.saisonal-section-reveal:nth-child(1) { animation-delay: 0s; }
.saisonal-section-reveal:nth-child(2) { animation-delay: 0.15s; }
.saisonal-section-reveal:nth-child(3) { animation-delay: 0.3s; }
.saisonal-section-reveal:nth-child(4) { animation-delay: 0.45s; }
.saisonal-section-reveal:nth-child(5) { animation-delay: 0.6s; }

@media (prefers-reduced-motion: reduce) {
    .saisonal-pulse-ring, .saisonal-hero-stat-value,
    .saisonal-topic-pill, .saisonal-bar-cell,
    .saisonal-live-dot, .saisonal-progress-fill,
    .saisonal-countdown, .saisonal-particles span,
    .saisonal-flip-badge, .saisonal-cluster-card.is-peak .accent-bar,
    .saisonal-section-reveal {
        animation: none !important;
        opacity: 1 !important;
        transform: none !important;
    }
}

/* --- Hero Section --- */
.saisonal-hero {
    position: relative;
    background: var(--c-surface);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--c-border);
    border-radius: var(--radius);
    padding: 24px 28px;
    overflow: hidden;
    opacity: 0;
    animation: dash-enter 0.5s cubic-bezier(0.22,1,0.36,1) 0.1s forwards;
}
.saisonal-hero::before {
    content: '';
    position: absolute;
    top: 0; left: 1px; right: 1px;
    height: 3px;
    background: linear-gradient(90deg, var(--s-grad-from, #84cc16), var(--s-grad-to, #22d3ee));
    border-radius: var(--radius) var(--radius) 0 0;
    z-index: 1;
}
.saisonal-hero::after {
    content: '';
    position: absolute;
    top: 0; left: -20%;
    width: 40%; height: 3px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.5), transparent);
    animation: saisonal-glow-slide 3s ease-in-out infinite;
    z-index: 2;
}

/* SVG Pulse Ring — premium arc with gradient + glow */
.saisonal-pulse-ring {
    animation: saisonal-pulse 3s ease-in-out infinite;
}
.saisonal-pulse-ring circle.track {
    fill: none;
    stroke: rgba(255,255,255,0.05);
    stroke-width: 5;
}
.saisonal-pulse-ring circle.value {
    fill: none;
    stroke-width: 5;
    stroke-linecap: round;
    /* transform/dashoffset set inline for dynamic values */
}
.saisonal-pulse-ring .ring-label {
    font-size: 13px;
    font-weight: 800;
    fill: var(--c-text);
    text-anchor: middle;
    dominant-baseline: central;
    letter-spacing: -0.02em;
}
.saisonal-pulse-ring .ring-sub {
    font-size: 6.5px;
    font-weight: 700;
    fill: var(--c-text-muted);
    text-anchor: middle;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}
@media (prefers-reduced-motion: reduce) {
    .saisonal-pulse-ring { animation: none; }
    .saisonal-pulse-ring circle.value { transition: none; }
}

/* Hero stat values with count-up feel */
.saisonal-hero-stat-value {
    font-size: 1.2rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1;
    opacity: 0;
    animation: saisonal-count-up 0.6s cubic-bezier(0.22,1,0.36,1) forwards;
}
.saisonal-hero-stat-label {
    font-size: 0.58rem;
    font-weight: 600;
    color: var(--c-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-top: 3px;
}

/* Topic pills with cascade */
.saisonal-topic-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 11px;
    border-radius: 10px;
    font-size: 0.68rem;
    font-weight: 600;
    transition: var(--transition);
    opacity: 0;
    animation: saisonal-pill-cascade 0.35s cubic-bezier(0.22,1,0.36,1) forwards;
}
.saisonal-topic-pill:hover {
    transform: translateY(-2px);
    filter: brightness(1.25);
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

/* --- Timeline Section (Heatmap) --- */
.saisonal-timeline-grid {
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: 3px;
    margin-bottom: 8px;
}
.saisonal-month-cell {
    padding: 6px 2px;
    background: rgba(255,255,255,0.03);
    border: 1px solid var(--c-border);
    border-radius: 8px;
    text-align: center;
    transition: var(--transition);
    min-height: 36px;
    position: relative;
}
.saisonal-month-cell:hover {
    background: rgba(255,255,255,0.07);
    border-color: var(--c-border-hover);
    transform: translateY(-1px);
}
.saisonal-month-cell.current {
    border-color: rgba(132,204,22,0.5);
    background: rgba(132,204,22,0.08);
    box-shadow: 0 0 16px rgba(132,204,22,0.12), inset 0 0 12px rgba(132,204,22,0.04);
}
/* Removed: vertical playhead line was bleeding into Hero section */
.saisonal-month-label {
    font-size: 0.62rem;
    font-weight: 700;
    color: var(--c-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 4px;
}
.saisonal-month-count {
    font-size: 0.72rem;
    font-weight: 800;
    color: var(--c-text-secondary);
    transition: var(--transition);
}
.saisonal-month-cell.current .saisonal-month-count {
    color: var(--c-accent);
}

/* Gantt bars with animation */
.saisonal-bars-row {
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: 3px;
    align-items: center;
    margin-bottom: 3px;
    transition: opacity 0.2s ease;
}
.saisonal-bars-row:hover {
    z-index: 2;
}
.saisonal-bars-row:hover .saisonal-bar-cell {
    height: 10px;
}
.saisonal-bar-cell {
    height: 6px;
    border-radius: 3px;
    transition: all 0.25s cubic-bezier(0.22,1,0.36,1);
    transform-origin: left center;
    animation: saisonal-bar-reveal 0.5s cubic-bezier(0.22,1,0.36,1) forwards;
}
.saisonal-bar-cell:hover {
    height: 12px !important;
    filter: brightness(1.4);
    box-shadow: 0 0 10px currentColor;
    border-radius: 4px;
}
.saisonal-bar-cell.peak { opacity: 1; }
.saisonal-bar-cell.active { opacity: 0.35; }
.saisonal-bar-cell.off { opacity: 0; pointer-events: none; }

/* --- Cluster Cards (enhanced) --- */
.saisonal-cluster-card {
    background: var(--c-surface);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--c-border);
    border-radius: var(--radius);
    padding: 16px 18px 14px 21px;
    margin-bottom: 10px;
    transition: all 0.25s cubic-bezier(0.22,1,0.36,1);
    position: relative;
    overflow: hidden;
}
.saisonal-cluster-card::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    background: var(--spec-color, #8b8ba0);
    transition: width 0.25s ease, box-shadow 0.25s ease;
}
.saisonal-cluster-card:hover {
    border-color: var(--c-border-hover);
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    background: rgba(255,255,255,0.05);
    transform: translateY(-3px);
}
.saisonal-cluster-card:hover::before {
    width: 5px;
    box-shadow: 3px 0 14px color-mix(in srgb, var(--spec-color, #8b8ba0) 35%, transparent);
}

/* Live indicator dot */
.saisonal-live-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    display: inline-block;
    margin-left: 6px;
    vertical-align: middle;
}
.saisonal-live-dot.peak {
    background: #f87171;
    animation: saisonal-live-pulse 2s ease-in-out infinite;
}
.saisonal-live-dot.active {
    background: #fbbf24;
    animation: saisonal-live-pulse-amber 2.5s ease-in-out infinite;
}
.saisonal-live-dot.off {
    background: transparent;
    border: 1.5px solid rgba(255,255,255,0.15);
}

/* Progress bar at bottom of cluster card */
.saisonal-progress-track {
    height: 3px;
    background: rgba(255,255,255,0.06);
    border-radius: 2px;
    margin-top: 12px;
    overflow: hidden;
}
.saisonal-progress-fill {
    height: 100%;
    border-radius: 2px;
    animation: saisonal-progress-fill 0.8s cubic-bezier(0.22,1,0.36,1) forwards;
}

/* Status pills */
.saisonal-status-pill {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.01em;
    transition: var(--transition);
    margin: 2px;
}
.saisonal-status-peak {
    background: rgba(248,113,113,0.12);
    color: #f87171;
}
.saisonal-status-active {
    background: rgba(251,191,36,0.12);
    color: #fbbf24;
}
.saisonal-status-off {
    background: rgba(255,255,255,0.06);
    color: #8b8ba0;
}
.saisonal-status-pill:hover {
    transform: translateY(-1px);
    filter: brightness(1.25);
}

/* --- Awareness (Departure Board Style) --- */
.saisonal-awareness-item, .saisonal-regulatory-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
    background: var(--c-surface);
    border: 1px solid var(--c-border);
    border-radius: var(--radius-sm);
    margin-bottom: 6px;
    transition: all 0.25s cubic-bezier(0.22,1,0.36,1);
    position: relative;
    overflow: hidden;
}
.saisonal-awareness-item::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    background: var(--c-accent);
    opacity: 0;
    transition: opacity 0.3s ease;
}
.saisonal-regulatory-item::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    background: var(--c-warn);
    opacity: 0;
    transition: opacity 0.3s ease;
}
.saisonal-awareness-item:hover, .saisonal-regulatory-item:hover {
    border-color: var(--c-border-hover);
    transform: translateX(4px);
    background: rgba(255,255,255,0.05);
    box-shadow: 0 4px 16px rgba(0,0,0,0.2);
}
.saisonal-awareness-item:hover::before, .saisonal-regulatory-item:hover::before {
    opacity: 1;
}

/* Countdown badge (departure board) */
.saisonal-countdown {
    min-width: 48px;
    text-align: center;
    padding: 6px 8px;
    border-radius: 8px;
    font-size: 0.88rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
    perspective: 400px;
    animation: saisonal-flip-in 0.5s cubic-bezier(0.22,1,0.36,1) forwards;
}
.saisonal-countdown.urgent {
    background: rgba(248,113,113,0.15);
    color: #f87171;
    box-shadow: 0 0 12px rgba(248,113,113,0.1);
    animation: saisonal-flip-in 0.5s cubic-bezier(0.22,1,0.36,1) forwards,
               saisonal-live-pulse 2s ease-in-out 0.5s infinite;
}
.saisonal-countdown.soon {
    background: rgba(251,191,36,0.15);
    color: #fbbf24;
}
.saisonal-countdown.normal {
    background: rgba(255,255,255,0.06);
    color: var(--c-text-secondary);
}

/* Regulatory progress bar (draining) */
.saisonal-drain-track {
    width: 100%;
    height: 3px;
    background: rgba(255,255,255,0.06);
    border-radius: 2px;
    margin-top: 6px;
    overflow: hidden;
}
.saisonal-drain-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.8s cubic-bezier(0.22,1,0.36,1);
}

.saisonal-article-badge {
    background: rgba(59,130,246,0.12);
    color: #3b82f6;
    padding: 2px 8px;
    border-radius: 8px;
    font-size: 0.68rem;
    font-weight: 600;
    white-space: nowrap;
    transition: var(--transition);
}
.saisonal-article-badge:hover {
    background: rgba(59,130,246,0.2);
    transform: translateY(-1px);
}

/* Category badges for regulatory */
.saisonal-cat-badge {
    padding: 1px 8px;
    border-radius: 8px;
    font-size: 0.58rem;
    font-weight: 700;
    white-space: nowrap;
}

/* =====================================================================
   THEMEN-RADAR v2 — Editorial Cards + Motion Effects
   ===================================================================== */

/* Urgency badge — pulsing dot */
@keyframes urgency-pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.6; transform: scale(1.3); }
}
.urgency-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
    vertical-align: middle;
}
.urgency-dot.sofort {
    background: #f87171;
    animation: urgency-pulse 1.5s ease-in-out infinite;
    box-shadow: 0 0 8px rgba(248,113,113,0.5);
}
.urgency-dot.diese_woche {
    background: #fbbf24;
    animation: urgency-pulse 2.5s ease-in-out infinite;
    box-shadow: 0 0 6px rgba(251,191,36,0.4);
}
.urgency-dot.beobachten {
    background: #6b6b82;
}

/* Editorial action banner */
.editorial-action {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 0.72rem;
    font-weight: 600;
    margin-bottom: 10px;
    transition: all 0.2s ease-out;
    border-left: 3px solid;
}
.editorial-action:hover {
    filter: brightness(1.15);
    transform: translateX(2px);
}
.editorial-action.sofort {
    background: rgba(248,113,113,0.08);
    color: #f87171;
    border-left-color: #f87171;
}
.editorial-action.diese_woche {
    background: rgba(251,191,36,0.08);
    color: #fbbf24;
    border-left-color: #fbbf24;
}
.editorial-action.beobachten {
    background: rgba(255,255,255,0.03);
    color: #6b6b82;
    border-left-color: #6b6b82;
}

/* Sparkline (pure CSS bars) */
.sparkline-mini {
    display: inline-flex;
    align-items: flex-end;
    gap: 2px;
    height: 20px;
    vertical-align: middle;
}
.sparkline-mini .spark-bar {
    width: 6px;
    border-radius: 2px 2px 0 0;
    transition: all 0.3s ease-out;
    min-height: 2px;
}
.sparkline-mini:hover .spark-bar {
    filter: brightness(1.3);
}
.sparkline-mini .spark-bar:last-child {
    opacity: 1;
}

/* Trend phase badge */
.trend-phase {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.6rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 2px 8px;
    border-radius: 6px;
}
.trend-phase.neu { background: rgba(34,211,238,0.12); color: #22d3ee; }
.trend-phase.wachsend { background: rgba(74,222,128,0.12); color: #4ade80; }
.trend-phase.peak { background: rgba(248,113,113,0.12); color: #f87171; }
.trend-phase.abflachend { background: rgba(139,139,160,0.12); color: #8b8ba0; }
.trend-phase.stabil { background: rgba(255,255,255,0.06); color: #a0a0b8; }

/* Source diversity pills */
.src-diversity {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.65rem;
    color: var(--c-text-muted);
    margin-top: 6px;
}
.src-pill {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 0.58rem;
    font-weight: 600;
    transition: all 0.2s ease-out;
}
.src-pill:hover {
    filter: brightness(1.2);
    transform: translateY(-1px);
}
.src-pill.hoch { background: rgba(74,222,128,0.12); color: #4ade80; }
.src-pill.mittel { background: rgba(251,191,36,0.12); color: #fbbf24; }
.src-pill.niedrig { background: rgba(139,139,160,0.12); color: #8b8ba0; }

/* First-mover badge */
.first-mover-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.6rem;
    font-weight: 700;
    background: rgba(34,211,238,0.12);
    color: #22d3ee;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    animation: urgency-pulse 3s ease-in-out infinite;
}

/* Storyline pitch cards */
.pitch-card {
    padding: 8px 12px;
    border-radius: 8px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 6px;
    transition: all 0.25s ease-out;
    cursor: default;
}
.pitch-card:hover {
    background: rgba(255,255,255,0.06);
    border-color: rgba(255,255,255,0.12);
    transform: translateX(4px);
    box-shadow: 0 2px 12px rgba(0,0,0,0.15);
}
.pitch-format {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 0.55rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    background: rgba(163,230,53,0.12);
    color: #a3e635;
    margin-right: 6px;
}

/* Radar card hover lift */
.radar-card-v2 {
    transition: all 0.25s ease-out;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px;
    background: rgba(255,255,255,0.035);
    padding: 16px;
    position: relative;
    overflow: hidden;
}
.radar-card-v2:hover {
    border-color: rgba(255,255,255,0.14);
    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    transform: translateY(-2px);
}
/* Left accent glow on hover */
.radar-card-v2::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
    border-radius: 14px 0 0 14px;
    transition: all 0.25s ease-out;
}
.radar-card-v2:hover::before {
    width: 4px;
    box-shadow: 2px 0 12px var(--accent-color, rgba(163,230,53,0.3));
}

/* GPU-accelerated animation hints for smooth compositing */
.dash-card, .a-card, .saisonal-section-reveal {
    will-change: transform, opacity;
}
.a-score-ring svg circle {
    will-change: stroke-dashoffset;
}

/* ===== Sort legend info icon + tooltip ===== */
.sort-legend-toggle {
    cursor: help;
    font-size: 0.7rem;
    opacity: 0.5;
    transition: opacity 0.2s ease;
    position: relative;
    display: inline-block;
}
.sort-legend-toggle:hover { opacity: 1; }
.sort-legend-toggle .sort-tooltip {
    display: none;
    position: absolute;
    left: 0;
    right: auto;
    top: 100%;
    margin-top: 6px;
    background: var(--c-surface-solid, rgba(20,20,42,0.97));
    border: 1px solid var(--c-border);
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 0.68rem;
    line-height: 1.6;
    color: var(--c-text-secondary);
    white-space: normal;
    min-width: 220px;
    max-width: 280px;
    z-index: 1000;
    box-shadow: 0 8px 32px rgba(0,0,0,0.15);
    pointer-events: none;
}
.sort-legend-toggle:hover .sort-tooltip {
    display: block;
}

/* ===== MOBILE: keep action button columns in a single row ===== */
/* Streamlit wraps columns on narrow screens — prevent that for button rows.
   Target: any horizontal block whose first child contains a checkbox (= article action row). */
@media (max-width: 768px) {
    .a-card { padding: 14px 16px; }
    .dash-bar { grid-template-columns: repeat(2, 1fr) !important; }
    .main .block-container { padding: 1rem 1rem 2rem 1rem; }

    /* Force all column rows to stay horizontal */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        gap: 2px !important;
    }
    /* Allow columns to shrink below their min-width */
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        min-width: 0 !important;
        flex-shrink: 1 !important;
    }
    /* Compact buttons */
    [data-testid="stHorizontalBlock"] button {
        padding: 4px 6px !important;
        min-height: 30px !important;
        font-size: 0.78rem !important;
    }
}

@media (prefers-reduced-motion: reduce) {
    /* Comprehensive catch-all: disable ALL animations and transitions */
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
    }
}


</style>
"""


def inject_css():
    """Inject the full custom CSS into the Streamlit app."""
    st.markdown(_get_css(), unsafe_allow_html=True)

    # Esanum-specific portal overrides — injected unconditionally so they apply
    # to Streamlit portals (popovers, dropdowns) that render outside stApp
    theme = st.session_state.get("theme", "dark")
    if theme == "esanum":
        st.markdown("""<style>
[data-testid="stPopoverBody"] { background: #FFFFFF !important; border: 1px solid #ECECEC !important; color: #333333 !important; }
[data-testid="stPopoverBody"] * { color: #333333 !important; }
[data-testid="stPopover"] > button { background: #FFFFFF !important; color: #005461 !important; border: 1px solid #ECECEC !important; }
[data-testid="stPopover"] > button:hover { background: #E5EEEF !important; border-color: #005461 !important; }
[data-baseweb="popover"] { background: #FFFFFF !important; }
[data-baseweb="popover"] li, [data-baseweb="popover"] [role="option"] { color: #333333 !important; background: #FFFFFF !important; }
[data-baseweb="popover"] li:hover, [data-baseweb="popover"] [role="option"]:hover { background: #F5F5F5 !important; }
[data-baseweb="popover"] [role="listbox"] { background: #FFFFFF !important; }
[data-baseweb="calendar"], [data-baseweb="datepicker"], [data-baseweb="calendar"] *, [data-baseweb="datepicker"] * { background-color: #FFFFFF !important; color: #444444 !important; }
[data-baseweb="calendar"] [role="gridcell"]:hover, [data-baseweb="calendar"] [role="gridcell"]:hover * { background-color: #E5EEEF !important; color: #005461 !important; }
[data-baseweb="calendar"] [aria-selected="true"], [data-baseweb="calendar"] [aria-selected="true"] * { background-color: #005461 !important; color: #FFFFFF !important; }
[data-baseweb="calendar"] button { background-color: transparent !important; color: #444444 !important; }
[data-baseweb="calendar"] button:hover { background-color: #E5EEEF !important; }
</style>""", unsafe_allow_html=True)

    # Apply theme via data-attribute — must use components.v1.html
    # because st.markdown strips <script> tags
    theme = st.session_state.get("theme", "dark")
    _theme_js = f"""
    <script>
    (function(){{
        var pd = window.parent.document;
        var root = pd.documentElement;
        var theme = "{theme}";
        if (theme === "esanum") {{
            root.setAttribute("data-theme", "esanum");
            pd.body.setAttribute("data-theme", "esanum");
        }} else {{
            root.removeAttribute("data-theme");
            pd.body.removeAttribute("data-theme");
        }}

        // Inject esanum popover overrides as a <style> tag in the parent document
        if (theme === "esanum") {{
            var styleId = "lumio-esanum-popover-fix-v2";
            // Always replace to ensure latest CSS is applied
            var oldS = pd.getElementById(styleId);
            if (oldS) oldS.remove();
            // Also remove legacy version
            var legacyS = pd.getElementById("lumio-esanum-popover-fix");
            if (legacyS) legacyS.remove();

            var s = pd.createElement("style");
            s.id = styleId;
            s.textContent = `
                [data-testid="stPopoverBody"],
                [data-testid="stPopover"] [data-testid="stPopoverBody"] {{
                    background: #FFFFFF !important;
                    border: 1px solid #ECECEC !important;
                    color: #333333 !important;
                }}
                [data-testid="stPopoverBody"] *,
                [data-testid="stPopoverBody"] p,
                [data-testid="stPopoverBody"] span,
                [data-testid="stPopoverBody"] div,
                [data-testid="stPopoverBody"] b,
                [data-testid="stPopoverBody"] li {{
                    color: #333333 !important;
                }}
                [data-testid="stPopover"] > button {{
                    background: #FFFFFF !important;
                    color: #005461 !important;
                    border: 1px solid #ECECEC !important;
                }}
                [data-testid="stPopover"] > button:hover {{
                    background: #E5EEEF !important;
                    border-color: #005461 !important;
                }}
                [data-baseweb="popover"] {{
                    background: #FFFFFF !important;
                }}
                [data-baseweb="popover"] *  {{
                    background-color: #FFFFFF !important;
                    color: #333333 !important;
                }}
                [data-baseweb="popover"] li:hover,
                [data-baseweb="popover"] [role="option"]:hover {{
                    background: #F5F5F5 !important;
                }}
                [data-baseweb="calendar"],
                [data-baseweb="datepicker"],
                [data-baseweb="calendar"] *,
                [data-baseweb="datepicker"] * {{
                    background-color: #FFFFFF !important;
                    color: #444444 !important;
                }}
                [data-baseweb="calendar"] [role="gridcell"]:hover,
                [data-baseweb="calendar"] [role="gridcell"]:hover * {{
                    background-color: #E5EEEF !important;
                    color: #005461 !important;
                }}
                [data-baseweb="calendar"] [aria-selected="true"],
                [data-baseweb="calendar"] [aria-selected="true"] * {{
                    background-color: #005461 !important;
                    color: #FFFFFF !important;
                }}
                [data-baseweb="calendar"] button {{
                    background-color: transparent !important;
                    color: #444444 !important;
                }}
                [data-baseweb="calendar"] button:hover {{
                    background-color: #E5EEEF !important;
                }}
            `;
            pd.head.appendChild(s);

            // Nuclear approach: scan ALL portal containers (body > div outside stApp)
            // for dark-background elements and force them white.
            // Does NOT rely on data-baseweb attributes at all.
            if (pd._lumioPortalFix) clearInterval(pd._lumioPortalFix);
            pd._lumioPortalFix = setInterval(function() {{
                // Find all direct children of body that are NOT the stApp
                var bodyChildren = pd.body.children;
                for (var i = 0; i < bodyChildren.length; i++) {{
                    var container = bodyChildren[i];
                    // Skip the main Streamlit app, scripts, styles, and iframes
                    if (container.tagName === 'SCRIPT' || container.tagName === 'STYLE' ||
                        container.tagName === 'LINK' || container.tagName === 'IFRAME' ||
                        container.tagName === 'NOSCRIPT') continue;
                    if (container.id === 'root' || container.id === 'lumio-fab' ||
                        container.getAttribute('data-testid') === 'stApp') continue;
                    // This is a portal container — force all elements to light theme
                    var els = container.querySelectorAll('*');
                    if (els.length === 0) continue;
                    container.style.setProperty('background-color', '#FFFFFF', 'important');
                    els.forEach(function(el) {{
                        var cs = pd.defaultView.getComputedStyle(el);
                        var bg = cs.backgroundColor;
                        // Parse background color to check if dark
                        var m = bg.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                        if (m) {{
                            var r = parseInt(m[1]), g = parseInt(m[2]), b = parseInt(m[3]);
                            // If element has a dark background (luminance < 80)
                            if (r < 80 && g < 80 && b < 80) {{
                                // Check if this is a selected day (teal)
                                var ariaSelected = el.getAttribute('aria-selected');
                                var inSelected = el.closest && el.closest('[aria-selected="true"]');
                                if (ariaSelected === 'true' || inSelected) {{
                                    el.style.setProperty('background-color', '#005461', 'important');
                                    el.style.setProperty('color', '#FFFFFF', 'important');
                                }} else {{
                                    el.style.setProperty('background-color', '#FFFFFF', 'important');
                                    el.style.setProperty('color', '#444444', 'important');
                                }}
                            }}
                        }}
                        // Also fix text on light backgrounds that's too light to read
                        var fg = cs.color;
                        var fm = fg.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                        if (fm) {{
                            var fr = parseInt(fm[1]), fg2 = parseInt(fm[2]), fb = parseInt(fm[3]);
                            if (fr > 200 && fg2 > 200 && fb > 200) {{
                                el.style.setProperty('color', '#444444', 'important');
                            }}
                        }}
                    }});
                }}
            }}, 150);

            // Global teal-button text fix: ensure ANY element with teal bg has white text
            if (pd._lumioTealFix) clearInterval(pd._lumioTealFix);
            pd._lumioTealFix = setInterval(function() {{
                var tealColors = ['rgb(0, 84, 97)', 'rgb(0, 62, 72)', 'rgb(0, 165, 174)'];
                var allEls = pd.querySelectorAll('button, [role="button"], a, span, div, p');
                allEls.forEach(function(el) {{
                    var bg = pd.defaultView.getComputedStyle(el).backgroundColor;
                    if (tealColors.indexOf(bg) !== -1) {{
                        el.style.setProperty('color', '#FFFFFF', 'important');
                        el.style.setProperty('-webkit-text-fill-color', '#FFFFFF', 'important');
                        // Also fix child text nodes
                        var kids = el.querySelectorAll('*');
                        kids.forEach(function(k) {{
                            k.style.setProperty('color', '#FFFFFF', 'important');
                            k.style.setProperty('-webkit-text-fill-color', '#FFFFFF', 'important');
                        }});
                    }}
                }});
            }}, 500);
        }} else {{
            var oldStyle = pd.getElementById("lumio-esanum-popover-fix-v2");
            if (oldStyle) oldStyle.remove();
            var legacyS2 = pd.getElementById("lumio-esanum-popover-fix");
            if (legacyS2) legacyS2.remove();
            if (pd._lumioPortalFix) {{
                clearInterval(pd._lumioPortalFix);
                delete pd._lumioPortalFix;
            }}
            if (pd._lumioTealFix) {{
                clearInterval(pd._lumioTealFix);
                delete pd._lumioTealFix;
            }}
        }}
    }})();
    </script>
    """
    st.components.v1.html(_theme_js, height=0)
