import os
from dotenv import load_dotenv

# updated imports
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from loader import load_and_split

load_dotenv()

def build_index():
    # 1. Load & chunk
    docs = load_and_split("../data")
    print(f"* Loaded {len(docs)} docs")
    # drop any that are empty
    docs = [d for d in docs if getattr(d, "page_content", "").strip()]
    if not docs:
        raise RuntimeError("No non-empty documents to index. Check your loader and data path.")

    # 2. Embed & persist to Chroma
    embedder = OpenAIEmbeddings()
    vectordb = Chroma.from_documents(
        documents=docs,
        embedding=embedder,
        persist_directory="vectordb/"
    )
    vectordb.persist()
    print("✅ Vectorstore built and saved to ./vectordb")

if __name__ == "__main__":
    build_index()