"""
HoI4 Achievement Checker
Streamlit app to view Hearts of Iron 4 achievement progress.
"""

import json
import re
import csv
import time
import textwrap
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
import extra_streamlit_components as stx
from steam_api import SteamAPI, SteamAPIError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CACHE_FILE = Path(__file__).parent / "achievements_cache.json"
HOI4_RED = "#B22222"
HOI4_DARK = "#1a1a2e"
HOI4_GOLD = "#c8a84b"

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="HoI4 Achievement Checker",
    page_icon="🎖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Dynamic Theme Support
# ---------------------------------------------------------------------------

def get_theme_css():
    vars = {
        "bg-app": "linear-gradient(135deg, #0d0d1a 0%, #1a1a2e 50%, #0d0d1a 100%)",
        "bg-sidebar": "linear-gradient(180deg, #0f0f20 0%, #1c1c30 100%)",
        "text-primary": "#e8e0d0",
        "text-secondary": "#999",
        "text-accent": "#d4af37", # Deep gold/yellow
        "card-bg-start": "#1a1a2e",
        "card-bg-end": "#1e1e38",
        "card-border": "#2a2a4a",
        "card-hover-border": "#d4af3766",
        "input-bg": "#0d0d1a",
        "input-border": "#d4af3755",
        "stat-card-bg-start": "#1e1e3a",
        "stat-card-bg-end": "#252545",
        "req-box-bg": "#1f1f35", # Light purple for requirements
        "divider": "#2a2a4a",
    }

    css_vars = "\n".join([f"    --{k}: {v};" for k, v in vars.items()])
    
    return f"""
<style>
    :root {{
    {css_vars}
    }}

    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Inter:wght@300;400;500;600&display=swap');

    /* ── Global ── */
    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
    }}
    .stApp {{
        background: var(--bg-app);
        color: var(--text-primary);
    }}

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {{
        background: var(--bg-sidebar);
        border-right: 1px solid var(--input-border);
    }}
    section[data-testid="stSidebar"] input {{
        background: var(--input-bg) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--input-border) !important;
        border-radius: 6px !important;
    }}

    /* ── Header title ── */
    .hoi4-title {{
        font-family: 'Cinzel', serif;
        font-size: 2.4rem;
        font-weight: 700;
        background: linear-gradient(90deg, #c8a84b, #f0d080, #c8a84b);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        letter-spacing: 3px;
        margin-bottom: 0;
        text-shadow: none;
    }}
    .hoi4-subtitle {{
        text-align: center;
        color: var(--text-secondary);
        font-size: 0.85rem;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-top: 4px;
    }}

    /* ── Stats bar ── */
    .stats-container {{
        display: flex;
        gap: 16px;
        margin: 20px 0;
    }}
    .stat-card {{
        flex: 1;
        background: linear-gradient(135deg, var(--stat-card-bg-start), var(--stat-card-bg-end));
        border: 1px solid var(--input-border);
        border-radius: 12px;
        padding: 18px 22px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }}
    .stat-value {{
        font-family: 'Cinzel', serif;
        font-size: 2rem;
        font-weight: 700;
        color: var(--text-accent);
    }}
    .stat-label {{
        font-size: 0.75rem;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-top: 4px;
    }}
    .stat-card.achieved {{ border-color: #4caf5066; }}
    .stat-card.achieved .stat-value {{ color: #4caf50; }}
    .stat-card.remaining {{ border-color: #ff6b3544; }}
    .stat-card.remaining .stat-value {{ color: #ff6b35; }}

    /* ── Progress bar ── */
    .progress-wrap {{
        background: var(--input-bg);
        border-radius: 999px;
        height: 18px;
        border: 1px solid var(--input-border);
        overflow: hidden;
        margin: 12px 0 24px;
    }}
    .progress-fill {{
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #8b0000, #c8a84b, #f0d080);
        transition: width 0.6s ease;
        position: relative;
    }}
    .progress-fill::after {{
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: linear-gradient(180deg, rgba(255,255,255,0.15) 0%, transparent 100%);
        border-radius: 999px;
    }}

    /* ── Filter tabs custom styling ── */
    div[data-testid="stHorizontalBlock"] button[kind="secondary"] {{
        background: transparent;
        border: 1px solid var(--input-border);
        color: var(--text-accent);
        border-radius: 8px;
    }}

    /* ── Clickable Achievement Card (details/summary) ── */
    details.ach-card {{
        background: linear-gradient(135deg, var(--card-bg-start), var(--card-bg-end));
        border: 1px solid var(--card-border);
        border-radius: 12px;
        margin-bottom: 12px;
        transition: border-color 0.2s, background 0.3s;
        overflow: hidden;
        display: block;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }}
    details.ach-card summary {{
        list-style: none;
        display: flex;
        gap: 16px;
        align-items: flex-start;
        padding: 16px;
        cursor: pointer;
        user-select: none;
    }}
    details.ach-card summary::-webkit-details-marker {{ display: none; }}
    
    details.ach-card[open] {{
        background: linear-gradient(135deg, var(--card-bg-end), var(--stat-card-bg-end));
        border-color: var(--text-accent);
    }}
    details.ach-card.achieved-card {{
        border-color: #4caf5033;
        background: linear-gradient(135deg, #1a2e1a, #1e2e1e);
    }}
    details.ach-card:hover {{
        border-color: var(--card-hover-border);
    }}

    .ach-icon {{
        width: 56px;
        height: 56px;
        border-radius: 8px;
        flex-shrink: 0;
        object-fit: cover;
        box-shadow: 0 4px 8px rgba(0,0,0,0.5); /* Icon depth */
    }}
    .ach-icon.gray {{ filter: grayscale(100%) brightness(0.6); }}
    .ach-content {{ flex: 1; min-width: 0; }}
    .ach-name {{
        font-family: 'Cinzel', serif;
        font-size: 0.95rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 2px;
    }}
    .ach-name.achieved-name {{ color: var(--text-accent); }}
    .ach-desc {{
        font-size: 0.78rem;
        color: var(--text-secondary);
        margin-bottom: 8px;
        line-height: 1.4;
    }}

    /* ── Expansion Content ── */
    .ach-details-content {{
        padding: 0 16px 16px 88px; /* Alignment with name */
        animation: slideDown 0.3s ease-out;
    }}
    @keyframes slideDown {{
        from {{ opacity: 0; transform: translateY(-10px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}

    .req-box {{
        background: var(--req-box-bg);
        padding: 12px;
        border-radius: 8px;
        border: 1px solid var(--card-border);
        font-size: 0.82rem;
        color: var(--text-primary);
    }}
    .req-title {{
        color: var(--text-accent);
        font-weight: bold;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 6px;
    }}
    .req-notes {{
        margin-top: 10px;
        color: var(--text-secondary);
        font-style: italic;
        border-top: 1px dashed var(--divider);
        padding-top: 8px;
        white-space: pre-wrap;
    }}
    .req-text {{ white-space: pre-wrap; line-height: 1.4; }}
    .ach-meta {{
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
        margin-top: 8px;
    }}
    .badge-achieved {{
        background: #4caf5022;
        border: 1px solid #4caf5066;
        color: #4caf50;
        border-radius: 999px;
        font-size: 0.68rem;
        padding: 2px 10px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }}
    .badge-locked {{
        background: #ff000011;
        border: 1px solid #ff000033;
        color: #cc4444;
        border-radius: 999px;
        font-size: 0.68rem;
        padding: 2px 10px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }}
    .global-bar-wrap {{
        display: flex;
        align-items: center;
        gap: 8px;
        flex: 1;
        min-width: 120px;
    }}
    .global-bar-track {{
        flex: 1;
        background: var(--input-bg);
        border-radius: 999px;
        height: 6px;
        overflow: hidden;
    }}
    .global-bar-fill {{
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #3a3a8a, #6a6ac8);
    }}
    .global-pct-label {{
        font-size: 0.72rem;
        color: var(--text-secondary);
        white-space: nowrap;
        min-width: 52px;
        text-align: right;
    }}
    .unlock-date {{
        font-size: 0.68rem;
        color: var(--text-secondary);
        white-space: nowrap;
    }}

    /* ── Divider ── */
    .section-divider {{
        border: none;
        border-top: 1px solid var(--divider);
        margin: 24px 0;
    }}

    /* ── New badge ── */
    .badge-new {{
        background: var(--text-accent);
        border: 1px solid var(--text-accent);
        color: white;
        border-radius: 999px;
        font-size: 0.65rem;
        padding: 1px 8px;
        font-weight: 700;
        letter-spacing: 1px;
    }}

    /* ── Difficulty Colors ── */
    .di-VE {{ border-left: 4px solid #b39ddb !important; }}
    .di-E {{ border-left: 4px solid #81d4fa !important; }}
    .di-M {{ border-left: 4px solid #a5d6a7 !important; }}
    .di-H {{ border-left: 4px solid #fff59d !important; }}
    .di-VH {{ border-left: 4px solid #ffcc80 !important; }}
    .di-I {{ border-left: 4px solid #ef9a9a !important; }}
    .di-UC {{ border-left: 4px solid #eeeeee !important; }}
    
    .di-bg-VE {{ background: linear-gradient(135deg, rgba(179, 157, 219, 0.25), rgba(179, 157, 219, 0.05)) !important; }}
    .di-bg-E {{ background: linear-gradient(135deg, rgba(129, 212, 250, 0.25), rgba(129, 212, 250, 0.05)) !important; }}
    .di-bg-M {{ background: linear-gradient(135deg, rgba(165, 214, 167, 0.25), rgba(165, 214, 167, 0.05)) !important; }}
    .di-bg-H {{ background: linear-gradient(135deg, rgba(255, 245, 157, 0.25), rgba(255, 245, 157, 0.05)) !important; }}
    .di-bg-VH {{ background: linear-gradient(135deg, rgba(255, 204, 128, 0.25), rgba(255, 204, 128, 0.05)) !important; }}
    .di-bg-I {{ background: linear-gradient(135deg, rgba(239, 154, 154, 0.25), rgba(239, 154, 154, 0.05)) !important; }}
    .di-bg-UC {{ background: linear-gradient(135deg, rgba(238, 238, 238, 0.15), rgba(238, 238, 238, 0.05)) !important; }}

    .play-as-badge {{
        background: var(--divider);
        color: var(--text-primary);
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 0.72rem;
        font-weight: bold;
        margin-right: 6px;
        display: inline-block;
        margin-bottom: 6px;
    }}
    .other-conds {{
        font-size: 0.72rem;
        color: var(--text-secondary);
        margin-bottom: 4px;
        display: block;
    }}
    .dlc-info {{
        font-size: 0.65rem;
        color: var(--text-secondary);
        margin-left: 8px;
        font-weight: normal;
        vertical-align: middle;
    }}

    /* ── Two-column notes layout ── */
    .notes-cols {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
        margin-top: 12px;
    }}
    .notes-col {{
        background: var(--req-box-bg);
        border: 1px solid var(--card-border);
        border-radius: 8px;
        padding: 14px;
        font-size: 0.8rem;
        color: var(--text-secondary);
        white-space: pre-wrap;
        line-height: 1.5;
    }}
    .notes-col-title {{
        font-size: 0.72rem;
        font-weight: bold;
        color: var(--text-accent);
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 4px;
    }}
    .wiki-link {{
        display: inline-block;
        margin-top: 12px;
        padding: 5px 16px;
        background: var(--card-bg-start);
        border: 1px solid var(--text-accent);
        border-radius: 6px;
        color: var(--text-accent);
        font-size: 0.78rem;
        text-decoration: none;
        transition: background 0.2s;
    }}
    .wiki-link:hover {{ background: var(--stat-card-bg-start); color: var(--text-accent); }}

    /* ── Streamlit element overrides ── */
    .stButton>button {{
        background: linear-gradient(135deg, #8b0000, #c00000);
        color: white;
        border: none;
        border-radius: 8px;
        font-family: 'Cinzel', serif;
        font-size: 0.85rem;
        letter-spacing: 1px;
        padding: 10px 20px;
        width: 100%;
        transition: opacity 0.2s;
    }}
    .stButton>button:hover {{ opacity: 0.85; }}

    /* ── Dark/Light Mode Switch overrides ── */
    div[data-testid="stSidebar"] section {{ background: transparent !important; }}
    
    /* Search box */
    .stTextInput>div>div>input {{
        background: var(--input-bg) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--input-border) !important;
        border-radius: 8px !important;
    }}
    .stSelectbox>div>div {{
        background: var(--input-bg) !important;
        border: 1px solid var(--input-border) !important;
        border-radius: 8px !important;
        color: var(--text-primary) !important;
    }}

    /* Alert messages */
    .stAlert {{ border-radius: 10px; }}
</style>
"""

