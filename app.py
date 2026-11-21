import datetime
import json
import os
import streamlit as st
from PIL import Image

ROLES = ["Primary Rusher", "Secondary Rusher", "Sniper", "Supporter"]
DATA_FILE = "cadence_data.json"

st.set_page_config(
    page_title="CADENCE",
    page_icon="CADENCEnobg.png" if os.path.exists("CADENCEnobg.png") else "📊",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Mobile-friendly rounded pill styling
st.markdown(
    """
    <style>
        .stApp {
            background-color: #0E0E10;
            color: #F4F4F5;
        }
        div.stButton > button {
            width: 100%;
            border-radius: 999px;
            border: none;
            padding: 0.65rem 1rem;
            font-weight: 700;
            background-color: #27272A;
            color: #F4F4F5;
        }
        div.stButton > button:hover {
            background-color: #22C55E;
            color: #09090B;
        }
        .team-banner {
            background-color: #E4E4E7;
            color: #09090B;
            border-radius: 999px;
            padding: 14px 20px;
            text-align: center;
            font-weight: 800;
            font-size: 1.15rem;
            margin-bottom: 12px;
        }
        .rank-card {
            background-color: #18181B;
            border-radius: 999px;
            padding: 10px 16px;
            margin-bottom: 8px;
            font-family: monospace;
            font-size: 0.9rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def default_stats():
    return {
        "rank": {"clash_squad": [], "battle_royale": []},
        "training": {"kd_ratio": 0.0, "avg_kd": 0.0, "logs": []},
    }


def recompute_avg_kd(player):
    tr = player.setdefault("stats", default_stats()).setdefault(
        "training", {"kd_ratio": 0.0, "avg_kd": 0.0, "logs": []}
    )
    logs = tr.get("logs", [])
    if not logs:
        tr["avg_kd"] = round(float(tr.get("kd_ratio", 0.0)), 2)
        return tr["avg_kd"]
    avg_val = sum(float(x.get("kd", 0.0)) for x in logs) / len(logs)
    tr["avg_kd"] = round(avg_val, 2)
    tr["kd_ratio"] = round(float(logs[-1].get("kd", tr["avg_kd"])), 2)
    return tr["avg_kd"]


def load_store():
    if not os.path.exists(DATA_FILE):
        return {"players": {}, "teams": {}, "active_player": None, "active_team": None}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("players", {})
    data.setdefault("teams", {})
    data.setdefault("active_player", None)
    data.setdefault("active_team", None)
    for _, p in data["players"].items():
        recompute_avg_kd(p)
    return data


def save_store(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def ensure_player(store, name, role=None):
    clean = name.strip()
    if not clean:
        return None
    if clean not in store["players"]:
        store["players"][clean] = {
            "player_name": clean,
            "role": role if role in ROLES else ROLES[0],
            "stats": default_stats(),
        }
    elif role in ROLES:
        store["players"][clean]["role"] = role
    recompute_avg_kd(store["players"][clean])
    return store["players"][clean]


def player_score_summary(player):
    st_obj = player.get("stats", default_stats())
    cs = sum(x.get("kills", 0) for x in st_obj.get("rank", {}).get("clash_squad", []))
    br = sum(x.get("kills", 0) for x in st_obj.get("rank", {}).get("battle_royale", []))
    avg_kd = recompute_avg_kd(player)
    return {
        "kills": cs + br,
        "avg_kd": avg_kd,
        "composite": round(cs + br + avg_kd * 10.0, 1),
    }


if "store" not in st.session_state:
    st.session_state.store = load_store()
if "page" not in st.session_state:
    st.session_state.page = "team"
if "selected_player_view" not in st.session_state:
    st.session_state.selected_player_view = None

store = st.session_state.store
logged_name = store.get("active_player")
if logged_name not in store["players"]:
    logged_name = None

# Top Logo
if os.path.exists("CADENCEnobg.png"):
    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        st.image("CADENCEnobg.png", width=130)
else:
    st.markdown("### CADENCE")

# First-time Login Screen
if not logged_name or st.session_state.page == "login":
    st.subheader("LOGIN DETAILS")
    p_name = st.text_input("Player Name", value=logged_name or "")
    p_role = st.pills("Select Role", ROLES, default=store["players"][logged_name]["role"] if logged_name else ROLES[0])

    if st.button("Continue to Team"):
        if not p_name.strip():
            st.error("Enter a player name first.")
        else:
            rec = ensure_player(store, p_name, p_role or ROLES[0])
            store["active_player"] = rec["player_name"]
            save_store(store)
            st.session_state.page = "team"
            st.rerun()
    st.stop()

logged_player = store["players"][logged_name]
st.caption(f"Logged in: **{logged_player['player_name']}** • {logged_player['role']}")

# Bottom-style Top Navigation (Team | Graphs | Menu)
nav_col1, nav_col2, nav_col3 = st.columns(3)
with nav_col1:
    if st.button("Team"):
        st.session_state.page = "team"
        st.session_state.selected_player_view = None
        st.rerun()
with nav_col2:
    if st.button("Graphs"):
        st.session_state.page = "graphs"
        st.session_state.selected_player_view = None
        st.rerun()
with nav_col3:
    if st.button("Menu"):
        st.session_state.page = "menu"
        st.session_state.selected_player_view = None
        st.rerun()

st.divider()

active_team_name = store.get("active_team")
if active_team_name not in store["teams"] and store["teams"]:
    active_team_name = list(store["teams"].keys())[-1]
    store["active_team"] = active_team_name
    save_store(store)

active_team = store["teams"].get(active_team_name)

# ---------------- PLAYERS & SCORE VIEW ----------------
if st.session_state.page == "players":
    if not active_team:
        st.session_state.page = "team"
        st.rerun()

    if st.button("← Back to Team"):
        st.session_state.page = "team"
        st.rerun()

    st.markdown(f"<div class='team-banner'>{active_team['team_name']}</div>", unsafe_allow_html=True)

    if st.session_state.selected_player_view:
        target_name = st.session_state.selected_player_view
        target_player = ensure_player(store, target_name)
        can_edit = (target_player["player_name"] == logged_player["player_name"])

        if st.button("← Back to Players"):
            st.session_state.selected_player_view = None
            st.rerun()

        st.subheader(f"{target_player['player_name']} ({'Editable' if can_edit else 'View Only'})")
        mode_tab = st.pills("Mode", ["Rank", "Training"], default="Rank")

        if mode_tab == "Rank":
            sub_mode = st.pills("Rank Type", ["Clash Squad", "Battle Royale"], default="Clash Squad")
            key = "clash_squad" if sub_mode == "Clash Squad" else "battle_royale"
            entries = target_player["stats"]["rank"].get(key, [])
            total_k = sum(x.get("kills", 0) for x in entries)
            st.progress(min(1.0, total_k / max(25, total_k)), text=f"Kill Bar — Kills: {total_k}")

            if can_edit:
                pick_d = st.date_input("Match Date", value=datetime.date.today()).isoformat()
                k_in = st.number_input("Kills", min_value=0, step=1, value=0)
                won_in = st.toggle("Match Won", value=True)
                if st.button("Save Match Record"):
                    entries.append({"date": pick_d, "kills": int(k_in), "won": bool(won_in)})
                    save_store(store)
                    st.rerun()

            for item in reversed(entries[-8:]):
                res = "WIN" if item.get("won") else "LOSS"
                st.markdown(
                    f"<div class='rank-card'>{item.get('date')} | Kills: {item.get('kills')} | {res}</div>",
                    unsafe_allow_html=True,
                )
        else:
            avg_kd = recompute_avg_kd(target_player)
            st.metric("Average K/D Ratio", f"{avg_kd:.2f}")
            logs = target_player["stats"]["training"].get("logs", [])

            if can_edit:
                pick_d = st.date_input("Training Date", value=datetime.date.today()).isoformat()
                kd_in = st.number_input("Game K/D Ratio", min_value=0.0, step=0.1, value=0.0, format="%.2f")
                kills_in = st.number_input("Kills", min_value=0, step=1, value=0)
                if st.button("Save Training Game"):
                    logs.append({"date": pick_d, "kd": round(float(kd_in), 2), "kills": int(kills_in)})
                    recompute_avg_kd(target_player)
                    save_store(store)
                    st.rerun()

            for item in reversed(logs[-8:]):
                st.markdown(
                    f"<div class='rank-card'>{item.get('date')} | K/D: {float(item.get('kd', 0.0)):.2f} | Kills: {item.get('kills', 0)}</div>",
                    unsafe_allow_html=True,
                )
    else:
        for member_name in active_team.get("members", []):
            ensure_player(store, member_name)
            if st.button(member_name, key=f"p_{member_name}"):
                st.session_state.selected_player_view = member_name
                st.rerun()

        st.markdown("---")
        new_mate = st.text_input("Add Player Name")
        new_mate_role = st.selectbox("Player Role", ROLES)
        if st.button("Add"):
            clean_m = new_mate.strip()
            if clean_m:
                ensure_player(store, clean_m, new_mate_role)
                if clean_m not in active_team["members"]:
                    active_team["members"].append(clean_m)
                save_store(store)
                st.rerun()

# ---------------- TEAM HOME ----------------
elif st.session_state.page == "team":
    banner_title = active_team["team_name"] if active_team else "THE EMPIRE"
    if st.button(banner_title, key="top_team_toggle"):
        if not active_team:
            t_new = {
                "team_name": banner_title,
                "invite_code": "CAD-01",
                "members": [logged_player["player_name"]],
                "invites_sent": [],
            }
            store["teams"][banner_title] = t_new
            store["active_team"] = banner_title
            save_store(store)
        st.session_state.page = "players"
        st.rerun()

    saved_names = list(store["teams"].keys())
    if saved_names:
        picked_team = st.selectbox(
            "Switch Team",
            options=saved_names,
            index=saved_names.index(active_team_name) if active_team_name in saved_names else 0,
        )
        if picked_team != active_team_name:
            store["active_team"] = picked_team
            save_store(store)
            st.rerun()

    t_name_in = st.text_input("Team Name", value=active_team["team_name"] if active_team else "THE EMPIRE")
    t_code_in = st.text_input("Invite Code", value=active_team["invite_code"] if active_team else "CAD-01")

    if st.button("Save Team"):
        clean_t = t_name_in.strip()
        if clean_t:
            if clean_t in store["teams"]:
                t_obj = store["teams"][clean_t]
                t_obj["invite_code"] = t_code_in.strip() or "CAD-01"
                if logged_player["player_name"] not in t_obj["members"]:
                    t_obj["members"].append(logged_player["player_name"])
            else:
                t_obj = {
                    "team_name": clean_t,
                    "invite_code": t_code_in.strip() or "CAD-01",
                    "members": [logged_player["player_name"]],
                    "invites_sent": [],
                }
                store["teams"][clean_t] = t_obj
            store["active_team"] = clean_t
            save_store(store)
            st.rerun()

    with st.expander("Add Team"):
        add_t_name = st.text_input("New Team Name", key="new_team_name_input")
        add_t_code = st.text_input("New Invite Code", value="CAD-02", key="new_team_code_input")
        if st.button("Create Team"):
            clean_add = add_t_name.strip()
            if clean_add:
                store["teams"][clean_add] = {
                    "team_name": clean_add,
                    "invite_code": add_t_code.strip() or "CAD-02",
                    "members": [logged_player["player_name"]],
                    "invites_sent": [],
                }
                store["active_team"] = clean_add
                save_store(store)
                st.rerun()

# ---------------- GRAPHS & TEAM PLAYER RANK ----------------
elif st.session_state.page == "graphs":
    members = active_team["members"] if active_team and active_team.get("members") else list(store["players"].keys())
    st.subheader(f"Team Player Rank — {active_team['team_name'] if active_team else 'All Players'}")

    ranked = []
    for m in members:
        p_rec = ensure_player(store, m)
        ranked.append((m, player_score_summary(p_rec)))
    ranked.sort(key=lambda x: x[1]["composite"], reverse=True)

    for idx, (m_name, info) in enumerate(ranked, start=1):
        st.markdown(
            f"<div class='rank-card'>#{idx} {m_name} • Kills: {info['kills']} • Avg K/D: {info['avg_kd']:.2f}</div>",
            unsafe_allow_html=True,
        )

    st.subheader("Analytics & Graphs")
    window = st.pills("Range", ["Date-wise", "Last 30 Days", "Last 90 Days"], default="Date-wise")
    metric = st.pills("Metric", ["Kills", "Avg K/D", "Games Played"], default="Kills")

    cutoff = None
    if window == "Last 30 Days":
        cutoff = datetime.date.today() - datetime.timedelta(days=30)
    elif window == "Last 90 Days":
        cutoff = datetime.date.today() - datetime.timedelta(days=90)

    def in_win(d_str):
        if not cutoff:
            return True
        try:
            return datetime.date.fromisoformat(d_str) >= cutoff
        except ValueError:
            return True

    rank_games = []
    tr_logs = []
    for m in members:
        s_data = ensure_player(store, m).get("stats", default_stats())
        for g in s_data.get("rank", {}).get("clash_squad", []) + s_data.get("rank", {}).get("battle_royale", []):
            if in_win(g.get("date", "")):
                rank_games.append(g)
        for t in s_data.get("training", {}).get("logs", []):
            if in_win(t.get("date", "")):
                tr_logs.append(t)

    wins_n = sum(1 for g in rank_games if g.get("won"))
    losses_n = len(rank_games) - wins_n
    win_pct = int((wins_n / len(rank_games)) * 100) if rank_games else 0
    st.caption(f"Games: {len(rank_games) + len(tr_logs)} | Win/Loss: {wins_n}W - {losses_n}L ({win_pct}%)")

    series = {}
    if metric == "Kills":
        for g in rank_games:
            dk = g.get("date", "N/A")
            series[dk] = series.get(dk, 0) + g.get("kills", 0)
    elif metric == "Avg K/D":
        buckets = {}
        for t in tr_logs:
            dk = t.get("date", "N/A")
            buckets.setdefault(dk, []).append(float(t.get("kd", 0.0)))
        for dk, vals in buckets.items():
            series[dk] = round(sum(vals) / len(vals), 2)
    else:
        for item in rank_games + tr_logs:
            dk = item.get("date", "N/A")
            series[dk] = series.get(dk, 0) + 1

    if series:
        st.bar_chart(series, height=220)
    else:
        st.info("No records for this filter yet.")

# ---------------- MENU ----------------
elif st.session_state.page == "menu":
    st.subheader("Menu")
    st.write(f"**Player:** {logged_player['player_name']}")
    st.write(f"**Role:** {logged_player['role']}")
    st.write(f"**Active Team:** {active_team['team_name'] if active_team else 'None'}")

    if st.button("Switch / Re-Login Player"):
        st.session_state.page = "login"
        st.rerun()