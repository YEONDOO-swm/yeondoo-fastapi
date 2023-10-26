from fastapi import Depends, HTTPException
from sqlalchemy import create_engine, Column, String, Text, Integer, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel
import os


# SQLAlchemy 연결 설정
db_url = f"mysql+pymysql://{os.environ['DB_ID']}:{os.environ['DB_PW']}@{os.environ['DB_DOMAIN']}/MAIN"
engine = create_engine(db_url)

# SQLAlchemy 세션 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# SQLAlchemy 모델 정의
Base = declarative_base()

class Context(Base):
    __tablename__ = "test2"
    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(Text)
    paperId = Column(String(255))

# Pydantic 모델 (API 요청용)
class ContextCreate(BaseModel):
    text: str
    paperId: str

class ContextQuery(BaseModel):
    paperId: str
    text: str

class ContextResponse(BaseModel):
    id: int
    text: str
    paperId: str
    

# FastAPI 엔드포인트: paperId와 text로 데이터 조회

def search_data(query: ContextCreate):
    db = SessionLocal()
    results = db.query(Context).filter(Context.paperId == query.paperId, Context.text.like(f"%{query.text}%")).all()
    db.close()
    return results


# FastAPI 엔드포인트: 데이터 추가
# @app.post("/add_data", response_model=TestCreate)
def add_data(src: ContextCreate):
    db = SessionLocal()
    db_data = Context(**src.dict())
    db.add(db_data)
    db.commit()
    db.refresh(db_data)
    db.close()
    return db_data

def read_data(item_id: int, paper_id: str):
    db = SessionLocal()
    tar_data = db.query(Context).filter(and_(Context.id == item_id, Context.paperId == paper_id)).first()
    db.close()
    if tar_data is None:
        raise HTTPException(status_code=404, detail="Data not found")
    return ContextResponse(id=tar_data.id, text=tar_data.text, paperId=tar_data.paperId)

def get_paper_data(paper_id: str):
    db = SessionLocal()
    data = db.query(Context).filter(Context.paperId == paper_id).first()
    db.close()
    if data is None:
        raise HTTPException(status_code=404, detail="Data not found")
    return ContextResponse(paperId=data.paperId, context=data.context)