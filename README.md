# 🎓 Selçuk Üniversitesi RAG Asistanı

Selçuk Üniversitesi yönetmeliklerini sorgulayan, yapay zeka destekli bir chatbot uygulamasıdır. PDF dokümanlarından bilgi çıkararak soruları **kaynak göstererek** yanıtlar.

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

## 📂 Proje Yapısı

```
Selcuk_RAG_Cloud/
├── app.py                # Streamlit arayüzü ve sohbet mantığı
├── rag_engine.py         # RAG zinciri, retriever ve LLM motoru
├── data_ingestion.py     # PDF → ChromaDB veri aktarım scripti
├── requirements.txt      # Sabitlenmiş bağımlılıklar
├── .env.example          # Ortam değişkenleri şablonu
├── data/                 # Kaynak PDF yönetmelikleri
│   ├── Burs Yönergesi.pdf
│   ├── Çift Ana Dal Yönergesi.pdf
│   ├── Diploma ... Yönerge.pdf
│   ├── Haklı ve Geçerli Mazeretler Yönergesi.pdf
│   └── Staj Yönergesi.pdf
├── chroma_db/            # Oluşturulan vektör veritabanı (git'te yok)
└── .devcontainer/        # GitHub Codespaces yapılandırması
```

## 💡 Kullanım

- **Soru sorun**: Metin kutusuna yönetmeliklerle ilgili sorularınızı yazın
- **PDF yükleyin**: Yan menüden ek PDF dokümanları yükleyerek oturum süresince asistanın bilgi tabanını genişletin
- **Kaynakları görün**: Her cevabın altındaki "📚 Kaynakları Gör" ile hangi dokümanlardan yanıt üretildiğini kontrol edin

## ☁️ Codespaces ile Kullanım

Proje, GitHub Codespaces ile tek tıkla çalışmaya hazırdır. `.devcontainer` yapılandırması otomatik olarak tüm bağımlılıkları kurar ve Streamlit'i başlatır.

> **Not**: `GROQ_API_KEY` ortam değişkenini Codespaces Secrets'a eklemeyi unutmayın.
