import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Borsa Karneleyici", page_icon="📈", layout="centered")

st.title("📈 Evrensel Hisse Karneleyici")
st.markdown("BIST veya ABD borsalarındaki hisselerin **Z-Score**, **Büyüme** ve **Değerleme** analizini yapar.")

# --- KENAR ÇUBUĞU ---
st.sidebar.header("Hisse Seçimi")
hisse_kodu_giris = st.sidebar.text_input("Hisse Kodu (Örn: GZNMI, AAPL)", value="GZNMI").upper()
analiz_butonu = st.sidebar.button("Analiz Et 🚀")

class StreamlitHisseAnaliz:
    def __init__(self, hisse_kodu):
        self.hisse_kodu_saf = hisse_kodu
        self.symbol = ""
        self.currency = "TL"
        
        with st.spinner(f'{hisse_kodu} verileri çekiliyor...'):
            # --- AKILLI HİSSE BULMA ---
            try:
                try_bist = f"{hisse_kodu}.IS"
                hisse_bist = yf.Ticker(try_bist)
                if not hisse_bist.history(period="5d").empty:
                    self.hisse = hisse_bist
                    self.symbol = try_bist
                    self.currency = "TRY"
                    st.success(f"✅ BIST Hissesi Bulundu: {try_bist}")
                else:
                    hisse_global = yf.Ticker(hisse_kodu)
                    if not hisse_global.history(period="5d").empty:
                        self.hisse = hisse_global
                        self.symbol = hisse_kodu
                        self.currency = hisse_global.info.get('currency', 'USD')
                        st.success(f"✅ Global Hisse Bulundu: {hisse_kodu}")
                    else:
                        st.error("❌ Hisse bulunamadı!")
                        self.hisse = None
                        return

                self.bs = self.hisse.balance_sheet
                self.is_ = self.hisse.financials
                self.info = self.hisse.info

            except Exception as e:
                st.error(f"Veri çekme hatası: {e}")
                self.hisse = None

        self.kriterler = []
        self.puan = 0
        self.toplam_mumkun_puan = 0
        self.z_score = 0

    def veri_getir(self, df, kalem_listesi):
        for kalem in kalem_listesi:
            if kalem in df.index:
                val = df.loc[kalem].iloc[0]
                return float(val) if pd.notnull(val) else 0.0
        return 0.0

    def veri_getir_gecmis(self, df, kalem_listesi, yil_once=0):
        for kalem in kalem_listesi:
            if kalem in df.index:
                if len(df.columns) > yil_once:
                    val = df.loc[kalem].iloc[yil_once]
                    return float(val) if pd.notnull(val) else 0.0
        return 0.0

    def analiz_yap(self):
        if not self.hisse: return
        
        try:
            # --- VERİLER ---
            satislar = self.veri_getir(self.is_, ['Total Revenue', 'Operating Revenue'])
            satislar_gecen_yil = self.veri_getir_gecmis(self.is_, ['Total Revenue'], 1)
            
            ebitda = self.veri_getir(self.is_, ['EBITDA', 'Normalized EBITDA'])
            if ebitda == 0: ebitda = self.veri_getir(self.is_, ['Operating Income'])
            ebitda_gecen_yil = self.veri_getir_gecmis(self.is_, ['EBITDA'], 1)
            
            net_kar = self.veri_getir(self.is_, ['Net Income', 'Net Income Common Stockholders'])
            
            donen_varliklar = self.veri_getir(self.bs, ['Current Assets', 'Total Current Assets'])
            kisa_vadeli_yuk = self.veri_getir(self.bs, ['Current Liabilities', 'Total Current Liabilities'])
            toplam_varliklar = self.veri_getir(self.bs, ['Total Assets'])
            toplam_yukumluluk = self.veri_getir(self.bs, ['Total Liabilities Net Minority Interest', 'Total Liabilities'])
            ozkaynaklar = self.veri_getir(self.bs, ['Stockholders Equity', 'Total Equity Gross Minority Interest'])
            finansal_borc = self.veri_getir(self.bs, ['Total Debt'])
            gecmis_yil_karlari = self.veri_getir(self.bs, ['Retained Earnings'])

            # --- HESAPLAMALAR ---
            cari_oran = donen_varliklar / kisa_vadeli_yuk if kisa_vadeli_yuk else 0
            isletme_sermayesi = donen_varliklar - kisa_vadeli_yuk
            kaldirac = toplam_yukumluluk / toplam_varliklar if toplam_varliklar else 0
            
            satis_buyume = (satislar - satislar_gecen_yil) / satislar_gecen_yil if satislar_gecen_yil else 0
            favok_buyume = (ebitda - ebitda_gecen_yil) / abs(ebitda_gecen_yil) if ebitda_gecen_yil else 0
            
            pd_dd = self.info.get('priceToBook')
            if pd_dd is None:
                piyasa_deg = self.info.get('marketCap', 0)
                if piyasa_deg > 0 and ozkaynaklar > 0: pd_dd = piyasa_deg / ozkaynaklar
                else: pd_dd = 0

            roe = net_kar / ozkaynaklar if ozkaynaklar else 0
            adil_pd_dd = roe * 10 
            
            # --- PUANLAMA ---
            self.kriter_ekle("Satış Büyümesi (Yıllık)", satis_buyume, 0.40, "BÜYÜME", format_tur="yuzde")
            self.kriter_ekle("FAVÖK Büyümesi (Yıllık)", favok_buyume, 0.30, "BÜYÜME", format_tur="yuzde")
            self.kriter_ekle("Net Kâr Pozitif mi?", net_kar, 0, "KARLILIK", format_tur="sayi")
            self.kriter_ekle("Özsermaye Kârlılığı (ROE)", roe, 0.20, "KARLILIK", format_tur="yuzde") 
            self.kriter_ekle("Cari Oran (> 1.20)", cari_oran, 1.20, "SAĞLIK", format_tur="sayi")
            self.kriter_ekle("Kaldıraç Oranı (< %70)", kaldirac, 0.70, "RİSK", ters=True, format_tur="yuzde")
            
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
            t3 = (ebitda * 0.8) / toplam_varliklar if toplam_varliklar else 0
            t4 = ozkaynaklar / toplam_yukumluluk if toplam_yukumluluk else 0
            self.z_score = (6.56 * t1) + (3.26 * t2) + (6.72 * t3) + (1.05 * t4)

            self.rapor_olustur()

        except Exception as e:
            st.error(f"Analiz Hatası: {e}")

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
        # SKOR KARTLARI
        col1, col2 = st.columns(2)
        col1.metric("Genel Puan", f"{self.puan} / {self.toplam_mumkun_puan}")
        
        z_renk = "normal"
        if self.z_score < 1.1: z_delta = "- Riskli"; z_renk="inverse"
        elif self.z_score > 2.6: z_delta = "+ Güvenli"
        else: z_delta = "İzle"
        
        col2.metric("Altman Z-Score", f"{self.z_score:.2f}", z_delta)

        # TABLO GÖRSELLEŞTİRME (RENKLİ)
        st.subheader("📊 Detaylı Analiz Tablosu")
        
        df = pd.DataFrame(self.kriterler)
        
        def renk_ver(val):
            color = '#d4edda' if val == "BAŞARILI" or val == "UCUZ" else '#f8d7da'
            return f'background-color: {color}; color: black'

        st.dataframe(df.style.applymap(renk_ver, subset=['Durum']), use_container_width=True)

        # GÖRSEL TABLO (Matplotlib)
        self.detayli_karne_ciz()

    def detayli_karne_ciz(self):
        # Matplotlib görselini Streamlit'e basma
        data = []
        renkler = []
        headers = ["KRİTER", "DEĞER", "HEDEF", "DURUM"]
        
        for k in self.kriterler:
            row = [k['Kriter'], k['Değer'], k['Hedef'], k['Durum']]
            data.append(row)
            if k['Durum'] in ["BAŞARILI", "UCUZ"]: renkler.append(["#d4edda"] * 4) 
            else: renkler.append(["#f8d7da"] * 4) 

        fig, ax = plt.subplots(figsize=(10, len(data) * 0.5 + 1.5))
        ax.axis('off')
        table = ax.table(cellText=data, colLabels=headers, cellColours=renkler, loc='center', cellLoc='center', bbox=[0, 0, 1, 1])
        table.auto_set_font_size(False); table.set_fontsize(10)
        for (row, col), cell in table.get_celld().items():
            if row == 0:
                cell.set_text_props(weight='bold', color='white')
                cell.set_facecolor('#333333')
        
        st.pyplot(fig)

# --- UYGULAMAYI ÇALIŞTIR ---
if analiz_butonu:
    app = StreamlitHisseAnaliz(hisse_kodu_giris)
    app.analiz_yap()