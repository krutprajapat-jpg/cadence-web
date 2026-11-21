import datetime
import hashlib
import os
import secrets
import streamlit as st
from supabase import create_client

ROLES = ["Primary Rusher", "Secondary Rusher", "Sniper", "Supporter"]

st.set_page_config(
    page_title="CADENCE",
    page_icon="CADENCEnobg.png" if os.path.exists("CADENCEnobg.png") else "📊",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
        .stApp {
            background-color: #0E0E10;
            color: #F4F4F5;
        }
        .block-container {
            max-width: 440px;
            padding-top: 1rem;
            padding-bottom: 3rem;
        }
        header, #MainMenu {
            visibility: hidden;
        }
        div.stButton > button {
            width: 100%;
            border-radius: 999px;
            border: none;
            padding: 0.55rem 1rem;
            font-weight: 700;
            background-color: #27272A;
            color: #F4F4F5;
        }
        div.stButton > button:hover {
            background-color: #22C55E;
            color: #09090B;
        }
        .team-pill {
            background-color: #E4E4E7;
            color: #09090B;
            border-radius: 999px;
            padding: 12px 18px;
            text-align: center;
            font-weight: 800;
            font-size: 1.05rem;
            margin: 6px 0 12px 0;
        }
        .info-pill {
            background-color: #18181B;
            border: 1px solid #27272A;
            border-radius: 999px;
            padding: 9px 14px;
            margin-bottom: 7px;
            font-family: monospace;
            font-size: 0.85rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def hash_password(password: str, salt: str | None = None) -> dict:
    use_salt = salt or secrets.token_hex(8)
    digest = hashlib.sha256(f"{use_salt}:{password}".encode("utf-8")).hexdigest()
    return {"salt": use_salt, "hash": digest}


def verify_password(password: str, auth_obj: dict | None) -> bool:
    if not auth_obj or "salt" not in auth_obj or "hash" not in auth_obj:
        return False
    check = hash_password(password, salt=auth_obj["salt"])
    return secrets.compare_digest(check["hash"], auth_obj["hash"])


def default_stats() -> dict:
    return {
        "rank": {"clash_squad": [], "battle_royale": []},
        "training": {"kd_ratio": 0.0, "avg_kd": 0.0, "logs": []},
    }


def recompute_avg_kd(player: dict) -> float:
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


def load_store() -> dict:
    sb = get_supabase()
    res = sb.table("cadence_store").select("data").eq("id", "main").execute()
    if res.data:
        data = res.data[0]["data"]
    else:
        data = {"players": {}, "teams": {}, "active_team": None}
        sb.table("cadence_store").upsert({"id": "main", "data": data}).execute()

    data.setdefault("players", {})
    data.setdefault("teams", {})
    data.setdefault("active_team", None)
    for _, p in data["players"].items():
        p.setdefault("stats", default_stats())
        recompute_avg_kd(p)
    return data


def save_store(data: dict) -> None:
    sb = get_supabase()
    sb.table("cadence_store").upsert({"id": "main", "data": data}).execute()


def ensure_player(store: dict, name: str, role: str | None = None, password: str | None = None) -> dict | None:
    clean = name.strip()
    if not clean:
        return None
    if clean not in store["players"]:
        rec = {
            "player_name": clean,
            "role": role if role in ROLES else ROLES[0],
            "stats": default_stats(),
        }
        if password:
            rec["auth"] = hash_password(password)
        store["players"][clean] = rec
    else:
        if role in ROLES:
            store["players"][clean]["role"] = role
        if password and "auth" not in store["players"][clean]:
            store["players"][clean]["auth"] = hash_password(password)
    recompute_avg_kd(store["players"][clean])
    return store["players"][clean]


def player_score_summary(player: dict) -> dict:
    st_obj = player.get("stats", default_stats())
    cs = sum(x.get("kills", 0) for x in st_obj.get("rank", {}).get("clash_squad", []))
    br = sum(x.get("kills", 0) for x in st_obj.get("rank", {}).get("battle_royale", []))
    avg_kd = recompute_avg_kd(player)
    return {
        "kills": cs + br,
        "avg_kd": avg_kd,
        "composite": round(cs + br + avg_kd * 10.0, 1),
    }


try:
    store = load_store()
except Exception as e:
    st.error("Could not connect to Supabase. Check SUPABASE_URL and SUPABASE_KEY in Streamlit Secrets.")
    st.code(str(e))
    st.stop()

if "logged_player" not in st.session_state:
    st.session_state.logged_player = None
if "force_login" not in st.session_state:
    st.session_state.force_login = False
if "sub_view" not in st.session_state:
    st.session_state.sub_view = None
if "selected_player_view" not in st.session_state:
    st.session_state.selected_player_view = None

logged_name = st.session_state.logged_player
if logged_name not in store["players"]:
    logged_name = None

if os.path.exists("CADENCEnobg.png"):
    _, mid, _ = st.columns([1.2, 1.6, 1.2])
    with mid:
        st.image("CADENCEnobg.png", width=115)
else:
    st.markdown("### CADENCE")

# ==========================================
# LOGIN / REGISTER WITH PASSWORD
# ==========================================
if not logged_name or st.session_state.force_login:
    st.markdown("#### Player Login")
    p_name_raw = st.text_input("Player Name", value=logged_name or "", placeholder="Enter your player name")
    clean_name = p_name_raw.strip()
    existing_player = store["players"].get(clean_name) if clean_name else None

    if existing_player and existing_player.get("auth"):
        pwd = st.text_input("Password", type="password", placeholder="Enter your password")
        if st.button("Login"):
            if not verify_password(pwd, existing_player.get("auth")):
                st.error("Wrong password for this player name.")
            else:
                st.session_state.logged_player = existing_player["player_name"]
                st.session_state.force_login = False
                st.rerun()
    else:
        default_role = existing_player.get("role", ROLES[0]) if existing_player else ROLES[0]
        p_role = st.pills("Role", ROLES, default=default_role)
        pwd = st.text_input("Create Password", type="password", placeholder="At least 4 characters")
        pwd2 = st.text_input("Confirm Password", type="password", placeholder="Re-enter password")

        if st.button("Create Account & Continue"):
            if not clean_name:
                st.error("Enter a player name first.")
            elif len(pwd) < 4:
                st.error("Password must be at least 4 characters.")
            elif pwd != pwd2:
                st.error("Passwords do not match.")
            else:
                rec = ensure_player(store, clean_name, p_role or ROLES[0], password=pwd)
                save_store(store)
                st.session_state.logged_player = rec["player_name"]
                st.session_state.force_login = False
                st.rerun()

    if logged_name and st.button("Cancel"):
        st.session_state.force_login = False
        st.rerun()

    st.stop()

logged_player = store["players"][logged_name]

active_team_name = store.get("active_team")
if active_team_name not in store["teams"] and store["teams"]:
    active_team_name = list(store["teams"].keys())[-1]
    store["active_team"] = active_team_name
    save_store(store)
active_team = store["teams"].get(active_team_name)

st.caption(f"**{logged_player['player_name']}** ({logged_player['role']}) • Team: **{active_team['team_name'] if active_team else 'None'}**")

selected_tab = st.segmented_control(
    "Navigation",
    options=["Team", "Graphs", "Menu"],
    default="Team",
    label_visibility="collapsed",
) or "Team"

if selected_tab != "Team":
    st.session_state.sub_view = None
    st.session_state.selected_player_view = None

# ==========================================
# 1. TEAM TAB
# ==========================================
if selected_tab == "Team":
    if st.session_state.sub_view == "players" and active_team:
        if st.button("← Back to Team"):
            st.session_state.sub_view = None
            st.session_state.selected_player_view = None
            st.rerun()

        st.markdown(f"<div class='team-pill'>{active_team['team_name']}</div>", unsafe_allow_html=True)

        if st.session_state.selected_player_view:
            target_player = ensure_player(store, st.session_state.selected_player_view)
            can_edit = (target_player["player_name"] == logged_player["player_name"])

            if st.button("← Back to Squad"):
                st.session_state.selected_player_view = None
                st.rerun()

            st.markdown(f"**{target_player['player_name']}** — {'Editable' if can_edit else 'View Only'}")
            sec = st.pills("Section", ["Rank", "Training"], default="Rank")

            if sec == "Rank":
                sub_m = st.pills("Mode", ["Clash Squad", "Battle Royale"], default="Clash Squad")
                m_key = "clash_squad" if sub_m == "Clash Squad" else "battle_royale"
                entries = target_player["stats"]["rank"].get(m_key, [])
                total_k = sum(x.get("kills", 0) for x in entries)
                st.progress(min(1.0, total_k / max(25, total_k)), text=f"Kills: {total_k}")

                if can_edit:
                    d_str = st.date_input("Date", value=datetime.date.today()).isoformat()
                    k_val = st.number_input("Kills", min_value=0, step=1, value=0)
                    won_val = st.toggle("Won Match", value=True)
                    if st.button("Save Match"):
                        entries.append({"date": d_str, "kills": int(k_val), "won": bool(won_val)})
                        save_store(store)
                        st.rerun()

                for item in reversed(entries[-8:]):
                    res = "WIN" if item.get("won") else "LOSS"
                    st.markdown(
                        f"<div class='info-pill'>{item.get('date')} | Kills: {item.get('kills')} | {res}</div>",
                        unsafe_allow_html=True,
                    )
            else:
                avg_kd = recompute_avg_kd(target_player)
                st.metric("Average K/D Ratio", f"{avg_kd:.2f}")
                logs = target_player["stats"]["training"].get("logs", [])

                if can_edit:
                    d_str = st.date_input("Date", value=datetime.date.today()).isoformat()
                    kd_val = st.number_input("Game K/D Ratio", min_value=0.0, step=0.1, value=0.0, format="%.2f")
                    kills_val = st.number_input("Kills", min_value=0, step=1, value=0)
                    if st.button("Save Training Game"):
                        logs.append({"date": d_str, "kd": round(float(kd_val), 2), "kills": int(kills_val)})
                        recompute_avg_kd(target_player)
                        save_store(store)
                        st.rerun()

                for item in reversed(logs[-8:]):
                    st.markdown(
                        f"<div class='info-pill'>{item.get('date')} | K/D: {float(item.get('kd', 0.0)):.2f} | Kills: {item.get('kills', 0)}</div>",
                        unsafe_allow_html=True,
                    )
        else:
            for member in active_team.get("members", []):
                ensure_player(store, member)
                if st.button(member, key=f"member_{member}"):
                    st.session_state.selected_player_view = member
                    st.rerun()

            with st.expander("Add Player"):
                new_p = st.text_input("Player Name", key="add_p_name")
                new_r = st.selectbox("Role", ROLES, key="add_p_role")
                new_pw = st.text_input("Password (if new player)", type="password", key="add_p_pw")
                if st.button("Add"):
                    clean_m = new_p.strip()
                    if clean_m:
                        ensure_player(store, clean_m, new_r, password=new_pw or None)
                        if clean_m not in active_team["members"]:
                            active_team["members"].append(clean_m)
                        save_store(store)
                        st.rerun()
    else:
        banner = active_team["team_name"] if active_team else "THE EMPIRE"
        if st.button(banner, key="open_squad_btn"):
            if not active_team:
                store["teams"][banner] = {
                    "team_name": banner,
                    "invite_code": "CAD-01",
                    "members": [logged_player["player_name"]],
                    "invites_sent": [],
                }
                store["active_team"] = banner
                save_store(store)
            st.session_state.sub_view = "players"
            st.rerun()

        saved_teams = list(store["teams"].keys())
        if len(saved_teams) > 1:
            chosen_team = st.selectbox(
                "Switch Team",
                options=saved_teams,
                index=saved_teams.index(active_team_name) if active_team_name in saved_teams else 0,
            )
            if chosen_team != active_team_name:
                store["active_team"] = chosen_team
                save_store(store)
                st.rerun()

        t_name = st.text_input("Team Name", value=active_team["team_name"] if active_team else "THE EMPIRE")
        t_code = st.text_input("Invite Code", value=active_team["invite_code"] if active_team else "CAD-01")

        if st.button("Save Team"):
            clean_t = t_name.strip()
            if clean_t:
                if clean_t in store["teams"]:
                    t_obj = store["teams"][clean_t]
                    t_obj["invite_code"] = t_code.strip() or "CAD-01"
                    if logged_player["player_name"] not in t_obj["members"]:
                        t_obj["members"].append(logged_player["player_name"])
                else:
                    store["teams"][clean_t] = {
                        "team_name": clean_t,
                        "invite_code": t_code.strip() or "CAD-01",
                        "members": [logged_player["player_name"]],
                        "invites_sent": [],
                    }
                store["active_team"] = clean_t
                save_store(store)
                st.rerun()

        with st.expander("Add Team"):
            add_t = st.text_input("New Team Name", key="new_t_name")
            add_c = st.text_input("Invite Code", value="CAD-02", key="new_t_code")
            if st.button("Create Team"):
                clean_add = add_t.strip()
                if clean_add:
                    store["teams"][clean_add] = {
                        "team_name": clean_add,
                        "invite_code": add_c.strip() or "CAD-02",
                        "members": [logged_player["player_name"]],
                        "invites_sent": [],
                    }
                    store["active_team"] = clean_add
                    save_store(store)
                    st.rerun()

# ==========================================
# 2. GRAPHS & TEAM PLAYER RANK TAB
# ==========================================
elif selected_tab == "Graphs":
    members = active_team["members"] if active_team and active_team.get("members") else list(store["players"].keys())
    st.markdown("**Team Player Rank**")

    ranked = []
    for m in members:
        p_rec = ensure_player(store, m)
        ranked.append((m, player_score_summary(p_rec)))
    ranked.sort(key=lambda pair: pair[1]["composite"], reverse=True)

    for idx, (m_name, info) in enumerate(ranked, start=1):
        st.markdown(
            f"<div class='info-pill'>#{idx} {m_name} • Kills: {info['kills']} • Avg K/D: {info['avg_kd']:.2f}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("**Graphs**")
    rng = st.pills("Range", ["Date-wise", "Last 30 Days", "Last 90 Days"], default="Date-wise")
    metric = st.pills("Metric", ["Kills", "Avg K/D", "Games Played"], default="Kills")

    cutoff = None
    if rng == "Last 30 Days":
        cutoff = datetime.date.today() - datetime.timedelta(days=30)
    elif rng == "Last 90 Days":
        cutoff = datetime.date.today() - datetime.timedelta(days=90)

    def in_range(d_str: str) -> bool:
        if not cutoff:
            return True
        try:
            return datetime.date.fromisoformat(d_str) >= cutoff
        except ValueError:
            return True

    rank_games = []
    tr_logs = []
    for m in members:
        s_obj = ensure_player(store, m).get("stats", default_stats())
        for g in s_obj.get("rank", {}).get("clash_squad", []) + s_obj.get("rank", {}).get("battle_royale", []):
            if in_range(g.get("date", "")):
                rank_games.append(g)
        for t in s_obj.get("training", {}).get("logs", []):
            if in_range(t.get("date", "")):
                tr_logs.append(t)

    wins_n = sum(1 for g in rank_games if g.get("won"))
    losses_n = len(rank_games) - wins_n
    win_pct = int((wins_n / len(rank_games)) * 100) if rank_games else 0
    st.caption(f"Games: {len(rank_games) + len(tr_logs)} | W/L: {wins_n}W-{losses_n}L ({win_pct}%)")

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
        st.bar_chart(series, height=200)
    else:
        st.caption("No records for this filter yet.")

# ==========================================
# 3. MENU TAB
# ==========================================
else:
    st.markdown(f"<div class='info-pill'>Player: {logged_player['player_name']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='info-pill'>Role: {logged_player['role']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='info-pill'>Team: {active_team['team_name'] if active_team else 'None'}</div>", unsafe_allow_html=True)

    if st.button("Switch Player"):
        st.session_state.force_login = True
        st.rerun()

    with st.expander("Change Password"):
        old_pw = st.text_input("Current Password", type="password", key="chg_old_pw")
        new_pw = st.text_input("New Password", type="password", key="chg_new_pw")
        if st.button("Update Password"):
            if not verify_password(old_pw, logged_player.get("auth")):
                st.error("Current password is incorrect.")
            elif len(new_pw) < 4:
                st.error("New password must be at least 4 characters.")
            else:
                logged_player["auth"] = hash_password(new_pw)
                save_store(store)
                st.success("Password updated.")