import streamlit as st
import pandas as pd
import urllib.request
import io

# Configuração da página
st.set_page_config(page_title="TL Financeiro - Executive Dashboard", layout="wide")

st.title("📊 TL Financeiro - Executive Dashboard")

# Link do SharePoint
ONEDRIVE_LINK = "https://tlportfolioconsultoria.sharepoint.com/:x:/s/financeiro/IQB8ppfjijXDSruvof6G0FUPAdZCrfvScsU7hM8qTXTh-fo?download=1"

@st.cache_data(ttl=60) # Recarrega os dados a cada 1 minuto
def load_data(url):
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
    )
    with urllib.request.urlopen(req) as response:
        content = response.read()
    
    # Especificado engine='openpyxl' explicitamente para resolver o erro
    df = pd.read_excel(io.BytesIO(content), sheet_name='Lançamentos', engine='openpyxl')
    df['DataRef'] = pd.to_datetime(df['DataRef'])
    df['AnoRef'] = df['DataRef'].dt.year
    df['MêsRef'] = df['DataRef'].dt.month
    return df

try:
    df_raw = load_data(ONEDRIVE_LINK)
    st.sidebar.success("✅ Conectado ao SharePoint!")
except Exception as e:
    st.error(f"Erro ao carregar os dados do SharePoint: {e}")
    st.stop()

# --- FILTROS LATERAIS ---
st.sidebar.header("⚙️ Filtros")
moeda = st.sidebar.radio("Selecione a Moeda", options=['USD', 'BRL', 'EUR'], index=0)

anos_disponiveis = sorted(df_raw['AnoRef'].dropna().unique().astype(int), reverse=True)
anos_selecionados = st.sidebar.multiselect("AnoRef", options=anos_disponiveis, default=anos_disponiveis[:2])

if anos_selecionados:
    df_filtered = df_raw[df_raw['AnoRef'].isin(anos_selecionados)].copy()
else:
    df_filtered = df_raw.copy()

df_filtered['Valor_Ativo'] = df_filtered[moeda]

# --- KPI 1: FINANCIAL KEYS (DRE) ---
st.subheader("📌 1. Financial Keys (DRE)")

def get_kpis(df_sub):
    portfolio = df_sub[df_sub['Serviço'] == 'TL Portfolio']['Valor_Ativo'].sum()
    voice = df_sub[df_sub['Serviço'] == 'TL Voice']['Valor_Ativo'].sum()
    scene = df_sub[df_sub['Serviço'] == 'TL Scene']['Valor_Ativo'].sum()
    other_rev = df_sub[df_sub['Serviço'].isin(['Other Revenues', 'Investment'])]['Valor_Ativo'].sum()
    refundables = df_sub[df_sub['Serviço'] == 'Refundables']['Valor_Ativo'].sum()
    
    total_sales = portfolio + voice + scene + other_rev + refundables
    custos = abs(df_sub[df_sub['Tipo'] == 'Costs']['Valor_Ativo'].sum())
    gross_revenue = total_sales - custos
    
    partner = abs(df_sub[df_sub['Classificação'] == 'Partner']['Valor_Ativo'].sum())
    expenses = abs(df_sub[df_sub['Classificação'] == 'Expenses']['Valor_Ativo'].sum())
    ebitda = gross_revenue - partner - expenses
    
    taxes = abs(df_sub[df_sub['Classificação'] == 'Taxes']['Valor_Ativo'].sum())
    bottom_line = ebitda - taxes
    
    return {
        "Total TL Portfolio Sales": portfolio,
        "Total TL Voice Sales": voice,
        "Total TL Scene Sales": scene,
        "Other Revenues + Investimento": other_rev,
        "Refundables": refundables,
        "Total Sales": total_sales,
        "Gross Revenue (net)": gross_revenue,
        "Partner (-)": -partner,
        "Expenses (-)": -expenses,
        "Total Costs (-)": -(custos + partner + expenses),
        "EBITDA": ebitda,
        "Taxes (-)": -taxes,
        "Bottom Line": bottom_line
    }

if len(anos_selecionados) >= 2:
    a1, a2 = anos_selecionados[0], anos_selecionados[1]
    kpi_a1 = get_kpis(df_filtered[df_filtered['AnoRef'] == a1])
    kpi_a2 = get_kpis(df_filtered[df_filtered['AnoRef'] == a2])
    
    df_dre = pd.DataFrame({f"{a1} ({moeda})": kpi_a1, f"{a2} ({moeda})": kpi_a2})
    df_dre['Var %'] = ((df_dre.iloc[:, 0] - df_dre.iloc[:, 1]) / df_dre.iloc[:, 1].abs() * 100).map("{:.1f}%".format)
    st.dataframe(df_dre.style.format("{:,.2f}", subset=[df_dre.columns[0], df_dre.columns[1]]), use_container_width=True)
else:
    kpi_single = get_kpis(df_filtered)
    st.dataframe(pd.DataFrame(kpi_single, index=[f"Resultado ({moeda})"]).T.style.format("{:,.2f}"), use_container_width=True)

# --- KPI 2: REVENUE COMPOSITION BY TYPE ---
st.markdown("---")
st.subheader("📊 2. Revenue Composition by Type")

rev_df = df_filtered[df_filtered['Classificação'] == 'Revenue'].groupby('Serviço')['Valor_Ativo'].sum().reset_index()
tot_rev = rev_df['Valor_Ativo'].sum()
rev_df['Share (%)'] = (rev_df['Valor_Ativo'] / tot_rev * 100) if tot_rev > 0 else 0

col1, col2 = st.columns([1, 1])
with col1:
    st.dataframe(rev_df.style.format({'Valor_Ativo': '{:,.2f}', 'Share (%)': '{:.2f}%'}), use_container_width=True)
with col2:
    st.bar_chart(rev_df.set_index('Serviço')['Share (%)'])
