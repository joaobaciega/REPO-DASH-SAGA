# DASH SAGA

## Base real — outubro de 2026

Cadastros: JEEP RAM (Ricardo, 2 consultores), JEEP T9 (Flávio, 3 consultores
e 5 técnicos) e JEEP BR-153 (Rafael, 6 consultores). O nome Katielen Neves
Nascimento segue a planilha de outubro. O preço dianteiro é R$ 249,00.
Vendas de traseiros estão desabilitadas enquanto `somente_dianteiro = sim`.

O único resultado informado é o da T9 em outubro de 2026: 10 refis dianteiros,
R$ 2.490,00 em vendas, R$ 120,00 de comissão de consultores e R$ 80,00 de
técnicos. Os 10 refis dos técnicos são atribuições das mesmas vendas; não
geram faturamento adicional. As comissões são valores **a receber**, sem
confirmação de pagamento. Passagens, comissões de gerentes, técnicos das
outras unidades e resultados das demais lojas não foram informados.

As telas **Relatório Por Técnico** e **Equipe e unidades** mostram esses
cadastros e resultados. Unidades sem resultado não recebem vendas fictícias.
Os registros anteriores permanecem somente no histórico de auditoria e nos
backups; não entram nos indicadores atuais.

## Atualizar Excel, MySQL local e Aiven

Feche o Excel antes da atualização. Para incorporar uma planilha no formato
`NOME / CARGO / VERBA / VENDAS / A RECEBER`, execute nesta pasta:

```powershell
python importar_verbas_unidade.py "C:\caminho\VERBAS NOVEMBRO.xlsx" --loja T9 --mes 2026-11
python atualizar_base.py --so-validar
python atualizar_base.py
```

O primeiro comando substitui o resultado da unidade/mês indicado dentro de
`BASE GRUPO SAGA.xlsx`, preserva outros meses e cadastros e guarda um backup.
Esse formato mensal considera somente vendas dianteiras, com passagens não
informadas. Os nomes são normalizados em maiúsculas; use sempre a mesma
grafia para evitar cadastros duplicados. Os preços e o gerente são obtidos da
aba `Preço por Unidade`. O mês é obrigatório porque não consta nas linhas da
planilha de verbas.

O último comando substitui toda a base operacional de **ambos os bancos
configurados** pelo conteúdo do Excel, com backup, validação e transação por
destino. Confira as mensagens `LOCAL: OK` e `ONLINE: OK`. Não há transação
distribuída: se apenas um destino falhar, corrija a conexão e repita a carga.
Também é possível editar o Excel diretamente e executar `ATUALIZAR_DADOS.bat`.
Se você controla passagens no Excel, mantenha-as na aba Consultores; importar
novamente o resumo de verbas do mesmo mês deixa esse campo sem informação.

Abas adicionais: `Equipe` cadastra consultores/técnicos mesmo sem vendas;
`Comissões Equipe` registra quantidades e verbas por pessoa/unidade/mês;
`Configuração` identifica `tipo_base = real` e `somente_dianteiro = sim`.
Comissões não informadas não são presumidas como zero. Uma comissão de
consultor deve ter as mesmas quantidades de seu lançamento; atribuições de
técnicos não podem exceder as vendas da unidade/mês.

`MODELO SAGA COMPLETO.xlsx` é uma cópia de referência desta entrega. Para
atualizações futuras, a fonte usada pelo importador é `BASE GRUPO SAGA.xlsx`.
Com o aplicativo em `destino = "online"`, use **Atualizar visualização** após
a carga (o cache também expira em 60 segundos). O cadastro da base real
substitui o aviso antigo de dados fictícios, mesmo se o Secret antigo ainda
tiver `dados_ficticios = true`.

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
dados_ficticios = false
```

Nesse modo, os indicadores, filtros e exportações leem diretamente a planilha;
nenhuma conexão MySQL é aberta. As oito telas ficam visíveis para apresentação.
Lançamento permite explorar a prévia, mas salvar/excluir ficam desabilitados.
Histórico explica que os eventos serão registrados quando o banco for conectado.
Técnicos e Verbas mostram as comissões que estiverem na planilha.

Sem arquivo de secrets e sem configuração no Cloud, o app também abre em modo
de demonstração. Uma conexão `online` configurada com erro não é substituída
automaticamente pela demonstração.

## Conectar o Aiven depois

Crie um banco exclusivo Saga no Aiven. Configure `[mysql_online]` no arquivo
local `.streamlit/secrets.toml`, seguindo `.streamlit/secrets.toml.example`,
e execute `python atualizar_base.py --destino online` para criar as tabelas e
carregar os dados. O certificado CA deve estar disponível no caminho configurado
em `ssl_ca`, tanto localmente quanto no projeto publicado.

O certificado público `certs/ca.pem` acompanha o repositório para o Streamlit
Cloud estabelecer a conexão TLS. O `.gitignore` permite esse arquivo específico
e continua excluindo secrets e quaisquer outros arquivos de `certs/`.

Em **Settings → Secrets** do aplicativo publicado, troque `destino = "demo"`
por `"online"` e adicione os blocos `[mysql_online]` e `[acesso]`. Reinicie o app
após a troca. Altere `dados_ficticios` para `false` somente quando substituir a
base pelos dados reais.

Os Secrets podem ser editados depois da publicação:
[documentação Streamlit](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).
