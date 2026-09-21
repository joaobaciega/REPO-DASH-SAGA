"""Contrato de dados das seis telas do dashboard Saga."""
import uuid

import pandas as pd
import streamlit as st
from sqlalchemy import text

from configuracao import BASE_DIR, criar_engine, destinos, destino_app
from planilha import ler_planilha
from repositorio import evento, inserir, transacao


@st.cache_resource
def _engine(cfg, online):
    return criar_engine(cfg, online=online)


def modo_demonstracao():
    return destino_app() == "demo"


def get_engine():
    if modo_demonstracao():
        raise ValueError("O modo demonstração não utiliza banco de dados.")
    nome, cfg = destinos(destino_app())[0]
    return _engine(cfg, nome == "online")


@st.cache_data(ttl=60)
def _ler_mysql(sql, parametros, cfg, online):
    with _engine(cfg, online).connect() as conn:
        return pd.read_sql(text(sql), conn, params=parametros)


def _ler(sql, parametros=None):
    nome, cfg = destinos(destino_app())[0]
    return _ler_mysql(sql, parametros, cfg, nome == "online")


@st.cache_data
def _excel_demo(caminho, modificacao):
    return ler_planilha(caminho)


def _demo():
    caminho = BASE_DIR / "BASE GRUPO SAGA.xlsx"
    return _excel_demo(str(caminho), caminho.stat().st_mtime_ns).tabelas


def ler_base_tidy():
    if modo_demonstracao():
        base = _demo()
        unidades = {r["id"]: r for r in base["unidades"]}
        consultores = {r["id"]: r for r in base["consultores"]}
        linhas = []
        for fato in base["lancamentos"]:
            r = dict(fato)
            u = unidades[r.pop("unidade_id")]
            c = consultores[r.pop("consultor_id")]
            r.update(consultor=c["nome"], unidade=u["nome_exibicao"], loja=u["loja"], marca=u["marca"])
            r["mes"] = pd.Timestamp(r["mes"])
            r["mes_label"] = r["mes"].strftime("%m/%Y")
            for campo in ("preco_diant", "preco_tras"):
                r[campo] = float(r[campo])
            r["total_diant"] = r["refil_diant"] * r["preco_diant"]
            r["total_tras"] = r["refil_tras"] * r["preco_tras"]
            r["total_geral"] = r["total_diant"] + r["total_tras"]
            r["aproveitamento"] = r["refil_diant"] / r["passagens"] if r["passagens"] else None
            linhas.append(r)
        return pd.DataFrame(linhas)
    df = _ler("SELECT * FROM vw_base_tidy")
    df["mes"] = pd.to_datetime(df["mes"])
    return df


def listar_unidades():
    if modo_demonstracao():
        return [dict(r, preco_diant=float(r["preco_diant"]), preco_tras=float(r["preco_tras"]))
                for r in sorted(_demo()["unidades"], key=lambda u: u["nome_exibicao"])]
    return _ler("SELECT * FROM unidades ORDER BY nome_exibicao").to_dict("records")


def listar_consultores(unidade_id):
    if modo_demonstracao():
        base = _demo()
        ids = {r["consultor_id"] for r in base["consultor_unidade"] if r["unidade_id"] == unidade_id}
        return sorted((r for r in base["consultores"] if r["id"] in ids), key=lambda r: r["nome"])
    return _ler("SELECT c.id, c.nome FROM consultores c JOIN consultor_unidade cu ON c.id=cu.consultor_id "
                "WHERE cu.unidade_id=:uid ORDER BY c.nome", {"uid": unidade_id}).to_dict("records")


def obter_lancamento(consultor_id, mes, unidade_id):
    if modo_demonstracao():
        for r in _demo()["lancamentos"]:
            if r["consultor_id"] == consultor_id and r["unidade_id"] == unidade_id and r["mes"] == mes:
                return dict(r, preco_diant=float(r["preco_diant"]), preco_tras=float(r["preco_tras"]))
        return None
    dados = _ler("SELECT * FROM lancamentos WHERE consultor_id=:cid AND mes=:mes AND unidade_id=:uid",
                 dict(cid=consultor_id, mes=mes, uid=unidade_id))
    if dados.empty:
        return None
    row = dados.iloc[0].to_dict()
    row["passagens"] = None if pd.isna(row["passagens"]) else int(row["passagens"])
    return row


def ler_vendas_verbas():
    if modo_demonstracao():
        cols = ["id", "data", "pedido", "cliente", "produto", "tipo_refil", "qtde", "preco_unit",
                "total_item", "verba_consultor", "total_consultor", "verba_gerente", "total_gerente",
                "verba_reserva", "total_reserva"]
        df = pd.DataFrame(_demo()["vendas_verbas"], columns=cols)
        for col in cols[7:]:
            df[col] = df[col].astype(float)
        df["qtde"] = df["qtde"].astype(int)
    else:
        df = _ler("SELECT * FROM vendas_verbas")
    df["data"] = pd.to_datetime(df["data"])
    return df


def ler_pagamentos_verba():
    df = (pd.DataFrame(_demo()["verbas_pagamentos"], columns=["mes", "consultor_pago", "gerente_pago"])
          if modo_demonstracao() else _ler("SELECT * FROM verbas_pagamentos"))
    return {pd.Timestamp(r.mes): dict(consultor=bool(r.consultor_pago), gerente=bool(r.gerente_pago))
            for r in df.itertuples()}


def ler_pagamentos_marketing():
    df = (pd.DataFrame(_demo()["verbas_marketing_pagos"], columns=["mes", "valor"])
          if modo_demonstracao() else _ler("SELECT * FROM verbas_marketing_pagos"))
    return {pd.Timestamp(r.mes): float(r.valor) for r in df.itertuples()}


def ler_historico_lancamentos():
    if modo_demonstracao():
        return pd.DataFrame()
    df = _ler("SELECT * FROM vw_lancamentos_historico ORDER BY id")
    for col in ("mes", "registrado_em"):
        df[col] = pd.to_datetime(df[col])
    return df


def diagnostico_historico():
    if modo_demonstracao():
        return {"modo": "demo", "eventos": 0}
    df = _ler("SELECT COUNT(*) AS eventos FROM lancamentos_historico")
    return {"eventos": int(df.iloc[0]["eventos"])}


def ultima_importacao():
    if modo_demonstracao():
        return None
    df = _ler("SELECT arquivo, registrado_em, linhas FROM importacoes ORDER BY registrado_em DESC LIMIT 1")
    return df.iloc[0].to_dict() if not df.empty else None


def _gravar(consultor_id, mes, unidade_id, passagens, refil_diant, refil_tras, *, excluir=False):
    if modo_demonstracao():
        raise ValueError("Demonstração somente para consulta: alterações não são gravadas.")
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
