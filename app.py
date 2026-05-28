import os
import json
import time
import secrets
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("PANEL_SECRET_KEY", secrets.token_hex(32))
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

limiter = Limiter(get_remote_address, app=app, default_limits=["120 per minute"])

DATA_PATH = Path(os.getenv("BOT_DATA_PATH", "data.json"))
CONFIG_PATH = Path(os.getenv("PANEL_CONFIG_PATH", "panel_config.json"))
LOG_PATH = Path(os.getenv("PANEL_LOG_PATH", "panel_logs.json"))

ADMIN_USER = os.getenv("PANEL_ADMIN_USER", "admin")
ADMIN_PASSWORD_HASH = os.getenv("PANEL_ADMIN_PASSWORD_HASH")

if not ADMIN_PASSWORD_HASH:
    ADMIN_PASSWORD_HASH = generate_password_hash(os.getenv("PANEL_ADMIN_PASSWORD", "troque-essa-senha"))

def now():
    return int(time.time())

def read_json(path, fallback):
    try:
        if not path.exists():
            return fallback
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def write_json(path, data):
    path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")

def load_data():
    return read_json(DATA_PATH, {})

def save_data(data):
    write_json(DATA_PATH, data)

def load_config():
    default = {
        "bot_name": "Livinho do Maranhão",
        "theme": "neon",
        "idol_user_id": "123456789",
        "idol_role_id": "987654321",
        "rng_channel_id": "",
        "anime_channel_id": "",
        "voice_log_channel_id": "",
        "welcome_message": "Bem-vindo ao painel do bot.",
        "maintenance": False
    }
    config = read_json(CONFIG_PATH, default)
    for key, value in default.items():
        config.setdefault(key, value)
    return config

def save_config(config):
    write_json(CONFIG_PATH, config)

def log_action(action, detail):
    logs = read_json(LOG_PATH, [])
    logs.append({
        "time": now(),
        "action": action,
        "detail": detail,
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr)
    })
    logs = logs[-300:]
    write_json(LOG_PATH, logs)

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def get_user_profile(data, user_id):
    user_id = str(user_id)
    if user_id not in data:
        data[user_id] = {}
    user = data[user_id]
    defaults = {
        "money": 100,
        "xp": 0,
        "rolls": 0,
        "anime_rolls": 0,
        "luck": 1.0,
        "classe": None,
        "melhor_aura": None,
        "melhor_aura_poder": 0,
        "kakera": 0,
        "aura_frag": 0,
        "anime_frag": 0,
        "badges": [],
        "titles": [],
        "harem": []
    }
    for key, value in defaults.items():
        user.setdefault(key, value)
    return user

def sorted_users(data):
    users = []
    for uid, profile in data.items():
        money = int(profile.get("money", 0) or 0)
        xp = int(profile.get("xp", 0) or 0)
        rolls = int(profile.get("rolls", 0) or 0)
        aura = profile.get("melhor_aura") or "Nenhuma"
        users.append({
            "id": uid,
            "money": money,
            "xp": xp,
            "rolls": rolls,
            "aura": aura,
            "power": int(profile.get("melhor_aura_poder", 0) or 0),
            "classe": profile.get("classe") or "Sem classe"
        })
    users.sort(key=lambda u: (u["xp"], u["money"]), reverse=True)
    return users

@app.context_processor
def inject_globals():
    return {"config": load_config(), "year": time.strftime("%Y")}

@app.route("/")
@login_required
def dashboard():
    data = load_data()
    users = sorted_users(data)
    total_money = sum(u["money"] for u in users)
    total_xp = sum(u["xp"] for u in users)
    total_rolls = sum(u["rolls"] for u in users)
    top_users = users[:8]
    logs = read_json(LOG_PATH, [])[-8:][::-1]
    return render_template("dashboard.html", users=users, top_users=top_users, total_money=total_money, total_xp=total_xp, total_rolls=total_rolls, logs=logs)

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("8 per minute")
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == ADMIN_USER and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session.clear()
            session["logged_in"] = True
            session["login_time"] = now()
            log_action("login", "Administrador entrou no painel")
            return redirect(url_for("dashboard"))
        flash("Usuário ou senha incorretos.", "danger")
        log_action("login_failed", f"Tentativa com usuário {username}")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    log_action("logout", "Administrador saiu do painel")
    session.clear()
    return redirect(url_for("login"))

@app.route("/users")
@login_required
def users():
    data = load_data()
    query = request.args.get("q", "").strip().lower()
    users = sorted_users(data)
    if query:
        users = [u for u in users if query in u["id"].lower() or query in u["aura"].lower() or query in u["classe"].lower()]
    return render_template("users.html", users=users, query=query)

