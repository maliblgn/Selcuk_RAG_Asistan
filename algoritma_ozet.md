# Şifreleme Algoritmaları — Çalışma ve Matematik Özeti

> **Alfabe:** 29 harfli Türk Alfabesi → `ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ`
> Her harf bir sayıya karşılık gelir: A=0, B=1, C=2, … Z=28

---

## 1. Vigenère Şifreleme

### Matematiksel Mantık

Vigenère, **çok-alfabeli (polyalphabetic)** bir şifreleme yöntemidir. Her harf, sabit bir anahtar yerine **anahtar kelimeden türetilen farklı bir kaydırma değeri** ile şifrelenir.

**Formül:**

```
Cᵢ = (Pᵢ + Kᵢ) mod 29
```

| Sembol | Anlamı |
|--------|--------|
| `Pᵢ` | Düz metnin i. harfinin alfabedeki sıra numarası |
| `Kᵢ` | Anahtar kelimenin `(i mod anahtar_uzunluk)`. harfinin sıra numarası |
| `Cᵢ` | Şifreli metnin i. harfinin sıra numarası |
| `mod 29` | 29 harfli alfabe içinde kalmasını sağlar |

### Adım Adım Örnek

```
Düz Metin  :  M  E  R  H  A  B  A
Anahtar    :  K  R  İ  P  T  O  K   ← anahtar tekrar eder
Sıra (P)   : 16  4 20  7  0  1  0
Sıra (K)   : 14 20 11 19 23 18 14
Toplam     : 30 24 31 26 23 19 14
mod 29     :  1 24  2 26 23 19 14
Şifreli    :  B  V  C  Ü  T  Ş  K
```

### Kod Çalışma Mantığı

```csharp
public static string VigenereSifrele(string metin, string anahtarKelime)
```

1. **Ön işleme:** Hem metin hem anahtar `MetniOnIsle()` ile temizlenir (küçük→büyük, özel karakter silme).
2. **Döngü:** Metnin her harfi için:
   - `x` = harfin alfabedeki indeksi
   - `k` = anahtar kelimenin `(i % anahtarUzunluk)`. harfinin indeksi
   - Yeni indeks = `(x + k) mod 29`
3. **Anahtar döngüsü:** Anahtar kelime metin uzunluğundan kısaysa, başa dönerek tekrar eder (`i % anahtarUzunluk`).

> [!TIP]
> Kaydırmalı şifrelemenin genelleştirilmiş halidir. Kaydırmalıda tek bir `k` varken, Vigenère'de **her harf için farklı bir k** kullanılır.

---

## 2. Dört Kare (Four-Square) Şifreleme

### Matematiksel Mantık

Dört Kare, **digraf (harf çifti) bazlı** bir şifreleme yöntemidir. 4 adet 6×5 matris kullanılır:

```
┌─────────────┬─────────────┐
│  Düz Alfabe │  Anahtar 1  │   ← Satır 1
│  (Sol Üst)  │  (Sağ Üst)  │
├─────────────┼─────────────┤
│  Anahtar 2  │  Düz Alfabe │   ← Satır 2
│  (Sol Alt)  │  (Sağ Alt)  │
└─────────────┴─────────────┘
```

- **Sol Üst & Sağ Alt:** Düz sıralı alfabe (A, B, C, Ç, D, E, …)
- **Sağ Üst:** 1. anahtar kelimeden türetilmiş karışık alfabe
- **Sol Alt:** 2. anahtar kelimeden türetilmiş karışık alfabe

**Matris Yapısı (6×5):** 29 harflik alfabe 6 satır × 5 sütun matrise yerleştirilir:

```
Satır 0: A  B  C  Ç  D
Satır 1: E  F  G  Ğ  H
Satır 2: I  İ  J  K  L
Satır 3: M  N  O  Ö  P
Satır 4: R  S  Ş  T  U
Satır 5: Ü  V  Y  Z  -    ← Son satırda 4 harf
```

**Şifreleme Kuralı:**

1. Düz metni **harf çiftlerine** ayır: `ME RH AB A_`
2. Her çift için:
   - 1. harfi **Sol Üst** (düz) matriste bul → `(satır₁, sütun₁)`
   - 2. harfi **Sağ Alt** (düz) matriste bul → `(satır₂, sütun₂)`
   - Şifreli 1. harf = **Sağ Üst** matristeki `(satır₁, sütun₂)` konumu
   - Şifreli 2. harf = **Sol Alt** matristeki `(satır₂, sütun₁)` konumu

```
Düz harf çifti:    (satır₁, sütun₁)  ve  (satır₂, sütun₂)
                         ↓                     ↓
Şifreli çift:   Anahtar1[satır₁, sütun₂]  Anahtar2[satır₂, sütun₁]
```

### Adım Adım Örnek

```
Anahtar 1: "KRİPTO"  →  Karışık alfabe: K R İ P T O A B C Ç D E F G Ğ H I J L M N Ö S Ş U Ü V Y Z
Anahtar 2: "GİZLİ"   →  Karışık alfabe: G İ Z L A B C Ç D E F Ğ H I J K M N O Ö P R S Ş T U Ü V Y

Düz metin: "ME" → M(satır=3, sütun=0), E(satır=1, sütun=0)
Şifreli 1. harf = Anahtar1[satır=3, sütun=0] = "M" (karışık alfabeden)
Şifreli 2. harf = Anahtar2[satır=1, sütun=0] = "B" (karışık alfabeden)
```

### Kod Çalışma Mantığı

```csharp
public static string DortKareSifrele(string metin, string anahtar1, string anahtar2)
```

