import streamlit as st
import pandas as pd
import requests
import io

# Configuração da página
st.set_page_config(page_title="TL Financeiro - Executive Dashboard", layout="wide")

st.title("📊 TL Financeiro - Executive Dashboard")

# URL do SharePoint
ONEDRIVE_LINK = "https://tlportfolioconsultoria.sharepoint.com/:x:/s/financeiro/IQB8ppfjijXDSruvof6G0FUPAdZCrfvScsU7hM8qTXTh-fo?download=1"

@st.cache_data(ttl=60) # Recarrega os dados a cada 1 minuto
def load_data(url):
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    })
    
    response = session.get(url, allow_redirects=True)
    download_url = response.url
    if "download=1" not in download_url:
        download_url += "&download=1" if "?" in download_url else "?download=1"
            
    final_response = session.get(download_url)
    excel_bytes = io.BytesIO(final_response.content)
    
    # Busca automática da linha onde está 'DataRef'
    df = None
    for header_row in range(0, 10):
        try:
            temp_df = pd.read_excel(excel_bytes, sheet_name='Lançamentos', header=header_row, engine='openpyxl')
            if 'DataRef' in temp_df.columns:
                df = temp_df
                break
        except Exception:
            continue
            
    if df is None:
        raise KeyError("A coluna 'DataRef' não foi encontrada nas primeiras linhas da aba 'Lançamentos'.")

    # 1. FILTRO DE APENAS "REALIZADO" NA COLUNA D (Status / Créd/Déb)
    # Verifica qual coluna na posição D (índice 2 ou 3) ou nome correspondente
    col_status = None
    for col in ['Status', 'Créd/Déb', df.columns[2], df.columns[3]]:
        if col in df.columns:
            if 'Realizado' in df[col].astype(str).values:
                col_status = col
                break
    
    if col_status:
        df = df[df[col_status].astype(str).str.strip().str.lower() == 'realizado'].copy()

    # Tratamento de datas
    df['DataRef'] = pd.to_datetime(df['DataRef'], errors='coerce')
    df = df.dropna(subset=['DataRef'])
    df['AnoRef'] = df['DataRef'].dt.year.astype(int)
    df['MêsRef'] = df['DataRef'].dt.month.astype(int)
    
    # Mapeamento do nome dos meses
    meses_map = {
        1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun',
        7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
    }
    df['MêsNome'] = df['MêsRef'].map(meses_map)
    
    return df

try:
    df_raw = load_data(ONEDRIVE_LINK)
    st.sidebar.success("✅ Conectado ao SharePoint! (Filtro: Apenas Realizados)")
except Exception as e:
    st.error(f"Erro ao carregar os dados do SharePoint: {e}")
    st.stop()

# --- FILTROS LATERAIS ---
st.sidebar.header("⚙️ Filtros")

# 1. Filtro de Moeda
moeda = st.sidebar.radio("Selecione a Moeda", options=['USD', 'BRL', 'EUR'], index=0)

# 2. Filtro por Ano
anos_disponiveis = sorted(df_raw['AnoRef'].unique(), reverse=True)
anos_selecionados = st.sidebar.multiselect("AnoRef", options=anos_disponiveis, default=anos_disponiveis[:2])

# 3. Filtro por Mês (Seleção de Meses para Somar)
meses_ordem = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
meses_disponiveis = [m for m in meses_ordem if m in df_raw['MêsNome'].unique()]
meses_selecionados = st.sidebar.multiselect("Meses", options=meses_disponiveis, default=meses_disponiveis)

# Aplicar filtros
df_filtered = df_raw.copy()

if anos_selecionados:
    df_filtered = df_filtered[df_filtered['AnoRef'].isin(anos_selecionados)]

if meses_selecionados:
    df_filtered = df_filtered[df_filtered['MêsNome'].isin(meses_selecionados)]

df_filtered['Valor_Ativo'] = pd.to_numeric(df_filtered[moeda], errors='coerce').fillna(0)

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

# --- KPI 4: RESULTADO POR MERCADO (RATEIO DE DESPESAS GLOBAIS) ---
st.markdown("---")
st.subheader("🌐 4. Resultado por Mercado (Com Rateio Proporcional de Despesas Globais)")

rec_merc = df_filtered[df_filtered['Classificação'] == 'Revenue'].groupby('Mercado')['Valor_Ativo'].sum()
tot_rec_merc = rec_merc.sum()
desp_merc = df_filtered[df_filtered['Classificação'].isin(['Expenses', 'Partner'])].groupby('Mercado')['Valor_Ativo'].sum().abs()
desp_global_merc = desp_merc.get('Global', 0)

resultado_merc = []
for m in [m for m in rec_merc.index if m != 'Global']:
    r = rec_merc.get(m, 0)
    pct = (r / tot_rec_merc) if tot_rec_merc > 0 else 0
    d_dir = desp_merc.get(m, 0)
    d_glob = desp_global_merc * pct
    d_tot = d_dir + d_glob
    
    resultado_merc.append({
        "Mercado": m,
        "Gross Revenue": r,
        "Share Receita (%)": pct * 100,
        "Despesa Direta": d_dir,
        "Despesa Global Alocada": d_glob,
        "Despesa Total": d_tot,
        "Resultado Net": r - d_tot
    })

st.dataframe(pd.DataFrame(resultado_merc).style.format({
    'Gross Revenue': '{:,.2f}',
    'Share Receita (%)': '{:.2f}%',
    'Despesa Direta': '{:,.2f}',
    'Despesa Global Alocada': '{:,.2f}',
    'Despesa Total': '{:,.2f}',
    'Resultado Net': '{:,.2f}'
}), use_container_width=True)

# --- KPI 5: RESULTADO POR BRAND / SERVIÇO (RATEIO DE DESPESAS GLOBAIS) ---
st.markdown("---")
st.subheader("🏷️ 5. Resultado por Brand / Serviço (Com Rateio Proporcional de Despesas Globais)")

rec_serv = df_filtered[df_filtered['Classificação'] == 'Revenue'].groupby('Serviço')['Valor_Ativo'].sum()
tot_rec_serv = rec_serv.sum()
desp_serv = df_filtered[df_filtered['Classificação'].isin(['Expenses', 'Partner'])].groupby('Serviço')['Valor_Ativo'].sum().abs()
desp_global_serv = desp_serv.get('Global', 0)

resultado_serv = []
for s in [s for s in rec_serv.index if s != 'Global']:
    r = rec_serv.get(s, 0)
    pct = (r / tot_rec_serv) if tot_rec_serv > 0 else 0
    d_dir = desp_serv.get(s, 0)
    d_glob = desp_global_serv * pct
    d_tot = d_dir + d_glob
    
    resultado_serv.append({
        "Brand / Serviço": s,
        "Gross Revenue": r,
        "Share Receita (%)": pct * 100,
        "Despesa Direta": d_dir,
        "Despesa Global Alocada": d_glob,
        "Despesa Total": d_tot,
        "Resultado Net": r - d_tot
    })

st.dataframe(pd.DataFrame(resultado_serv).style.format({
    'Gross Revenue': '{:,.2f}',
    'Share Receita (%)': '{:.2f}%',
    'Despesa Direta': '{:,.2f}',
    'Despesa Global Alocada': '{:,.2f}',
    'Despesa Total': '{:,.2f}',
    'Resultado Net': '{:,.2f}'
}), use_container_width=True)
