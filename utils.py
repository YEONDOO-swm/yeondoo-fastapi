from PyPDF2 import PdfReader
import fitz
import tiktoken

def read_pdf(filepath):
    """Takes a filepath to a PDF and returns a string of the PDF's contents"""
    # creating a pdf reader object
    reader = PdfReader(filepath)
    pdf_text = ""
    # page_number = 0
    # prev = None
    # table = []
    for page in reader.pages:
        # page_number += 1
        pdf_text += page.extract_text()
        # pdf_text += page.extract_text() + f"\nPage Number: {page_number}"
    
    # for out in reader.outline:
    #     try:
    #         prev = out['/Title']
    #         table.append(prev)
    #         # print(out['/Title'])
    #     except:
    #         table.append(prev)
    return pdf_text

def read_pdf_and_create_chunks(filepath, n):

    ### READ IN PDF
    doc = fitz.open(filepath)
    tokenizer = tiktoken.get_encoding("cl100k_base")

    text_chunks = []
    meta_chunks = []


    for page_number in range(len(doc)):
        page = doc[page_number]
        texts = page.get_text()

        text_temps = ""
        total_token = 0
        x = []
        y = []

        for text in texts.split('\n'):
            if len(text) == 0:
                continue
            if text[-1] == '-':
                text = text[:-1]

            tokens = tokenizer.encode(text,disallowed_special=())

            if total_token + len(tokens) > n:
                meta_temps = [page_number,min(x),min(y),max(x),max(y)]
                text_chunks.append(text_temps)
                meta_chunks.append(meta_temps)
                text_temps = ""
                total_token = 0
                x.clear()
                y.clear()

            total_token += len(tokens)
            text_temps += text
            text_instances = page.search_for(text)
            if text_instances != None:
                x.append(text_instances[0][0])
                y.append(text_instances[0][1])
                x.append(text_instances[0][2])
                y.append(text_instances[0][3])
                    
                
        if text_temps != "":
            meta_temps = [page_number,min(x),min(y),max(x),max(y)]
            text_chunks.append(text_temps)
            meta_chunks.append(meta_temps)
            text_temps = ""
            total_token = 0
            x.clear()
            y.clear()

    doc.close()

    return text_chunks, meta_chunks


def create_chunks(tokens, n, tokenizer):
    """Returns successive n-sized chunks from provided text."""
    
    # tokens = tokenizer.encode(text,disallowed_special=())
    i = 0
    while i < len(tokens):
        # Find the nearest end of sentence within a range of 0.5 * n and 1.5 * n tokens
        j = min(i + int(1.5 * n), len(tokens))
        while j > i + int(0.5 * n):
            # Decode the tokens and check for full stop or newline
            chunk = tokenizer.decode(tokens[i:j])
            if chunk.endswith(".") or chunk.endswith("\n"):
                break
            j -= 1
        # If no end of sentence found, use n tokens as the chunk size
        if j == i + int(0.5 * n):
            j = min(i + n, len(tokens))
        yield tokens[i:j]
        i = j

