from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Session, relationship
import datetime

DATABASE_URL = "sqlite:///./polla.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    nombre = Column(String, nullable=False)
    pin_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    icon_emoji = Column(String, default="⚽")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    predictions = relationship("Prediction", back_populates="user")
    special = relationship("SpecialPrediction", back_populates="user", uselist=False)

class Match(Base):
    __tablename__ = "matches"
    id = Column(String, primary_key=True)
    stage = Column(String, nullable=False)
    group_name = Column(String, nullable=True)
    team_home = Column(String, nullable=False)
    team_away = Column(String, nullable=False)
    score_home = Column(Integer, nullable=True)
    score_away = Column(Integer, nullable=True)
    match_datetime = Column(String, nullable=False)
    venue = Column(String, nullable=True)
    is_finished = Column(Boolean, default=False)
    is_locked = Column(Boolean, default=False)
    predictions = relationship("Prediction", back_populates="match")

class Prediction(Base):
    __tablename__ = "predictions"
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    match_id = Column(String, ForeignKey("matches.id"), primary_key=True)
    score_home = Column(Integer, nullable=False)
    score_away = Column(Integer, nullable=False)
    points_earned = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)
    user = relationship("User", back_populates="predictions")
    match = relationship("Match", back_populates="predictions")

class SpecialPrediction(Base):
    __tablename__ = "special_predictions"
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    champion = Column(String, nullable=True)
    runner_up = Column(String, nullable=True)
    top_scorer = Column(String, nullable=True)
    pts_champion = Column(Integer, default=0)
    pts_runner_up = Column(Integer, default=0)
    pts_top_scorer = Column(Integer, default=0)
    user = relationship("User", back_populates="special")

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = Session(engine)
    try:
        yield db
    finally:
        db.close()
