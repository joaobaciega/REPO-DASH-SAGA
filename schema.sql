-- MySQL 8.0+. Executado automaticamente por atualizar_base.py no banco configurado.
-- Não contém DROP, TRUNCATE, USE ou credenciais.
CREATE TABLE IF NOT EXISTS saga_metadata (
  chave VARCHAR(50) PRIMARY KEY, valor VARCHAR(100) NOT NULL
) ENGINE=InnoDB;
INSERT IGNORE INTO saga_metadata VALUES ('projeto', 'dashboard_saga_v1');

CREATE TABLE IF NOT EXISTS unidades (
  id CHAR(64) PRIMARY KEY,
  nome_exibicao VARCHAR(300) NOT NULL, loja VARCHAR(140) NOT NULL,
  marca VARCHAR(140) NOT NULL, gerente VARCHAR(180),
  preco_diant DECIMAL(12,2) NOT NULL, preco_tras DECIMAL(12,2) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
CREATE TABLE IF NOT EXISTS consultores (
  id CHAR(64) PRIMARY KEY, nome VARCHAR(180) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
CREATE TABLE IF NOT EXISTS consultor_unidade (
  consultor_id CHAR(64) NOT NULL, unidade_id CHAR(64) NOT NULL,
  PRIMARY KEY (consultor_id, unidade_id),
  FOREIGN KEY (consultor_id) REFERENCES consultores(id),
  FOREIGN KEY (unidade_id) REFERENCES unidades(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
CREATE TABLE IF NOT EXISTS lancamentos (
  consultor_id CHAR(64) NOT NULL, unidade_id CHAR(64) NOT NULL, mes DATE NOT NULL,
  gerente VARCHAR(180), passagens INT UNSIGNED NULL,
  refil_diant INT UNSIGNED NOT NULL, refil_tras INT UNSIGNED NOT NULL,
  preco_diant DECIMAL(12,2) NOT NULL, preco_tras DECIMAL(12,2) NOT NULL,
  PRIMARY KEY (consultor_id, unidade_id, mes),
  FOREIGN KEY (consultor_id) REFERENCES consultores(id),
  FOREIGN KEY (unidade_id) REFERENCES unidades(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS lancamentos_historico (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  consultor_id CHAR(64) NOT NULL, unidade_id CHAR(64) NOT NULL, mes DATE NOT NULL,
  consultor VARCHAR(180) NOT NULL, unidade VARCHAR(300) NOT NULL, marca VARCHAR(140) NOT NULL,
  gerente VARCHAR(180), passagens INT UNSIGNED NULL,
  refil_diant INT UNSIGNED NOT NULL, refil_tras INT UNSIGNED NOT NULL,
  preco_diant DECIMAL(12,2) NOT NULL, preco_tras DECIMAL(12,2) NOT NULL,
  tipo VARCHAR(20) NOT NULL, origem VARCHAR(20) NOT NULL, lote CHAR(36),
  registrado_em DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  INDEX idx_historico (consultor_id, unidade_id, mes, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS vendas_verbas (
  id INT PRIMARY KEY, data DATE NOT NULL, pedido VARCHAR(100) NOT NULL,
  cliente VARCHAR(180), produto VARCHAR(180), tipo_refil VARCHAR(5) NOT NULL,
  qtde INT UNSIGNED NOT NULL, preco_unit DECIMAL(12,2) NOT NULL,
  total_item DECIMAL(14,2) NOT NULL,
  verba_consultor DECIMAL(12,2) NOT NULL, total_consultor DECIMAL(14,2) NOT NULL,
  verba_gerente DECIMAL(12,2) NOT NULL, total_gerente DECIMAL(14,2) NOT NULL,
  verba_reserva DECIMAL(12,2) NOT NULL, total_reserva DECIMAL(14,2) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS verbas_pagamentos (
  mes DATE PRIMARY KEY, consultor_pago BOOLEAN NOT NULL, gerente_pago BOOLEAN NOT NULL
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS verbas_marketing_pagos (
  mes DATE PRIMARY KEY, valor DECIMAL(14,2) NOT NULL
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS importacoes (
  id CHAR(36) PRIMARY KEY, arquivo VARCHAR(255) NOT NULL, sha256 CHAR(64) NOT NULL,
  linhas INT NOT NULL, faturamento DECIMAL(16,2) NOT NULL,
  registrado_em DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE OR REPLACE SQL SECURITY INVOKER VIEW vw_base_tidy AS
SELECT c.nome AS consultor, u.nome_exibicao AS unidade, u.loja, u.marca, l.gerente,
       l.mes, DATE_FORMAT(l.mes, '%m/%Y') AS mes_label,
       l.passagens, l.refil_diant, l.refil_tras, l.preco_diant, l.preco_tras,
       l.refil_diant / NULLIF(l.passagens, 0) AS aproveitamento,
       l.refil_diant * l.preco_diant AS total_diant,
       l.refil_tras * l.preco_tras AS total_tras,
       l.refil_diant * l.preco_diant + l.refil_tras * l.preco_tras AS total_geral
FROM lancamentos l JOIN consultores c ON c.id = l.consultor_id
JOIN unidades u ON u.id = l.unidade_id;

CREATE OR REPLACE SQL SECURITY INVOKER VIEW vw_lancamentos_historico AS
SELECT h.*,
       ROW_NUMBER() OVER w AS n_lancamento,
       refil_diant / NULLIF(passagens, 0) AS aproveitamento,
       refil_diant * preco_diant + refil_tras * preco_tras AS total_geral,
       CAST(passagens AS SIGNED) - COALESCE(CAST(LAG(passagens) OVER w AS SIGNED), 0) AS passagens_periodo,
       CAST(refil_diant AS SIGNED) - COALESCE(CAST(LAG(refil_diant) OVER w AS SIGNED), 0) AS refil_diant_periodo,
       CAST(refil_tras AS SIGNED) - COALESCE(CAST(LAG(refil_tras) OVER w AS SIGNED), 0) AS refil_tras_periodo,
       (refil_diant * preco_diant + refil_tras * preco_tras) -
       COALESCE(LAG(refil_diant * preco_diant + refil_tras * preco_tras) OVER w, 0) AS total_periodo
FROM lancamentos_historico h
WINDOW w AS (PARTITION BY consultor_id, unidade_id, mes ORDER BY id);
