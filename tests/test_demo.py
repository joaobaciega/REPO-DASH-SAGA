import hashlib
from types import SimpleNamespace

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import configuracao
import db


@pytest.fixture
def demo(monkeypatch):
    st.cache_data.clear()
    monkeypatch.setattr(configuracao, "ler_config", lambda: {"app": {"destino": "demo"}})
    def proibido(*args, **kwargs):
        raise AssertionError("Demonstração tentou abrir conexão SQL")
    monkeypatch.setattr(db, "_ler_mysql", proibido)
    monkeypatch.setattr(db, "_engine", proibido)
    yield
    st.cache_data.clear()


def test_dados_demo_sem_mysql_e_bloqueio_de_gravacao(demo):
    dados = db.ler_base_tidy()
    assert dados["total_geral"].sum() == 2275
    assert dados["passagens"].sum() == 428
    assert len(db.listar_unidades()) == 2
    unidade = db.listar_unidades()[0]
    consultor = db.listar_consultores(unidade["id"])[0]
    mes = dados["mes"].iloc[0].date()
    args = consultor["id"], mes, unidade["id"]
    assert db.obter_lancamento(*args)["refil_diant"] == 15
    assert db.ler_vendas_verbas().empty
    assert db.ler_pagamentos_verba() == {}
    assert db.ler_pagamentos_marketing() == {}
    assert db.ler_historico_lancamentos().empty
    assert db.ultima_importacao() is None
    with pytest.raises(ValueError, match="não são gravadas"):
        db.salvar_lancamento(*args, 99, 99, 99)
    with pytest.raises(ValueError, match="não são gravadas"):
        db.excluir_lancamento(*args)


def test_seis_telas_demo_e_filtro_sem_banco(demo):
    excel = configuracao.BASE_DIR / "BASE GRUPO SAGA.xlsx"
    antes = hashlib.sha256(excel.read_bytes()).hexdigest()
    app = AppTest.from_file(str(configuracao.BASE_DIR / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert not app.error
    assert any(m.value == "R$ 2.275,00" for m in app.metric)
    paginas = app.sidebar.radio[0].options
    assert len(paginas) == 6
    app.sidebar.multiselect[1].set_value(["Volkswagen · Loja 1"]).run()
    assert any(m.value == "R$ 935,00" for m in app.metric)
    for pagina in paginas[1:]:
        app.sidebar.radio[0].set_value(pagina).run()
        assert not app.exception, [e.message for e in app.exception]
        assert not app.error, [e.value for e in app.error]
        if "Relatório" in pagina:
            assert len(app.get("download_button")) >= 1
        if "Lançamento" in pagina:
            assert next(b for b in app.button if b.label == "Salvar lançamento").disabled
            assert next(b for b in app.button if b.label == "Excluir lançamento").disabled
    assert hashlib.sha256(excel.read_bytes()).hexdigest() == antes


def test_sem_secrets_inicia_demo(monkeypatch, tmp_path):
    monkeypatch.setattr(configuracao, "SECRETS", tmp_path / "ausente.toml")
    def sem_secrets():
        raise FileNotFoundError()
    monkeypatch.setattr(st, "secrets", SimpleNamespace(to_dict=sem_secrets))
    assert configuracao.destino_app() == "demo"
    with pytest.raises(ValueError, match="Nenhum destino"):
        configuracao.destinos("online")


def test_online_incompleto_nao_faz_fallback_demo(monkeypatch):
    monkeypatch.setattr(configuracao, "ler_config", lambda: {"app": {"destino": "online"}})
    assert not db.modo_demonstracao()
    with pytest.raises(ValueError, match="Nenhum destino"):
        db.ler_base_tidy()
