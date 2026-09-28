<?php
/**
 * One-time installer: creates tables + owner account.
 *
 * CLI (recommended, from web/):
 *   php setup/install.php myowner SecretPass123
 *
 * Web (temporary, DELETE afterwards):
 *   visit setup/install.php?user=myowner&pass=SecretPass123
 *
 * After installation, DELETE this file from the server.
 */

require_once __DIR__ . '/../api/config.php';

$user = $_GET['user'] ?? ($argv[1] ?? null);
$pass = $_GET['pass'] ?? ($argv[2] ?? null);

if (!$user || !$pass || strlen((string)$pass) < 6 || preg_match('/[a-z]/i', (string)$user) === 0) {
    die("Usage: php install.php <username> <password(min6)>\n");
}

$pdo = new PDO(
    'mysql:host=' . DB_HOST . ';port=' . DB_PORT . ';dbname=' . DB_NAME . ';charset=utf8mb4',
    DB_USER,
    DB_PASS,
    [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]
);

$statements = [
    "CREATE TABLE IF NOT EXISTS users (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT,
        username VARCHAR(64) NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        role ENUM('owner','cashier') NOT NULL DEFAULT 'cashier',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uq_users_username (username)
    ) ENGINE=InnoDB",
    "CREATE TABLE IF NOT EXISTS sessions (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT,
        user_id INT UNSIGNED NOT NULL,
        token CHAR(64) NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME NOT NULL,
        PRIMARY KEY (id),
        UNIQUE KEY uq_sessions_token (token),
        KEY idx_sessions_user (user_id),
        CONSTRAINT fk_sessions_user FOREIGN KEY (user_id)
            REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE
    ) ENGINE=InnoDB",
    "CREATE TABLE IF NOT EXISTS products (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT,
        name VARCHAR(120) NOT NULL,
        price_cents BIGINT NOT NULL DEFAULT 0,
        category VARCHAR(60) NOT NULL DEFAULT 'OTHER',
        is_active TINYINT(1) NOT NULL DEFAULT 1,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        KEY idx_products_category (category)
    ) ENGINE=InnoDB",
    "CREATE TABLE IF NOT EXISTS receipts (
        receipt_no VARCHAR(24) NOT NULL,
        client_ref VARCHAR(64) NULL,
        sale_time DATETIME NOT NULL,
        cashier_id INT UNSIGNED NULL,
        total_cents BIGINT NOT NULL DEFAULT 0,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (receipt_no),
        UNIQUE KEY uq_receipts_client_ref (client_ref),
        KEY idx_receipts_time (sale_time),
        CONSTRAINT fk_receipts_cashier FOREIGN KEY (cashier_id)
            REFERENCES users (id) ON DELETE SET NULL ON UPDATE CASCADE
    ) ENGINE=InnoDB",
    "CREATE TABLE IF NOT EXISTS sales (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        receipt_no VARCHAR(24) NOT NULL,
        product_id INT UNSIGNED NULL,
        product_name VARCHAR(120) NOT NULL,
        price_cents BIGINT NOT NULL,
        quantity INT UNSIGNED NOT NULL DEFAULT 1,
        subtotal_cents BIGINT NOT NULL,
        sale_time DATETIME NOT NULL,
        cashier_id INT UNSIGNED NULL,
        data_hash CHAR(64) NULL,
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
    ) ENGINE=InnoDB",
    "CREATE TABLE IF NOT EXISTS receipt_counters (
        day DATE NOT NULL,
        seq INT UNSIGNED NOT NULL DEFAULT 0,
        PRIMARY KEY (day)
    ) ENGINE=InnoDB",
    "CREATE TABLE IF NOT EXISTS anchors (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT,
        anchor_date DATE NOT NULL,
        merkle_root CHAR(64) NOT NULL,
        tx_hash VARCHAR(66) NULL,
        chain VARCHAR(20) NULL,
        status ENUM('pending','anchored','failed') NOT NULL DEFAULT 'pending',
        tx_count INT UNSIGNED NOT NULL DEFAULT 0,
        grand_total_cents BIGINT NOT NULL DEFAULT 0,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        anchored_at DATETIME NULL,
        PRIMARY KEY (id),
        UNIQUE KEY uq_anchors_date (anchor_date)
    ) ENGINE=InnoDB",
];

foreach ($statements as $sql) {
    $pdo->exec($sql);
}
echo "tables ok\n";

// Seed products (matches your sales_data.json) - skipped if already present.
$count = (int)$pdo->query('SELECT COUNT(*) FROM products')->fetchColumn();
if ($count === 0) {
    $ins = $pdo->prepare('INSERT INTO products (name, price_cents, category) VALUES (?,?,?)');
    foreach ([
        ['PS5 GAMES', 2000, 'GAMES'],
        ['STICKERS', 2000, 'MERCH'],
        ['STICKERS P', 8000, 'MERCH'],
        ['PINS', 3000, 'MERCH'],
        ['PINS P', 8000, 'MERCH'],
        ['LANYARD', 7000, 'MERCH'],
        ['PS5', 3000, 'GAMES'],
    ] as $p) {
        $ins->execute($p);
    }
    echo "products seeded\n";
}

// Owner account (idempotent: update password if exists).
$hash = password_hash((string)$pass, PASSWORD_DEFAULT);
$st = $pdo->prepare('SELECT id FROM users WHERE username = ?');
$st->execute([$user]);
if ($st->fetch()) {
    $pdo->prepare('UPDATE users SET password_hash = ?, role = "owner" WHERE username = ?')->execute([$hash, $user]);
} else {
    $pdo->prepare('INSERT INTO users (username, password_hash, role) VALUES (?,?, "owner")')->execute([$user, $hash]);
}
echo "owner '$user' ready\n";

echo "install ok - DELETE setup/install.php from the server now.\n";