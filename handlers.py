from fastapi import Query
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
# sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

async def get_papers(query : str = Query(None,description = "검색 키워드")):
    

    search = arxiv.Search(
    query = "'"+query+"'",
    max_results = 50,#50개당 1초 소요 
    sort_by = arxiv.SortCriterion.Relevance,
    sort_order = arxiv.SortOrder.Descending
    )

    papers = []

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

async def post_chat(data: Annotated[dict,{
                    "paperId" : str,
                    "question" : str,
                    "history" : list,
}]):

    client = chromadb.HttpClient(host='10.0.140.252', port=port_chroma_db)
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.environ['OPENAI_API_KEY'],
                model_name="text-embedding-ada-002"
    )
    try:
        collection = client.get_collection(data['paperId'], embedding_function=openai_ef)
    except:
        collection = client.create_collection(name=data['paperId'], embedding_function=openai_ef)

        search = arxiv.Search(
                    id_list = [data['paperId']],
                    max_results = 1,
                    sort_by = arxiv.SortCriterion.Relevance,
                    sort_order = arxiv.SortOrder.Descending
                )
        result = next(search.results())
        doc_file_name = result.download_pdf()

        pdf_text, table = read_pdf(doc_file_name)

        tokenizer = tiktoken.get_encoding("cl100k_base")
   
        chunks = create_chunks(pdf_text, 1500, tokenizer)
        text_chunks = [tokenizer.decode(chunk) for chunk in chunks]
        collection.add(
            ids = [str(i) for i in range(len(text_chunks))],
            documents = text_chunks,
            metadatas = [{"index":table[i]} for i in range(len(text_chunks))],
        )
        os.remove(doc_file_name)

    query_results = collection.query(
        query_texts=[data['question']],
        n_results=1,
        # todo meta filtering
    )

    messages = [
            {"role": "system", "content": MAIN_PROMPT},
            {"role": "user", "content": CHAT_PROMPT},
            {"role": "user", "content": f"contex : {query_results['documents'][0][0]}"},
            {"role": "user","content": f"user's question : {data['question']}"}
    ]

    response = openai.ChatCompletion.create(
            model=MODEL,
            messages=messages,
            temperature=0,
            stream = True,
    )
    
    def generate_chunks():
            for chunk in response:
                try:
                    yield chunk["choices"][0]["delta"].content
                except:
                     yield ""
                
    return StreamingResponse(
        content=generate_chunks(),
        media_type="text/plain"
    )
    # Todo 
    # 1. history {role: assistant, content: } , {role: user, content: } 
    # 2. 토큰 사용량을 추적하는 로직
    # 3. 임베딩 gpt function -> local function

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
        collection = client.create_collection(name=paperId, embedding_function=openai_ef)

        doc_file_name = result.download_pdf()

        pdf_text, table = read_pdf(doc_file_name)

        tokenizer = tiktoken.get_encoding("cl100k_base")
   
        chunks = create_chunks(pdf_text, 1500, tokenizer)
        text_chunks = [tokenizer.decode(chunk) for chunk in chunks]
        collection.add(
            ids = [str(i) for i in range(len(text_chunks))],
            documents = text_chunks,
            metadatas = [{"index":table[i]} for i in range(len(text_chunks))],
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
        "question" : response['choices'][0]['message']['content'].split('\n\n')[1].split('\n')[1:],
    }