# DASH SAGA

## Apresentar no Streamlit Cloud sem banco

Publique o conteúdo atualizado desta pasta no repositório, incluindo
`BASE GRUPO SAGA.xlsx`, `assets/logo.png`, os arquivos Python, `requirements.txt`
e `.streamlit/config.toml`. Prefira colocar o conteúdo da pasta Saga na raiz do
repositório para o Streamlit encontrar o tema. Use Python 3.14 e `app.py` como
arquivo principal. Não publique `.streamlit/secrets.toml` com credenciais locais.

No campo **Secrets**, basta colar:

```toml
[app]
destino = "demo"
dados_ficticios = true
```

Nesse modo, os indicadores, filtros e exportações leem diretamente a planilha;
nenhuma conexão MySQL é aberta. As seis telas ficam visíveis para apresentação.
Lançamento permite explorar a prévia, mas salvar/excluir ficam desabilitados.
Histórico explica que os eventos serão registrados quando o banco for conectado.
Verbas permanece sem valores porque a planilha não traz essa base.

Sem arquivo de secrets e sem configuração no Cloud, o app também abre em modo
de demonstração. Uma conexão `online` configurada com erro não é substituída
automaticamente pela demonstração.

## Conectar o Aiven depois

Crie um banco exclusivo Saga no Aiven. Configure `[mysql_online]` no arquivo
local `.streamlit/secrets.toml`, seguindo `.streamlit/secrets.toml.example`,
e execute `python atualizar_base.py --destino online` para criar as tabelas e
carregar os dados. O certificado CA deve estar disponível no caminho configurado
em `ssl_ca`, tanto localmente quanto no projeto publicado.

Em **Settings → Secrets** do aplicativo publicado, troque `destino = "demo"`
por `"online"` e adicione os blocos `[mysql_online]` e `[acesso]`. Reinicie o app
após a troca. Altere `dados_ficticios` para `false` somente quando substituir a
base pelos dados reais.

Os Secrets podem ser editados depois da publicação:
[documentação Streamlit](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).
