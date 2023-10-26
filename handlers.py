from fastapi import Query, HTTPException
import arxiv
import chromadb
from chromadb.utils import embedding_functions
from utils import *
import os
from prompts import *
import openai
from fastapi.responses import StreamingResponse
from ports import *
from typing import Annotated
import requests
import re
import httpx
from database import *
from collections import defaultdict

Google_API_KEY = os.environ["GOOGLE_API_KEY"]
Google_SEARCH_ENGINE_ID = os.environ["GOOGLE_SEARCH_ENGINE_ID"]

def get_papers(query : str = Query(None,description = "검색 키워드")):
    
    token_limit_exceeded = False
    papers = []
    search_query = "site:arxiv.org " + query
    url = f"https://www.googleapis.com/customsearch/v1?key={Google_API_KEY}&cx={Google_SEARCH_ENGINE_ID}&q={search_query}&start=0"
    res = requests.get(url).json()

    try:
        search_result = res.get("items")

        pattern = r'^\d+\.\d+$'

        paper_list = []

        for i in range(len(search_result)):
            paper_id = search_result[i]['link'].split('/')[-1]
            if paper_id in paper_list:
                continue
            if bool(re.match(pattern, paper_id)):
                paper_list.append(search_result[i]['link'].split('/')[-1])
                
        search = arxiv.Search(
            id_list = paper_list,
            max_results = len(paper_list),
            sort_by = arxiv.SortCriterion.Relevance,
            sort_order = arxiv.SortOrder.Descending
        )

        for result in search.results():
            paper_info={}
            paper_info["paperId"] = result.entry_id.split('/')[-1][:-2]
            paper_info["year"] = int(result.published.year)
            paper_info["title"] = result.title
            paper_info["authors"] = [author.name for author in result.authors]
            paper_info["summary"] = result.summary
            paper_info["url"] = result.entry_id
            paper_info["categories"] = result.categories
            papers.append(paper_info)
    except:
        token_limit_exceeded = True

    search = arxiv.Search(
        query = "'"+query+"'",
        max_results = 20,#50개당 1초 소요 
        sort_by = arxiv.SortCriterion.Relevance,
        sort_order = arxiv.SortOrder.Descending
    )



    for result in search.results():
        paper_info={}
        paper_info["paperId"] = result.entry_id.split('/')[-1][:-2]
        paper_info["year"] = int(result.published.year)
        paper_info["title"] = result.title
        paper_info["authors"] = [author.name for author in result.authors]
        paper_info["summary"] = result.summary
        paper_info["url"] = result.entry_id
        paper_info["categories"] = result.categories
        papers.append(paper_info)


    return  {
        "papers":papers,
        "token_limit_exceeded" : token_limit_exceeded,
    }


async def get_chat(paperId : str = Query(None,description = "논문 ID")):

    client = chromadb.HttpClient(host='10.0.140.252', port=8000)
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.environ['OPENAI_API_KEY'],
                model_name="text-embedding-ada-002"
    )
    search = arxiv.Search(
                    id_list = [paperId],
                    max_results = 1,
                    sort_by = arxiv.SortCriterion.Relevance,
                    sort_order = arxiv.SortOrder.Descending
            )
    result = next(search.results())

    try:
        collection = client.get_collection(paperId, embedding_function=openai_ef)
    except:
        
        prefix = "gs://arxiv-dataset/arxiv/arxiv/pdf"

        src_file_name = os.path.join(prefix,paperId.split('.')[0],result.entry_id.split("/")[-1]+".pdf")

        doc_file_name = os.path.join("./",paperId+".pdf")

        cmd="gsutil -m cp "+src_file_name+" "+doc_file_name

        os.system(cmd)

        if not os.path.exists(doc_file_name):
            doc_file_name = result.download_pdf()

        texts = read_pdf(doc_file_name)

        tokenizer = tiktoken.get_encoding("cl100k_base")
        tokens = tokenizer.encode(texts, disallowed_special=())

        chunks_100 = create_chunks(tokens, 100, tokenizer)
        chunks_5k = create_exact_chunks_with_overlap(tokens, 5000, 500)
        chunks_10k = create_exact_chunks_with_overlap(tokens, 10000, 500)

        text_chunks_100 = [tokenizer.decode(chunk) for chunk in chunks_100]
        text_chunks_5k = [tokenizer.decode(chunk) for chunk in chunks_5k]
        text_chunks_10k = [tokenizer.decode(chunk) for chunk in chunks_10k]


        collection = client.create_collection(name=paperId,metadata = {"hnsw:space": "cosine"}, embedding_function=openai_ef)

        collection.add(
            ids = [str(i) for i in range(len(text_chunks_100))],
            documents = text_chunks_100,
        )
        for chunk in text_chunks_5k:
            context_5k = ContextCreate(text=chunk,paperId=f"{paperId}_5k")
            add_data(context_5k)
        for chunk in text_chunks_10k:
            context_10k = ContextCreate(text=chunk,paperId=f"{paperId}_10k")
            add_data(context_10k)
        os.remove(doc_file_name)




