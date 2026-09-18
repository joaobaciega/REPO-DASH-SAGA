"""Contrato de dados das seis telas do dashboard Saga."""
import uuid

import pandas as pd
import streamlit as st
from sqlalchemy import text

from configuracao import criar_engine, destinos, ler_config
from repositorio import evento, inserir, transacao


@st.cache_resource
def get_engine():
    destino = ler_config().get("app", {}).get("destino", "local")
    nome, cfg = destinos(destino)[0]
    return criar_engine(cfg, online=nome == "online")


def _ler(sql, parametros=None):
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=parametros)


@st.cache_data(ttl=60)
def ler_base_tidy():
    df = _ler("SELECT * FROM vw_base_tidy")
    df["mes"] = pd.to_datetime(df["mes"])
    return df


@st.cache_data(ttl=60)
def listar_unidades():
    return _ler("SELECT * FROM unidades ORDER BY nome_exibicao").to_dict("records")


@st.cache_data(ttl=60)
def listar_consultores(unidade_id):
    return _ler("SELECT c.id, c.nome FROM consultores c JOIN consultor_unidade cu ON c.id=cu.consultor_id "
                "WHERE cu.unidade_id=:uid ORDER BY c.nome", {"uid": unidade_id}).to_dict("records")


def obter_lancamento(consultor_id, mes, unidade_id):
    dados = _ler("SELECT * FROM lancamentos WHERE consultor_id=:cid AND mes=:mes AND unidade_id=:uid",
                 dict(cid=consultor_id, mes=mes, uid=unidade_id))
    if dados.empty:
        return None
    row = dados.iloc[0].to_dict()
    row["passagens"] = None if pd.isna(row["passagens"]) else int(row["passagens"])
    return row


@st.cache_data(ttl=60)
def ler_vendas_verbas():
    df = _ler("SELECT * FROM vendas_verbas")
    df["data"] = pd.to_datetime(df["data"])
    return df


@st.cache_data(ttl=60)
def ler_pagamentos_verba():
    df = _ler("SELECT * FROM verbas_pagamentos")
    return {pd.Timestamp(r.mes): dict(consultor=bool(r.consultor_pago), gerente=bool(r.gerente_pago))
            for r in df.itertuples()}


@st.cache_data(ttl=60)
def ler_pagamentos_marketing():
    df = _ler("SELECT * FROM verbas_marketing_pagos")
    return {pd.Timestamp(r.mes): float(r.valor) for r in df.itertuples()}


@st.cache_data(ttl=60)
def ler_historico_lancamentos():
    df = _ler("SELECT * FROM vw_lancamentos_historico ORDER BY id")
    for col in ("mes", "registrado_em"):
        df[col] = pd.to_datetime(df[col])
    return df


def diagnostico_historico():
    df = _ler("SELECT COUNT(*) AS eventos FROM lancamentos_historico")
    return {"eventos": int(df.iloc[0]["eventos"])}


@st.cache_data(ttl=60)
def ultima_importacao():
    df = _ler("SELECT arquivo, registrado_em, linhas FROM importacoes ORDER BY registrado_em DESC LIMIT 1")
    return df.iloc[0].to_dict() if not df.empty else None


def _gravar(consultor_id, mes, unidade_id, passagens, refil_diant, refil_tras, *, excluir=False):
    parametros = dict(cid=consultor_id, uid=unidade_id, mes=mes)
    with transacao(get_engine()) as conn:
        u = dict(conn.execute(text("SELECT * FROM unidades WHERE id=:uid"), parametros).mappings().one())
        c = dict(conn.execute(text("SELECT * FROM consultores WHERE id=:cid"), parametros).mappings().one())
        atual = conn.execute(text("SELECT * FROM lancamentos WHERE consultor_id=:cid AND unidade_id=:uid AND mes=:mes"),
                             parametros).mappings().first()
        if excluir and atual is None:
            return
        f = dict(atual) if atual else dict(consultor_id=consultor_id, unidade_id=unidade_id, mes=mes,
                   gerente=u["gerente"], preco_diant=u["preco_diant"], preco_tras=u["preco_tras"])
        f.update(passagens=passagens, refil_diant=refil_diant, refil_tras=refil_tras)
        if not excluir:
            from planilha import numero
            for campo in ("passagens", "refil_diant", "refil_tras"):
                f[campo] = numero(f[campo], campo, inteiro=True, opcional=campo == "passagens")
        conn.execute(text("DELETE FROM lancamentos WHERE consultor_id=:cid AND unidade_id=:uid AND mes=:mes"), parametros)
        if not excluir:
            inserir(conn, "lancamentos", [f])
        inserir(conn, "lancamentos_historico", [evento(f, {unidade_id:u}, {consultor_id:c}, "app", str(uuid.uuid4()), excluido=excluir)])
    st.cache_data.clear()


def salvar_lancamento(consultor_id, mes, unidade_id, passagens, refil_diant, refil_tras):
    _gravar(consultor_id, mes, unidade_id, passagens, refil_diant, refil_tras)


def excluir_lancamento(consultor_id, mes, unidade_id):
    _gravar(consultor_id, mes, unidade_id, 0, 0, 0, excluir=True)
