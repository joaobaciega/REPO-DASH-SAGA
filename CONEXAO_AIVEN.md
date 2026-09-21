# Conexão Aiven — Dashboard Saga

Informações fornecidas em 21/09/2026.

| Campo | Valor |
|---|---|
| Serviço | `dashboard-saga-mysql` |
| Host | `dashboard-saga-mysql-dashboard-vendas-dahruj.l.aivencloud.com` |
| Porta | `14618` |
| Usuário | `avnadmin` |
| Banco confirmado para o dashboard | `dashboard_saga` |
| Configuração e senha | `.streamlit/secrets.toml`, seção `[mysql_online]` |
| Certificado CA | `certs/ca.pem` |

A senha foi salva somente no arquivo de secrets. As barras usadas para escapar
os sublinhados na mensagem foram interpretadas como formatação Markdown.
O certificado fornecido foi convertido para PEM com quebras de linha e teve
seu formato validado pelo módulo SSL do Python.

Em 21/09/2026, a conexão com TLS e o banco `dashboard_saga` foram confirmados.
O passo de configuração e a primeira carga online foram concluídos com
`python atualizar_base.py --destino online`, retornando `ONLINE: OK`.
`criar_banco = false` utiliza o banco já criado pelo usuário no Aiven.

Foram criadas as tabelas e views, e a conferência em nova conexão após o COMMIT
confirmou 2 unidades, 6 consultores, 6 lançamentos, 428 passagens, 199 refis
dianteiros, 57 traseiros, R$ 2.275,00 de faturamento e 6 eventos no histórico.
Os dados continuam fictícios, provenientes de `BASE GRUPO SAGA.xlsx`.

Relatório da carga: `logs/carga_e728ac62-14f8-403f-b2d6-34840ca99f37.json`.
O backup anterior à carga está indicado nesse relatório.

A primeira execução identificou incompatibilidade de collation na criação de
`consultor_unidade`: o banco Aiven usa `utf8mb4_0900_ai_ci`, enquanto as tabelas
referenciadas usam `utf8mb4_bin`. O `schema.sql` foi corrigido para declarar
`utf8mb4_bin` também nessa tabela, e a execução seguinte concluiu a carga.
Referência: [requisitos de chaves estrangeiras do MySQL](https://dev.mysql.com/doc/refman/8.0/en/create-table-foreign-keys.html).

## Uso futuro

Os scripts do projeto já leem a seção `[mysql_online]`. Para manutenção, use a
configuração centralizada, sem repetir a senha em scripts, comandos ou notas.
`configuracao.destinos("online")` retorna a configuração e
`configuracao.criar_engine(cfg, online=True)` cria a conexão com verificação TLS.

Quando desejar carregar/substituir os dados online, execute na pasta Saga:

```powershell
python atualizar_base.py --destino online
```

Esse comando substitui a base operacional online pela planilha e faz backup
antes da gravação. `python atualizar_base.py`, sem filtro, passa a incluir tanto
o banco local quanto o online, pois ambos estão configurados.

O modo atual do dashboard foi preservado. A carga online foi executada; a troca
dos Secrets do Streamlit de `demo` para `online` é uma etapa separada e ainda
não foi realizada nesta operação.

`.streamlit/secrets.toml` e `certs/` já estão excluídos pelo `.gitignore` local.
Para o Streamlit Cloud, forneça as credenciais pelo campo Secrets e disponibilize
o certificado CA no caminho configurado; esse arquivo não é enviado
automaticamente ao GitHub enquanto a pasta estiver ignorada.
