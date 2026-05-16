import json, uuid, bcrypt
from database import engine, Base, Match, User, init_db
from sqlalchemy.orm import Session

def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode()[:72], bcrypt.gensalt()).decode()

def seed_matches():
    with open("data/matches.json", encoding="utf-8") as f:
        data = json.load(f)
    with Session(engine) as db:
        if db.query(Match).count() > 0:
            print("Matches already seeded"); return
        for m in data:
            db.add(Match(
                id=m["id"], stage=m["stage"], group_name=m["group_name"],
                team_home=m["team_home"], team_away=m["team_away"],
                score_home=m["score_home"], score_away=m["score_away"],
                match_datetime=m["match_date"], venue=m.get("venue",""),
            ))
        db.commit()
        print(f"Seeded {len(data)} matches")

def seed_admin():
    with Session(engine) as db:
        if db.query(User).filter_by(username="admin").first():
            print("Admin ya existe"); return
        db.add(User(id=str(uuid.uuid4()), username="admin",
                    nombre="Administrador", pin_hash=hash_pin("0000"), is_admin=True))
        db.commit()
        print("Admin creado (user=admin, pin=0000)")

if __name__ == "__main__":
    init_db(); seed_matches(); seed_admin()
