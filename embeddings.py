#!/usr/bin/env python3
"""
Generate embeddings for signals using sentence-transformers (local, multilingual)
"""

from sentence_transformers import SentenceTransformer
import math
import numpy as np

# Load multilingual model
print("Loading model (first time only, takes ~1 min)...")
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

def get_embedding(text):
    """Get embedding for a text"""
    return model.encode(text, convert_to_tensor=False)

def cosine_similarity(vec1, vec2):
    """Calculate cosine similarity"""
    if vec1 is None or vec2 is None or len(vec1) == 0 or len(vec2) == 0:
        return 0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a ** 2 for a in vec1))
    magnitude2 = math.sqrt(sum(b ** 2 for b in vec2))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0
    
    return dot_product / (magnitude1 * magnitude2)

if __name__ == "__main__":
    text1 = "Εκκένωση πληθυσμού από τον Νότιο Λίβανο"
    text2 = "Χιλιάδες άνθρωποι φεύγουν από το Λίβανο"
    
    print("Generating embeddings...")
    emb1 = get_embedding(text1)
    emb2 = get_embedding(text2)
    
    similarity = cosine_similarity(emb1, emb2)
    print(f"✅ Similarity: {similarity:.2%}")
    
    if similarity >= 0.85:
        print("✅ These are duplicates!")
    else:
        print("❌ These are different signals")
