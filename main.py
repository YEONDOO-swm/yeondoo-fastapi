from fastapi import FastAPI, Depends
from typing import Annotated
from handlers import *
from ports import *
import uvicorn


app = FastAPI()

# def run():
#     log_config_path = "./log/log.ini"
#     uvicorn.run('main:app', host="0.0.0.0",port=port_uvicorn, reload=True,log_config=log_config_path)

# if __name__ == '__main__':
#     run()

@app.get("/")
async def root():
    return {"message": "Hello World"}
@app.get("/papers")
async def get_api_papers(result_papers: Annotated[dict, Depends(get_papers)]):
    return result_papers

@app.post("/chat")
async def post_api_chat(answer: Annotated[dict, Depends(post_chat)]):
    return answer

@app.get("/chat")
async def get_api_chat(answer: Annotated[dict, Depends(get_chat)]):
    return answer
    
@app.post("/coordinates")
async def post_api_coordinates(answer: Annotated[dict, Depends(get_chat)]):
    return answer