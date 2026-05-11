---
title: Selcuk RAG Asistan
emoji: 🎓
colorFrom: blue
colorTo: indigo
sdk: streamlit
app_file: app.py
pinned: false
---

# Selcuk RAG Asistan

Selcuk RAG Asistan, Selcuk Universitesi yonetmelik ve yonergeleri icin hazirlanmis Streamlit tabanli bir RAG asistanidir.

## Ozellikler

- ChromaDB tabanli retrieval
- Groq LLM ile cevap uretimi
- Metadata-aware rerank
- Belge, madde, sayfa ve URL kaynak gosterimi
- Inline citation ve kaynak paneli eslesmesi

## Gerekli Secrets

- `GROQ_API_KEY`
- `ADMIN_PASSWORD` opsiyonel

## Onerilen Variables

- `FLASHRANK_ENABLED=false`
- `METADATA_RERANK_ENABLED=true`
- `MULTI_QUERY_ENABLED=true`
- `MULTI_QUERY_LEGAL_SAFE_MODE=true`
- `METADATA_RERANK_CANDIDATE_K=25`
- `FINAL_CONTEXT_DOCS=4`
- `MAX_CONTEXT_CHARS=4000`

## Test Sorulari

- AKTS nedir?
- Selcuk Universitesi lisansustu egitiminde AKTS ne anlama gelir?
- Selcuk Universitesi'nde tez izleme komitesi kac ogretim uyesinden olusur?
- Selcuk Universitesi'nde doktora yeterlik sinavlari ile ilgili esaslar nelerdir?
