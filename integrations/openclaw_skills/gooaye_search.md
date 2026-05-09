# OpenClaw Skill: gooaye_search

## Purpose
Semantic search across all 660 episodes (delegates to Hermes for vector search).

## Trigger phrases
- "找股癌講過 [topic]"
- "search gooaye for [keyword]"
- "EP for [topic]"

## Implementation

### Without Hermes (simple regex search)
```python
# Quick text search across 660 episodes JSON
import json, re

with open(os.path.expanduser('~/Documents/Claude/Projects/股癌/股癌_全集歷史_660集.json')) as f:
    data = json.load(f)

def search(keyword):
    matches = []
    for ep in data['episodes']:
        text = ep['title'] + ' ' + ep['description_preview']
        if keyword.lower() in text.lower():
            matches.append({
                'ep': ep['ep'],
                'date': ep['date'],
                'title': ep['title'],
                'snippet': text[:200]
            })
    return matches[:10]  # top 10

# Example: "找講過 NVIDIA" → top 10 EPs mentioning NVIDIA
```

### With Hermes (semantic search via vector DB)
```python
# Delegate to Hermes Agent
import requests

resp = requests.post(
    "http://YOUR_HERMES_HOST:PORT/api/search",
    json={"query": user_query, "top_k": 5}
)
results = resp.json()
# Returns: [{ep: 645, similarity: 0.87, snippet: "..."}, ...]
```

## Example interactions

User: "找股癌講過 NVIDIA 估值"
Claw: 找到 5 集相關：
      📍 EP645 (3/21) - NVIDIA 轉型 AI 工廠 (similarity 0.91)
      📍 EP623 (1/4) - NVDA 估值偏高警示 (0.85)
      📍 EP590 (9/15) - PCB 弱勢 + NVDA 持續強 (0.78)
      📍 EP540 (3/12) - NVDA 法說後動能 (0.74)
      📍 EP480 (8/24) - AI 軍備期 NVDA 主導 (0.71)

User: "找升息週期相關"
Claw: 找到主要集數：
      📍 EP200-310 (2022) - 升息週期主軸期
      📍 EP280 - 「Fed 不會這麼快降」
      📍 EP295 - 「降息預期過早」

## Skill metadata
- name: gooaye_search
- delegates_to: hermes-agent
- fallback: local-regex
