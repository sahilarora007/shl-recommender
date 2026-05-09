import os
import json
import numpy as np
import faiss
import pickle
from dotenv import load_dotenv

load_dotenv()

EMBEDDING_DIM = 384
_model = None

def _get_model():
    """Lazy-load the model — runs AFTER uvicorn has already bound the port."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # lazy import
        print("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        print("Model loaded.")
    return _model

EMBEDDING_DIM = 384

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
        model = _get_model()
        vec = model.encode(text, normalize_embeddings=True)
        return vec.astype("float32")
    except Exception as e:
        print(f"Embedding error: {e}")
        return np.zeros(EMBEDDING_DIM, dtype="float32")

def get_embeddings_batch(texts: list[str]) -> np.ndarray:
    """Batch encode all texts at once — sentence-transformers handles batching internally."""
    model = _get_model()
    print(f"  Encoding {len(texts)} catalog entries...")
    vecs = model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
    print(f"  Done. Shape: {vecs.shape}")
    return vecs.astype("float32")

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
            print(f"Index loaded: {self.index.ntotal} vectors, dim={self.index.d}")
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

            dim = vecs.shape[1]
            self.index = faiss.IndexFlatIP(dim)
            self.index.add(vecs)

            faiss.write_index(self.index, index_path)
            with open(pkl_path, "wb") as f:
                pickle.dump(self.catalog, f)
            print(f"FAISS index built and saved. {self.index.ntotal} vectors, dim={dim}")

    def search(self, query: str, top_k: int = 15) -> list[dict]:
        if self.index is None:
            return []

        vec = get_embedding(query).reshape(1, -1)
        k = min(top_k, len(self.catalog))
        if k == 0:
            return []

        distances, indices = self.index.search(vec, k)
        return [self.catalog[idx] for idx in indices[0] if idx < len(self.catalog)]

store = VectorStore()

def load_index():
    store.load_index()

def search_catalog(query: str, k: int = 15) -> list[dict]:
    return store.search(query, top_k=k)