@app.route("/users/<user_id>", methods=["GET", "POST"])
@login_required
def edit_user(user_id):
    data = load_data()
    user = get_user_profile(data, user_id)
    if request.method == "POST":
        fields = ["money", "xp", "rolls", "anime_rolls", "kakera", "aura_frag", "anime_frag", "luck"]
        for field in fields:
            value = request.form.get(field)
            if value is None:
                continue
            try:
                user[field] = float(value) if field == "luck" else int(value)
            except ValueError:
                pass
        user["classe"] = request.form.get("classe", "").strip() or None
        user["melhor_aura"] = request.form.get("melhor_aura", "").strip() or None
        try:
            user["melhor_aura_poder"] = int(request.form.get("melhor_aura_poder", 0))
        except ValueError:
            user["melhor_aura_poder"] = 0
        save_data(data)
        log_action("edit_user", f"Editou usuário {user_id}")
        flash("Usuário salvo com sucesso.", "success")
        return redirect(url_for("edit_user", user_id=user_id))
    return render_template("edit_user.html", user=user, user_id=user_id)

@app.route("/users/<user_id>/grant", methods=["POST"])
@login_required
def grant_user(user_id):
    data = load_data()
    user = get_user_profile(data, user_id)
    kind = request.form.get("kind")
    try:
        amount = int(request.form.get("amount", 0))
    except ValueError:
        amount = 0
    if kind in ["money", "xp", "rolls", "anime_rolls", "kakera"] and amount != 0:
        user[kind] = int(user.get(kind, 0) or 0) + amount
        save_data(data)
        log_action("grant_user", f"{kind} {amount:+} para {user_id}")
        flash("Alteração aplicada.", "success")
    else:
        flash("Alteração inválida.", "danger")
    return redirect(url_for("edit_user", user_id=user_id))

@app.route("/commands")
@login_required
def commands():
    catalog = [
        {"name": "/daily", "group": "Economia", "desc": "Pega recompensa diária com moedas e giros."},
        {"name": "/work", "group": "Economia", "desc": "Trabalha para ganhar moedas com cooldown."},
        {"name": "/gamble", "group": "Economia", "desc": "Aposta moedas na roleta."},
        {"name": "/shop", "group": "Loja", "desc": "Mostra itens compráveis."},
        {"name": "/buy", "group": "Loja", "desc": "Compra luck, rolls ou anime rolls."},
        {"name": "/stats", "group": "Perfil", "desc": "Mostra XP, moedas e melhor aura."},
        {"name": "/roll", "group": "Aura RNG", "desc": "Gira uma ou várias auras."},
        {"name": "/auralist", "group": "Aura RNG", "desc": "Lista chances das auras."},
        {"name": "/topaura", "group": "Aura RNG", "desc": "Ranking de melhores auras."},
        {"name": "/boost", "group": "Aura RNG", "desc": "Compra boost de sorte."},
        {"name": "/duel", "group": "Aura RNG", "desc": "Duelo usando poder da melhor aura."},
        {"name": "/wish", "group": "Anime RNG", "desc": "Gira personagens de anime."},
        {"name": "/claim", "group": "Anime RNG", "desc": "Pega o personagem atual."},
        {"name": "/collection", "group": "Anime RNG", "desc": "Mostra coleção de personagens."},
        {"name": "/sell", "group": "Anime RNG", "desc": "Vende personagem da coleção."},
        {"name": "/character", "group": "Servidor", "desc": "Escolhe personagem/classe."},
        {"name": "/rerace", "group": "Servidor", "desc": "Troca ou remove personagem."}
    ]
    return render_template("commands.html", commands=catalog)

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    config = load_config()
    if request.method == "POST":
        for key in config.keys():
            if key == "maintenance":
                config[key] = request.form.get(key) == "on"
            else:
                config[key] = request.form.get(key, config[key]).strip()
        save_config(config)
        log_action("settings", "Atualizou configurações do painel")
        flash("Configurações salvas.", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html", config=config)

@app.route("/logs")
@login_required
def logs():
    logs = read_json(LOG_PATH, [])[::-1]
    return render_template("logs.html", logs=logs)

@app.route("/api/status")
@login_required
def api_status():
    data = load_data()
    users = sorted_users(data)
    return jsonify({
        "ok": True,
        "users": len(users),
        "money": sum(u["money"] for u in users),
        "xp": sum(u["xp"] for u in users),
        "time": now()
    })

@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", code=404, message="Essa página sumiu no multiverso."), 404

@app.errorhandler(429)
def rate_limited(error):
    return render_template("error.html", code=429, message="Calma aí, muitas tentativas em pouco tempo."), 429

if __name__ == "__main__":
    app.run(host=os.getenv("PANEL_HOST", "0.0.0.0"), port=int(os.getenv("PORT", os.getenv("PANEL_PORT", "10000"))))
