from langchain_openai import ChatOpenAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.document_loaders import PDFPlumberLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

template = """
You are a RAG chatbot assistant responsible for retrieving information from a PDF file containing working policies and regulations, and answering users’ questions.
Question: {question}
Context: {context}
Answer:
"""

# The RAG pipeline (LLM + embedded PDF) is built lazily on first use so this
# module imports cleanly without RITS_*/BASE_URL configured, and the heavy
# embedding/PDF work only happens when a query is actually made.
_chain = None
_vector_store = None


def _build():
    global _chain, _vector_store
    if _chain is not None:
        return
    api_key = os.getenv("RITS_API_KEY")
    api_url = os.getenv("RITS_BASE_URL")
    model = os.getenv("RITS_MODEL")
    base_url = os.getenv("BASE_URL", "")

    embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")
    _vector_store = InMemoryVectorStore(embeddings)
    llm = ChatOpenAI(model=model, api_key=api_key, base_url=api_url)
    _chain = ChatPromptTemplate.from_template(template) | llm

    pdf_path = (
        base_url + "examples/RagChatbot_MCPServer/pdfs/work_rules_and_regulations_2016.pdf"
    )
    documents = PDFPlumberLoader(pdf_path).load()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200, add_start_index=True
    )
    _vector_store.add_documents(text_splitter.split_documents(documents))


def raw_ask_for_workpolicy(question: str) -> str:
    _build()
    relevant_docs = _vector_store.similarity_search(question)
    context = "\n\n".join([doc.page_content for doc in relevant_docs])
    result = _chain.invoke({"question": question, "context": context})
    return result.content
