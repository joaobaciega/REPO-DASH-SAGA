"""Configuração compartilhada pelo dashboard e pelo importador (Python 3.11+)."""
from pathlib import Path
import re
import ssl
import tomllib

from sqlalchemy import create_engine
from sqlalchemy.engine import URL

BASE_DIR = Path(__file__).resolve().parent
SECRETS = BASE_DIR / ".streamlit" / "secrets.toml"


class CertificadoAusenteError(ValueError):
    """Arquivo CA configurado não está no pacote publicado."""


def mensagem_erro_conexao(exc):
    """Diagnóstico publicável: nunca inclui senha, URL ou parâmetros SQL."""
    if isinstance(exc, CertificadoAusenteError):
        return ("O certificado CA não foi encontrado no aplicativo publicado. "
                "Inclua certs/ca.pem no repositório e confira ssl_ca nos Secrets.")
    original = getattr(exc, "orig", exc)
    argumentos = getattr(original, "args", ())
    codigo = argumentos[0] if argumentos and isinstance(argumentos[0], int) else None
    mensagens = {
        1045: "O Aiven recusou as credenciais. Confira usuário e senha em [mysql_online] nos Secrets.",
        1049: "O banco configurado não existe nesse serviço. Confira database nos Secrets.",
        1146: "As tabelas do dashboard não foram encontradas nesse banco. Confira database e execute a carga online.",
        2003: "Não foi possível estabelecer a conexão com o Aiven. Confira host, porta, certificado e acesso de rede.",
    }
    return mensagens.get(codigo, "Não foi possível acessar os dados. Confira a configuração do banco e do certificado nos Secrets.")


def ler_config():
    if SECRETS.exists():
        with SECRETS.open("rb") as arquivo:
            return tomllib.load(arquivo)
    # Permite secrets fornecidos pelo ambiente de hospedagem do Streamlit.
    import streamlit as st
    try:
        return st.secrets.to_dict()
    except FileNotFoundError:
        return {"app": {"destino": "demo", "dados_ficticios": True}}


def destino_app():
    cfg = ler_config()
    destino = cfg.get("app", {}).get("destino")
    if destino is None:
        destino = "local" if "mysql" in cfg else "online" if "mysql_online" in cfg else "demo"
    if destino not in ("local", "online", "demo"):
        raise ValueError("Destino do dashboard inválido: use local, online ou demo.")
    return destino


def destinos(filtro=None):
    config = ler_config()
    resultado = [(nome, dict(config[chave])) for nome, chave in
                 (("local", "mysql"), ("online", "mysql_online")) if chave in config]
    if filtro and filtro != "todos":
        resultado = [item for item in resultado if item[0] == filtro]
    if not resultado:
        raise ValueError("Nenhum destino solicitado está configurado em .streamlit/secrets.toml.")
    return resultado


def criar_engine(cfg, *, sem_banco=False, online=False):
    banco = cfg.get("database", "")
    if not re.fullmatch(r"[A-Za-z0-9_]+", banco):
        raise ValueError("Nome de banco inválido: use letras, números e sublinhado.")
    if "dahruj" in banco.lower() or "dahurj" in banco.lower():
        raise ValueError("Use um banco exclusivo da Saga. O banco Dahruj não pode ser usado.")
    args = {"connect_timeout": 10, "read_timeout": 60, "write_timeout": 60}
    remoto = cfg.get("host", "127.0.0.1") not in ("localhost", "127.0.0.1", "::1")
    if online or remoto or cfg.get("ssl_ca"):
        ca = cfg.get("ssl_ca")
        if ca:
            caminho = Path(ca)
            if not caminho.is_absolute():
                caminho = BASE_DIR / caminho
            if not caminho.is_file():
                raise CertificadoAusenteError("Certificado CA não encontrado. Confira ssl_ca nas configurações.")
            args["ssl"] = ssl.create_default_context(cafile=str(caminho))
        else:
            args["ssl"] = ssl.create_default_context()
    url = URL.create("mysql+pymysql", username=cfg["user"], password=cfg["password"],
                     host=cfg.get("host", "127.0.0.1"), port=int(cfg.get("port", 3306)),
                     database=None if sem_banco else banco, query={"charset": "utf8mb4"})
    return create_engine(url, pool_pre_ping=True, connect_args=args)
