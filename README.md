# 🎓 Selçuk Üniversitesi RAG Asistanı

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://selcuk-rag-asistan.streamlit.app/)
[![CI](https://github.com/maliblgn/Selcuk_RAG_Asistan/actions/workflows/ci.yml/badge.svg)](https://github.com/maliblgn/Selcuk_RAG_Asistan/actions/workflows/ci.yml)

🔗 **Canlı Demo:** [https://selcuk-rag-asistan.streamlit.app](https://selcuk-rag-asistan.streamlit.app/)

Selçuk Üniversitesi yönetmeliklerini sorgulayan, yapay zeka destekli bir chatbot uygulamasıdır. PDF dokümanlarından bilgi çıkararak soruları yanıtlar.

## 🛠️ Teknoloji Yığını

| Bileşen | Teknoloji |
|---|---|
| **UI** | Streamlit |
| **LLM** | Groq API (Llama 3.1 8B Instant) |
| **Embedding** | HuggingFace `intfloat/multilingual-e5-small` |
| **Vektör DB** | ChromaDB |
| **Framework** | LangChain |

## 📋 Gereksinimler

- Python 3.11+
- Groq API anahtarı ([console.groq.com](https://console.groq.com) üzerinden alınır)

## 🚀 Kurulum

```bash
# 1. Sanal ortam oluştur
python -m venv venv

# 2. Sanal ortamı aktifleştir
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Bağımlılıkları yükle
pip install -r requirements.txt

# 4. API anahtarını ayarla
cp .env.example .env
# .env dosyasına GROQ_API_KEY değerini girin

# 5. Veritabanını oluştur (ilk kurulumda bir kere)
python data_ingestion.py

# 6. Uygulamayı başlat
streamlit run app.py
```

## 🧪 Testler

```bash
pytest tests/ -v
```

## 📂 Proje Yapısı

```
Selcuk_RAG_Asistan/
├── app.py                # Streamlit arayüzü ve sohbet mantığı
├── rag_engine.py         # RAG zinciri, retriever ve LLM motoru
├── data_ingestion.py     # PDF → ChromaDB veri aktarım scripti
├── requirements.txt      # Bağımlılıklar
├── .env.example          # Ortam değişkenleri şablonu
├── data/                 # Kaynak PDF yönetmelikleri
│   ├── Burs Yönergesi.pdf
│   ├── Çift Ana Dal Yönergesi.pdf
│   ├── Diploma ... Yönerge.pdf
│   ├── Haklı ve Geçerli Mazeretler Yönergesi.pdf
│   └── Staj Yönergesi.pdf
├── chroma_db/            # Vektör veritabanı
├── tests/                # Pytest birim testleri
│   └── test_rag_engine.py
├── .github/
│   └── workflows/
│       └── ci.yml        # GitHub Actions CI pipeline
└── .devcontainer/        # GitHub Codespaces yapılandırması
```

## 💡 Kullanım

- **Soru sorun**: Metin kutusuna yönetmeliklerle ilgili sorularınızı yazın
- **PDF yükleyin**: Yan menüden ek PDF dokümanları yükleyerek oturum süresince asistanın bilgi tabanını genişletin
- **Kaynak alıntısı**: Her yanıtın sonunda `📄 Kaynak: <belge adı>` bilgisi görünür

## ☁️ Codespaces ile Kullanım

Proje, GitHub Codespaces ile tek tıkla çalışmaya hazırdır. `.devcontainer` yapılandırması otomatik olarak tüm bağımlılıkları kurar ve Streamlit'i başlatır.

> **Not**: `GROQ_API_KEY` ortam değişkenini Codespaces Secrets'a eklemeyi unutmayın.
