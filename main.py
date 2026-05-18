# main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from collections import defaultdict
import json as json_mod, uuid, datetime

from database import get_db, User, Match, Prediction, SpecialPrediction, init_db
from auth import hash_pin, verify_pin, create_token, get_current_user, require_admin
from scoring import calculate_points, calculate_special_points
from bracket import resolve_r32_placeholders, resolve_knockout_winner

app = FastAPI(title="Polla Mundial 2026")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")

with open("data/flags.json", encoding="utf-8") as f:
    FLAGS = json_mod.load(f)

@app.on_event("startup")
def startup():
    init_db()

@app.get("/", include_in_schema=False)
def root():
    return FileResponse("static/index.html")

# ── Helpers ───────────────────────────────────────────────────────────────────

def match_dict(m: Match, pred: Prediction | None = None) -> dict:
    d = {"id": m.id, "stage": m.stage, "group_name": m.group_name,
         "team_home": m.team_home, "team_away": m.team_away,
         "flag_home": FLAGS.get(m.team_home, "🏳️"),
         "flag_away": FLAGS.get(m.team_away, "🏳️"),
         "score_home": m.score_home if m.is_finished else None,
         "score_away": m.score_away if m.is_finished else None,
         "match_datetime": m.match_datetime, "venue": m.venue,
         "is_finished": m.is_finished, "is_locked": m.is_locked,
         "user_prediction": None}
    if pred:
        d["user_prediction"] = {"score_home": pred.score_home, "score_away": pred.score_away,
                                 "points_earned": pred.points_earned}
    return d

def calc_standings(matches: list[dict]) -> list:
    teams: dict[str, dict] = {}
    for m in matches:
        for team, flag in [(m["team_home"], m["flag_home"]), (m["team_away"], m["flag_away"])]:
            if team and team not in teams:
                teams[team] = {"team": team, "flag": flag,
                               "pj": 0, "g": 0, "e": 0, "p": 0, "gf": 0, "gc": 0, "pts": 0}
        if not m["is_finished"]:
            continue
        sh, sa, th, ta = m["score_home"], m["score_away"], m["team_home"], m["team_away"]
        if not th or not ta:
            continue
        teams[th]["pj"] += 1; teams[ta]["pj"] += 1
        teams[th]["gf"] += sh; teams[th]["gc"] += sa
        teams[ta]["gf"] += sa; teams[ta]["gc"] += sh
        if sh > sa:
            teams[th]["g"] += 1; teams[th]["pts"] += 3; teams[ta]["p"] += 1
        elif sa > sh:
            teams[ta]["g"] += 1; teams[ta]["pts"] += 3; teams[th]["p"] += 1
        else:
            teams[th]["e"] += 1; teams[th]["pts"] += 1; teams[ta]["e"] += 1; teams[ta]["pts"] += 1
    ranked = sorted(teams.values(), key=lambda t: (-t["pts"], -(t["gf"] - t["gc"]), -t["gf"], t["team"]))
    for i, t in enumerate(ranked):
        t["pos"] = i + 1; t["dif"] = t["gf"] - t["gc"]
    return ranked

# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterIn(BaseModel):
    username: str; nombre: str; pin: str

class LoginIn(BaseModel):
    username: str; pin: str