async def post_chat(data: Annotated[dict,{
                    "paperId" : str,
                    "question" : str,
                    "history" : list,
                    "extraPaperId" : str,
                    "underline" : str,
}]):
    id_point = defaultdict(int)
    opt = "10k"

    if data["extraPaperId"] is not None:
        opt = "5k"
    paper_context = []
    extra_context = []


    client = chromadb.HttpClient(host='10.0.140.252', port=8000)
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.environ['OPENAI_API_KEY'],
                model_name="text-embedding-ada-002"
    )

    try:
        collection = client.get_collection(data['paperId'], embedding_function=openai_ef)
        
    except:
        raise HTTPException(status_code=400, detail="잘못된 요청: 임베딩 되지 않은 문서입니다.")

    if data['extraPaperId'] is not None:
        extra_id_point = defaultdict(int)
        try:
            extra_collection = client.get_collection(data['extraPaperId'], embedding_function=openai_ef)
        except:
            await get_chat(data['extraPaperId'])
            extra_collection = client.get_collection(data['extraPaperId'], embedding_function=openai_ef)

        extra_query_results = extra_collection.query(
                query_texts=data['question'],
                n_results=10,
        )
        
        for result in extra_query_results['documents'][0]:
            ctx = ContextCreate(text = result, paperId=f"{data['extraPaperId']}_{opt}")
            search_results = search_data(ctx)
            
            for search_result in search_results:
                id_integer = int(search_result.id)
                extra_id_point[id_integer] += 1

        extra_max_value = max(extra_id_point.values())  # 최대값 찾기
        extra_max_keys = [key for key, value in extra_id_point.items() if value == extra_max_value]
        r = read_data(min(extra_max_keys), f"{data['extraPaperId']}_{opt}")
        extra_context.append(r.text)

    query_results = collection.query(
        query_texts=data['question'],
        n_results=10,
    )

    for result in query_results['documents'][0]:

        ctx = ContextCreate(text = result, paperId=f"{data['paperId']}_{opt}")
        search_results = search_data(ctx)
        for search_result in search_results:
            id_integer = int(search_result.id)
            id_point[id_integer] += 1
            
            
    if data["underline"] is not None:
        ctx = ContextCreate(text = data["underline"], paperId=f"{data['paperId']}_{opt}")
        search_results = search_data(ctx)
        for search_result in search_results:
            id_integer = int(search_result.id)
            id_point[search_result.id] += 10


    max_value = max(id_point.values())  # 최대값 찾기
    max_keys = [key for key, value in id_point.items() if value == max_value]
    r = read_data(min(max_keys), f"{data['paperId']}_{opt}")
    paper_context.append(r.text)
    messages = [
            {"role": "system", "content": MAIN_PROMPT},
            {"role": "user", "content": CHAT_PROMPT},
            {"role": "user", "content": f"***contex(paperid={data['paperId']}) : {paper_context}***"},
    ]

    if data['extraPaperId'] is not None:
        
        messages.append({"role": "user", "content": EXTRA_PAPER_PROMPT})
        messages.append({"role": "user", "content": f"***extra_contex(paperid={data['extraPaperId']}) : {extra_context}***"})

    messages.append({"role": "user","content": f"user's question : {data['question']}"})

    response = openai.ChatCompletion.create(
            model=MODEL,
            messages=messages,
            temperature=0,
            max_tokens = 1000,
            stream = True,
    )

    def generate_chunks():
        for chunk in response:
            try:
                # yield chunk["choices"][0]["delta"].content + "\n"
                yield chunk["choices"][0]["delta"].content
            except:
                yield ""
                
    return StreamingResponse(
        content=generate_chunks(),
        media_type="text/plain"
    )


async def post_coordinates(data: Annotated[dict,{
                    "key" : str,
                    "coordinates" : list,
}]):

    # 대상 서버의 IP 주소와 포트 설정
    target_host = "10.0.129.165"
    target_port = 8080

    # 대상 서버의 URL 생성
    target_url = f"http://{target_host}:{target_port}/api/coordinates?key={data['key']}"

    # httpx를 사용하여 POST 요청 보내기
    async with httpx.AsyncClient() as client:
        payload = {"coordinates": data['coordinates']}  # 요청 데이터 준비
        response = await client.post(target_url, json=payload)

    # 응답 처리
    status_code = response.status_code
    response_data = response.json()

    return {"status_code": status_code, "response_data": response_data}