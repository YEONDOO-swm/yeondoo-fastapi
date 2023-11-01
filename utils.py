from PyPDF2 import PdfReader
import fitz
import tiktoken
import re
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

    doc = fitz.open(filepath)
    tokenizer = tiktoken.get_encoding("cl100k_base")

    text_chunks = []
    meta_chunks = []

    for page_number in range(len(doc)):
        page = doc[page_number]
        texts = page.get_text("blocks")
        

        text_tmp = ""

        flag = False

        x_min = -1
        x_max = -1
        y_min = -1
        y_max = -1
        for text in texts:
            if text[6] == 1:
                continue
            if flag == False:
                flag = True
                x_min = text[0]
                x_max = text[2]
                y_min = text[1]
                y_max = text[3]
            text_tmp += text[4]

            tokens = tokenizer.encode(text_tmp,disallowed_special=())
            x_min = min(x_min,text[0])
            x_max = max(x_max,text[2])
            y_min = min(y_min,text[1])
            y_max = max(y_max,text[3])

            if len(tokens) >= n:
                text_chunks.append(text_tmp)
                meta_chunks.append([page_number,x_min,y_min,x_max,y_max])
                text_tmp = ""
                flag = False
        if text_tmp != "" and len(text_tmp)>=10:
            text_chunks.append(text_tmp)
            meta_chunks.append([page_number,x_min,y_min,x_max,y_max])
            text_tmp = ""
            flag = False

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

def create_chunks_with_overlap(tokens, n, tokenizer, overlap):
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

        if j >= len(tokens):
            yield tokens[-n:]
            break
        else:
            yield tokens[i:j]
     
        k = j - overlap
        if k < 0:
            k = 0
        i = k

def create_exact_chunks_with_overlap(tokens, n, overlap):
    i = 0
    j = 0
    while i < len(tokens):
        # Find the nearest end of sentence within a range of 0.5 * n and 1.5 * n tokens
        j += n
        if j >= len(tokens):
            yield tokens[-n:]
            break
        else:
            yield tokens[i:j]
        i = j
        i -= overlap

def extract_reference(pdf_text, paperId):
    ret = []
    try:
        reference_pattern = re.compile(r'(?i)(arXiv:|CoRR, abs/)([0-9]{4}\.[0-9]{4,6}|.*\.[0.9]{7})')

        # reference_pattern = re.compile(r'(?i)(arXiv:([0-9]{4}\.[0-9]{4,6}|.*\.[0-9]{7}))|(?i)(CoRR, abs/([0-9]{4}\.[0-9]{4,6}|.*\.[0-9]{7}))')
        matches = reference_pattern.findall(pdf_text)
        for match in matches:
            reference = match[1] if match[1] else match[3]
            if reference != paperId:
                ret.append(reference)

    except Exception as e:
        print(e)

    return ret