from fastapi import Query, HTTPException
import arxiv
import chromadb
from chromadb.utils import embedding_functions
from utils import *
import tiktoken
import os
from prompts import *
import openai
from fastapi.responses import StreamingResponse
from ports import *
from typing import Annotated
import requests
import re
import time

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

    # start_time = time.time()

    client = chromadb.HttpClient(host='10.0.140.252', port=port_chroma_db)
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
    # first_time = time.time()
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
        # second_time = time.time()
        text_chunks, meta_chunks = read_pdf_and_create_chunks(doc_file_name, 500)


        collection = client.create_collection(name=paperId,metadata = {"hnsw:space": "cosine"}, embedding_function=openai_ef)

        collection.add(
            ids = [str(i) for i in range(len(text_chunks))],
            documents = text_chunks,
            metadatas = [{"paperId":paperId, "page":meta_chunks[j][0],"x0":meta_chunks[j][1],"y0":meta_chunks[j][2],"x1":meta_chunks[j][3],"y1":meta_chunks[j][4]} for j in range(len(text_chunks))],
        )
        os.remove(doc_file_name)
        # third_time = time.time()

    # messages = [
    #         {"role": "system", "content": GET_CHAT_PROMPT},
    #         {"role": "user", "content": f"ABSTRACT : {result.summary}"},
    # ]

    # response = openai.ChatCompletion.create(
    #         model=MODEL,
    #         messages=messages,
    #         temperature=0,
    #         stream = False,
    # )
                
    # return {
    #     "summary" : response['choices'][0]['message']['content'].split('\n\n')[0].split('\n')[1:],
    #     "questions" : response['choices'][0]['message']['content'].split('\n\n')[1].split('\n')[1:],
    # }

    # return {
    #     "summary" : result.summary,
    #     "first_time" : first_time - start_time,
    #     "second_time" : second_time - first_time,
    #     "third_time" : third_time - second_time
    # }

    return {
        "summary" : result.summary,
    }
 



async def post_chat(data: Annotated[dict,{
                    "paperId" : str,
                    "question" : str,
                    "history" : list,
                    "extraPaperId" : str,
                    "underline" : str,
                    "pageIndex" : int,
}]):
    
    client = chromadb.HttpClient(host='10.0.140.252', port=port_chroma_db)
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.environ['OPENAI_API_KEY'],
                model_name="text-embedding-ada-002"
    )

    try:
        collection = client.get_collection(data['paperId'], embedding_function=openai_ef)
        if data['extraPaperId'] is not None:
            extra_collection = client.get_collection(data['extraPaperId'], embedding_function=openai_ef)
    except:
        raise HTTPException(status_code=400, detail="잘못된 요청: 임베딩 되지 않은 문서입니다.")
    

    query_results = collection.query(
        query_texts=data['question'],
        n_results=2,
    )
    context = [ result for result in query_results['documents'][0]]
    

    if data["underline"] is not None:
        underline_query_results = collection.query(
            query_texts=data["underline"],
            n_results=1,
        )
        underline_context = [ result for result in underline_query_results['documents'][0]]
        context = context + underline_context

    
    messages = [
            {"role": "system", "content": MAIN_PROMPT},
            {"role": "user", "content": CHAT_PROMPT},
            {"role": "user", "content": f"***contex(paperid={data['paperId']}) : {context}***"},
    ]
    if data['extraPaperId'] is not None:
        extra_query_results = extra_collection.query(
            query_texts=data['question'],
            n_results=2,
        )
        extra_context = [ result for result in extra_query_results['documents'][0]]
        messages.append({"role": "user", "content": EXTRA_PAPER_PROMPT})
        messages.append({"role": "user", "content": f"***extra_contex(paperid={data['extraPaperId']}) : {extra_context}***"})
        
    messages.append({"role": "user","content": f"user's question : {data['question']}"})


    response = openai.ChatCompletion.create(
            model=MODEL,
            messages=messages,
            temperature=0,
            stream = False,
    )
    if data['extraPaperId'] is not None:
        return {"answer": response['choices'][0]['message']['content'],
                "coordinates" : [meta for meta in query_results['metadatas'][0]] + [meta for meta in extra_query_results['metadatas'][0]],
                "context" : context,
                "extra_context" : extra_context,
                }
    else:
        return {"answer": response['choices'][0]['message']['content'],
                "coordinates" : [meta for meta in query_results['metadatas'][0]],
                "context" : context,
                }