1. **Padding:** Metin tek uzunluklu ise sonuna `A` eklenir.
2. **Alfabe oluşturma:** `AnahtardanAlfabeOlustur()` metodu ile her anahtar kelimeden karışık alfabe üretilir:
   - Önce anahtar kelimenin harfleri (tekrarsız)
   - Sonra alfabenin kalan harfleri
3. **Çift çift işleme:** Her 2 harf için:
   - Düz alfabede satır/sütun bulunur: `satır = indeks / 5`, `sütun = indeks % 5`
   - Çapraz matris konumları hesaplanır
   - Karışık alfabelerden şifreli harfler seçilir

> [!IMPORTANT]
> Digraf sisteminde harf çiftleri bağımsız şifrelenir. Tek bir harfin değişmesi sadece kendi çiftini etkiler.

---

## 3. Hill Şifreleme

### Matematiksel Mantık

Hill şifreleme, **lineer cebir (matris çarpımı)** tabanlı bir şifreleme yöntemidir. Düz metin harfleri vektör olarak ifade edilir ve bir **anahtar matrisle** çarpılır.

**2×2 Matris Formülü:**

```
┌      ┐   ┌     ┐   ┌    ┐
│ C₁   │ = │ a  b│ × │ P₁ │   (mod 29)
│ C₂   │   │ c  d│   │ P₂ │
└      ┘   └     ┘   └    ┘
```

**Açık formül:**

```
C₁ = (a × P₁ + b × P₂) mod 29
C₂ = (c × P₁ + d × P₂) mod 29
```

| Sembol | Anlamı |
|--------|--------|
| `P₁, P₂` | Düz metnin harf çiftinin sıra numaraları |
| `a, b, c, d` | 2×2 anahtar matrisin elemanları |
| `C₁, C₂` | Şifreli harf çiftinin sıra numaraları |

### Determinant Şartı

Matrisin **tersi alınabilir** olması gerekir (deşifre edilebilmesi için):

```
det = (a × d - b × c) mod 29

Şart: EBOB(det, 29) = 1   ← Determinant ile 29 aralarında asal olmalı
```

29 bir asal sayı olduğu için, determinant **0'dan farklı** (mod 29) olmalıdır.

Geçerli determinant değerleri: `1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28`
Geçersiz determinant: `0`

### Adım Adım Örnek

```
Anahtar Matris:  [3  5]    Düz Metin: "ME"
                 [2  7]    M=16, E=4

C₁ = (3×16 + 5×4) mod 29 = (48 + 20) mod 29 = 68 mod 29 = 10  → İ
C₂ = (2×16 + 7×4) mod 29 = (32 + 28) mod 29 = 60 mod 29 =  2  → C

Determinant: (3×7 - 5×2) mod 29 = (21-10) mod 29 = 11
EBOB(11, 29) = 1 ✓ → Matris geçerli!

"ME" → "İC"
```

### Kod Çalışma Mantığı

```csharp
public static string HillSifrele(string metin, int[,] anahtarMatris)
```

1. **Padding:** Metin tek uzunluklu ise sonuna `A` eklenir (2'li bloklar gerektiğinden).
2. **Matris doğrulama:**
   - Matris boyutu 2×2 mi? Değilse `ArgumentException` fırlatılır.
   - Determinant hesaplanır: `det = (a*d - b*c) mod 29`
   - `Ebob(det, 29) != 1` ise hata fırlatılır (matris terslenemez).
3. **Şifreleme döngüsü:** Her 2 harf için:
   - `x1`, `x2` = harf çiftinin indeksleri
   - Matris çarpımı uygulanır:
     - `y1 = (a*x1 + b*x2) mod 29`
     - `y2 = (c*x1 + d*x2) mod 29`
   - Yeni indekslerden harfler elde edilir.

> [!WARNING]
> Kullanıcı geçersiz bir matris girerse (det ≡ 0 mod 29), program hata mesajı gösterir ve şifreleme yapmaz. Bu, deşifrelemenin mümkün olması için zorunlu bir kontroldür.

---

## Karşılaştırma Tablosu

| Özellik | Vigenère | Dört Kare | Hill |
|---------|----------|-----------|------|
| **Tür** | Çok-alfabeli yerine koyma | Digraf yerine koyma | Matris çarpımı |
| **İşlem birimi** | Tek harf | 2'li harf çifti | 2'li harf çifti |
| **Anahtar** | Kelime | 2 kelime | 2×2 matris (4 sayı) |
| **Matematik** | Toplama mod 29 | Matris konum değiştirme | Lineer cebir mod 29 |
| **Güvenlik** | Frekans analizi ile kırılabilir | Daha dirençli | Bilinen düz metin saldırısına açık |
| **Padding** | Gerekli değil | Tek ise A eklenir | Tek ise A eklenir |

---

## Ortak Yardımcı Metodlar

### `MetniOnIsle(string)`
Tüm algoritmalarda kullanılan ön işleme metodu:
- Küçük harfler → büyük harf (Türkçe uyumlu: ı→I, i→İ, ç→Ç, vb.)
- Boşluk, noktalama, sayılar kaldırılır
- Sonuç: sadece 29 harfli alfabedeki karakterler

### `Mod29(int)`
Negatif sayılar için de doğru çalışan modüler aritmetik:
```csharp
return (deger % 29 + 29) % 29;
```

### `Ebob(int, int)` — Sadece Hill'de
Öklid algoritması ile en büyük ortak bölen hesaplama:
```
Ebob(a, b): b == 0 ise a döner, değilse Ebob(b, a%b)
```
