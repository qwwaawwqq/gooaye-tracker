#!/usr/bin/env python3
"""
Hermes Task: embed_660_episodes
Purpose: Embed all 660 episodes' descriptions to vector DB for semantic search.
Run once after Hermes setup: hermes run embed_660_episodes.py
"""

import json
import os
from pathlib import Path

# Hermes provides these via its SDK
from hermes import vector_store, openai_client  # adjust import per Hermes docs

GOOAYE_JSON = Path.home() / "Documents/Claude/Projects/股癌/股癌_全集歷史_660集.json"
COLLECTION_NAME = "gooaye_episodes"

def main():
    print("📚 Loading 660 episodes...")
    with open(GOOAYE_JSON) as f:
        data = json.load(f)
    episodes = data['episodes']
    print(f"  ✓ Loaded {len(episodes)} episodes")

    print("🧠 Creating vector collection...")
    collection = vector_store.create_or_get(COLLECTION_NAME)

    print("🔄 Embedding episodes (batch of 100)...")
    batch_size = 100
    for i in range(0, len(episodes), batch_size):
        batch = episodes[i:i+batch_size]
        texts = [
            f"EP{e['ep']} {e['title']}\n{e['description_preview']}"
            for e in batch
        ]
        # OpenAI embedding (cheap: $0.02/M tokens)
        embeddings = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=texts
        ).data

        # Upsert to vector store
        for e, emb in zip(batch, embeddings):
            collection.upsert(
                id=str(e['ep']),
                vector=emb.embedding,
                metadata={
                    'ep': e['ep'],
                    'date': e['date'],
                    'title': e['title'],
                    'duration_min': e['duration_min'],
                    'snippet': e['description_preview'][:300],
                }
            )
        print(f"  ✓ Embedded {min(i+batch_size, len(episodes))}/{len(episodes)}")

    print(f"\n🎉 Done! {len(episodes)} episodes embedded to '{COLLECTION_NAME}'")
    print(f"   Estimated cost: ~$0.50 (one-time)")
    print(f"\nTry: hermes search '{COLLECTION_NAME}' 'NVIDIA 估值'")

if __name__ == "__main__":
    main()
