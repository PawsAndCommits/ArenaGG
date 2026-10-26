"""Integración con Steam OpenID y Steam Web API (CS2 AppID 730)."""
import re
from urllib.parse import urlencode

import requests
from flask import current_app, request, url_for


STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"
CS2_APPID = 730


def url_login():
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": url_for("usuarios.steam_callback", _external=True),
        "openid.realm": request.url_root.rstrip("/"),
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return f"{STEAM_OPENID_URL}?{urlencode(params)}"


def validar_openid():
    params = {
        "openid.ns": request.args.get("openid.ns"),
        "openid.mode": "check_authentication",
        "openid.op_endpoint": request.args.get("openid.op_endpoint"),
        "openid.claimed_id": request.args.get("openid.claimed_id"),
        "openid.identity": request.args.get("openid.identity"),
        "openid.return_to": request.args.get("openid.return_to"),
        "openid.response_nonce": request.args.get("openid.response_nonce"),
        "openid.assoc_handle": request.args.get("openid.assoc_handle"),
        "openid.signed": request.args.get("openid.signed"),
        "openid.sig": request.args.get("openid.sig"),
    }
    try:
        resp = requests.post(STEAM_OPENID_URL, data=params, timeout=10)
        return "is_valid:true" in resp.text
    except Exception:
        return False


def extraer_steam_id():
    claimed = request.args.get("openid.claimed_id") or request.args.get("openid.identity") or ""
    m = re.search(r"(\d{17})$", claimed)
    if m:
        return m.group(1)
    return None


def resumen_jugador(steamid):
    key = current_app.config.get("STEAM_API_KEY")
    if not key or not steamid:
        return None
    try:
        resp = requests.get(
            "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
            params={"key": key, "steamids": steamid},
            timeout=10,
        )
        data = resp.json()
        players = data.get("response", {}).get("players", [])
        return players[0] if players else None
    except Exception:
        return None


def estadisticas_cs2(steamid):
    key = current_app.config.get("STEAM_API_KEY")
    if not key or not steamid:
        return None
    try:
        resp = requests.get(
            "https://api.steampowered.com/ISteamUserStats/GetUserStatsForGame/v2/",
            params={"key": key, "steamid": steamid, "appid": CS2_APPID},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        stats = data.get("playerstats", {}).get("stats", []) or []
        mapping = {s.get("name"): s.get("value") for s in stats}
        kills = mapping.get("total_kills", 0) or 0
        deaths = mapping.get("total_deaths", 0) or 0
        wins = mapping.get("total_wins", 0) or 0
        rounds_won = mapping.get("total_rounds_won", 0) or 0
        shots_hit = mapping.get("total_shots_hit", 0) or 0
        shots_fired = mapping.get("total_shots_fired", 0) or 0
        kd = round(kills / deaths, 2) if deaths > 0 else float(kills)
        hs_pct = round((shots_hit / shots_fired) * 100, 1) if shots_fired > 0 else 0.0
        return {
            "kills": kills,
            "deaths": deaths,
            "kd": kd,
            "wins": wins,
            "rounds_won": rounds_won,
            "shots_hit": shots_hit,
            "shots_fired": shots_fired,
            "headshot_percentage": hs_pct,
        }
    except Exception:
        return None


def horas_cs2(steamid):
    key = current_app.config.get("STEAM_API_KEY")
    if not key or not steamid:
        return None
    try:
        resp = requests.get(
            "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/",
            params={"key": key, "steamid": steamid, "include_appinfo": 1, "include_played_free_games": 1},
            timeout=10,
        )
        data = resp.json()
        games = data.get("response", {}).get("games", []) or []
        for g in games:
            if g.get("appid") == CS2_APPID:
                minutos = g.get("playtime_forever", 0) or 0
                horas = round(minutos / 60, 1)
                return {"minutes": minutos, "hours": horas}
        return {"minutes": 0, "hours": 0.0}
    except Exception:
        return None
