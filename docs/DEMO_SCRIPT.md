# Demo Script

## Demo Oncesi Kontrol

- HF Space aciliyor mu?
- Uygulamada ChromaDB hazir degil hatasi var mi?
- Admin kalite paneli acilabiliyor mu?
- Test edilecek demo sorulari hazir mi?
- Kaynak paneli ve inline citation davranisi gozlenecek mi?

## Demo Akisi

1. Ana sayfa acilir.
2. Sistem durumu / kalite paneli gosterilir.
3. AKTS gibi tanim sorusu sorulur.
4. Tez izleme komitesi gibi madde/sayi sorusu sorulur.
5. Doktora yeterlik gibi daha uzun kaynakli cevap sorusu sorulur.
6. Kutuphane/yemekhane saatleri gibi guncel bilgi sorusu sorulur ve fallback davranisi gosterilir.
7. Ders kredisi gibi sayi/hallucination riski olan soru test edilir.
8. Kaynak paneli ve inline citation eslesmesi gosterilir.

## Demo Sorulari

- AKTS nedir?
- Selcuk Universitesi'nde tez izleme komitesi kac ogretim uyesinden olusur?
- Selcuk Universitesi'nde doktora yeterlik sinavlari ile ilgili esaslar nelerdir?
- Selcuk Universitesi kutuphanesinde hangi saatlerde hizmet sunulur?
- Selcuk Universitesi yemekhane hizmetleri hangi saatlerde sunulur?
- Selcuk Universitesi'nde ders kredisi nasil hesaplanir?
- Selcuk Universitesi ogrencilere ucretsiz laptop veriyor mu?

## Beklenen Davranislar

- Kaynakli cevaplarda inline citation gorunur.
- Kaynak panelindeki `[1]`, cevap icindeki `[1]` ile ayni belgeye baglanir.
- Kaynak yoksa veya soru guncel operasyonel bilgi gerektiriyorsa guvenli fallback verilir.
- Cevap icinde ayri `Kaynaklar` veya URL listesi gorunmez.
- Uzun sayi dizisi uretilmez.
- Alakasiz kaynaklar kaynak panelini doldurmaz.

## Demo Sirasinda Soylenecek Kisa Aciklama

Bu uygulama Selcuk Universitesi'nin indekslenmis resmi yonetmelik ve yonerge kaynaklari uzerinde calisan bir RAG asistanidir. Soru geldiginde once ilgili kaynak parcalari bulunur, metadata-aware rerank ile siralanir, sonra model sadece bu baglama dayanarak cevap uretir. Cevap sonrasinda kaynak bloklari, URL sizintilari ve dusuk kaliteli ciktilar guardrail katmanindan gecer. Kaynakta acik bilgi yoksa sistem cevap uydurmak yerine guvenli fallback verir.

Kalite paneli canli cevap sistemini degistirmez; sadece yerelde uretilen evaluation raporlarini ve ChromaDB saglik durumunu okunabilir hale getirir.

## Demo Notlari

- Bu sistem resmi belge yerine gecmez.
- Gunluk yemek listesi, bugunku program veya anlik calisma saatleri gibi bilgiler corpus icinde yoksa cevaplanmayabilir.
- Admin kalite paneli read-only calisir ve shell command calistirmaz.
