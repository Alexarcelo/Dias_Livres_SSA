import streamlit as st
import mysql.connector
import decimal
import pandas as pd
from datetime import timedelta
import matplotlib.pyplot as plt
import gspread 
from google.cloud import secretmanager 
import json
from google.oauth2.service_account import Credentials

def gerar_df_sales(base_luck):
    # Parametros de Login AWS
    config = {
    'user': 'user_automation_jpa',
    'password': 'luck_jpa_2024',
    'host': 'comeia.cixat7j68g0n.us-east-1.rds.amazonaws.com',
    'database': base_luck
    }
    # Conexão as Views
    conexao = mysql.connector.connect(**config)
    cursor = conexao.cursor()

    request_name = f'SELECT `Cod_Reserva_Principal`, `Cod_Reserva`, `Data_Servico`, `Data Execucao` FROM vw_sales'

    # Script MySql para requests
    cursor.execute(
        request_name
    )
    # Coloca o request em uma variavel
    resultado = cursor.fetchall()
    # Busca apenas o cabecalhos do Banco
    cabecalho = [desc[0] for desc in cursor.description]

    # Fecha a conexão
    cursor.close()
    conexao.close()

    # Coloca em um dataframe e muda o tipo de decimal para float
    df = pd.DataFrame(resultado, columns=cabecalho)
    df = df.applymap(lambda x: float(x) if isinstance(x, decimal.Decimal) else x)
    return df

def gerar_df_router(base_luck):
    
    config = {
    'user': 'user_automation_jpa',
    'password': 'luck_jpa_2024',
    'host': 'comeia.cixat7j68g0n.us-east-1.rds.amazonaws.com',
    'database': base_luck
    }
    
    conexao = mysql.connector.connect(**config)
    cursor = conexao.cursor()

    request_name = f'SELECT `Reserva`, `Data Execucao`, `Status do Servico`, `Status da Reserva`, `Tipo de Servico`, `Servico`, `Cliente`, `Parceiro`, `Total ADT`, `Total CHD`, `Est Origem`, `Est Destino` FROM vw_router'

    # Script MySql para requests
    cursor.execute(
        request_name
    )
    # Coloca o request em uma variavel
    resultado = cursor.fetchall()
    # Busca apenas o cabecalhos do Banco
    cabecalho = [desc[0] for desc in cursor.description]

    # Fecha a conexão
    cursor.close()
    conexao.close()

    # Coloca em um dataframe e muda o tipo de decimal para float
    df = pd.DataFrame(resultado, columns=cabecalho)
    df = df.applymap(lambda x: float(x) if isinstance(x, decimal.Decimal) else x)
    return df

def calcular_media_estadia(df_ultimos_servicos_filtrado):

    df_ref = df_ultimos_servicos_filtrado[~(pd.isna(df_ultimos_servicos_filtrado['Data OUT']))].reset_index(drop=True)

    df_ref['Data IN'] = pd.to_datetime(df_ref['Data IN'])

    df_ref['Data OUT'] = pd.to_datetime(df_ref['Data OUT'])

    df_ref['Dias Estadia'] = (df_ref['Data OUT'] - df_ref['Data IN']).dt.days

    df_ref['Dias Estadia'] = df_ref['Dias Estadia'].astype(int)

    media_estadia = round(df_ref['Dias Estadia'].mean(), 0)

    return media_estadia

def puxar_df_sales():

    st.session_state.df_sales = gerar_df_sales(st.session_state.base_luck)

    st.session_state.df_sales = st.session_state.df_sales.rename(columns={'Cod_Reserva_Principal': 'Reserva Mae'})

    st.session_state.df_sales.loc[pd.isna(st.session_state.df_sales['Reserva Mae']), 'Reserva Mae'] = st.session_state.df_sales['Cod_Reserva']

    st.session_state.df_sales['Data_Servico'] = pd.to_datetime(st.session_state.df_sales['Data_Servico'], unit='s').dt.date

