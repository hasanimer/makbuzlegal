import streamlit as st
import pandas as pd
import io
import random
from datetime import date, datetime, timedelta

# ==========================================
# 1. AYARLAR VE 2025 PARAMETRELERİ
# ==========================================
st.set_page_config(
    page_title="MakbuzTekno (2025)",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
    # Tema ayarı: Streamlit ın `set_page_config` fonksiyonu "theme" anahtarını
    # kabul etmediğinden bu ayarı .streamlit/config.toml dosyası ile yapmak daha güvenlidir.
    menu_items={'About': 'Legal Design Projesi'}
)

# 2025 Resmi Verileri (Kaynak: AAÜT PDF)
PARAMETRELER_2025 = {
    # --- DANIŞMA VE DİLEKÇE ---
    "Sozlu_Danisma_Buro": 4000.00,
    "Sozlu_Danisma_Cagri": 7000.00,
    # Minimal sözlü danışma (kullanılan anahtar: Danisma_Sozlu)
    "Danisma_Sozlu": 4000.00,
    "Yazili_Danisma": 7000.00,
    "Dilekce_Yazimi": 6000.00,
    "Ihtarname_Protesto": 6000.00,
    
    # --- SÖZLEŞMELER ---
    "Kira_Sozlesmesi": 8000.00,
    "Sirket_Ana_Sozlesmesi": 21000.00,
    
    # --- MAHKEME VEKİL ÜCRETLERİ (MAKTU) ---
    "Sulh_Hukuk": 30000.00,
    "Sulh_Ceza": 18000.00,
    "Asliye_Hukuk": 45000.00,
    "Agir_Ceza": 65000.00,
    "Idare_Vergi_Durusmasiz": 30000.00,
    "Idare_Vergi_Durusmali": 40000.00,
    "Icra_Mahkemesi": 11000.00,
    "Icra_Takipleri": 9000.00,
    
    # --- DİĞER GİDERLER ---
    "Damga_Vergisi_Beyanname": 443.70
}

# --- NİSBİ ORANLAR (İCRA VE KONUSU PARA OLAN DAVALAR) ---
NISBI_ORANLAR = [
    {"limit": 600000, "oran": 0.16},
    {"limit": 600000, "oran": 0.15},   # Sonraki 600 bin
    {"limit": 1200000, "oran": 0.14},  # Sonraki 1.2 milyon
    {"limit": 1200000, "oran": 0.13},  # Sonraki 1.2 milyon
    {"limit": 1800000, "oran": 0.11},  # Sonraki 1.8 milyon
    {"limit": 2400000, "oran": 0.08},  # Sonraki 2.4 milyon
    {"limit": 3000000, "oran": 0.05},  # Sonraki 3 milyon
    {"limit": 3600000, "oran": 0.03},  # Sonraki 3.6 milyon
    {"limit": 4200000, "oran": 0.02},  # Sonraki 4.2 milyon
    {"limit": float('inf'), "oran": 0.01} # 18.6 milyondan yukarısı
]

