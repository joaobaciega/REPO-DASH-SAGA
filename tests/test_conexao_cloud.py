import ssl
import os

import pytest
from pymysql.err import OperationalError

import configuracao


def test_certificado_ausente_explica_falha_antes_de_abrir_conexao():
    cfg = dict(host="exemplo.aivencloud.com", port=12345, user="usuario",
               password="SEGREDO_TESTE", database="dashboard_saga", ssl_ca="certs/inexistente.pem")
    with pytest.raises(configuracao.CertificadoAusenteError) as erro:
        configuracao.criar_engine(cfg, online=True)
    msg = configuracao.mensagem_erro_conexao(erro.value)
    assert "certs/ca.pem" in msg
    assert "SEGREDO_TESTE" not in msg


def test_certificado_publicado_e_tls_verificado(monkeypatch):
    cfg = dict(host="exemplo.aivencloud.com", port=12345, user="usuario",
               password="SEGREDO_TESTE", database="dashboard_saga", ssl_ca="certs/ca.pem")
    monkeypatch.setattr(configuracao, "create_engine", lambda url, **kwargs: kwargs)
    argumentos = configuracao.criar_engine(cfg, online=True)
    ctx = argumentos["connect_args"]["ssl"]
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname


@pytest.mark.parametrize("exc", [OperationalError(1045, "SEGREDO_TESTE"),
                                ValueError("SEGREDO_TESTE"),
                                OperationalError(2003, "SEGREDO_TESTE")])
def test_diagnostico_nao_expoe_conteudo_da_excecao(exc):
    assert "SEGREDO_TESTE" not in configuracao.mensagem_erro_conexao(exc)


@pytest.mark.skipif(os.getenv("SAGA_TEST_AIVEN") != "1", reason="Leitura real do Aiven somente quando solicitada.")
def test_streamlit_com_secrets_cloud_e_ca_publicado(monkeypatch, tmp_path):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    cfg = configuracao.destinos("online")[0][1]
    raiz = configuracao.BASE_DIR
    monkeypatch.setattr(configuracao, "SECRETS", tmp_path / "secrets-inexistentes.toml")
    monkeypatch.setattr(configuracao, "BASE_DIR", tmp_path)
    st.cache_resource.clear()
    st.cache_data.clear()
    app = AppTest.from_file(str(raiz / "app.py"), default_timeout=60)
    app.secrets.clear()
    app.secrets.update({"app": {"destino": "online", "dados_ficticios": True},
                        "mysql_online": cfg, "acesso": {"senha_lancamento": "SENHA_TESTE"}})
    app.run()
    assert not app.exception
    assert any("certs/ca.pem" in e.value for e in app.error)
    # Simula a inclusão do certificado no pacote publicado. Nenhum dado é gravado.
    (tmp_path / "certs").mkdir()
    (tmp_path / "certs" / "ca.pem").write_bytes((raiz / "certs" / "ca.pem").read_bytes())
    st.cache_resource.clear()
    st.cache_data.clear()
    app.run()
    assert not app.exception, [e.message for e in app.exception]
    assert not app.error, [e.value for e in app.error]
    assert any(m.value == "R$ 2.275,00" for m in app.metric)
    for pagina in ("Relatório Por Gerente", "Relatório Por Consultor", "Verbas"):
        app.sidebar.radio[0].set_value(pagina).run()
        assert not app.exception
        assert not app.error
    app.button(key="btn_cadeado").click().run()
    app.text_input[0].set_value("SENHA_TESTE")
    next(b for b in app.button if b.label == "Entrar").click().run()
    assert not app.exception
    assert not app.error
    app.sidebar.radio[0].set_value("🗂️ Histórico").run()
    assert not app.exception
    assert not app.error
    st.cache_resource.clear()
    st.cache_data.clear()
