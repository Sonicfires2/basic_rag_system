import os
from dotenv import load_dotenv
from typing import List
from pydantic import PrivateAttr

# Updated imports
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain.chains import RetrievalQA
from langchain.schema import BaseRetriever, Document
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

# Load environment variables
load_dotenv()

txt = """
You are a research assistant. Whenever asked, use the provided context to answer the question.
"""
system_msg = SystemMessagePromptTemplate.from_template(txt)
human_msg = HumanMessagePromptTemplate.from_template("""
Context:
{context}

Question: {question}
""")

chat_prompt = ChatPromptTemplate.from_messages([system_msg, human_msg])

class RecentRetriever(BaseRetriever):
    _base: BaseRetriever = PrivateAttr()
    _fetch_k: int = PrivateAttr()
    _return_k: int = PrivateAttr()

    def __init__(self, base_retriever: BaseRetriever, fetch_k: int = 20, return_k: int = 4):
        super().__init__()
        self._base = base_retriever
        self._fetch_k = fetch_k
        self._return_k = return_k

    def _get_relevant_documents(self, query: str) -> List[Document]:
        docs = self._base.get_relevant_documents(query, k=self._fetch_k)
        # keep only dated docs
        docs = [d for d in docs if d.metadata.get("date")]
        # sort by date descending
        docs.sort(key=lambda d: d.metadata["date"], reverse=True)

        # inject metadata into content for LLM
        for d in docs:
            md = d.metadata
            header = (
                f"Title: {md.get('title', '')}\n"
                f"Date:  {md.get('date', '')}\n"
                f"URL:   {md.get('url', '')}\n\n"
            )
            d.page_content = header + d.page_content

        # return top-k most recent
        return docs[: self._return_k]


def main():
    # 1) Load vectorstore
    vectordb = Chroma(
        persist_directory="vectordb/",
        embedding_function=OpenAIEmbeddings()
    )

    # 2) Wrap retriever for recency
    base_ret = vectordb.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 5, "fetch_k": 20, "lambda_mult": 0.5},
    )
    recent_ret = RecentRetriever(base_ret)

    # debug: show base documents
    base_docs = base_ret.get_relevant_documents("Altis Labs news", k=10)
    for d in base_docs:
        print(d.metadata, d.page_content[:100])
    
    # Create LLM without system_message override
    llm = ChatOpenAI(model_name="gpt-4", temperature=0.0)

    # Build RetrievalQA with custom prompt
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=recent_ret,
        chain_type_kwargs={"prompt": chat_prompt}
    )

    # 5) Interactive loop
    while True:
        q = input("\n🔍 Your question (or 'exit'): ")
        if q.strip().lower() == "exit":
            break
        ans = qa_chain.run(q)
        print(f"\n💡 Answer:\n{ans}\n")

if __name__ == "__main__":
    main()