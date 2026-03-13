import os
import shutil
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# Klasör Yolları
DATA_DIR = "./data"
DB_DIR = "./chroma_db"

def statik_veritabani_olustur():
    print("🧹 Eski veritabanı temizleniyor...")
    if os.path.exists(DB_DIR):
        shutil.rmtree(DB_DIR)
        
    print(f"📥 '{DATA_DIR}' klasöründeki PDF'ler okunuyor...")
    loader = PyPDFDirectoryLoader(DATA_DIR)
    docs = loader.load()
    print(f"✅ Toplam {len(docs)} sayfa bulundu.")

    print("✂️ Metinler anlam bütünlüğüne göre parçalanıyor...")
    # Akademik metinler için 1000 karakter idealdir, overlap ile bağlam kopmaz
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    parcalar = text_splitter.split_documents(docs)
    print(f"✅ Toplam {len(parcalar)} parça oluşturuldu.")

    print("🧠 Vektörler (Embeddings) oluşturulup Chroma'ya kaydediliyor...")
    embedding_model = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
    
    Chroma.from_documents(
        documents=parcalar,
        embedding=embedding_model,
        persist_directory=DB_DIR
    )

    print("🚀 İŞLEM TAMAM! Statik veritabanı kusursuz bir şekilde hazırlandı.")

if __name__ == "__main__":
    statik_veritabani_olustur()     