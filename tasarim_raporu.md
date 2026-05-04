# 🎨 Tasarım Revizyonu Raporu: Selçuk RAG Asistanı

Google Stitch gibi araçlara mevcut projenin yapısını ve tasarım ihtiyaçlarını en doğru şekilde aktarabilmen için, uygulamada yer alan tüm UI (Kullanıcı Arayüzü) bileşenlerini ve mevcut CSS/Tema yapılandırmalarını aşağıda listeledim.

**Kullanabileceğin Promt İpucu:** *Google Stitch'e bu dosyayı vererek projede Streamlit framework'ü ile oluşturulmuş mevcut yapıyı gösterip buna uygun, daha modern ve yenilikçi bir arayüz tasarım (örn. Next.js / Tailwind veya yeni Streamlit komponentleri/Custom component tasarımları) üretmesini isteyebilirsin.*

---

## 1. Global Tema Ayarları (Streamlit Native - `.streamlit/config.toml`)
Proje şu anda koyu (dark) formata göre yapılandırılmış bir Streamlit teması kullanıyor:
- **Ana Renk (Primary):** `#1E88E5` (Parlak Mavi)
- **Arka Plan (Background):** `#0E1117` (Çok Koyu Lacivert/Siyah)
- **İkincil Arka Plan (Sidebar vb.):** `#1A1D26` (Koyu Gri/Lacivert)
- **Metin (Text):** `#FAFAFA` (Buz Beyazı)
- **Font:** `sans serif`

## 2. Özel CSS Müdahaleleri (`<style>`)
Mevcut uygulamada Streamlit standartlarını bir miktar kırıp farklılaştırmak için eklenen özel CSS kodları şunlardır:
- **Sayfa Alt Bilgisi (Footer):** Sayfanın en altına yapışık, yukarıya doğru hafif gradient geçişli (transparan to `#0E1117`), `#888` renginde metinden oluşan minimal bir footer bileşeni.
- **Butonlar (`.stButton > button`):** Köşeleri yumuşatılmış (`border-radius: 20px`), yazıları biraz küçültülmüş (`0.85rem`) modern görünümlü düğmeler.
- **Başlık Altı Çizgisi (`.header-divider`):** Ana başlığın altında boydan boya uzanan, soldan mavi `#1E88E5` başlayıp sağa doğru kaybolan (transparent) 3px kalınlığında gradient vurgu çizgisi.

## 3. Sayfa Yapısı ve Temel Düzen
- **Layout:** Sayfa geneli `centered` (merkeze ortalanmış standart sütun) olarak ayarlanmış. Tarayıcıyı tam kaplamıyor.
- **Sayfa Başlığı ve İkon:** Tarayıcı sekmesinde "Selçuk RAG Asistanı" ve "🎓" ikonu yer alıyor.
- **Ana Başlık:** Ekranın en üstünde HTML `H1` etiketi ile "**🎓 Selçuk Üni. Yönetmelik Asistanı**" ve hemen altında yukarıda bahsedilen özel gradient çizgi var. 

## 4. Sol Kenar Çubuğu (Sidebar)
Yan panelde verileri yönetmek adına kontrol mekanizmaları konumlandırılmış:
- **Bilgi Tabanı Sekmesi:** 
  - `H3` başlığı ("📚 Bilgi Tabanı").
  - **Açılır Kapanır Kutu (Expander):** "📂 Yüklü Yönetmelikler (X)" başlıklı, tıkladığında var olan yönetmeliklerin listesini gösteren bir kutu.
- **Diğer Bileşenler:**
  - "🗑️ Sohbeti Temizle" Butonu.
  - `H3` başlıklı "ℹ️ Hakkında" sekmesi; altında sistemin hangi model (Llama) ve embedding yöntemleriyle geliştirildiğini anlatan gri, küçük harfli bilgi metni (`caption`).
  - *Not:* Bölümler genelde İnce Çizgiler (`divider`) ile birbirinden ayrılmış.

## 5. Ana Sohbet Arayüzü (Chatbot)
### A) Başlangıç (Boş) Durumu Karşılama Ekranı
Uygulamaya ilk girildiğinde hiçbir mesaj yokken görünen boş durum arayüzü:
- **Hoşgeldin Mesajı:** Blok alıntı (`>`) içerisinde kullanıcıyı karşılayan bir metin ("*👋 Merhaba! Selçuk Üniversitesi...*").
- **Örnek Soru Seçeneği Kartları (Grid Layout):** 2 satır ve 2 sütundan oluşan `2x2`'lik bir grid panelde 4 adet önerilen soru butonu:
  1. *📋 Staj muafiyet şartları nelerdir?*
  2. *📘 Çift ana dal nasıl yapılır?*
  3. *💰 Burs başvuru koşulları nelerdir?*
  4. *📄 Diploma eki nedir?*

### B) Aktif Sohbet Ekranı Durumu
- **Mesaj Baloncukları (Chat Messages):**
  - **Kullanıcı Avatarı:** `👤` 
  - **Asistan Avatarı:** `🎓` (Model tarafından üretilen Markdown formatında yanıtların basıldığı metin ağırlıklı alan)
- **Takip Edilen Sorular (Öneriler):** Asistan cevap verdikten sonra, sayfanın aşağı kısmında **"🔎 Bunları da sorabilirsiniz:"** alt başlığıyla önerilen alt soru butonları dinamik (2-3 sütunlu) olarak belirir. 
- **Veri Giriş Çubuğu (Chat Input):** En altta kullanıcının soru yazıp enter tuşuyla gönderdiği mesaj barı ("Sorunuzu yazın...").
- **Asistan Düşünme Göstergeleri (Spinners):** AI çalışırken ekranda "Soru analiz ediliyor...", "Dökümanlar taranıyor..." ibareleri dönen ikon (spinner) ile gösteriliyor.

## 6. Hata ve Durum Bildirimleri (Alerts - Toasts)
Sistem aşağıdaki Streamlit built-in bileşenleri ile reaksiyon gösteriyor:
- **Success (Yeşil Uyarı):** Veriler başarılı eklendiğinde.
- **Warning (Sarı Uyarı):** Beklenen parametre girilmediğinde.
- **Error (Kırmızı Uyarı/Hata):** API limit aşıldığında veya sistem çöktüğünde ("⏳ API istek limiti aşıldı...").

---

**Genel Önerim:** Stitch üzerinden tasarımı yaparken bu Streamlit bazlı sınırları bir kenara bırakıp (eğer tamamen yeni bir kodlama altyapısına geçmeye açıksan) bu ihtiyaç haritasını çok daha profesyonel bir Dashboard mantığıyla tasarlatabilirsin. Tasarım oluştuktan sonra bana görselleri veya HTML/Next.js/React vb. çıktıları vererek projeye modern entegrasyonu sağlayabiliriz! 🚀
