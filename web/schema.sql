-- =====================================================================
-- Warlocks Sales Tracker - MySQL Schema (v2)
--
-- MONEY IS STORED AS INTEGER CENTAVOS (BIGINT). Never floats:
--   ₱30.00  -> 3000        ₱55.50 -> 5550
-- This removes rounding drift entirely. The API converts to/from pesos.
--
-- Run this on MySQL 5.7+/8.0 or MariaDB 10.4+ (phpMyAdmin or CLI).
-- =====================================================================

CREATE DATABASE IF NOT EXISTS sales_tracker
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE sales_tracker;

-- Fresh reinstall: uncomment to wipe first (DESTRUCTIVE).
-- SET FOREIGN_KEY_CHECKS = 0;
-- DROP TABLE IF EXISTS sales, receipts, receipt_counters, products, sessions, users, anchors;
-- SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- Users & auth
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
  id            INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  username      VARCHAR(64)      NOT NULL,
  password_hash VARCHAR(255)     NOT NULL,
  role          ENUM('owner','cashier') NOT NULL DEFAULT 'cashier',
  created_at    TIMESTAMP        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_username (username)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sessions (
  id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id    INT UNSIGNED NOT NULL,
  token      CHAR(64)     NOT NULL,
  created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at DATETIME     NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_sessions_token (token),
  KEY idx_sessions_user (user_id),
  CONSTRAINT fk_sessions_user FOREIGN KEY (user_id)
    REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Products (inventory)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
  id          INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  name        VARCHAR(120)  NOT NULL,
  price_cents BIGINT        NOT NULL DEFAULT 0,
  category    VARCHAR(60)   NOT NULL DEFAULT 'OTHER',
  is_active   TINYINT(1)    NOT NULL DEFAULT 1,
  created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_products_category (category)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Receipts (one row per sale transaction)
-- client_ref makes checkout idempotent: a retried request with the same
-- client_ref returns the ORIGINAL receipt instead of charging twice.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS receipts (
  receipt_no  VARCHAR(24)   NOT NULL,
  client_ref  VARCHAR(64)   NULL,
  sale_time   DATETIME      NOT NULL,
  cashier_id  INT UNSIGNED  NULL,
  total_cents BIGINT        NOT NULL DEFAULT 0,
  created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (receipt_no),
  UNIQUE KEY uq_receipts_client_ref (client_ref),
  KEY idx_receipts_time (sale_time),
  CONSTRAINT fk_receipts_cashier FOREIGN KEY (cashier_id)
    REFERENCES users (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Sale lines. data_hash is the SHA-256 transparency fingerprint.
-- data_hash is NULL only for the split second during insert (unique
-- indexes allow many NULLs in MySQL/MariaDB), then filled in.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sales (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  receipt_no     VARCHAR(24)     NOT NULL,
  product_id     INT UNSIGNED    NULL,
  product_name   VARCHAR(120)    NOT NULL,
  price_cents    BIGINT          NOT NULL,
  quantity       INT UNSIGNED    NOT NULL DEFAULT 1,
  subtotal_cents BIGINT          NOT NULL,
  sale_time      DATETIME        NOT NULL,
  cashier_id     INT UNSIGNED    NULL,
  data_hash      CHAR(64)        NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_sales_hash (data_hash),
  KEY idx_sales_receipt (receipt_no),
  KEY idx_sales_time (sale_time),
  CONSTRAINT fk_sales_receipt FOREIGN KEY (receipt_no)
    REFERENCES receipts (receipt_no) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_sales_product FOREIGN KEY (product_id)
    REFERENCES products (id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_sales_cashier FOREIGN KEY (cashier_id)
    REFERENCES users (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Atomic per-day receipt sequence. Incremented with
--   INSERT ... VALUES (day, LAST_INSERT_ID(1))
--   ON DUPLICATE KEY UPDATE seq = LAST_INSERT_ID(seq + 1)
-- which is race-free even with simultaneous cashiers.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS receipt_counters (
  day DATE         NOT NULL,
  seq INT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (day)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Anchors (daily transparency anchor)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS anchors (
  id               INT UNSIGNED NOT NULL AUTO_INCREMENT,
  anchor_date      DATE         NOT NULL,
  merkle_root      CHAR(64)     NOT NULL,
  tx_hash          VARCHAR(66)  NULL,
  chain            VARCHAR(20)  NULL,
  status           ENUM('pending','anchored','failed') NOT NULL DEFAULT 'pending',
  tx_count         INT UNSIGNED NOT NULL DEFAULT 0,
  grand_total_cents BIGINT      NOT NULL DEFAULT 0,
  created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  anchored_at      DATETIME     NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_anchors_date (anchor_date)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Seed products from sales_data.json (prices in centavos)
-- ---------------------------------------------------------------------
INSERT INTO products (name, price_cents, category) VALUES
  ('PS5 GAMES',  2000, 'GAMES'),
  ('STICKERS',   2000, 'MERCH'),
  ('STICKERS P', 8000, 'MERCH'),
  ('PINS',       3000, 'MERCH'),
  ('PINS P',     8000, 'MERCH'),
  ('LANYARD',    7000, 'MERCH'),
  ('PS5',        3000, 'GAMES');