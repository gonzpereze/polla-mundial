# bracket.py
from sqlalchemy.orm import Session
from database import Match

def get_group_standings_raw(db: Session, group: str) -> list:
    matches = db.query(Match).filter_by(stage="group", group_name=group).all()
    teams: dict[str, dict] = {}
    for m in matches:
        for team in [m.team_home, m.team_away]:
            if team and team not in teams:
                teams[team] = {"team": team, "pts": 0, "gf": 0, "gc": 0, "pj": 0}
        if m.score_home is None:
            continue
        sh, sa, th, ta = m.score_home, m.score_away, m.team_home, m.team_away
        if not th or not ta:
            continue
        teams[th]["pj"] += 1; teams[ta]["pj"] += 1
        teams[th]["gf"] += sh; teams[th]["gc"] += sa
        teams[ta]["gf"] += sa; teams[ta]["gc"] += sh
        if sh > sa:
            teams[th]["pts"] += 3
        elif sa > sh:
            teams[ta]["pts"] += 3
        else:
            teams[th]["pts"] += 1; teams[ta]["pts"] += 1
    return sorted(teams.values(), key=lambda t: (-t["pts"], -(t["gf"] - t["gc"]), -t["gf"], t["team"]))

# Slots R32: mapeo de match_id a qué posiciones de grupos van en cada slot
R32_SLOTS = {
    "R32-01": ("1A", "2B"), "R32-02": ("1C", "2D"), "R32-03": ("1E", "2F"), "R32-04": ("1G", "2H"),
    "R32-05": ("1I", "2J"), "R32-06": ("1K", "2L"), "R32-07": ("2A", "1B"), "R32-08": ("2C", "1D"),
    "R32-09": ("2E", "1F"), "R32-10": ("2G", "1H"), "R32-11": ("2I", "1J"), "R32-12": ("2K", "1L"),
    "R32-13": ("3rd-1", "3rd-2"), "R32-14": ("3rd-3", "3rd-4"),
    "R32-15": ("3rd-5", "3rd-6"), "R32-16": ("3rd-7", "3rd-8"),
}

def resolve_r32_placeholders(db: Session):
    groups = "ABCDEFGHIJKL"
    standings = {g: get_group_standings_raw(db, g) for g in groups}
    all_done = all(
        all(m.is_finished for m in db.query(Match).filter_by(stage="group", group_name=g).all())
        for g in groups
    )
    for mid, (ph, pa) in R32_SLOTS.items():
        r32 = db.query(Match).filter_by(id=mid).first()
        if not r32 or r32.is_finished:
            continue

        def resolve(slot: str) -> str | None:
            if slot.startswith("3rd"):
                return None
            pos = int(slot[0]) - 1
            grp = slot[1]
            st = standings.get(grp, [])
            return st[pos]["team"] if len(st) > pos else None

        th = resolve(ph); ta = resolve(pa)
        if th:
            r32.team_home = th
        if ta:
            r32.team_away = ta

    if all_done:
        thirds = []
        for g in groups:
            st = standings[g]
            if len(st) >= 3:
                t = dict(st[2]); t["group"] = g; thirds.append(t)
        thirds.sort(key=lambda t: (-t["pts"], -(t["gf"] - t["gc"]), -t["gf"]))
        best8 = [t["team"] for t in thirds[:8]]
        third_slots = ["R32-13", "R32-14", "R32-15", "R32-16"]
        for i, sid in enumerate(third_slots):
            r32 = db.query(Match).filter_by(id=sid).first()
            if r32:
                if i * 2 < len(best8):
                    r32.team_home = best8[i * 2]
                if i * 2 + 1 < len(best8):
                    r32.team_away = best8[i * 2 + 1]
    db.commit()

def resolve_knockout_winner(db: Session, match: Match):
    if match.score_home is None or match.score_home == match.score_away:
        return
    winner = match.team_home if match.score_home > match.score_away else match.team_away
    loser = match.team_away if match.score_home > match.score_away else match.team_home
    next_stage = {
        "round_of_32": "round_of_16",
        "round_of_16": "quarter_final",
        "quarter_final": "semi_final",
        "semi_final": "final",
    }.get(match.stage)
    if not next_stage:
        return
    num = int(match.id.split("-")[1])
    next_num = (num + 1) // 2
    prefix = {"round_of_16": "R16", "quarter_final": "QF", "semi_final": "SF", "final": "F"}[next_stage]
    next_id = f"{prefix}-{next_num:02d}"
    nm = db.query(Match).filter_by(id=next_id).first()
    if nm:
        if num % 2 == 1:
            nm.team_home = winner
        else:
            nm.team_away = winner
    if match.stage == "semi_final":
        tp = db.query(Match).filter_by(id="TP-01").first()
        if tp:
            if match.id == "SF-01":
                tp.team_home = loser
            else:
                tp.team_away = loser
    db.commit()