# ---------------------------------------------------------------------------
# Render injected CSS
# ---------------------------------------------------------------------------
st.markdown(get_theme_css(), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "last_updated": None,
        "known_achievements": [],
    }


def save_cache(data: dict):
    # Ensure credentials are NEVER saved to server-side cache
    clean_data = data.copy()
    clean_data.pop("api_key", None)
    clean_data.pop("steam_id", None)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(clean_data, f, ensure_ascii=False, indent=2)


def detect_new_achievements(schema: list[dict], cache: dict) -> list[str]:
    """Return list of new achievement API names not yet in cache."""
    known = set(cache.get("known_achievements", []))
    current = {a["name"] for a in schema}
    return list(current - known)


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

@st.cache_data
def load_csv_data(file_path: Path) -> dict:
    """Load achievement_list.csv and return dict keyed by English name."""
    result = {}
    if not file_path.exists():
        return result
    try:
        # Reading as utf-8-sig to handle Japanese characters correctly
        with open(file_path, encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Use .strip() and .lower() for robust matching
                # Check for multiple possible header names if necessary, 
                # but we fixed it to "Achievements Name"
                name = row.get("Achievements Name", "").strip().lower()
                if not name:
                    # Fallback for corrupted header if detected
                    # (Though we fixed it, this makes it more robust)
                    name = next(iter(row.values()), "").strip().lower()
                
                if name:
                    result[name] = {
                        "ja_name": row.get("実績日本語名", "").strip(),
                        "country_tag": row.get("国家タグ", "").strip(),
                        "difficulty": row.get("難易度", "").strip(),
                        "dlc": row.get("DLC", "").strip(),
                        "conditions": row.get("達成条件", "").strip(),
                        "notes_ja": row.get("日本語Wiki補足説明", "").strip(),
                        "notes_en": row.get("英語Wiki補足説明", "").strip(),
                        "wiki_link": row.get("英語Wikiリンク", "").strip(),
                    }
    except Exception as e:
        st.warning(f"CSV読み込みエラー: {e}")
    return result


def init_session():
    cache = load_cache()
    
    # Load wiki data (legacy, kept for difficulty/background color data)
    wiki_data = {}
    try:
        with open("wiki_data.json", "r", encoding="utf-8") as f:
            wiki_data = json.load(f)
    except Exception:
        pass

    # Load achievement_list.csv as primary data source
    csv_path = Path(__file__).parent / "achievement_list.csv"
    csv_data = load_csv_data(csv_path)
        
    defaults = {
        "api_key": "",
        "steam_id": "",
        "data": None,
        "error": None,
        "new_achievements": [],
        "last_fetched": None,
        "wiki_data": wiki_data,
        "csv_path": csv_path,
        "auto_fetched": False,
        "show_about": False,
        "cookies_initialized": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # Initial load from cookies if available
    # Note: CookieManager is handled in render_sidebar because it's a component


# ---------------------------------------------------------------------------
# Fetch & merge data
# ---------------------------------------------------------------------------

def fetch_data(api_key: str, steam_id: str):
    st.session_state.error = None
    st.session_state.data = None
    st.session_state.new_achievements = []

    try:
        api = SteamAPI(api_key)
        with st.spinner("Steam API からデータを取得中..."):
            result = api.get_all_data(steam_id, lang="japanese")

        schema = api.get_schema("japanese")
        cache = load_cache()
        new_achs = detect_new_achievements(schema, cache)

        # Update cache (credentials are excluded in save_cache)
        cache["known_achievements"] = [a["name"] for a in schema]
        cache["last_updated"] = datetime.utcnow().isoformat()
        save_cache(cache)

        st.session_state.data = result
        st.session_state.new_achievements = new_achs
        st.session_state.last_fetched = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    except SteamAPIError as e:
        st.session_state.error = str(e)
    except Exception as e:
        st.session_state.error = f"予期せぬエラー: {e}"


# ---------------------------------------------------------------------------
# UI Components
# ---------------------------------------------------------------------------

def render_header():
    st.markdown(textwrap.dedent('<h1 class="hoi4-title">🎖️ HoI4 Achievement Checker</h1>'), unsafe_allow_html=True)
    st.markdown(textwrap.dedent('<p class="hoi4-subtitle">Hearts of Iron IV · 実績達成率トラッカー</p>'), unsafe_allow_html=True)


def render_progress(total: int, achieved: int):
    remaining = total - achieved
    pct = (achieved / total * 100) if total > 0 else 0

    st.markdown(textwrap.dedent(f"""
    <div class="stats-container">
        <div class="stat-card">
            <div class="stat-value">{total}</div>
            <div class="stat-label">総実績数</div>
        </div>
        <div class="stat-card achieved">
            <div class="stat-value">{achieved}</div>
            <div class="stat-label">達成済み</div>
        </div>
        <div class="stat-card remaining">
            <div class="stat-value">{remaining}</div>
            <div class="stat-label">残り実績</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{pct:.1f}%</div>
            <div class="stat-label">達成率</div>
        </div>
    </div>
    <div class="progress-wrap">
        <div class="progress-fill" style="width:{pct:.2f}%"></div>
    </div>
    """), unsafe_allow_html=True)


def render_achievement_card(ach: dict, new_achievement_names: set):
    is_achieved = ach["achieved"]
    is_new = ach["name"] in new_achievement_names
    
    # CSV is primary; lookup by displayName (case-insensitive).
    csv_data = load_csv_data(st.session_state.csv_path)
    csv = csv_data.get(ach["displayName"].lower(), {})
    wiki = st.session_state.get("wiki_data", {}).get(ach["name"], {})

    # Difficulty: CSV has "Very Easy" string; wiki_data has "VE" code
    di_label = csv.get("difficulty", "")
    di_code_map = {
        "Very Easy": "VE", "Easy": "E", "Medium": "M",
        "Hard": "H", "Very Hard": "VH", "Insane": "I", "Uncategorized": "UC"
    }
    di = di_code_map.get(di_label) or wiki.get("difficulty", "UC")
    di_cls = f"di-{di}"
    di_bg_cls = f"di-bg-{di}"

    card_cls = f"ach-card {di_cls} {di_bg_cls}"
    if is_achieved:
        card_cls += " achieved-card"

    name_cls = "ach-name achieved-name" if is_achieved else "ach-name"
    icon_url = ach["icon"] if is_achieved else ach["icongray"]
    icon_cls = "" if is_achieved else "gray"
    badge = '<span class="badge-achieved">✓ 達成済み</span>' if is_achieved else '<span class="badge-locked">🔒 未達成</span>'
    new_badge = '<span class="badge-new">NEW</span>' if is_new else ""

    global_pct = float(ach.get("global_pct", 0.0))
    global_bar_width = min(global_pct, 100.0)

    unlock_info = ""
    if is_achieved and ach.get("unlocktime", 0) > 0:
        dt = datetime.fromtimestamp(ach["unlocktime"]).strftime("%Y-%m-%d")
        unlock_info = f'<span class="unlock-date">🗓 {dt}</span>'

    icon_html = f'<img src="{icon_url}" class="ach-icon {icon_cls}" />' if icon_url else \
                f'<div class="ach-icon {icon_cls}" style="background:#2a2a4a;display:flex;align-items:center;justify-content:center;font-size:1.8rem;">🎖️</div>'

    desc = ach["description"] or ("隠し実績" if ach.get("hidden") else "説明なし")

    # --- Header info from CSV ---
    ja_name = csv.get("ja_name", "")
    country_tag = csv.get("country_tag", "")
    dlc_label = csv.get("dlc", "") or wiki.get("dlc", "")

    ja_name_html = f'<span style="color:#c8a84b;font-size:0.85em;font-weight:normal;margin-left:8px;">《{ja_name}》</span>' if ja_name else ""
    tag_html = f'<span class="play-as-badge">🏳️ {country_tag}</span>' if country_tag else ""
    di_display = di_label if di_label else {"VE":"Very Easy","E":"Easy","M":"Medium","H":"Hard","VH":"Very Hard","I":"Insane","UC":"Uncategorized"}.get(di, "")
    dlc_info_html = f'<span class="dlc-info">⚙ {di_display} • {dlc_label}</span>' if (di_display or dlc_label) else ""

    # --- Expansion content from CSV ---
    conditions = csv.get("conditions", "")
    notes_ja = csv.get("notes_ja", "")
    notes_en = csv.get("notes_en", "")
    wiki_link = csv.get("wiki_link", "")

    conditions_html = ""
    if conditions:
        cond_esc = conditions.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        conditions_html = f'''
        <div class="req-box" style="margin-bottom:12px;">
            <div class="req-title">🎯 達成条件</div>
            <div class="req-text">{cond_esc}</div>
        </div>
        '''

    def make_notes_col(flag, title, text):
        if not text:
            return f'<div class="notes-col" style="opacity:0.3;"><div class="notes-col-title">{flag} {title}</div>未記載</div>'
        esc = text.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        return f'<div class="notes-col"><div class="notes-col-title">{flag} {title}</div><div>{esc}</div></div>'

    wiki_link_html = ""
    if wiki_link:
        wiki_link_html = f'<a href="{wiki_link}" target="_blank" rel="noopener noreferrer" class="wiki-link">🔗 英語 Wiki を開く</a>'

    notes_cols_html = ""
    if notes_ja or notes_en:
        left = make_notes_col("🇯🇵", "日本語 Wiki", notes_ja)
        right = make_notes_col("🇬🇧", "英語 Wiki", notes_en)
        notes_cols_html = f'<div class="notes-cols">{left}{right}</div>'

    details_html = ""
    if conditions_html or notes_cols_html or wiki_link_html:
        details_html = f'''
        <div class="ach-details-content">
            {conditions_html}
            {notes_cols_html}
            {wiki_link_html}
        </div>
        '''

    meta_html = "".join([badge, unlock_info])

    html_content = f"""
    <details class="{card_cls}">
    <summary>
        {icon_html}
        <div class="ach-content">
            <div class="{name_cls}">{ach['displayName']}{ja_name_html} {new_badge} {dlc_info_html}</div>
            <div class="ach-desc">{desc}</div>
            {tag_html}
            <div class="ach-meta">
                {meta_html}
                <div class="global-bar-wrap">
                    <div class="global-bar-track">
                        <div class="global-bar-fill" style="width:{global_bar_width:.1f}%"></div>
                    </div>
                    <span class="global-pct-label">全体 {global_pct:.1f}%</span>
                </div>
            </div>
        </div>
    </summary>
    {details_html}
    </details>
    """
    clean_html = "".join([line.strip() for line in html_content.split("\n")])
    st.markdown(clean_html, unsafe_allow_html=True)



def render_achievements_list(data: dict, new_achievement_names: set, filter_mode: str, play_as_filter: str, di_filter: str, search: str, sort_mode: str):
    achievements = data["achievements"]

    # ── Filtering ───────────────────────────────────────────────────────────
    if filter_mode == "達成済み":
        achievements = [a for a in achievements if a["achieved"]]
    elif filter_mode == "未達成":
        achievements = [a for a in achievements if not a["achieved"]]

    wiki_data = st.session_state.get("wiki_data", {})
    csv_data = load_csv_data(st.session_state.csv_path)

    if play_as_filter != "すべて":
        achievements = [
            a for a in achievements
            if play_as_filter.lower() in (csv_data.get(a["displayName"].lower(), {}).get("country_tag") or wiki_data.get(a["name"], {}).get("play_as") or "").lower()
        ]

    if di_filter:
        di_map_inv = {
            "Very Easy": "VE", "Easy": "E", "Medium": "M", 
            "Hard": "H", "Very Hard": "VH", "Insane": "I", "Uncategorized": "UC"
        }
        target_dis = [di_map_inv.get(d) for d in di_filter]
        achievements = [
            a for a in achievements
            if csv_data.get(a["displayName"].lower(), {}).get("difficulty") in di_filter or \
               wiki_data.get(a["name"], {}).get("difficulty") in target_dis
        ]

    if search:
        q = search.lower()
        achievements = [
            a for a in achievements
            if q in a["displayName"].lower() or \
               q in (csv_data.get(a["displayName"].lower(), {}).get("ja_name") or "").lower() or \
               q in (a["description"] or "").lower()
        ]

    # ── Sorting ─────────────────────────────────────────────────────────────
    if sort_mode == "全体達成率 (高い順)":
        achievements.sort(key=lambda x: x["global_pct"], reverse=True)
    elif sort_mode == "全体達成率 (低い順)":
        achievements.sort(key=lambda x: x["global_pct"])
    elif sort_mode == "達成日時 (新しい順)":
        achievements.sort(key=lambda x: x["unlocktime"], reverse=True)
    elif sort_mode == "名前 (A→Z)":
        achievements.sort(key=lambda x: x["displayName"].lower())

    st.markdown(f"<p style='color:#666;font-size:0.8rem;margin-bottom:12px;'>{len(achievements)} 件表示</p>", unsafe_allow_html=True)

    if not achievements:
        st.info("該当する実績が見つかりませんでした。")
        return

    for ach in achievements:
        render_achievement_card(ach, new_achievement_names)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar():
    with st.sidebar:
        st.markdown(
            '<div style="font-family:Cinzel,serif;font-size:1.1rem;color:var(--text-accent);'
            'text-align:center;padding:10px 0 20px;letter-spacing:2px;">⚙ 設定</div>',
            unsafe_allow_html=True,
        )

        # Cookie Management
        cookie_manager = stx.CookieManager()
        
        # Load from cookies once
        if not st.session_state.cookies_initialized:
            c_api = cookie_manager.get(cookie="hoi4_api_key")
            c_id = cookie_manager.get(cookie="hoi4_steam_id")
            if c_api: st.session_state.api_key = c_api
            if c_id: st.session_state.steam_id = c_id
            st.session_state.cookies_initialized = True
            
            # --- Auto-fetch on startup from cookies ---
            if not st.session_state.auto_fetched:
                if st.session_state.api_key.strip() and st.session_state.steam_id.strip():
                    st.session_state.auto_fetched = True
                    fetch_data(st.session_state.api_key.strip(), st.session_state.steam_id.strip())
                    st.rerun()

        api_key = st.text_input(
            "Steam API キー",
            value=st.session_state.api_key,
            type="password",
            placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            help="https://steamcommunity.com/dev/apikey で取得",
            key="input_api_key"
        )
        steam_id = st.text_input(
            "Steam ID (64bit)",
            value=st.session_state.steam_id,
            placeholder="76561198XXXXXXXXX",
            help="自身のプロフィール画面のURLの数字",
            key="input_steam_id"
        )

        st.session_state.api_key = api_key
        st.session_state.steam_id = steam_id

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("🔄 データを更新"):
            if not api_key.strip():
                st.error("Steam API キーを入力してください")
            elif not steam_id.strip():
                st.error("Steam ID を入力してください")
            else:
                # Save to cookies
                cookie_manager.set("hoi4_api_key", api_key.strip(), expires_at=datetime.now() + timedelta(days=30), key="set_api_key")
                cookie_manager.set("hoi4_steam_id", steam_id.strip(), expires_at=datetime.now() + timedelta(days=30), key="set_steam_id")
                fetch_data(api_key.strip(), steam_id.strip())

        if st.button("📊 CSVを再読み込み"):
            st.cache_data.clear()
            st.toast("CSVデータを再読み込みしました", icon="✅")
            st.rerun()

        if st.button("ℹ️ このサイトについて"):
            st.session_state.show_about = not st.session_state.show_about

        if st.session_state.show_about:
            about_path = Path(__file__).parent / "about.txt"
            if about_path.exists():
                with open(about_path, "r", encoding="utf-8") as f:
                    about_text = f.read()
                st.info(about_text)
            else:
                st.warning("about.txt が見つかりません")

        st.markdown("<br>", unsafe_allow_html=True)
        col_wiki_ja, col_wiki_en = st.columns(2)
        with col_wiki_ja:
            st.link_button("🇯🇵 日本語Wiki", "https://hoi4data.paradoxwiki.org/?96bc0c61a4e9")
        with col_wiki_en:
            st.link_button("🇬🇧 英語Wiki", "https://hoi4.paradoxwikis.com/Achievements")

        if st.session_state.last_fetched:
            st.markdown(
                f'<p style="font-size:0.72rem;color:#555;text-align:center;margin-top:12px;">'
                f'最終更新: {st.session_state.last_fetched}</p>',
                unsafe_allow_html=True,
            )

        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

        # Cache info
        cache = load_cache()
        if cache.get("last_updated"):
            known_count = len(cache.get("known_achievements", []))
            st.markdown(
                f'<p style="font-size:0.72rem;color:#555;">'
                f'キャッシュ: {known_count} 実績<br>'
                f'更新日時: {cache["last_updated"][:10]}</p>',
                unsafe_allow_html=True,
            )

        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
        st.markdown(
            '<p style="font-size:0.7rem;color:#444;text-align:center;">'
            'Hearts of Iron IV<br>App ID: 394360</p>',
            unsafe_allow_html=True,
        )

    return api_key, steam_id


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    init_session()
    render_header()
    render_sidebar()

    main_col = st.container()
    with main_col:
        if st.session_state.error:
            st.error(f"❌ エラー: {st.session_state.error}")
            st.markdown(
                """
**よくある原因：**
- Steam API キーが正しくない
- Steam ID が正しくない（64bit ID が必要です）
- プロフィールが非公開（Steam のプライバシー設定で「ゲームの詳細」を公開してください）
                """,
                unsafe_allow_html=False,
            )

        data = st.session_state.data
        new_achievement_names = set(st.session_state.new_achievements)

        if data is None:
            # ── Welcome screen ───────────────────────────────────────────────
            st.markdown(textwrap.dedent(f"""
                <div style="text-align:center;padding:60px 20px;">
                    <p style="font-size:3rem;margin-bottom:16px;">🎖️</p>
                    <p style="font-family:Cinzel,serif;font-size:1.2rem;color:#c8a84b;letter-spacing:2px;">
                        実績データを読み込んでください
                    </p>
                    <p style="color:#666;font-size:0.9rem;margin-top:12px;">
                        左のサイドバーに Steam API キーと Steam ID を入力して<br>
                        「データを更新」ボタンを押してください。
                    </p>
                    <br>
                    <p style="color:#555;font-size:0.8rem;">
                        🔑 API キー取得: <code>https://steamcommunity.com/dev/apikey</code><br>
                        🆔 Steam ID 確認: <code>自身のプロフィール画面のURLの数字</code>
                    </p>
                </div>
            """), unsafe_allow_html=True)
            return

        # ── New achievement notification ──────────────────────────────────
        if new_achievement_names:
            st.success(
                f"🆕 **{len(new_achievement_names)} 個の新しい実績が検出されました！**  "
                + ", ".join(list(new_achievement_names)[:5])
                + ("..." if len(new_achievement_names) > 5 else "")
            )

        # ── Stats bar ────────────────────────────────────────────────────
        render_progress(data["total"], data["achieved_count"])

        # ── Filter & Sort controls ────────────────────────────────────────
        col_sort, col_country, col_di, col_search = st.columns([2, 3, 2, 3])
        
        with col_sort:
            sort_mode = st.selectbox(
                "並び替え",
                ["全体達成率 (高い順)", "全体達成率 (低い順)", "達成日時 (新しい順)", "名前 (A→Z)"],
            )

        with col_country:
            csv_data = load_csv_data(st.session_state.csv_path)
            wiki_data = st.session_state.get("wiki_data", {})
            play_as_options = ["すべて"]
            
            tags = set()
            tag_pattern = re.compile(r'^[A-Z]{3}$')
            if csv_data:
                for v in csv_data.values():
                    t = v.get("country_tag")
                    if t:
                        for part in re.split(r'[,/]', t):
                            clean_tag = part.strip()
                            if tag_pattern.match(clean_tag):
                                tags.add(clean_tag)
            if wiki_data:
                for v in wiki_data.values():
                    p = v.get("play_as")
                    if p:
                        for part in re.split(r'[,/]', p):
                            clean_tag = part.strip()
                            if tag_pattern.match(clean_tag):
                                tags.add(clean_tag)
            play_as_options.extend(sorted(list(tags)))
            
            play_as_filter = st.selectbox(
                "プレイ国 (タグ)",
                play_as_options,
                help="国家タグまたは国名で絞り込みます"
            )

        with col_di:
            di_options = ["Very Easy", "Easy", "Medium", "Hard", "Very Hard", "Insane", "Uncategorized"]
            di_filter = st.multiselect(
                "難易度",
                di_options,
                help="複数の難易度を選択して絞り込めます（未選択で全表示）"
            )

        with col_search:
            search = st.text_input(
                "実績を検索",
                placeholder="🔍 実績名・説明で検索...",
            )

        # Filter mode (Achieved/Locked) tabs
        filter_mode = st.radio(
            "表示対象",
            ["すべて", "達成済み", "未達成"],
            horizontal=True,
            label_visibility="collapsed"
        )

        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
        
        render_achievements_list(data, new_achievement_names, filter_mode, play_as_filter, di_filter, search, sort_mode)


if __name__ == "__main__":
    main()
