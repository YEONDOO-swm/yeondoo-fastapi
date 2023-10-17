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
# sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
Google_API_KEY = os.environ["GOOGLE_API_KEY"]
Google_SEARCH_ENGINE_ID = os.environ["GOOGLE_SEARCH_ENGINE_ID"]

def get_papers(query : str = Query(None,description = "검색 키워드")):
    
    papers = []
    search_query = "site:arxiv.org " + query
    url = f"https://www.googleapis.com/customsearch/v1?key={Google_API_KEY}&cx={Google_SEARCH_ENGINE_ID}&q={search_query}&start=0"
    res = requests.get(url).json()

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
        papers.append(paper_info)

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
        
        papers.append(paper_info)


    return  {
        "papers":papers
    }

# async def post_chat(data: Annotated[dict,{
#                     "paperId" : str,
#                     "question" : str,
#                     "history" : list,
# }]):
#     total_cost = 0
#     client = chromadb.HttpClient(host='10.0.140.252', port=port_chroma_db)
#     openai_ef = embedding_functions.OpenAIEmbeddingFunction(
#                 api_key=os.environ['OPENAI_API_KEY'],
#                 model_name="text-embedding-ada-002"
#     )

#     #여기는 무조건 get_chat 다음에 온다고 가정하고 예외처리만하자 임베딩 기능 제거
#     #단, 포스트맨 디버깅 시에만 사용할것
#     try:
#         collection = client.get_collection(data['paperId'], embedding_function=openai_ef)
#     except:
        

#         search = arxiv.Search(
#                     id_list = [data['paperId']],
#                     max_results = 1,
#                     sort_by = arxiv.SortCriterion.Relevance,
#                     sort_order = arxiv.SortOrder.Descending
#                 )
#         result = next(search.results())
#         doc_file_name = result.download_pdf()

#         pdf_text, table = read_pdf(doc_file_name)
        
#         tokenizer = tiktoken.get_encoding("cl100k_base")
   
#         chunks = create_chunks(pdf_text, 1500, tokenizer)
#         text_chunks = [tokenizer.decode(chunk) for chunk in chunks]
        
#         # embedding 비용 계산 로직 -> embedding price도 넘겨줘야 할 듯?
#         collection = client.create_collection(name=data['paperId'], embedding_function=openai_ef)
#         collection.add(
#             ids = [str(i) for i in range(len(text_chunks))],
#             documents = text_chunks,
#             metadatas = [{"index":table[j]} for j in range(len(text_chunks))],
#         )
#         os.remove(doc_file_name)

#     query_results = collection.query(
#         query_texts=[data['question']],
#         n_results=3,
#         # todo meta filtering
#     )
#     context = [ result for result in query_results['documents'][0]]
#     messages = [
#             {"role": "system", "content": MAIN_PROMPT},
#             {"role": "user", "content": CHAT_PROMPT},
#             {"role": "user", "content": f"contex : {context}"},
#             {"role": "user","content": f"user's question : {data['question']}"}
#     ]

#     response = openai.ChatCompletion.create(
#             model=MODEL,
#             messages=messages,
#             temperature=0,
#             stream = False,
#     )
#     # "track":{"totalTokens":response['usage']['total_tokens'],
#     #                  "promptTokens":response['usage']['prompt_tokens'],
#     #                  "completionTokens":response['usage']['completion_tokens']
#     return {"answer": response['choices'][0]['message']['content'], 
#             "totalCost": total_cost,
#             }
    # def generate_chunks():
    #         for chunk in response:
    #             try:
    #                 # yield chunk["choices"][0]["delta"].content + "\n"
    #                 yield chunk["choices"][0]["delta"].content
    #             except:
    #                  yield ""
                
    # return StreamingResponse(
    #     content=generate_chunks(),
    #     media_type="text/plain"
    # )
    # Todo 
    # 1. history {role: assistant, content: } , {role: user, content: } 
    # 2. 토큰 사용량을 추적하는 로직
    # 3. 임베딩 gpt function -> local function

# async def get_chat(paperId : str = Query(None,description = "논문 ID"), credit: int = Query(None,description = "남은 크레딧 달러")):
#     embedding_tokens = 0
#     client = chromadb.HttpClient(host='10.0.140.252', port=port_chroma_db)
#     openai_ef = embedding_functions.OpenAIEmbeddingFunction(
#                 api_key=os.environ['OPENAI_API_KEY'],
#                 model_name="text-embedding-ada-002"
#     )
#     search = arxiv.Search(
#                     id_list = [paperId],
#                     max_results = 1,
#                     sort_by = arxiv.SortCriterion.Relevance,
#                     sort_order = arxiv.SortOrder.Descending
#             )
#     result = next(search.results())
#     try:
#         collection = client.get_collection(paperId, embedding_function=openai_ef)
#     except:
        

#         doc_file_name = result.download_pdf()

#         pdf_text = read_pdf(doc_file_name)

