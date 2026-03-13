import os
import shutil
import logging
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Klasör Yolları (her zaman bu dosyanın bulunduğu dizine göre)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_BASE_DIR, "data")
DB_DIR = os.path.join(_BASE_DIR, "chroma_db")

def statik_veritabani_olustur():
    logger.info("Eski veritabanı temizleniyor...")
    if os.path.exists(DB_DIR):
        shutil.rmtree(DB_DIR)

    logger.info("'%s' klasöründeki PDF'ler okunuyor...", DATA_DIR)
    if not os.path.exists(DATA_DIR):
        raise FileNotFoundError(f"Veri dizini bulunamadı: {DATA_DIR}")

    loader = PyPDFDirectoryLoader(DATA_DIR)
    docs = loader.load()
    logger.info("Toplam %d sayfa bulundu.", len(docs))

    logger.info("Metinler anlam bütünlüğüne göre parçalanıyor...")
    # Akademik metinler için 1000 karakter idealdir, overlap ile bağlam kopmaz
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    parcalar = text_splitter.split_documents(docs)
    logger.info("Toplam %d parça oluşturuldu.", len(parcalar))

    logger.info("Vektörler (Embeddings) oluşturulup Chroma'ya kaydediliyor...")
    embedding_model = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")

    Chroma.from_documents(
        documents=parcalar,
        embedding=embedding_model,
        persist_directory=DB_DIR
    )

    logger.info("İŞLEM TAMAM! Statik veritabanı kusursuz bir şekilde hazırlandı.")

if __name__ == "__main__":
    statik_veritabani_olustur()