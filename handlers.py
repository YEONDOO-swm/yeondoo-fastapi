from fastapi import Query
import arxiv
import chromadb
from chromadb.utils import embedding_functions
from utils import read_pdf, create_chunks
import tiktoken
import os
from prompts import *
import openai
from fastapi.responses import StreamingResponse
# sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

async def get_papars(keyword : str = Query(None,description = "검색 키워드")):
    

    search = arxiv.Search(
    query = "'"+keyword+"'",
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

async def post_chat(paperId : str = Query(None,description = "논문 ID"),
                    question : str = Query(None,description = "사용자 질문"),
                    history : list = Query(None,description = "채팅 히스토리")):
    # todo history {role: assistant, content: } , {role: user, content: } 
    # chat_history_tuples = []
    # for message in data.history:
    #     chat_history_tuples.append((message[0], message[1]))
    
    # with get_openai_callback() as cb:
    #     chain = ConversationalRetrievalChain_yeondoo.from_llm(OpenAI(temperature=0,max_tokens=512), docsearch.as_retriever(),combine_docs_chain_kwargs={"prompt": CHAT_PROMPT})
    #     outs = chain({"question": data.query,"paper_id":data.paperId,"chat_history":chat_history_tuples})    

    # return {"answer": outs['answer'], "track":{"totalTokens":cb.total_tokens,"promptTokens":cb.prompt_tokens,"completionTokens":cb.completion_tokens,"totalCost":cb.total_cost}}
    
    # 1. history를 튜플로 변환하는 로직
    # 2. 토큰 사용량을 추적하는 로직
    # 3. Paper id를 가지고 chroma db에서 해당 collection을 찾고,
    client = chromadb.HttpClient(host='10.0.140.252', port=8000)
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.environ['OPENAI_API_KEY'],
                model_name="text-embedding-ada-002"
    )
    try:
        collection = client.get_collection(paperId, embedding_function=openai_ef)
    except:
        collection = client.create_collection(name=paperId, embedding_function=openai_ef)
        search = arxiv.Search(
                    id_list = [paperId],
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
        query_texts=[question],
        n_results=1,
        # todo meta filtering
    )

    messages = [
            {"role": "system", "content": MAIN_PROMPT},
            {"role": "user", "content": CHAT_PROMPT},
            {"role": "user", "content": f"contex : {query_results['documents'][0][0]}"},
            {"role": "user","content": f"user's question : {question}"}
    ]
    response = openai.ChatCompletion.create(
            model=MODEL,
            messages=messages,
            temperature=0,
            stream = True,
    )
    def generate_chunks_default():
            for chunk in response:
                yield chunk
    
    return StreamingResponse(
        content=generate_chunks_default(),
        media_type="text/plain"
    )
    # db에 hit하면. collection 내부에서 가장 유사한 구절 1개를 가져오기
    # db에 hit하지 않으면, paper id를 이름으로 collection을 만들고, "."단위로 끊어서 임베딩하기