#         tokenizer = tiktoken.get_encoding("cl100k_base")

#         tokens = tokenizer.encode(pdf_text,disallowed_special=())

#         embedding_tokens = len(tokens)
#         # embedding_tokens -> get_price(model,len(tokens))->price
#         if credit < embedding_tokens:
#             raise HTTPException(status_code=402, detail="Payment Required")
        
#         chunks = create_chunks(tokens, 1500, tokenizer)
#         # chunks = create_chunks(pdf_text, 1500, tokenizer)

#         text_chunks = [tokenizer.decode(chunk) for chunk in chunks]
#         # embedding 비용 계산 로직 -> embedding price도 넘겨줘야 할 듯?
#         # 토큰양이 특정 범위를 벗어나는 경우 예외처리하기
#         collection = client.create_collection(name=paperId, embedding_function=openai_ef)

#         collection.add(
#             ids = [str(i) for i in range(len(text_chunks))],
#             documents = text_chunks,
#             metadatas = [{"coordinate":coordinate_chunks[j]} for j in range(len(text_chunks))],
#         )
#         os.remove(doc_file_name)


#     messages = [
#             {"role": "system", "content": GET_CHAT_PROMPT},
#             {"role": "user", "content": f"ABSTRACT : {result.summary}"},
#     ]

#     response = openai.ChatCompletion.create(
#             model=MODEL,
#             messages=messages,
#             temperature=0,
#             stream = False,
#     )
                
#     return {
#         "summary" : response['choices'][0]['message']['content'].split('\n\n')[0].split('\n')[1:],
#         "questions" : response['choices'][0]['message']['content'].split('\n\n')[1].split('\n')[1:],
#         "embeddingTokens" : embedding_tokens,
#     }


async def get_chat(paperId : str = Query(None,description = "논문 ID")):

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
    try:
        collection = client.get_collection(paperId, embedding_function=openai_ef)
    except:
        
        doc_file_name = result.download_pdf()
        text_chunks, meta_chunks = read_pdf_and_create_chunks(doc_file_name, 120)

        # embedding 비용 계산 로직 -> embedding price도 넘겨줘야 할 듯?
        # 토큰양이 특정 범위를 벗어나는 경우 예외처리하기
        collection = client.create_collection(name=paperId,metadata = {"hnsw:space": "cosine"}, embedding_function=openai_ef)

        collection.add(
            ids = [str(i) for i in range(len(text_chunks))],
            documents = text_chunks,
            metadatas = [{"page":meta_chunks[j][0],"x0":meta_chunks[j][1],"y0":meta_chunks[j][2],"x1":meta_chunks[j][3],"y1":meta_chunks[j][4]} for j in range(len(text_chunks))],
        )
        os.remove(doc_file_name)


    messages = [
            {"role": "system", "content": GET_CHAT_PROMPT},
            {"role": "user", "content": f"ABSTRACT : {result.summary}"},
    ]

    response = openai.ChatCompletion.create(
            model=MODEL,
            messages=messages,
            temperature=0,
            stream = False,
    )
                
    return {
        "summary" : response['choices'][0]['message']['content'].split('\n\n')[0].split('\n')[1:],
        "questions" : response['choices'][0]['message']['content'].split('\n\n')[1].split('\n')[1:],
    }


async def post_chat(data: Annotated[dict,{
                    "paperId" : str,
                    "question" : str,
                    "history" : list,
                    "extraPaperId" : str,
                    "underline" : str,
}]):

    client = chromadb.HttpClient(host='10.0.140.252', port=port_chroma_db)
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.environ['OPENAI_API_KEY'],
                model_name="text-embedding-ada-002"
    )

    #여기는 무조건 get_chat 다음에 온다고 가정하고 예외처리만하자 임베딩 기능 제거
    #단, 포스트맨 디버깅 시에만 사용할것
    try:
        collection = client.get_collection(data['paperId'], embedding_function=openai_ef)
    except:
        raise HTTPException(status_code=400, detail="잘못된 요청: 임베딩 되지 않은 문서입니다.")
    
    

    messages = [
            {"role": "system", "content": QUESTION_PROMPT},
            {"role": "user","content": data['question']}
    ]

    response = openai.ChatCompletion.create(
                model=MODEL,
                messages=messages,
                temperature=0,
    )
    rich_question = response['choices'][0]['message']['content']

    query_results = collection.query(
        query_texts=rich_question,
        n_results=1,
    )
    context = [ result for result in query_results['documents'][0]]
    messages = [
            {"role": "system", "content": MAIN_PROMPT},
            {"role": "user", "content": CHAT_PROMPT},
            {"role": "user", "content": f"contex : {context}"},
            {"role": "user","content": f"user's question : {data['question']}"}
    ]

    response = openai.ChatCompletion.create(
            model=MODEL,
            messages=messages,
            temperature=0,
            stream = False,
    )

    return {"answer": response['choices'][0]['message']['content'],
            "coordinates" : query_results['metadatas'][0][0],
            }