# --- CSS Tasarımı (MakbuzTek Mavisi) ---
st.markdown("""
<style>
    .main { background-color: #f4f7f6; }
    .stButton>button {
        background-color: #0056b3; color: white; border-radius: 6px;
    }
    .stButton>button:hover { background-color: #004494; color: white; }
    div[data-testid="stMetric"] {
        background-color: white; padding: 15px; border-radius: 10px;
        border-left: 5px solid #0056b3; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SİMÜLASYON VERİ TABANI (UHAP/İCRATEK)
# ==========================================
if 'uyap_dosyalari' not in st.session_state:
    st.session_state.uyap_dosyalari = [
        {"Dosya No": "2024/105 Esas", "Mahkeme": "Ankara 2. Asliye Hukuk", "Müvekkil": "Ahmet Yılmaz", "Tutar": 30000},
        {"Dosya No": "2025/12 Soruşturma", "Mahkeme": "İstanbul C.Başsavcılığı", "Müvekkil": "Mehmet Demir", "Tutar": 15000}
    ]

# ==========================================
# 3. MOTOR FONKSİYONLARI
# ==========================================
def smm_hesapla_2025(tutar, hesap_yonu, kdv, stopaj, tevkifat):
    if hesap_yonu == "Brütten Nete":
        brut = tutar
    else: # Netten Brüte
        brut = tutar / (1 - (stopaj / 100))
    
    stopaj_tutari = brut * (stopaj / 100)
    net_kdv_haric = brut - stopaj_tutari
    kdv_tutari = brut * (kdv / 100)
    
    tevkifat_tutari = 0
    if tevkifat > 0:
        tevkifat_tutari = kdv_tutari * (tevkifat / 10)
    
    kdv_tahsil = kdv_tutari - tevkifat_tutari
    ele_gecen = net_kdv_haric + kdv_tahsil
    
    return round(brut, 2), round(stopaj_tutari, 2), round(kdv_tahsil, 2), round(ele_gecen, 2)

# --- AAÜT Hesaplama Motoru (Genel Hükümler Entegreli) ---
def aaut_teklif_hesapla(dava_turu, dava_degeri, asama_durumu="Tamamı", icra_odeme_durumu=False):
    """
    AAÜT 2025 Rakamları ve Genel Hükümler (Madde 6, 7, 11, 13) kurallarına göre hesaplar.
    """
    # 1. Sabit Veriler (Önceki PDF'ten)
    MAKTU_UCRETLER = {
        "Sulh Hukuk": 30000.00,
        "Sulh Ceza": 18000.00,
        "Asliye Hukuk": 45000.00,
        "Tüketici Mahkemesi": 22500.00,
        "Fikri Sınai Haklar": 55000.00,
        "Ağır Ceza": 65000.00,
        "İdare/Vergi (Duruşmasız)": 30000.00,
        "İcra Daireleri (Takip)": 9000.00,
        "İcra Mahkemesi": 11000.00,
        "Bölge Adliye (İstinaf)": 35000.00
    }
    
    # 2. Nisbi Oranlar (3. Kısım)
    def nisbi_hesapla(deger):
        dilimler = [
            (600000, 0.16), (600000, 0.15), (1200000, 0.14),
            (1200000, 0.13), (1800000, 0.11), (2400000, 0.08),
            (3000000, 0.05), (3600000, 0.03), (4200000, 0.02)
        ]
        toplam_ucret = 0
        kalan = deger
        
        for limit, oran in dilimler:
            if kalan <= 0: break
            hesap_tabani = min(kalan, limit)
            toplam_ucret += hesap_tabani * oran
            kalan -= hesap_tabani
            
        if kalan > 0: # 18.6 Milyon üzeri (Madde 10)
            toplam_ucret += kalan * 0.01
            
        return toplam_ucret

    # 3. Hesaplama Mantığı
    maktu_taban = MAKTU_UCRETLER.get(dava_turu, 0)
    
    # Konusu Para Olan İşlerde Kural (Madde 13): Nisbi ücret maktunun altında kalamaz.
    if dava_degeri > 0:
        nisbi_sonuc = nisbi_hesapla(dava_degeri)
        # İcra takiplerinde maktu tavanı asıl alacağı geçemez (Madde 11/1)
        if "İcra" in dava_turu and maktu_taban > dava_degeri:
            maktu_taban = dava_degeri
            
        ham_ucret = max(maktu_taban, nisbi_sonuc)
        hesap_tipi = "Nisbi (Değer Esaslı)"
    else:
        ham_ucret = maktu_taban
        hesap_tipi = "Maktu (Sabit)"

    # 4. İndirim ve Özel Durumlar (Genel Hükümler)
    
    # Madde 6 ve 7: Ön inceleme öncesi sulh/feragat/görevsizlik -> Yarısı
    if asama_durumu == "Ön İnceleme Öncesi (Sulh/Feragat/Görevsizlik)":
        nihai_ucret = ham_ucret / 2
        aciklama = "Madde 6/7 gereği 1/2 oranında ücret takdir edildi."
        
    # Madde 11/4-5: İcrada ödeme süresi içinde ödeme -> 3/4
    elif "İcra" in dava_turu and icra_odeme_durumu:
        nihai_ucret = ham_ucret * 0.75
        aciklama = "Madde 11 gereği ödeme süresinde tahsilat (3/4) uygulandı."
        
    else:
        nihai_ucret = ham_ucret
        aciklama = "Tam ücret (Madde 5 gereği)."

    return nihai_ucret, hesap_tipi, aciklama

# ==========================================
# 4. ARAYÜZ VE MODÜLLER
# ==========================================

# --- KENAR ÇUBUĞU ---
with st.sidebar:
    st.title("MakbuzTekno")
    st.caption("2025 Uyumlu • E-SMM Portalı")
    
    # MakbuzTek Kredi Modeli Simülasyonu
    st.metric("Kalan Kontör", "85 Adet", delta="-2 (Bu Ay)")
    st.button("💳 Kontör Yükle")
    
    st.divider()
    menu = st.radio("MENÜ", ["📊 Genel Bakış", "🧮 SMM Oluştur", "🤝 Teklif Hazırlama", "📋 Ödeme Evrakçısı", "🔗 Entegrasyonlar", "❓ SSS & Yardım"])

# --- SAYFA 1: DASHBOARD ---
if menu == "📊 Genel Bakış":
    st.header("Finansal Durum (2025)")
    
    # 2025 Vergi Hatırlatmaları
    st.info(f"ℹ️ 2025 Yılı Damga Vergisi (Beyanname) **{PARAMETRELER_2025['Damga_Vergisi_Beyanname']} TL** olmuştur.")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Bu Ay Kesilen", "45.000 ₺", "3 Makbuz")
    col2.metric("Ödenecek Stopaj", "9.000 ₺", delta_color="inverse")
    col3.metric("KDV Tahakkuku", "8.100 ₺", delta_color="inverse")

# --- SAYFA 2: SMM OLUŞTUR (UHAP ENTEGRE) ---
elif menu == "🧮 SMM Oluştur":
    st.subheader("Yeni Makbuz Düzenle")
    
    # Entegrasyon Butonları
    col_int1, col_int2 = st.columns(2)
    with col_int1:
        if st.button("📂 İcraTek / UHAP'tan Dosya Getir"):
            st.session_state['dosya_secimi'] = True
            
    if st.session_state.get('dosya_secimi'):
        secilen_dosya = st.selectbox("Dosya Seçiniz:", st.session_state.uyap_dosyalari, format_func=lambda x: f"{x['Dosya No']} - {x['Müvekkil']}")
        if secilen_dosya:
            varsayilan_tutar = secilen_dosya['Tutar']
            varsayilan_aciklama = f"{secilen_dosya['Dosya No']} nolu dosya vekalet ücreti"
    else:
        varsayilan_tutar = 0.0
        varsayilan_aciklama = ""

    st.divider()
    
    # Hesaplama Formu
    with st.form("makbuz_form"):
        c1, c2 = st.columns(2)
        with c1:
            tutar = st.number_input("Tutar (TL)", value=float(varsayilan_tutar), step=500.0)
            yon = st.radio("Yön", ["Brütten Nete", "Netten Brüte"], horizontal=True)
            aciklama = st.text_input("Açıklama", value=varsayilan_aciklama)
        with c2:
            kdv = st.selectbox("KDV", [20, 10])
            stopaj = st.selectbox("Stopaj", [20, 0]) # CMK için 0 seçeneği
            tevkifat = st.selectbox("Tevkifat", [0, 5, 9], format_func=lambda x: "Yok" if x==0 else f"{x}/10")
            
        if st.form_submit_button("Hesapla ve Önizle"):
            brut, stp, kdv_tahsil, toplam = smm_hesapla_2025(tutar, yon, kdv, stopaj, tevkifat)
            
            st.success("✅ Makbuz Taslağı Oluşturuldu")
            # Legal Design Sonuç Kartı
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Brüt", f"{brut:,.2f} ₺")
            d2.metric("Stopaj", f"{stp:,.2f} ₺")
            d3.metric("KDV", f"{kdv_tahsil:,.2f} ₺")
            d4.metric("ELE GEÇEN", f"{toplam:,.2f} ₺", delta="Net")
            
            # Asgari Ücret Uyarısı (2025 Kontrolü)
            if brut < PARAMETRELER_2025["Danisma_Sozlu"]:
                st.warning(f"⚠️ Dikkat: Tutarınız 2025 Asgari Ücret Tarifesi ({PARAMETRELER_2025['Danisma_Sozlu']} TL) altındadır!")

# --- SAYFA 3: YARDIM (MAKBUZTEK SSS) ---
elif menu == "❓ SSS & Yardım":
    st.subheader("Akıllı Yardım Asistanı")
    st.info("💡 İPUCU: GİB sorgulama ekranında 'Brüt' yazan yere makbuzun **NET** tutarını yazmalısınız. (Madde 19)")
    
    soru = st.text_input("Sorunuzu yazın (Örn: İptal, E-İmza)", "")
    
    # SSS Veritabanı (Güncel)
    if "iptal" in soru.lower():
        st.write("**Cevap:** Makbuz ONAYLANDI ise 'İptal Et' butonunu kullanın. Defter-Beyan'a işlendiyse oradan da silmeniz gerekir.")
    elif "imza" in soru.lower():
        st.write("**Cevap:** E-İmza/Mali Mühür sadece ilk aktivasyonda takılı olmalıdır. Günlük kullanımda gerekmez.")
    elif "kağıt" in soru.lower():
        st.write("**Cevap:** Aktivasyon sonrası kağıt makbuz düzenlenemez. Sistemden çıktı alıp 'suret' olarak verebilirsiniz.")

# --- YENİ SEKME: ÖDEME EVRAK ASİSTANI ---
elif menu == "📋 Ödeme Evrakçısı":
    st.title("Hakediş ve Evrak Asistanı")
    st.markdown("Merkezi Yönetim Harcama Belgeleri Yönetmeliği'ne göre hazırlamanız gereken evraklar.")
    
    islem_turu = st.selectbox("İşlem Türü Seçiniz", [
        "Karşı Vekalet Ücreti (Kamu Kurumu)",
        "CMK / Adli Yardım Ödemesi",
        "Beraat Eden Memur Avukatlığı",
        "İcra/Mahkeme Masrafı İadesi"
    ])
    
    st.divider()
    
    if islem_turu == "Karşı Vekalet Ücreti (Kamu Kurumu)":
        st.subheader("📌 Hazırlanacak Evrak Listesi (Madde 29)")
        st.checkbox("Serbest Meslek Makbuzu (e-SMM çıktısı)")
        st.checkbox("Mahkeme İlamı (Aslı veya Onaylı Sureti)")
        st.checkbox("Kesinleşme Şerhi (Kanunen gerekliyse)")
        st.checkbox("İcranın Geri Bırakılması kararı olmadığına dair belge")
        st.checkbox("Banka Hesap Bilgilerini içeren dilekçe")
        st.info("İpucu: UYAP üzerinden yapılan masraflar için tek tek dekont yerine 'UYAP Onaylı Liste' sunabilirsiniz. (Madde 29/a)")

    elif islem_turu == "Beraat Eden Memur Avukatlığı":
        st.subheader("📌 Hazırlanacak Evrak Listesi (Madde 40/b)")
        st.checkbox("Serbest Meslek Makbuzu")
        st.checkbox("Kesinleşmiş Beraat Kararı (Aslı/Onaylı)")
        st.checkbox("Vekaletname Örneği")
        st.checkbox("Dava masrafları yapıldıysa faturaları")

    elif islem_turu == "İcra/Mahkeme Masrafı İadesi":
        st.subheader("📌 Hazırlanacak Evrak Listesi (Madde 29/a)")
        st.checkbox("Mahkeme/İcra Vezne Alındıları")
        st.checkbox("Veya Mahkeme Giderleri Listesi (Onaylı)")
        st.checkbox("UYAP İşlem Listesi (Elektronik ödemeler için)")

    elif islem_turu == "CMK / Adli Yardım Ödemesi":
        st.write("**Cevap:** Aktivasyon sonrası kağıt makbuz düzenlenemez. Sistemden çıktı alıp 'suret' olarak verebilirsiniz.")
