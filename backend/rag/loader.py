import os
from dotenv import load_dotenv
from typing import List
import yaml
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

# Load environment variables if needed
load_dotenv()

def load_and_split(
    input_path: str,
    chunk_size: int = 800,
    overlap: int = 200
) -> List[Document]:
    """
    Load PDF and Markdown files from `input_path` (file or directory),
    parse Markdown front-matter metadata manually, then split into text chunks.
    """
    # 1. Gather file paths
    pdf_paths: List[str] = []
    md_paths: List[str] = []

    if os.path.isdir(input_path):
        for fn in os.listdir(input_path):
            full = os.path.join(input_path, fn)
            lower = fn.lower()
            if lower.endswith(".pdf"):
                pdf_paths.append(full)
            elif lower.endswith(".md"):
                md_paths.append(full)
    else:
        lower = input_path.lower()
        if lower.endswith(".pdf"):
            pdf_paths = [input_path]
        elif lower.endswith(".md"):
            md_paths = [input_path]
        else:
            raise ValueError(f"No .pdf or .md files found at {input_path!r}")

    # 2. Load documents
    docs: List[Document] = []

    # PDFs via PyPDFLoader
    for path in pdf_paths:
        loader = PyPDFLoader(path)
        for d in loader.load():
            d.metadata.setdefault("source", os.path.basename(path))
            docs.append(d)

    # Markdown: manual front-matter parse
    for path in md_paths:
        with open(path, 'r', encoding='utf-8') as f:
            raw = f.read()
        metadata = {}
        content = raw
        if raw.startswith('---'):
            parts = raw.split('---', 2)
            if len(parts) >= 3:
                header = parts[1]
                content = parts[2].lstrip('\n')
                try:
                    metadata = yaml.safe_load(header) or {}
                except yaml.YAMLError:
                    metadata = {}
        docs.append(Document(page_content=content, metadata=metadata))

    if not docs:
        raise RuntimeError(f"No documents loaded from {input_path!r}")

    # 3. Split into chunks, preserving metadata
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap
    )
    split_docs = splitter.split_documents(docs)

    if not split_docs:
        raise RuntimeError("No document chunks created.")

    return split_docs

if __name__ == "__main__":
    path = "./data"
    chunks = load_and_split(path)
    print(f"Loaded and split into {len(chunks)} chunks from {path}")
