from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.document_loaders import PDFPlumberLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
# Init components
api_key = os.getenv("RITS_API_KEY", None)
api_url = os.getenv("RITS_BASE_URL", None)
model = os.getenv("RITS_MODEL", None)

embeddings = HuggingFaceEmbeddings(model_name='BAAI/bge-small-en-v1.5')
vector_store = InMemoryVectorStore(embeddings)
model = ChatOpenAI(model=model)

template = """
You are a RAG chatbot assistant responsible for retrieving information from a PDF file containing salary/compensation information, and answering users’ questions.
Question: {question}
Context: {context}
Answer:
"""

# Setup prompt templatetext-embedding-ada-002
prompt = ChatPromptTemplate.from_template(template)
chain = prompt | model

# Load and index PDF (done only once, before answering)
base_url = os.getenv("BASE_URL", None)
pdf_path = base_url + "examples/RagChatbot_MCPServer/pdfs/salary_summary.pdf"

loader = PDFPlumberLoader(pdf_path)
documents = loader.load()

# Split and index
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    add_start_index=True
)
chunks = text_splitter.split_documents(documents)
vector_store.add_documents(chunks)


def raw_ask_for_salary(question: str) -> str:
    relevant_docs = vector_store.similarity_search(question)
    context = "\n\n".join([doc.page_content for doc in relevant_docs])
    result = chain.invoke({"question": question, "context": context})
    return result.content
