from pydantic import BaseModel

class chat_dto(BaseModel):
    paperId: str
    query: str
    history: list # [(question1,answer1),(question2,answer2)...]