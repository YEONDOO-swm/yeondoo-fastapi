from fastapi import FastAPI, Depends
from typing import Annotated
from handlers import *
import uvicorn


app = FastAPI()

def run():
    log_config_path = "./log/log.ini"
    uvicorn.run('main:app', host="0.0.0.0",port=8000, reload=True,log_config=log_config_path)


@app.get("/papers")
async def get_api_papars(result_papers: Annotated[dict, Depends(get_papars)]):
    return result_papers

@app.post("/chat")
async def post_api_chat(answer: Annotated[dict, Depends(post_chat)]):
    return answer
    
    
if __name__ == '__main__':
    run()