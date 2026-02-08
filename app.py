import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Borsa Karne", page_icon="📈", layout="centered")

# --- CSS İLE MODERN TASARIM ---
st.markdown("""
<style>
    .stTextInput > div > div > input {text-align: center; font-size: 20px;}
    .metric-box {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- BAŞLIK ---
st.markdown("<h1 style='text-align: center; color: #0068c9;'>📈 Sefer Mesut - Borsa Analiz</h1>", unsafe_allow_html=True)
st.caption("En güncel ÇEYREKLİK verilerle analiz yapar. (Kaynak: Yahoo Finance)")

st.write("") 

# --- ARAMA ALANI ---
col1, col2 = st.columns([3, 1]) 
with col1:
    hisse_kodu_giris = st.text_input("Hisse Kodu", value="", placeholder="Örn: GZNMI, THYAO, AAPL", label_visibility="collapsed").upper()
with col2:
    analiz_butonu = st.button("ANALİZ ET 🚀", type="primary", use_container_width=True)

st.divider()

class StreamlitHisseAnaliz:
    def __init__(self, hisse_kodu):
        self.hisse_kodu_saf = hisse_kodu
        self.symbol = ""
        self.currency = "TL"
        self.son_bilanco_tarihi = "Bilinmiyor"
        
        if not hisse_kodu:
            st.warning("Lütfen bir hisse kodu girin.")
            self.hisse = None
            return

        with st.spinner(f'{hisse_kodu} en güncel verilerle taranıyor...'):
            try:
                # 1. BIST Kontrolü
                try_bist = f"{hisse_kodu}.IS"
                hisse_bist = yf.Ticker(try_bist)
                if not hisse_bist.history(period="5d").empty:
                    self.hisse = hisse_bist
                    self.symbol = try_bist
                    self.currency = "TRY"
                    st.toast(f"✅ BIST Bulundu: {try_bist}", icon="🇹🇷")
                else:
                    # 2. Global Kontrol
                    hisse_global = yf.Ticker(hisse_kodu)
                    if not hisse_global.history(period="5d").empty:
                        self.hisse = hisse_global
                        self.symbol = hisse_kodu
                        self.currency = hisse_global.info.get('currency', 'USD')
                        st.toast(f"✅ Global Bulundu: {hisse_kodu}", icon="🌍")
                    else:
                        st.error(f"❌ '{hisse_kodu}' bulunamadı!")
                        self.hisse = None
                        return

                # ÇEYREKLİK VERİLERİ ÇEKİYORUZ
                self.bs = self.hisse.quarterly_balance_sheet
                self.is_ = self.hisse.quarterly_financials
                self.info = self.hisse.info
                
                # Tarih Kontrolü
                if not self.bs.empty:
                    tarih_obj = self.bs.columns[0] # En yeni sütun
                    self.son_bilanco_tarihi = tarih_obj.strftime("%d.%m.%Y")
                else:
                    self.son_bilanco_tarihi = "Veri Yok"

            except Exception as e:
                st.error(f"Veri Çekme Hatası: {e}")
                self.hisse = None

        self.kriterler = []
        self.puan = 0
        self.toplam_mumkun_puan = 0
        self.z_score = 0

    def veri_getir(self, df, kalem_listesi, sutun_idx=0):
        if df.empty or len(df.columns) <= sutun_idx:
            return 0.0
        for kalem in kalem_listesi:
            if kalem in df.index:
                val = df.iloc[:, sutun_idx].loc[kalem]
                return float(val) if pd.notnull(val) else 0.0
        return 0.0

    def analiz_yap(self):
        if not self.hisse: return
        
        try:
            # --- VERİLERİ TOPLA (ÇEYREKLİK) ---
            satislar_guncel = self.veri_getir(self.is_, ['Total Revenue', 'Operating Revenue'], 0)
            satislar_gecen_yil_ceyrek = self.veri_getir(self.is_, ['Total Revenue'], 4) 
            
            ebitda_guncel = self.veri_getir(self.is_, ['EBITDA', 'Normalized EBITDA'], 0)
            if ebitda_guncel == 0: ebitda_guncel = self.veri_getir(self.is_, ['Operating Income'], 0)
            ebitda_gecen_yil_ceyrek = self.veri_getir(self.is_, ['EBITDA'], 4)
            
            net_kar = self.veri_getir(self.is_, ['Net Income', 'Net Income Common Stockholders'], 0)
            
            donen_varliklar = self.veri_getir(self.bs, ['Current Assets', 'Total Current Assets'], 0)
            kisa_vadeli_yuk = self.veri_getir(self.bs, ['Current Liabilities', 'Total Current Liabilities'], 0)
            toplam_varliklar = self.veri_getir(self.bs, ['Total Assets'], 0)
            toplam_yukumluluk = self.veri_getir(self.bs, ['Total Liabilities Net Minority Interest', 'Total Liabilities'], 0)
            ozkaynaklar = self.veri_getir(self.bs, ['Stockholders Equity', 'Total Equity Gross Minority Interest'], 0)
            gecmis_yil_karlari = self.veri_getir(self.bs, ['Retained Earnings'], 0)

            # --- HESAPLAMALAR ---
            cari_oran = donen_varliklar / kisa_vadeli_yuk if kisa_vadeli_yuk else 0
            isletme_sermayesi = donen_varliklar - kisa_vadeli_yuk
            kaldirac = toplam_yukumluluk / toplam_varliklar if toplam_varliklar else 0
            
            satis_buyume = (satislar_guncel - satislar_gecen_yil_ceyrek) / satislar_gecen_yil_ceyrek if satislar_gecen_yil_ceyrek else 0
            favok_buyume = (ebitda_guncel - ebitda_gecen_yil_ceyrek) / abs(ebitda_gecen_yil_ceyrek) if ebitda_gecen_yil_ceyrek else 0
            
            pd_dd = self.info.get('priceToBook')
            if pd_dd is None:
                piyasa_deg = self.info.get('marketCap', 0)
                if piyasa_deg > 0 and ozkaynaklar > 0: pd_dd = piyasa_deg / ozkaynaklar
                else: pd_dd = 0

            # Tahmini Yıllık ROE (Çeyreklik x 4)
            roe = (net_kar * 4) / ozkaynaklar if ozkaynaklar else 0
            adil_pd_dd = roe * 10 
            
            # --- PUANLAMA ---
            self.kriter_ekle("Satış Büyümesi (Çeyreklik)", satis_buyume, 0.40, "BÜYÜME", format_tur="yuzde")
            self.kriter_ekle("FAVÖK Büyümesi (Çeyreklik)", favok_buyume, 0.30, "BÜYÜME", format_tur="yuzde")
            self.kriter_ekle("Net Kâr (Son Çeyrek)", net_kar, 0, "KARLILIK", format_tur="sayi")
            self.kriter_ekle("Yıllıklandırılmış ROE", roe, 0.30, "KARLILIK", format_tur="yuzde") 
            self.kriter_ekle("Cari Oran (> 1.20)", cari_oran, 1.20, "SAĞLIK", format_tur="sayi")
            self.kriter_ekle("Kaldıraç Oranı (< %75)", kaldirac, 0.75, "RİSK", ters=True, format_tur="yuzde")
            
            degerleme_durumu = pd_dd < adil_pd_dd
            self.kriterler.append({
                'Kriter': "PD/DD Oranı",
                'Değer': f"{pd_dd:.2f}",
                'Hedef': f"< {adil_pd_dd:.2f} (Adil)",
                'Durum': "UCUZ" if degerleme_durumu else "PAHALI",
                'Kategori': "DEĞERLEME"
            })
            if degerleme_durumu: self.puan += 1
            self.toplam_mumkun_puan += 1

            # --- Z-SCORE ---
            t1 = isletme_sermayesi / toplam_varliklar if toplam_varliklar else 0
            t2 = gecmis_yil_karlari / toplam_varliklar if toplam_varliklar else 0
            t3 = (ebitda_guncel * 4) / toplam_varliklar if toplam_varliklar else 0
            t4 = ozkaynaklar / toplam_yukumluluk if toplam_yukumluluk else 0
            self.z_score = (6.56 * t1) + (3.26 * t2) + (6.72 * t3) + (1.05 * t4)

            self.rapor_olustur()

        except Exception as e:
            st.error(f"Hesaplama Hatası: {e}")

    def kriter_ekle(self, ad, deger, esik, kategori, ters=False, format_tur="sayi"):
        if ters: basarili = deger < esik
        else: basarili = deger > esik
            
        if format_tur == "yuzde":
            gosterim = f"%{deger*100:.1f}"
            hedef_gosterim = f"{'<' if ters else '>'} %{esik*100:.0f}"
        else:
            curr_symbol = "₺" if self.currency == "TRY" else self.currency
            gosterim = f"{deger:.2f}" if abs(deger) < 1000 else f"{deger/1_000_000:.1f} M {curr_symbol}"
            hedef_gosterim = f"{'<' if ters else '>'} {esik}"

        self.kriterler.append({
            'Kriter': ad,
            'Değer': gosterim,
            'Hedef': hedef_gosterim,
            'Durum': "BAŞARILI" if basarili else "BAŞARISIZ",
            'Kategori': kategori
        })
        self.toplam_mumkun_puan += 1
        if basarili: self.puan += 1

    def rapor_olustur(self):
        st.write("")
        col1, col2 = st.columns(2)
        
        col1.metric("Genel Skor", f"{self.puan} / {self.toplam_mumkun_puan}")
        
        if self.z_score < 1.1: z_delta = "- Riskli"; z_renk="inverse"
        elif self.z_score > 2.6: z_delta = "+ Güvenli"
        else: z_delta = "İzle"
        col2.metric("Altman Z-Score", f"{self.z_score:.2f}", z_delta)
        
        with col2:
            with st.expander("ℹ️ Z-Score Detayı"):
                st.markdown("""
                **Altman Z-Skor**, iflas riskini ölçen bir formüldür.
                - 🟢 **> 2.60:** Güvenli
                - 🟡 **1.10 - 2.60:** Gri Bölge
                - 🔴 **< 1.10:** Riskli
                """)

        st.subheader(f"📊 {self.hisse_kodu_saf} Analiz Raporu")
        
        df = pd.DataFrame(self.kriterler)
        def renk_ver(val):
            return 'background-color: #d1e7dd; color: black' if val in ["BAŞARILI", "UCUZ"] else 'background-color: #f8d7da; color: black'
        st.dataframe(df.style.applymap(renk_ver, subset=['Durum']), use_container_width=True, hide_index=True)
        
        bugun = datetime.now().strftime("%d.%m.%Y")
        st.info(f"📅 **Rapor Tarihi:** {bugun} | 🧾 **Veri Kaynağı (Son Bilanço):** {self.son_bilanco_tarihi} (Çeyreklik)")

        self.detayli_karne_ciz(bugun)

    def detayli_karne_ciz(self, bugun):
        data = []
        renkler = []
        headers = ["KRİTER", "DEĞER", "HEDEF", "DURUM"]
        
        for k in self.kriterler:
            row = [k['Kriter'], k['Değer'], k['Hedef'], k['Durum']]
            data.append(row)
            if k['Durum'] in ["BAŞARILI", "UCUZ"]: renkler.append(["#d4edda"] * 4) 
            else: renkler.append(["#f8d7da"] * 4) 

        fig, ax = plt.subplots(figsize=(10, len(data) * 0.5 + 2))
        ax.axis('off')
        
        table = ax.table(cellText=data, colLabels=headers, cellColours=renkler, loc='center', cellLoc='center', bbox=[0, 0.1, 1, 0.9])
        table.auto_set_font_size(False); table.set_fontsize(10)
        
        for (row, col), cell in table.get_celld().items():
            if row == 0:
                cell.set_text_props(weight='bold', color='white')
                cell.set_facecolor('#333333')
        
        # --- İMZA KISMI ---
        plt.figtext(0.5, 0.05, f"Analiz Tarihi: {bugun} | Dönem: {self.son_bilanco_tarihi}", ha="center", fontsize=9, color="gray")
        # BURASI GÜNCELLENDİ:
        plt.figtext(0.5, 0.02, "Powered by Sefer Mesut", ha="center", fontsize=9, color="#0068c9", weight="bold")

        st.pyplot(fig)

if analiz_butonu:
    app = StreamlitHisseAnaliz(hisse_kodu_giris)
    app.analiz_yap()