def puxar_df_router_2():

    st.session_state.df_router_2_bruto = gerar_df_router(st.session_state.base_luck)

    st.session_state.filtrar_servicos_geral = []

    st.session_state.filtrar_servicos_geral.extend(list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Serviços IN'].tolist())))

    st.session_state.filtrar_servicos_geral.extend(list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Serviços TOUR'].tolist())))

    st.session_state.df_router_2 = \
        st.session_state.df_router_2_bruto[(~st.session_state.df_router_2_bruto['Status do Servico'].isin(list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Status do Serviço'].tolist())))) & 
                                         (~st.session_state.df_router_2_bruto['Status da Reserva'].isin(list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Status da Reserva'].tolist())))) & 
                                         (~pd.isna(st.session_state.df_router_2_bruto[list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Colunas Vazias'].tolist()))]).any(axis=1)) &
                                         (~st.session_state.df_router_2_bruto['Servico'].isin(st.session_state.filtrar_servicos_geral))].reset_index(drop=True)
    
    st.session_state.df_router_2['Data Execucao'] = pd.to_datetime(st.session_state.df_router_2['Data Execucao'])

    st.session_state.df_router_2['Reserva Mae'] = st.session_state.df_router_2['Reserva'].str[:10]  

    reservas_com_combo = st.session_state.df_router_2.loc[st.session_state.df_router_2['Servico'].isin(list(filter(lambda x: x != '', st.session_state.df_config['Combos Flexíveis'].tolist()))), 
                                                        'Reserva Mae'].unique()
    
    st.session_state.df_router_2 = st.session_state.df_router_2[~st.session_state.df_router_2['Reserva Mae'].isin(reservas_com_combo)].reset_index(drop=True) 
    
    st.session_state.df_router_2['Total Paxs'] = st.session_state.df_router_2[['Total ADT', 'Total CHD']].sum(axis=1)

def puxar_dados_phoenix():

    puxar_df_sales()

    puxar_df_router_2()

def gerar_df_ultimos_servicos():

    st.session_state.df_router_2 = st.session_state.df_router_2.drop_duplicates(subset=['Reserva Mae', 'Data Execucao']).reset_index(drop=True)

    df_trf_in_repetidos = st.session_state.df_router_2[st.session_state.df_router_2['Tipo de Servico']=='IN'].groupby(['Reserva Mae'])['Servico'].count().reset_index()

    df_trf_in_repetidos = df_trf_in_repetidos[df_trf_in_repetidos['Servico']>1].reset_index(drop=True)

    st.session_state.df_router_2 = st.session_state.df_router_2[~st.session_state.df_router_2['Reserva Mae'].isin(df_trf_in_repetidos['Reserva Mae'].unique().tolist())].reset_index(drop=True)

    df_trf_out_repetidos = st.session_state.df_router_2[st.session_state.df_router_2['Tipo de Servico']=='OUT'].groupby(['Reserva Mae'])['Servico'].count().reset_index()

    df_trf_out_repetidos = df_trf_out_repetidos[df_trf_out_repetidos['Servico']>1].reset_index(drop=True)

    st.session_state.df_router_2 = st.session_state.df_router_2[~st.session_state.df_router_2['Reserva Mae'].isin(df_trf_out_repetidos['Reserva Mae'].unique().tolist())].reset_index(drop=True)

    df_ultimos_servicos = (st.session_state.df_router_2.groupby('Reserva Mae', as_index=False)\
                           .agg({'Data Execucao': ['max', 'min'], 'Cliente': 'first', 'Parceiro': 'first', 'Total Paxs': 'first', 'Est Origem': 'first', 'Est Destino': 'first'}))

    df_ultimos_servicos.columns = ['Reserva Mae', 'Data Ultimo Servico', 'Data Primeiro Servico', 'Cliente', 'Parceiro', 'Total Paxs', 'Est Origem', 'Est Destino']

    df_ultimos_servicos['Data Ultimo Servico'] = df_ultimos_servicos['Data Ultimo Servico'].dt.date

    df_ultimos_servicos['Data Primeiro Servico'] = df_ultimos_servicos['Data Primeiro Servico'].dt.date

    df_ultimos_servicos_filtrado = df_ultimos_servicos[(df_ultimos_servicos['Data Ultimo Servico'] >= st.session_state.data_inicial) & 
                                                       (df_ultimos_servicos['Data Ultimo Servico'] <= st.session_state.data_final)].reset_index(drop=True)
    
    return df_ultimos_servicos_filtrado

def incluir_data_in_out(df_ultimos_servicos_filtrado):

    df_in = st.session_state.df_router_2[st.session_state.df_router_2['Tipo de Servico']=='IN'].reset_index(drop=True)

    df_in['Data Execucao'] = df_in['Data Execucao'].dt.date

    df_in = df_in.rename(columns={'Data Execucao': 'Data IN'})

    df_ultimos_servicos_filtrado = pd.merge(df_ultimos_servicos_filtrado, df_in[['Reserva Mae', 'Data IN', 'Servico']], on='Reserva Mae', how='left')

    df_ultimos_servicos_filtrado = df_ultimos_servicos_filtrado[~pd.isna(df_ultimos_servicos_filtrado['Data IN'])].reset_index(drop=True)

    df_out = st.session_state.df_router_2[st.session_state.df_router_2['Tipo de Servico']=='OUT'].reset_index(drop=True)

    df_out['Data Execucao'] = df_out['Data Execucao'].dt.date

    df_out = df_out.rename(columns={'Data Execucao': 'Data OUT'})

    df_ultimos_servicos_filtrado = pd.merge(df_ultimos_servicos_filtrado, df_out[['Reserva Mae', 'Data OUT']], on='Reserva Mae', how='left')

    st.session_state.media_estadia = calcular_media_estadia(df_ultimos_servicos_filtrado)

    df_ultimos_servicos_filtrado.loc[pd.isna(df_ultimos_servicos_filtrado['Data OUT']), 'Data OUT'] = df_ultimos_servicos_filtrado['Data IN'] + timedelta(days=st.session_state.media_estadia)

    return df_ultimos_servicos_filtrado

def grafico_linha_percentual(referencia, eixo_x, eixo_y_1, ref_1_label, titulo):

    referencia[eixo_x] = referencia[eixo_x].astype(str)
    
    fig, ax = plt.subplots(figsize=(15, 8))
    
    plt.plot(referencia[eixo_x], referencia[eixo_y_1], label = ref_1_label, linewidth = 0.5, color = 'black')
    
    for i in range(len(referencia[eixo_x])):
        texto = str(round(referencia[eixo_y_1][i] * 100, 1)) + "%"
        plt.text(referencia[eixo_x][i], referencia[eixo_y_1][i], texto, ha='center', va='bottom')

    plt.title(titulo, fontsize=30)
    plt.xlabel('Ano/Mês')
    ax.legend(loc='lower right', bbox_to_anchor=(1.2, 1))
    st.pyplot(fig)
    plt.close(fig)

def contabilizar_servicos_depois_in_e_total(df_ultimos_servicos_filtrado):

    # Criação de um mapeamento para reserva -> data IN
    reserva_to_data_in = df_ultimos_servicos_filtrado.set_index('Reserva Mae')['Data IN']

    # Calcular Servicos Depois do IN
    df_sales = st.session_state.df_sales
    df_sales = df_sales[df_sales['Reserva Mae'].isin(reserva_to_data_in.index)]
    df_sales['Data_Servico'] = pd.to_datetime(df_sales['Data_Servico'])  # Certifique-se de que é datetime

    servicos_depois_in = df_sales[df_sales['Data_Servico'] >= df_sales['Reserva Mae'].map(reserva_to_data_in)]
    servicos_count = servicos_depois_in.groupby('Reserva Mae')['Data Execucao'].nunique()

    # Calcular Total Servicos
    df_router_2 = st.session_state.df_router_2
    total_servicos_count = df_router_2.groupby('Reserva Mae')['Data Execucao'].nunique()

    # Atualizar DataFrame original
    df_ultimos_servicos_filtrado['Servicos Depois do IN'] = df_ultimos_servicos_filtrado['Reserva Mae'].map(servicos_count).fillna(0)
    df_ultimos_servicos_filtrado['Total Servicos'] = df_ultimos_servicos_filtrado['Reserva Mae'].map(total_servicos_count).fillna(0)
    df_ultimos_servicos_filtrado = recalcular_servicos_reservas_diferentes(df_ultimos_servicos_filtrado)

    return df_ultimos_servicos_filtrado

def contabilizar_dias_livres_chegada_e_saida(df_ultimos_servicos_filtrado):

    df_ultimos_servicos_filtrado['Dias Livres na Chegada'] = df_ultimos_servicos_filtrado['Dias Estadia'] - \
        (df_ultimos_servicos_filtrado['Total Servicos'] - df_ultimos_servicos_filtrado['Servicos Depois do IN'])

    df_ultimos_servicos_filtrado['Dias Livres na Saída'] = df_ultimos_servicos_filtrado['Dias Livres na Chegada'] - df_ultimos_servicos_filtrado['Servicos Depois do IN']

    df_ultimos_servicos_filtrado = df_ultimos_servicos_filtrado[df_ultimos_servicos_filtrado['Dias Livres na Saída']>-1].reset_index(drop=True)

    return df_ultimos_servicos_filtrado

def criar_colunas_ano_mes(df):

    df['ano'] = pd.to_datetime(df['Data OUT']).dt.year

    df['mes'] = pd.to_datetime(df['Data OUT']).dt.month

def ajustar_dataframe_group_mensal(df):

    df_group = df.groupby(['ano', 'mes'])[['Dias Livres na Chegada', 'Dias Livres na Saída']].sum().reset_index()

    df_group = df_group[(df_group['mes']>=data_inicial.month) & (df_group['mes']<=data_final.month)].reset_index(drop=True)

    df_group['mes/ano'] = pd.to_datetime(df_group['ano'].astype(str) + '-' + df_group['mes'].astype(str)).dt.to_period('M')

    df_group['Aproveitamento'] = round(-(df_group['Dias Livres na Saída']/df_group['Dias Livres na Chegada']-1), 4)

    return df_group

def recalcular_servicos_reservas_diferentes(df_in_out, data_relatorio):

    df_in_out['Data IN'] = pd.to_datetime(df_in_out['Data IN'])
    df_in_out['Data OUT'] = pd.to_datetime(df_in_out['Data OUT'])

    df_router_2 = st.session_state.df_router[(st.session_state.df_router['Data Execucao']>=data_relatorio) & (st.session_state.df_router['Tipo de Servico'].isin(['TOUR', 'TRANSFER']))]\
        .reset_index(drop=True)
    df_router_2['Chave'] = df_router_2['Cliente'] + "|" + df_router_2['Parceiro']

    df_in_out['Chave'] = df_in_out['Cliente'] + "|" + df_in_out['Parceiro']

    dias_por_chave = df_router_2.groupby('Chave')['Data Execucao'].nunique()
    
    df_in_out['Qtd. Servicos'] = df_in_out['Chave'].map(dias_por_chave).fillna(df_in_out['Qtd. Servicos'])

    df_in_out['Dias Livres'] = df_in_out['Dias Estadia'] - df_in_out['Qtd. Servicos']

    return df_in_out

def recalcular_servicos_reservas_diferentes(df_in_out):
    
    df_in_out['Data IN'] = pd.to_datetime(df_in_out['Data IN'])
    df_in_out['Data OUT'] = pd.to_datetime(df_in_out['Data OUT'])

    # Preparar chave para agrupamento
    df_router_2 = st.session_state.df_router_2[(st.session_state.df_router_2['Tipo de Servico'].isin(['TOUR', 'TRANSFER']))].reset_index(drop=True)
    df_router_2['Chave'] = df_router_2['Cliente'] + "|" + df_router_2['Parceiro']

    # Criar chave no DataFrame original
    df_in_out['Chave'] = df_in_out['Cliente'] + "|" + df_in_out['Parceiro']

    # Agrupar pelo campo "Chave"
    df_ref = df_router_2.groupby('Chave')
    dias_por_chave = df_ref['Data Execucao'].nunique()

    # Atualizar Total Servicos para chaves com múltiplas reservas
    df_in_out['Total Servicos'] = df_in_out['Chave'].map(dias_por_chave).fillna(df_in_out['Total Servicos'])

    return df_in_out

def puxar_aba_simples(id_gsheet, nome_aba, nome_df):

    nome_credencial = st.secrets["CREDENCIAL_SHEETS"]
    credentials = service_account.Credentials.from_service_account_info(nome_credencial)
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    credentials = credentials.with_scopes(scope)
    client = gspread.authorize(credentials)

    spreadsheet = client.open_by_key(id_gsheet)
    
    sheet = spreadsheet.worksheet(nome_aba)

    sheet_data = sheet.get_all_values()

    st.session_state[nome_df] = pd.DataFrame(sheet_data[1:], columns=sheet_data[0])

def inserir_config(df_itens_faltantes, id_gsheet, nome_aba):

    nome_credencial = st.secrets["CREDENCIAL_SHEETS"]
    credentials = service_account.Credentials.from_service_account_info(nome_credencial)
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    credentials = credentials.with_scopes(scope)
    client = gspread.authorize(credentials)
    
    spreadsheet = client.open_by_key(id_gsheet)

    sheet = spreadsheet.worksheet(nome_aba)

    sheet.batch_clear(["A2:Z100"])

    data = df_itens_faltantes.values.tolist()
    sheet.update('A2', data)

    st.success('Configurações salvas com sucesso!')

def plotar_analises(titulo, df):

    st.header(titulo)

    container_resultado = st.container(border=True)

    dias_livres_na_chegada = df['Dias Livres na Chegada'].sum()

    dias_livres_na_saída = df['Dias Livres na Saída'].sum()

    total_paxs_df_salvo = df['Total Paxs'].sum()

    aproveitamento = -(dias_livres_na_saída/dias_livres_na_chegada-1)

    container_resultado.subheader(f'Total de Paxs = {int(total_paxs_df_salvo)}')

    container_resultado.subheader(f'Dias Livres na Chegada = {int(dias_livres_na_chegada)}')

    container_resultado.subheader(f'Dias Livres na Saída = {int(dias_livres_na_saída)}')

    container_resultado.subheader(f'Aproveitamento = {round(aproveitamento*100, 1)}%')

st.set_page_config(layout='wide')

if not 'df_config' in st.session_state:

    puxar_aba_simples(st.session_state.id_sheet, st.session_state.aba_sheet, 'df_config')

if not 'mostrar_config' in st.session_state:

    st.session_state.mostrar_config = False

# Títulos da página

st.title(st.session_state.titulo_4)

st.subheader('*apenas paxs com TRF IN*')

row0 = st.columns(1)

st.divider()

st.header('Configurações')

alterar_configuracoes = st.button('Visualizar Configurações')

if alterar_configuracoes:

    if st.session_state.mostrar_config == True:

        st.session_state.mostrar_config = False

    else:

        st.session_state.mostrar_config = True

row01 = st.columns(3)

if st.session_state.mostrar_config == True:

    with row01[0]:

        lista_opcoes_status_servicos = sorted(set(sorted(st.session_state.df_router_bruto['Status do Servico'].dropna().unique().tolist()) + 
                                                  list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Status do Serviço'].tolist()))))

        filtrar_status_servico = st.multiselect('Excluir Status do Serviço', lista_opcoes_status_servicos, key='filtrar_status_servico', 
                                                default=list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Status do Serviço'].tolist())))
        
        lista_opcoes_status_reserva = sorted(set(sorted(st.session_state.df_router_bruto['Status da Reserva'].unique().tolist()) + 
                                                 list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Status da Reserva'].tolist()))))

        filtrar_status_reserva = st.multiselect('Excluir Status da Reserva', lista_opcoes_status_reserva, key='filtrar_status_reserva', 
                                                default=list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Status da Reserva'].tolist())))
        
        combos_flex = st.multiselect('Combo Flexível', 
                                     sorted(st.session_state.df_router_bruto[st.session_state.df_router_bruto['Servico'].str.upper().str.contains('COMBO')]['Servico'].dropna().unique().tolist()), 
                                     key='combos_flex', default=list(filter(lambda x: x != '', st.session_state.df_config['Combos Flexíveis'].tolist())))

    with row01[1]:

        lista_opcoes_servicos_in = sorted(set(sorted(st.session_state.df_router_bruto[st.session_state.df_router_bruto['Tipo de Servico']=='IN']['Servico'].unique().tolist()) + 
                                                     list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Serviços IN'].tolist()))))
        
        filtrar_servicos_in = st.multiselect('Excluir Serviços IN', lista_opcoes_servicos_in, key='filtrar_servicos_in', 
                                             default=list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Serviços IN'].tolist())))
        
        lista_opcoes_servicos = sorted(set(sorted(st.session_state.df_router_bruto[st.session_state.df_router_bruto['Tipo de Servico'].dropna().isin(['TOUR', 'TRANSFER'])]['Servico'].unique().tolist()) + 
                                           list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Serviços TOUR'].tolist()))))
        
        container_servicos = st.container(height=200)
        
        filtrar_servicos_tt = container_servicos.multiselect('Excluir Serviços TOUR', lista_opcoes_servicos, key='filtrar_servicos_tt', 
                                             default=list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Serviços TOUR'].tolist())))
        
    with row01[2]:

        filtrar_colunas_vazias = st.multiselect('Não Permitir Valor Vazio', sorted(st.session_state.df_router_bruto.columns.tolist()), key='filtrar_colunas_vazias', 
                                                default=list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Colunas Vazias'].tolist())))
        
        hoteis_all_inclusive = st.multiselect('Hoteis All Inclusive', 
                                            sorted(st.session_state.df_router_bruto[st.session_state.df_router_bruto['Tipo de Servico']=='IN']['Est Destino'].dropna().unique().tolist()), 
                                            key='hoteis_all_inclusive', default=list(filter(lambda x: x != '', st.session_state.df_config['Hoteis All Inclusive'].tolist())))
        
        st.session_state.filtrar_servicos_geral = []

        st.session_state.filtrar_servicos_geral.extend(filtrar_servicos_in)

        st.session_state.filtrar_servicos_geral.extend(filtrar_servicos_tt)

    salvar_config = st.button('Salvar Configurações')

    if salvar_config:

        lista_escolhas = [filtrar_status_servico, filtrar_status_reserva, filtrar_colunas_vazias, filtrar_servicos_in, filtrar_servicos_tt, hoteis_all_inclusive, combos_flex]

        st.session_state.df_config = pd.DataFrame({f'Coluna{i+1}': pd.Series(lista) for i, lista in enumerate(lista_escolhas)})

        st.session_state.df_config = st.session_state.df_config.fillna('')

        inserir_config(st.session_state.df_config, st.session_state.id_sheet, st.session_state.aba_sheet)

        puxar_aba_simples(st.session_state.id_sheet, st.session_state.aba_sheet, 'df_config')

st.divider()

# Puxar dados do Phoenix

if not 'df_sales' in st.session_state:

    with st.spinner('Puxando dados do Phoenix...'):

        puxar_dados_phoenix()

row1 = st.columns(2)

st.divider()

row12 = st.columns(3)

st.divider()

row2 = st.columns(1)

st.divider()

row3 = st.columns(1)

# Botão pra atualizar dados do Phoenix

with row1[0]:

    atualizar_phoenix = st.button('Atualizar Dados Phoenix')

    if atualizar_phoenix:

        with st.spinner('Puxando dados do Phoenix...'):

            puxar_dados_phoenix()

# Container com botão de datas e botão de gerar análise

with row1[0]:

    container_datas = st.container(border=True)

    container_datas.subheader('Período')

    data_inicial = container_datas.date_input('Data Inicial', value=None ,format='DD/MM/YYYY', key='data_inicial')

    data_final = container_datas.date_input('Data Final', value=None ,format='DD/MM/YYYY', key='data_final')

    gerar_analise = container_datas.button('Gerar Análise')

# Script de geração de análise

if gerar_analise and data_final and data_inicial:

    # Tirando dados do dataframe usado pra mostrar gráfico

    if 'df_group_salvo' in st.session_state:

        st.session_state.df_group_salvo = st.session_state.df_group_salvo.iloc[0:0]

    # Inserir colunas de Data Ultimo Servico e Data Primeiro Servico e filtrar as reservas que tem ultimo serviço dentro do período especificado

    df_ultimos_servicos_filtrado = gerar_df_ultimos_servicos()

    # Inclusão de data de IN e data de OUT e definição de data de OUT em cima de média de estadia p/ reservas sem OUT

    df_ultimos_servicos_filtrado = incluir_data_in_out(df_ultimos_servicos_filtrado)

    # Criando coluna Dias Estadia

    df_ultimos_servicos_filtrado['Dias Estadia'] = (pd.to_datetime(df_ultimos_servicos_filtrado['Data OUT']) - pd.to_datetime(df_ultimos_servicos_filtrado['Data IN'])).dt.days + 1

    st.session_state.df_reservas_negativas = df_ultimos_servicos_filtrado[df_ultimos_servicos_filtrado['Dias Estadia']<0].reset_index(drop=True)

    df_ultimos_servicos_filtrado = df_ultimos_servicos_filtrado[(df_ultimos_servicos_filtrado['Dias Estadia']>=0) & (df_ultimos_servicos_filtrado['Dias Estadia']<100)].reset_index(drop=True)

    df_ultimos_servicos_filtrado = df_ultimos_servicos_filtrado.drop_duplicates().reset_index(drop=True)

    # Contabilizando Serviços Depois do IN e Total Serviços de cada reserva

    df_ultimos_servicos_filtrado = contabilizar_servicos_depois_in_e_total(df_ultimos_servicos_filtrado)

    # Contabilizar Dias Livres na Chegada e Dias Livres na Saída (e filtrando reservas que não tenham dias livres na saída > -1)

    df_ultimos_servicos_filtrado = contabilizar_dias_livres_chegada_e_saida(df_ultimos_servicos_filtrado)

    st.session_state.df_salvo = df_ultimos_servicos_filtrado

    st.session_state.df_salvo_sem_all_inclusive = \
    st.session_state.df_salvo[(~st.session_state.df_salvo['Est Origem'].isin(list(filter(lambda x: x != '', st.session_state.df_config['Hoteis All Inclusive'].tolist())))) & 
                              (~st.session_state.df_salvo['Est Destino'].isin(list(filter(lambda x: x != '', st.session_state.df_config['Hoteis All Inclusive'].tolist()))))].reset_index(drop=True)
    
    st.session_state.df_salvo_apenas_all_inclusive = \
    st.session_state.df_salvo[(st.session_state.df_salvo['Est Origem'].isin(list(filter(lambda x: x != '', st.session_state.df_config['Hoteis All Inclusive'].tolist())))) | 
                              (st.session_state.df_salvo['Est Destino'].isin(list(filter(lambda x: x != '', st.session_state.df_config['Hoteis All Inclusive'].tolist()))))].reset_index(drop=True)

    if data_inicial.month != data_final.month:

        # Criando colunas ano e mes

        criar_colunas_ano_mes(st.session_state.df_salvo)

        criar_colunas_ano_mes(st.session_state.df_salvo_sem_all_inclusive)

        criar_colunas_ano_mes(st.session_state.df_salvo_apenas_all_inclusive)

        # Agrupando dataframe por ano e mes, criando coluna mes_ano, filtrando período selecionado pelo usuário e calculando o aproveitamento de cada mês

        st.session_state.df_group_salvo = ajustar_dataframe_group_mensal(st.session_state.df_salvo)

        st.session_state.df_group_salvo_sem_all_inclusive = ajustar_dataframe_group_mensal(st.session_state.df_salvo_sem_all_inclusive)

        st.session_state.df_group_salvo_apenas_all_inclusive = ajustar_dataframe_group_mensal(st.session_state.df_salvo_apenas_all_inclusive)

if 'df_reservas_negativas' in st.session_state:

    nomes_reservas = ', '.join(st.session_state.df_reservas_negativas['Reserva Mae'].unique().tolist())

    n_reservas = len(st.session_state.df_reservas_negativas['Reserva Mae'].unique().tolist())

    if n_reservas>0:

        with row0[0]:

            with st.expander(f'*Existem {n_reservas} reservas com data de OUT antes do IN e, portanto, foram desconsideradas da análise*'):

                st.markdown(f'*{nomes_reservas}*')

# Gráfico de resultado de análise entre meses diferentes

if 'df_group_salvo' in st.session_state and len(st.session_state.df_group_salvo)>0:

    if len(list(filter(lambda x: x != '', st.session_state.df_config['Hoteis All Inclusive'].tolist())))==0:

        with row2[0]:

            grafico_linha_percentual(st.session_state.df_group_salvo, 'mes/ano', 'Aproveitamento', 'Aproveitamento', 'Aproveitamento Dias Livres | Geral')

    else:

        with row2[0]:

            grafico_linha_percentual(st.session_state.df_group_salvo, 'mes/ano', 'Aproveitamento', 'Aproveitamento', 'Aproveitamento Dias Livres | Geral')

            grafico_linha_percentual(st.session_state.df_group_salvo_sem_all_inclusive, 'mes/ano', 'Aproveitamento', 'Aproveitamento', 'Aproveitamento Dias Livres | Sem All Inclusive')

            grafico_linha_percentual(st.session_state.df_group_salvo_apenas_all_inclusive, 'mes/ano', 'Aproveitamento', 'Aproveitamento', 'Aproveitamento Dias Livres | Apenas All Inclusive')

# Texto de resultado de análise

if 'df_salvo' in st.session_state:

    with row12[0]:

        plotar_analises('Análise Geral', st.session_state.df_salvo)

    if len(list(filter(lambda x: x != '', st.session_state.df_config['Hoteis All Inclusive'].tolist())))>0:

        with row12[1]:

            plotar_analises('Análise s/ All Inclusive', st.session_state.df_salvo_sem_all_inclusive)

        with row12[2]:

            plotar_analises('Análise Apenas All Inclusive', st.session_state.df_salvo_apenas_all_inclusive)

    with row3[0]:

        st.header('Análise por Serviço')

        filtrar_servicos_analise = st.multiselect('Visualizar Apenas:', sorted(st.session_state.df_salvo['Servico'].unique().tolist()), default=None)

        if len(list(filter(lambda x: x != '', st.session_state.df_config['Hoteis All Inclusive'].tolist())))>0:

            visualizar_all_inclusive = st.multiselect('Visualização Hoteis All Inclusive', ['Desconsiderar Hoteis All Inclusive', 'Considerar Apenas Hoteis All Inclusive'], default=None)

        else:

            visualizar_all_inclusive = None

        if len(filtrar_servicos_analise)>0:

            if visualizar_all_inclusive is not None:

                if len(visualizar_all_inclusive)==1 and visualizar_all_inclusive[0]=='Desconsiderar Hoteis All Inclusive':

                    df_analise = st.session_state.df_salvo_sem_all_inclusive.copy()

                elif len(visualizar_all_inclusive)==1 and visualizar_all_inclusive[0]=='Considerar Apenas Hoteis All Inclusive':

                    df_analise = st.session_state.df_salvo_apenas_all_inclusive.copy()

                elif len(visualizar_all_inclusive)==0:

                    df_analise = st.session_state.df_salvo.copy()

            else:

                df_analise = st.session_state.df_salvo.copy()

            df_analise = df_analise[df_analise['Servico'].isin(filtrar_servicos_analise)].reset_index(drop=True)

            nome_servicos = ', '.join(filtrar_servicos_analise)

            plotar_analises(f'Análise {nome_servicos}', df_analise)

            if 'df_group_salvo' in st.session_state and len(st.session_state.df_group_salvo)>0:

                df_group_analise = ajustar_dataframe_group_mensal(df_analise)

                grafico_linha_percentual(df_group_analise, 'mes/ano', 'Aproveitamento', 'Aproveitamento', 'Aproveitamento Dias Livres')

        st.header('Análise por Parceiro')

        filtrar_parceiros_analise = st.multiselect('Visualizar Apenas:', sorted(st.session_state.df_salvo['Parceiro'].unique().tolist()), default=None)

        if len(list(filter(lambda x: x != '', st.session_state.df_config['Hoteis All Inclusive'].tolist())))>0:

            visualizar_all_inclusive_2 = st.multiselect('Visualização Hoteis All Inclusive', ['Desconsiderar Hoteis All Inclusive', 'Considerar Apenas Hoteis All Inclusive'], default=None, 
                                                        key='visualizar_all_inclusive_2')

        else:

            visualizar_all_inclusive_2 = None

        if len(filtrar_parceiros_analise)>0:

            if visualizar_all_inclusive_2 is not None:

                if len(visualizar_all_inclusive_2)==1 and visualizar_all_inclusive_2[0]=='Desconsiderar Hoteis All Inclusive':

                    df_analise = st.session_state.df_salvo_sem_all_inclusive.copy()

                elif len(visualizar_all_inclusive_2)==1 and visualizar_all_inclusive_2[0]=='Considerar Apenas Hoteis All Inclusive':

                    df_analise = st.session_state.df_salvo_apenas_all_inclusive.copy()

                elif len(visualizar_all_inclusive_2)==0:

                    df_analise = st.session_state.df_salvo.copy()

            else:

                df_analise = st.session_state.df_salvo.copy()

            df_analise = df_analise[df_analise['Parceiro'].isin(filtrar_parceiros_analise)].reset_index(drop=True)

            nome_servicos = ', '.join(filtrar_parceiros_analise)

            plotar_analises(f'Análise {nome_servicos}', df_analise)

            if 'df_group_salvo' in st.session_state and len(st.session_state.df_group_salvo)>0:

                df_group_analise = ajustar_dataframe_group_mensal(df_analise)

                grafico_linha_percentual(df_group_analise, 'mes/ano', 'Aproveitamento', 'Aproveitamento', 'Aproveitamento Dias Livres')
