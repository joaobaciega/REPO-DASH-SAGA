"""Equipe, atribuições dos técnicos e comissões informadas na planilha."""
import io

import pandas as pd
import streamlit as st

import db


def dinheiro(valor):
    return f'R$ {valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def exportar(df, nome):
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine='openpyxl')
    st.download_button('📥 Exportar relatório (Excel)', buf.getvalue(), file_name=nome,
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', key=nome)


def painel_comissoes(cargo=None):
    df = db.ler_comissoes_equipe()
    if cargo:
        df = df[df['cargo'] == cargo]
    if df.empty:
        st.info('Nenhuma comissão informada para este relatório.')
        return False
    prefixo = cargo or 'equipe'
    meses = sorted(df['mes'].unique(), reverse=True)
    c1, c2 = st.columns(2)
    mes = c1.selectbox('Mês', meses, format_func=lambda m: pd.Timestamp(m).strftime('%m/%Y'), key=f'mes_{prefixo}')
    unidades = ['Todas as unidades'] + [u['nome_exibicao'] for u in db.listar_unidades()]
    unidade = c2.selectbox('Unidade', unidades, key=f'unidade_{prefixo}')
    df = df[df['mes'] == mes]
    if unidade != unidades[0]:
        df = df[df['unidade'] == unidade]
    if df.empty:
        st.info('Sem resultado informado para esta unidade neste mês.')
        return True
    if cargo:
        c1, c2, c3 = st.columns(3)
        c1.metric('Técnicos com resultado', df['pessoa_id'].nunique())
        c2.metric('Refis atribuídos', int((df['refil_diant'] + df['refil_tras']).sum()))
        c3.metric('Comissão a receber', dinheiro(df['total'].sum()))
    else:
        c1, c2, c3 = st.columns(3)
        def total_cargo(nome):
            valores = df.loc[df['cargo'] == nome, 'total']
            return dinheiro(valores.sum()) if not valores.empty else 'Não informado'
        c1.metric('Consultores · a receber', total_cargo('consultor'))
        c2.metric('Técnicos · a receber', total_cargo('técnico'))
        c3.metric('Total informado · a receber', dinheiro(df['total'].sum()))
    st.caption('Os refis dos técnicos são as mesmas vendas dos consultores e não acrescentam faturamento. '
               'Valores a receber conforme a planilha; pagamento não confirmado. '
               'Comissões de gerentes não configuradas.')
    tabela = df[['nome', 'cargo', 'unidade', 'refil_diant', 'refil_tras', 'verba_diant', 'verba_tras', 'total']].rename(columns={
        'nome': 'Nome', 'cargo': 'Cargo', 'unidade': 'Unidade', 'refil_diant': 'Refil Diant.',
        'refil_tras': 'Refil Tras.', 'verba_diant': 'Verba Diant. (R$)',
        'verba_tras': 'Verba Tras. (R$)', 'total': 'A receber (R$)'})
    tabela = tabela.sort_values(['Unidade', 'Cargo', 'Nome']).reset_index(drop=True)
    st.dataframe(tabela, hide_index=True, width='stretch')
    exportar(tabela, f'{prefixo}_{pd.Timestamp(mes):%Y_%m}.xlsx')
    return True


def pagina_tecnicos():
    st.title('🔧 Relatório por Técnico')
    painel_comissoes('técnico')


def pagina_equipe():
    st.title('Equipe e unidades')
    equipe = db.ler_equipe()
    vendas = db.ler_base_tidy()
    for u in db.listar_unidades():
        st.subheader(u['nome_exibicao'])
        st.write(f"**Gerente:** {u['gerente']} · **Preço dianteiro:** {dinheiro(u['preco_diant'])}")
        tem_resultado = (vendas['unidade'] == u['nome_exibicao']).any()
        st.caption('Resultado mensal disponível no dashboard.' if tem_resultado else 'Sem resultado de vendas informado.')
        membros = equipe[equipe['unidade_id'] == u['id']][['nome', 'cargo']].rename(columns={'nome': 'Nome', 'cargo': 'Cargo'})
        st.dataframe(membros.sort_values(['Cargo', 'Nome']), hide_index=True, width='stretch')
        if not (membros['Cargo'] == 'técnico').any():
            st.caption('Técnicos ainda não informados para esta unidade.')
