import os
import json
import numpy as np
import faiss
import pickle
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY", "")
client = None
if api_key:
    client = genai.Client(api_key=api_key)

EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIM = 3072

def build_embed_text(entry: dict) -> str:
    parts = [
        entry["name"],
        entry.get("description", ""),
        entry.get("test_type_label", ""),
        " ".join(entry.get("job_levels", [])),
        " ".join(entry.get("tags", [])),
    ]
    return " | ".join(p for p in parts if p)

def get_embedding(text: str) -> np.ndarray:
    try:
        if not client:
            return np.random.rand(EMBEDDING_DIM).astype("float32")
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
        )
        return np.array(result.embeddings[0].values, dtype="float32")
    except Exception as e:
        print(f"Embedding error: {e}")
        return np.random.rand(EMBEDDING_DIM).astype("float32")

def get_embeddings_batch(texts: list[str]) -> np.ndarray:
    """Embed texts one at a time — Gemini batch API returns only 1 result for large batches."""
    embeddings = []
    for i, text in enumerate(texts):
        if (i + 1) % 20 == 0:
            print(f"  Embedding {i+1}/{len(texts)}...")
        vec = get_embedding(text)
        embeddings.append(vec)
    return np.array(embeddings, dtype="float32")

class VectorStore:
    def __init__(self):
        self.index = None
        self.catalog = []

    def load_index(self, catalog_path="catalog.json", index_path="catalog.index", pkl_path="catalog.pkl"):
        if os.path.exists(index_path) and os.path.exists(pkl_path):
            print("Loading existing FAISS index...")
            self.index = faiss.read_index(index_path)
            with open(pkl_path, "rb") as f:
                self.catalog = pickle.load(f)
        else:
            print("Building new FAISS index...")
            if not os.path.exists(catalog_path):
                print("Catalog not found. Cannot build index.")
                return
            with open(catalog_path, "r", encoding="utf-8") as f:
                self.catalog = json.load(f)
            
            if not self.catalog:
                return
                
            texts = [build_embed_text(e) for e in self.catalog]
            vecs = get_embeddings_batch(texts)
            faiss.normalize_L2(vecs)
            
            dim = vecs.shape[1]
            self.index = faiss.IndexFlatIP(dim)
            self.index.add(vecs)
            
            faiss.write_index(self.index, index_path)
            with open(pkl_path, "wb") as f:
                pickle.dump(self.catalog, f)
            print("FAISS index built and saved.")

    def search(self, query: str, top_k: int = 15) -> list[dict]:
        if self.index is None:
            return []
            
        vec = get_embedding(query).reshape(1, -1)
        faiss.normalize_L2(vec)
        
        k = min(top_k, len(self.catalog))
        if k == 0:
            return []
            
        distances, indices = self.index.search(vec, k)
        
        results = []
        for idx in indices[0]:
            if idx < len(self.catalog):
                results.append(self.catalog[idx])
        return results

store = VectorStore()

def load_index():
    store.load_index()

def search_catalog(query: str, k: int = 15) -> list[dict]:
    return store.search(query, top_k=k)