@app.post("/api/auth/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if len(body.pin) != 4 or not body.pin.isdigit():
        raise HTTPException(400, "PIN debe ser 4 dígitos")
    if db.query(User).filter_by(username=body.username.lower()).first():
        raise HTTPException(400, "Username ya existe")
    u = User(id=str(uuid.uuid4()), username=body.username.lower(),
             nombre=body.nombre, pin_hash=hash_pin(body.pin))
    db.add(u); db.commit()
    return {"token": create_token(u.id, u.username, u.is_admin),
            "user": {"id": u.id, "username": u.username, "nombre": u.nombre, "is_admin": u.is_admin}}

@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(username=body.username.lower()).first()
    if not u or not verify_pin(body.pin, u.pin_hash):
        raise HTTPException(401, "Usuario o PIN incorrecto")
    return {"token": create_token(u.id, u.username, u.is_admin),
            "user": {"id": u.id, "username": u.username, "nombre": u.nombre, "is_admin": u.is_admin}}

@app.get("/api/me")
def me(user=Depends(get_current_user)):
    return user

@app.get("/api/flags")
def get_flags():
    return FLAGS

# ── Partidos ──────────────────────────────────────────────────────────────────

@app.get("/api/matches")
def get_matches(db: Session = Depends(get_db), user=Depends(get_current_user)):
    matches = db.query(Match).all()
    preds = {p.match_id: p for p in db.query(Prediction).filter_by(user_id=user["sub"]).all()}
    return [match_dict(m, preds.get(m.id)) for m in matches]

@app.get("/api/groups")
def get_groups(db: Session = Depends(get_db), user=Depends(get_current_user)):
    group_matches = db.query(Match).filter_by(stage="group").all()
    preds = {p.match_id: p for p in db.query(Prediction).filter_by(user_id=user["sub"]).all()}
    groups: dict[str, list] = defaultdict(list)
    for m in group_matches:
        groups[m.group_name].append(match_dict(m, preds.get(m.id)))
    return {g: {"matches": ms, "standings": calc_standings(ms)} for g, ms in sorted(groups.items())}

@app.get("/api/bracket")
def get_bracket(db: Session = Depends(get_db), user=Depends(get_current_user)):
    stages = ["round_of_32", "round_of_16", "quarter_final", "semi_final", "third_place", "final"]
    preds = {p.match_id: p for p in db.query(Prediction).filter_by(user_id=user["sub"]).all()}
    return {s: [match_dict(m, preds.get(m.id)) for m in db.query(Match).filter_by(stage=s).all()] for s in stages}

# ── Predicciones ──────────────────────────────────────────────────────────────

class PredIn(BaseModel):
    match_id: str; score_home: int; score_away: int

@app.get("/api/predictions/mine")
def my_preds(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return [{"match_id": p.match_id, "score_home": p.score_home, "score_away": p.score_away,
             "points_earned": p.points_earned}
            for p in db.query(Prediction).filter_by(user_id=user["sub"]).all()]

@app.post("/api/predictions")
def save_pred(body: PredIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    m = db.query(Match).filter_by(id=body.match_id).first()
    if not m:
        raise HTTPException(404, "Partido no encontrado")
    if m.is_locked or m.is_finished:
        raise HTTPException(400, "Partido bloqueado")
    p = db.query(Prediction).filter_by(user_id=user["sub"], match_id=body.match_id).first()
    if p:
        p.score_home = body.score_home; p.score_away = body.score_away
        p.updated_at = datetime.datetime.utcnow()
    else:
        db.add(Prediction(user_id=user["sub"], match_id=body.match_id,
                          score_home=body.score_home, score_away=body.score_away))
    db.commit()
    return {"ok": True}

# ── Especiales ────────────────────────────────────────────────────────────────

class SpecialIn(BaseModel):
    champion: str | None = None
    runner_up: str | None = None
    top_scorer: str | None = None

@app.get("/api/special/mine")
def my_special(db: Session = Depends(get_db), user=Depends(get_current_user)):
    sp = db.query(SpecialPrediction).filter_by(user_id=user["sub"]).first()
    if not sp:
        return {}
    return {"champion": sp.champion, "runner_up": sp.runner_up, "top_scorer": sp.top_scorer,
            "pts_champion": sp.pts_champion, "pts_runner_up": sp.pts_runner_up, "pts_top_scorer": sp.pts_top_scorer}

@app.post("/api/special")
def save_special(body: SpecialIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sp = db.query(SpecialPrediction).filter_by(user_id=user["sub"]).first()
    if sp:
        sp.champion = body.champion; sp.runner_up = body.runner_up; sp.top_scorer = body.top_scorer
    else:
        db.add(SpecialPrediction(user_id=user["sub"], champion=body.champion,
                                  runner_up=body.runner_up, top_scorer=body.top_scorer))
    db.commit()
    return {"ok": True}

# ── Leaderboard ───────────────────────────────────────────────────────────────

@app.get("/api/leaderboard")
def leaderboard(db: Session = Depends(get_db), user=Depends(get_current_user)):
    board = []
    for u in db.query(User).all():
        match_pts = sum(p.points_earned for p in u.predictions)
        sp = u.special
        special_pts = (sp.pts_champion + sp.pts_runner_up + sp.pts_top_scorer) if sp else 0
        board.append({"user_id": u.id, "username": u.username, "nombre": u.nombre, "icon": u.icon_emoji,
                      "match_points": match_pts, "special_points": special_pts,
                      "total_points": match_pts + special_pts, "is_current_user": u.id == user["sub"]})
    board.sort(key=lambda x: -x["total_points"])
    for i, r in enumerate(board):
        r["rank"] = i + 1
    return board

# ── Admin ─────────────────────────────────────────────────────────────────────

class ResultIn(BaseModel):
    match_id: str; score_home: int; score_away: int

@app.post("/api/admin/result")
def enter_result(body: ResultIn, db: Session = Depends(get_db), _=Depends(require_admin)):
    m = db.query(Match).filter_by(id=body.match_id).first()
    if not m:
        raise HTTPException(404, "Partido no encontrado")
    m.score_home = body.score_home; m.score_away = body.score_away
    m.is_finished = True; m.is_locked = True; db.commit()
    preds = db.query(Prediction).filter_by(match_id=body.match_id).all()
    for p in preds:
        p.points_earned = calculate_points(body.score_home, body.score_away, p.score_home, p.score_away)
    db.commit()
    if m.stage == "group":
        resolve_r32_placeholders(db)
    else:
        resolve_knockout_winner(db, m)
    return {"ok": True, "predictions_updated": len(preds)}

@app.get("/api/admin/users")
def list_users(db: Session = Depends(get_db), _=Depends(require_admin)):
    return [{"id": u.id, "username": u.username, "nombre": u.nombre, "is_admin": u.is_admin}
            for u in db.query(User).all()]

@app.post("/api/admin/lock/{match_id}")
def lock_match(match_id: str, db: Session = Depends(get_db), _=Depends(require_admin)):
    m = db.query(Match).filter_by(id=match_id).first()
    if not m:
        raise HTTPException(404)
    m.is_locked = True; db.commit()
    return {"ok": True}
