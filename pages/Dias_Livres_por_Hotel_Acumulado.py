import streamlit as st
import mysql.connector
import decimal
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder
from datetime import date, timedelta
import gspread 
from google.cloud import secretmanager 
import json
from google.oauth2.service_account import Credentials
from google.oauth2 import service_account

def gerar_df_phoenix(vw_name, base_luck):
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

    request_name = f'SELECT * FROM {vw_name}'

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

def puxar_dados_phoenix():

    st.session_state.df_router_bruto = gerar_df_phoenix('vw_router', st.session_state.base_luck)

    st.session_state.filtrar_servicos_geral = []

    st.session_state.filtrar_servicos_geral.extend(list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Serviços IN'].tolist())))

    st.session_state.filtrar_servicos_geral.extend(list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Serviços TOUR'].tolist())))

    st.session_state.df_router = \
        st.session_state.df_router_bruto[(~st.session_state.df_router_bruto['Status do Servico'].isin(list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Status do Serviço'].tolist())))) & 
                                         (~st.session_state.df_router_bruto['Status da Reserva'].isin(list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Status da Reserva'].tolist())))) & 
                                         (~pd.isna(st.session_state.df_router_bruto[list(filter(lambda x: x != '', st.session_state.df_config['Filtrar Colunas Vazias'].tolist()))]).any(axis=1)) &
                                         (~st.session_state.df_router_bruto['Servico'].isin(st.session_state.filtrar_servicos_geral))].reset_index(drop=True)

    st.session_state.df_router['Reserva Mae'] = st.session_state.df_router['Reserva'].str[:10] 

    reservas_com_combo = st.session_state.df_router.loc[st.session_state.df_router['Servico'].isin(list(filter(lambda x: x != '', st.session_state.df_config['Combos Flexíveis'].tolist()))), 
                                                        'Reserva Mae'].unique()
    
    st.session_state.df_router = st.session_state.df_router[~st.session_state.df_router['Reserva Mae'].isin(reservas_com_combo)].reset_index(drop=True) 
    
    st.session_state.df_router['Total Paxs'] = st.session_state.df_router[['Total ADT', 'Total CHD']].sum(axis=1)

def calcular_media_estadia():

    df_in_geral = st.session_state.df_router[(st.session_state.df_router['Tipo de Servico']=='IN')].reset_index(drop=True)

    df_in_geral = df_in_geral.drop_duplicates(subset=['Reserva Mae', 'Data Execucao']).reset_index(drop=True)

    df_in_geral = df_in_geral[~df_in_geral['Reserva Mae'].isin(df_in_geral[df_in_geral['Reserva Mae'].duplicated()]['Reserva Mae'].unique().tolist())].reset_index(drop=True)

    df_out_geral = st.session_state.df_router[(st.session_state.df_router['Tipo de Servico']=='OUT')].reset_index(drop=True)

    df_in_out_geral = pd.merge(df_in_geral[['Reserva Mae', 'Servico', 'Voo', 'Data Execucao']], df_out_geral[['Reserva Mae', 'Data Execucao']], on='Reserva Mae', how='left')

    df_in_out_geral = df_in_out_geral.rename(columns={'Data Execucao_x': 'Data IN', 'Data Execucao_y': 'Data OUT', 'Voo': 'Voo IN'})

    df_in_out_geral = df_in_out_geral[(~pd.isna(df_in_out_geral['Data OUT']))].reset_index(drop=True)

    df_in_out_geral['Dias Estadia'] = (pd.to_datetime(df_in_out_geral['Data OUT']) - pd.to_datetime(df_in_out_geral['Data IN'])).dt.days

    df_in_out_geral = df_in_out_geral[(df_in_out_geral['Dias Estadia']>=0)].reset_index(drop=True)

    df_in_out_geral['Dias Estadia'] = df_in_out_geral['Dias Estadia'].astype(int)

    df_in_out_geral = df_in_out_geral[~(pd.isna(df_in_out_geral['Voo IN']))].reset_index(drop=True)

    media_estadia = round(df_in_out_geral['Dias Estadia'].mean(), 0)

    return media_estadia

def inserir_datas_in_out_voo_in(df_in):

    lista_reservas_in = df_in['Reserva Mae'].unique().tolist()

    df_out = st.session_state.df_router[(st.session_state.df_router['Tipo de Servico']=='OUT') & (st.session_state.df_router['Reserva Mae'].isin(lista_reservas_in))].reset_index(drop=True)

    df_in_out = pd.merge(df_in[['Reserva Mae', 'Servico', 'Voo', 'Horario Voo', 'Data Execucao', 'Est Destino', 'Cliente', 'Telefone Cliente', 'Parceiro', 'Total Paxs']], 
                         df_out[['Reserva Mae', 'Data Execucao']], on='Reserva Mae', how='left')

    df_in_out = df_in_out.rename(columns={'Data Execucao_x': 'Data IN', 'Data Execucao_y': 'Data OUT', 'Voo': 'Voo IN'})

    df_in_out['Dias Estadia'] = (pd.to_datetime(df_in_out['Data OUT']) - pd.to_datetime(date.today())).dt.days

    df_in_out['Dias Estadia'] = df_in_out['Dias Estadia'].fillna(media_estadia)

    df_in_out['Dias Estadia'] = df_in_out['Dias Estadia'].astype(int)

    df_in_out['Dias Estadia'] = df_in_out['Dias Estadia']-1

    st.session_state.df_reservas_negativas = df_in_out[df_in_out['Dias Estadia']<0].reset_index(drop=True)

    st.session_state.df_reservas_negativas = st.session_state.df_reservas_negativas[st.session_state.df_reservas_negativas['Data OUT']>date.today()].reset_index(drop=True)

    df_in_out = df_in_out[(df_in_out['Dias Estadia']>=0) & (df_in_out['Dias Estadia']<100)].reset_index(drop=True)

    df_in_out = df_in_out.drop_duplicates().reset_index(drop=True)

    return df_in_out, lista_reservas_in

def contabilizar_servicos_por_reserva(df_in_out):

    df_tour_transfer = st.session_state.df_router[(st.session_state.df_router['Tipo de Servico'].isin(['TOUR', 'TRANSFER'])) & (st.session_state.df_router['Reserva Mae'].isin(lista_reservas_in)) & 
                                                  (st.session_state.df_router['Data Execucao']>date.today())].reset_index(drop=True)

    df_tour_transfer_group = df_tour_transfer.groupby(['Data Execucao', 'Reserva Mae'])['Servico'].count().reset_index()

    df_tour_transfer_group = df_tour_transfer_group.groupby(['Reserva Mae'])['Servico'].count().reset_index()

    df_tour_transfer_group = df_tour_transfer_group.rename(columns={'Servico': 'Qtd. Servicos'})

    df_in_out = pd.merge(df_in_out, df_tour_transfer_group, on='Reserva Mae', how='left')

    df_in_out['Qtd. Servicos'] = df_in_out['Qtd. Servicos'].fillna(0)

    return df_in_out

def calcular_estadia_dias_livres(df_in_out):

    df_in_out['Dias Livres'] = df_in_out['Dias Estadia']-df_in_out['Qtd. Servicos']

    return df_in_out

def plotar_tabela_com_voos_dias_livres(df_in_out):

    df_final = df_in_out.groupby('Est Destino').agg({'Dias Livres': 'sum'}).reset_index()

    df_final = df_final.sort_values(by=['Dias Livres'], ascending=False).reset_index(drop=True)

    gb = GridOptionsBuilder.from_dataframe(df_final)
    gb.configure_selection('multiple', use_checkbox=True, header_checkbox=True)
    gb.configure_grid_options(domLayout='autoHeight')
    gb.configure_grid_options(domLayout='autoWidth')
    gridOptions = gb.build()

    with row1[1]:

        grid_response = AgGrid(df_final, gridOptions=gridOptions, enable_enterprise_modules=False, fit_columns_on_grid_load=True)

    selected_rows = grid_response['selected_rows']

    return selected_rows

def plotar_tabela_row_servico_especifico(df_ref, row2):

    with row2[0]:

        container_dataframe = st.container()

        container_dataframe.dataframe(df_ref[['Reserva Mae', 'Cliente', 'Telefone Cliente', 'Est Destino', 'Data IN', 'Data OUT', 'Total Paxs', 'Qtd. Servicos', 'Dias Estadia', 
                                              'Dias Livres']].sort_values(by='Est Destino'), hide_index=True, use_container_width=True)

def filtrar_apenas_ultimo_trf_in(df_in):

    reservas_duplicadas = df_in[df_in['Reserva Mae'].duplicated()]['Reserva Mae'].unique().tolist()

    df_duplicados = df_in[df_in['Reserva Mae'].isin(reservas_duplicadas)].reset_index()

    df_duplicados_max_in = df_duplicados.groupby('Reserva Mae')['Data Execucao'].max().reset_index()

    df_verificacao = pd.merge(df_in, df_duplicados_max_in, on='Reserva Mae', how='left', suffixes=('', '_max'))

    df_verificacao = df_verificacao[(df_verificacao['Data Execucao_max']==df_verificacao['Data Execucao']) | (pd.isna(df_verificacao['Data Execucao_max']))].reset_index(drop=True)

    df_in = df_verificacao.drop(columns='Data Execucao_max')

    return df_in, reservas_duplicadas
  
def recalcular_servicos_reservas_diferentes(df_in_out, data_relatorio):

    df_in_out['Data IN'] = pd.to_datetime(df_in_out['Data IN'])
    df_in_out['Data OUT'] = pd.to_datetime(df_in_out['Data OUT'])

    df_router_2 = st.session_state.df_router[(st.session_state.df_router['Data Execucao']>data_relatorio) & (st.session_state.df_router['Tipo de Servico'].isin(['TOUR', 'TRANSFER']))]\
        .reset_index(drop=True)
    df_router_2['Chave'] = df_router_2['Cliente'] + "|" + df_router_2['Parceiro']

    df_in_out['Chave'] = df_in_out['Cliente'] + "|" + df_in_out['Parceiro']

    dias_por_chave = df_router_2.groupby('Chave')['Data Execucao'].nunique()
    
    df_in_out['Qtd. Servicos'] = df_in_out['Chave'].map(dias_por_chave).fillna(df_in_out['Qtd. Servicos'])

    df_in_out['Dias Livres'] = df_in_out['Dias Estadia'] - df_in_out['Qtd. Servicos']

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
    
st.set_page_config(layout='wide')

if not 'df_config' in st.session_state:

    puxar_aba_simples(st.session_state.id_sheet, st.session_state.aba_sheet, 'df_config')

if not 'mostrar_config' in st.session_state:

    st.session_state.mostrar_config = False

st.title(st.session_state.titulo_3)

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

# Puxando dados do Phoenix

if not 'df_router' in st.session_state:

    with st.spinner('Puxando dados do Phoenix...'):

        puxar_dados_phoenix()

if not 'df_final' in st.session_state:

    st.session_state.df_final = pd.DataFrame(columns=['Reserva Mae', 'Servico', 'Voo IN', 'Horario Voo', 'Data IN', 'Est Destino', 'Cliente', 'Telefone Cliente', 'Parceiro', 'Total Paxs', 'Data OUT', 
                                                      'Qtd. Servicos', 'Dias Estadia', 'Dias Livres', 'Chave'])

st.divider()

row1 = st.columns(2)

row2 = st.columns(1)

# Botão pra puxar dados do Phoenix manualmente

with row1[0]:

    atualizar_phoenix = st.button('Atualizar Dados Phoenix')

    if atualizar_phoenix:

        with st.spinner('Puxando dados do Phoenix...'):

            puxar_dados_phoenix()

# Botões de input de datas

with row1[0]:

    container_datas = st.container(border=True)

    container_datas.subheader('Data Limite - IN')

    data_limite = container_datas.date_input('Data Limite', value=date.today() - timedelta(days=1) ,format='DD/MM/YYYY', key='data_limite')

    gerar_analise = container_datas.button('Gerar Análise')

if gerar_analise:

    # Pegando reservas que fizeram trf in até a data limite

    df_in = st.session_state.df_router[(st.session_state.df_router['Data Execucao'] <= data_limite) & (st.session_state.df_router['Tipo de Servico']=='IN')].reset_index(drop=True)

    # Retirando linhas que tem mais de um IN na mesma data

    df_in = df_in.drop_duplicates(subset=['Reserva Mae', 'Data Execucao']).reset_index(drop=True)

    # Filtrando apenas último trf in das reservas que tem mais de um trf in cadastrado

    df_in, reservas_duplicadas = filtrar_apenas_ultimo_trf_in(df_in)

    # Calculando média de estadia

    media_estadia = calcular_media_estadia()

    # Inserindo colunas Data IN, Data OUT e Voo IN

    df_in_out, lista_reservas_in = inserir_datas_in_out_voo_in(df_in)

    # Filtrando reservas que estão nos hoteis e que realmente ainda é possível fazer alguma venda

    df_in_out_na_base = df_in_out[df_in_out['Data OUT']>=data_limite + timedelta(days=3)].reset_index(drop=True)

    # Inserindo contabilização de serviços por reserva

    df_in_out_na_base = contabilizar_servicos_por_reserva(df_in_out_na_base)

    # Calculando Estadia de reservas e Dias Livres

    df_in_out_na_base = calcular_estadia_dias_livres(df_in_out_na_base)

    # Recalcular número de serviços de reservas diferentes que deveriam ser de uma mesma reserva

    df_in_out_na_base = recalcular_servicos_reservas_diferentes(df_in_out_na_base, date.today())

    df_in_out_na_base = df_in_out_na_base[df_in_out_na_base['Dias Livres']>=0].reset_index(drop=True)

    st.session_state.df_final = df_in_out_na_base

    st.session_state.df_final['Data IN'] = st.session_state.df_final['Data IN'].dt.date

    st.session_state.df_final['Data OUT'] = st.session_state.df_final['Data OUT'].dt.date

if 'df_reservas_negativas' in st.session_state:

    nomes_reservas = ', '.join(st.session_state.df_reservas_negativas['Reserva Mae'].unique().tolist())

    n_reservas = len(st.session_state.df_reservas_negativas['Reserva Mae'].unique().tolist())

    if n_reservas>0:

        with row0[0]:

            with st.expander(f'*Existem {n_reservas} reservas com data de OUT antes do IN e, portanto, foram desconsideradas da análise*'):

                st.markdown(f'*{nomes_reservas}*')

if len(st.session_state.df_final)>0:

    # Plotando tabela com voos e pegando a seleção do usuário

    if len(st.session_state.df_final)>0:

        selected_rows = plotar_tabela_com_voos_dias_livres(st.session_state.df_final)

        if selected_rows is not None and len(selected_rows)>0:

            df_ref = st.session_state.df_final[st.session_state.df_final['Est Destino'].isin(selected_rows['Est Destino'].unique().tolist())].reset_index(drop=True)

            total_dias_livres = df_ref['Dias Livres'].sum()

            total_paxs_ref = df_ref['Total Paxs'].sum()

            with row1[1]:

                st.subheader(f'Total de dias livres dos hoteis selecionados = {int(total_dias_livres)}')

                st.subheader(f'Total de paxs dos hoteis selecionados = {int(total_paxs_ref)}')

            plotar_tabela_row_servico_especifico(df_ref, row2)
