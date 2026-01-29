import os
import faiss
import requests
import numpy as np
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

DEFAULT_DOC_ID = os.getenv("GOOGLE_DOC_ID")

class RagEngine:
    def __init__(self, doc_id: str = DEFAULT_DOC_ID):
        self.embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.dimension = 384
        self.index = faiss.IndexFlatL2(self.dimension)
        self.chunks = []

        if doc_id:
            self.load_from_google_doc(doc_id)

    def load_from_google_doc(self, doc_id: str):
        url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
        try:
            response = requests.get(url)
            response.raise_for_status()
            text = response.text
            self.chunks = [t.strip() for t in text.split('\n\n') if len(t.strip()) > 10]
            if self.chunks:
                embeddings = self.embedder.encode(self.chunks)
                self.index.add(np.array(embeddings).astype('float32'))
        except Exception as e:
            print(f"{e}")

    def search(self, query: str, k: int = 2) -> str:
        if not self.chunks or self.index.ntotal == 0:
            return ""
        query_vec = self.embedder.encode([query])
        distances, indices = self.index.search(np.array(query_vec).astype('float32'), k)
        results = []
        for idx in indices[0]:
            if idx != -1 and idx < len(self.chunks):
                results.append(self.chunks[idx])
        return "\n---\n".join(results)

rag = RagEngine()