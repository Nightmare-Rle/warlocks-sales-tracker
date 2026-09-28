<?php
/**
 * Warlocks Sales Tracker - REST API router (v2).
 *
 * Works WITHOUT URL rewriting (shared-hosting safe):
 *   GET/POST  /api/index.php?r=products
 *   also works with PATH_INFO: /api/index.php/products
 *
 * MONEY: all amounts are handled as integer centavos internally. The API
 * accepts/returns pesos as strings ("30.00"); *_cents fields are included
 * for clients that want exact integers (e.g. the desktop sync).
 *
 * Endpoints:
 *   POST   login                 {username,password}        -> {token,user}
 *   POST   logout
 *   GET    me
 *   GET    products
 *   POST   products              {name,price,category}
 *   PUT    products/:id          {name,price,category,is_active}
 *   DELETE products/:id
 *   POST   sales                 {items:[{product_id,quantity}], client_ref?}
 *   GET    sales?date=&page=&per_page=
 *   GET    summary?from=&to=
 *   GET    anchors/pending       (X-Anchor-Secret)
 *   POST   anchors/confirm       (X-Anchor-Secret)
 *   GET    verify/:ref          PUBLIC (receipt_no or data_hash)
 *   GET    anchors/latest       PUBLIC
 */

require_once __DIR__ . '/helpers.php';

header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization, X-Anchor-Secret');
header('X-Content-Type-Options: nosniff');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

$method = $_SERVER['REQUEST_METHOD'];
$raw = isset($_GET['r']) ? (string)$_GET['r'] : trim((string)($_SERVER['PATH_INFO'] ?? ''), '/');
$parts = array_values(array_filter(explode('/', strtolower($raw)), 'strlen'));

/** Shape one sale line for JSON (pesos strings + exact cent integers). */
function sale_out(array $l): array
{
    return [
        'id'             => (int)$l['id'],
        'receipt_no'     => $l['receipt_no'],
        'product_id'     => $l['product_id'] === null ? null : (int)$l['product_id'],
        'product_name'   => $l['product_name'],
        'price'          => cents_to_peso((int)$l['price_cents']),
        'price_cents'    => (int)$l['price_cents'],
        'quantity'       => (int)$l['quantity'],
        'subtotal'       => cents_to_peso((int)$l['subtotal_cents']),
        'subtotal_cents' => (int)$l['subtotal_cents'],
        'sale_time'      => $l['sale_time'],
        'cashier_id'     => $l['cashier_id'] === null ? null : (int)$l['cashier_id'],
        'data_hash'      => $l['data_hash'],
    ];
}

/** Full receipt payload (used by create + list + idempotent retry). */
function receipt_payload(PDO $pdo, array $r): array
{
    $st = $pdo->prepare('SELECT * FROM sales WHERE receipt_no = ? ORDER BY id');
    $st->execute([$r['receipt_no']]);
    $lines = array_map('sale_out', $st->fetchAll());
    $total = cents_to_peso((int)$r['total_cents']);
    return [
        'receipt_no'       => $r['receipt_no'],
        'client_ref'       => $r['client_ref'],
        'sale_time'        => $r['sale_time'],
        'cashier_id'       => $r['cashier_id'] === null ? null : (int)$r['cashier_id'],
        'grand_total'      => $total,
        'grand_total_cents'=> (int)$r['total_cents'],
        'total'            => $total, // alias for older clients
        'lines'            => $lines,
    ];
}

try {
    switch (true) {

        /* ---------------------------------------------------------- */
        /* Auth                                                        */
        /* ---------------------------------------------------------- */
        case $method === 'POST' && $parts[0] === 'login' && count($parts) === 1:
            $b = body();
            $username = trim((string)($b['username'] ?? ''));
            $password = (string)($b['password'] ?? '');
            if ($username === '' || $password === '') {
                respond(400, ['error' => 'Username and password required']);
            }
            $st = db()->prepare('SELECT * FROM users WHERE username = ? LIMIT 1');
            $st->execute([$username]);
            $u = $st->fetch();
            if (!$u || !password_verify($password, $u['password_hash'])) {
                respond(401, ['error' => 'Invalid credentials']);
            }
            $token = login_user((int)$u['id']);
            respond(200, [
                'token' => $token,
                'user'  => ['id' => (int)$u['id'], 'username' => $u['username'], 'role' => $u['role']],
            ]);

        case $method === 'POST' && $parts[0] === 'logout' && count($parts) === 1:
            $auth = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
            if (preg_match('/^Bearer\s+([a-f0-9]{64})$/i', trim($auth), $m)) {
                logout_token($m[1]);
            }
            respond(200, ['ok' => true]);

        case $method === 'GET' && $parts[0] === 'me' && count($parts) === 1:
            $u = require_login();
            respond(200, ['user' => $u]);

        /* ---------------------------------------------------------- */
        /* Products                                                    */
        /* ---------------------------------------------------------- */
        case $method === 'GET' && $parts[0] === 'products' && count($parts) === 1:
            require_login();
            $rows = db()->query('SELECT id, name, price_cents, category, is_active FROM products WHERE is_active = 1 ORDER BY category, name')->fetchAll();
            $out = array_map(function ($p) {
                return [
                    'id'          => (int)$p['id'],
                    'name'        => $p['name'],
                    'price'       => cents_to_peso((int)$p['price_cents']),
                    'price_cents' => (int)$p['price_cents'],
                    'category'    => $p['category'],
                    'is_active'   => (int)$p['is_active'],
                ];
            }, $rows);
            respond(200, ['products' => $out]);

        case $method === 'POST' && $parts[0] === 'products' && count($parts) === 1:
            require_owner();
            $b = body();
            $name = trim((string)($b['name'] ?? ''));
            $priceCents = peso_to_cents($b['price'] ?? 0);
            $category = strtoupper(trim((string)($b['category'] ?? 'OTHER'))) ?: 'OTHER';
            if ($name === '' || $priceCents < 0) {
                respond(400, ['error' => 'Valid name and price required']);
            }
            $st = db()->prepare('INSERT INTO products (name, price_cents, category) VALUES (?,?,?)');
            $st->execute([$name, $priceCents, $category]);
            respond(201, ['id' => (int)db()->lastInsertId(), 'name' => $name, 'price' => cents_to_peso($priceCents), 'price_cents' => $priceCents, 'category' => $category]);

        case $method === 'PUT' && $parts[0] === 'products' && isset($parts[1]):
            require_owner();
            $b = body();
            $st = db()->prepare('SELECT id FROM products WHERE id = ?');
            $st->execute([(int)$parts[1]]);
            if (!$st->fetch()) {
                respond(404, ['error' => 'Product not found']);
            }
            $sets = []; $vals = [];
            if (array_key_exists('name', $b)) {
                $sets[] = 'name = ?'; $vals[] = trim((string)$b['name']);
            }
            if (array_key_exists('category', $b)) {
                $sets[] = 'category = ?'; $vals[] = strtoupper(trim((string)$b['category'])) ?: 'OTHER';
            }
            if (array_key_exists('price', $b)) {
                $sets[] = 'price_cents = ?'; $vals[] = peso_to_cents($b['price']);
            }
            if (array_key_exists('is_active', $b)) {
                $sets[] = 'is_active = ?'; $vals[] = (int)$b['is_active'];
            }
            if (!$sets) {
                respond(400, ['error' => 'Nothing to update']);
            }
            $vals[] = (int)$parts[1];
            db()->prepare('UPDATE products SET ' . implode(', ', $sets) . ' WHERE id = ?')->execute($vals);
            respond(200, ['ok' => true]);

        case $method === 'DELETE' && $parts[0] === 'products' && isset($parts[1]):
            require_owner();
            // SOFT delete: never remove the row, otherwise the product_id in
            // historical sales would change (FK) and break every anchored hash.
            $st = db()->prepare('UPDATE products SET is_active = 0 WHERE id = ?');
            $st->execute([(int)$parts[1]]);
            respond(200, ['ok' => true, 'soft_deleted' => true]);

        /* ---------------------------------------------------------- */
        /* Sales                                                       */
        /* ---------------------------------------------------------- */
        case $method === 'POST' && $parts[0] === 'sales' && count($parts) === 1:
            $u = require_login();
            $b = body();
            $items = $b['items'] ?? null;
            $clientRef = isset($b['client_ref']) ? trim((string)$b['client_ref']) : null;
            if ($clientRef === '') {
                $clientRef = null;
            }
            if ($clientRef !== null && !preg_match('/^[A-Za-z0-9._-]{8,64}$/', $clientRef)) {
                respond(400, ['error' => 'Invalid client_ref']);
            }

            $pdo = db();

            // Idempotency: a retried checkout returns the original receipt.
            if ($clientRef !== null) {
                $st = $pdo->prepare('SELECT * FROM receipts WHERE client_ref = ?');
                $st->execute([$clientRef]);
                if ($existing = $st->fetch()) {
                    respond(200, receipt_payload($pdo, $existing));
                }
            }

            if (!is_array($items) || count($items) === 0) {
                respond(400, ['error' => 'Items array required']);
            }

            $quantities = [];
            foreach ($items as $it) {
                $pid = (int)($it['product_id'] ?? 0);
                $qty = (int)($it['quantity'] ?? 0);
                if ($pid <= 0 || $qty <= 0) {
                    respond(400, ['error' => 'Each item needs product_id and a positive quantity']);
                }
                if ($qty > 100000) {
                    respond(400, ['error' => 'Quantity too large']);
                }
                $quantities[$pid] = ($quantities[$pid] ?? 0) + $qty;
            }

            $products = [];
            $st = $pdo->prepare('SELECT id, name, price_cents FROM products WHERE id = ? AND is_active = 1');
            foreach (array_keys($quantities) as $pid) {
                $st->execute([$pid]);
                $p = $st->fetch();
                if (!$p) {
                    respond(400, ['error' => "Product #$pid not found or inactive"]);
                }
                $products[$pid] = $p;
            }

            $day = date('Y-m-d');
            $saleTime = date('Y-m-d H:i:s');

            $totalCents = 0;
            foreach ($quantities as $pid => $qty) {
                $totalCents += (int)$products[$pid]['price_cents'] * $qty;
            }

            $pdo->beginTransaction();
            try {
                // Race-free daily sequence.
                $seq = receipt_next_seq($pdo, $day);
                $receipt = 'S-' . date('Ymd') . '-' . str_pad((string)$seq, 4, '0', STR_PAD_LEFT);

                $pdo->prepare(
                    'INSERT INTO receipts (receipt_no, client_ref, sale_time, cashier_id, total_cents)
                     VALUES (?,?,?,?,?)'
                )->execute([$receipt, $clientRef, $saleTime, (int)$u['id'], $totalCents]);

                $ins = $pdo->prepare(
                    'INSERT INTO sales (receipt_no, product_id, product_name, price_cents, quantity, subtotal_cents, sale_time, cashier_id, data_hash)
                     VALUES (?,?,?,?,?,?,?,?,NULL)'
                );
                foreach ($quantities as $pid => $qty) {
                    $p = $products[$pid];
                    $sub = (int)$p['price_cents'] * $qty;
                    $ins->execute([$receipt, $pid, $p['name'], (int)$p['price_cents'], $qty, $sub, $saleTime, (int)$u['id']]);
                    $saleId = (int)$pdo->lastInsertId();
                    $hash = hash_sale_line($receipt, $pid, $p['name'], (int)$p['price_cents'], $qty, $sub, $saleTime, (int)$u['id'], $saleId);
                    $pdo->prepare('UPDATE sales SET data_hash = ? WHERE id = ?')->execute([$hash, $saleId]);
                }
                $pdo->commit();
            } catch (PDOException $e) {
                if ($pdo->inTransaction()) {
                    $pdo->rollBack();
                }
                // Lost the client_ref race: return the winner's receipt.
                if ($clientRef !== null && $e->getCode() === '23000') {
                    $st = $pdo->prepare('SELECT * FROM receipts WHERE client_ref = ?');
                    $st->execute([$clientRef]);
                    if ($existing = $st->fetch()) {
                        respond(200, receipt_payload($pdo, $existing));
                    }
                }
                throw $e;
            } catch (Throwable $e) {
                if ($pdo->inTransaction()) {
                    $pdo->rollBack();
                }
                throw $e;
            }

            // Make sure a placeholder anchor row exists for today.
            $pdo->prepare(
                'INSERT INTO anchors (anchor_date, merkle_root, tx_count, grand_total_cents)
                 VALUES (?, "", 0, 0)
                 ON DUPLICATE KEY UPDATE id = id'
            )->execute([$day]);

            $st = $pdo->prepare('SELECT * FROM receipts WHERE receipt_no = ?');
            $st->execute([$receipt]);
            respond(201, receipt_payload($pdo, $st->fetch()));

        case $method === 'GET' && $parts[0] === 'sales' && count($parts) === 1:
            require_login();
            $date = (string)($_GET['date'] ?? date('Y-m-d'));
            $page = max(1, (int)($_GET['page'] ?? 1));
            $per = min(200, max(1, (int)($_GET['per_page'] ?? 50)));
            $off = ($page - 1) * $per;

            $pdo = db();
            $st = $pdo->prepare(
                'SELECT * FROM receipts WHERE DATE(sale_time) = ? ORDER BY sale_time DESC, receipt_no DESC LIMIT ' . $per . ' OFFSET ' . $off
            );
            $st->execute([$date]);
            $receipts = $st->fetchAll();

            $out = [];
            foreach ($receipts as $r) {
                $payload = receipt_payload($pdo, $r);
                $payload['hash'] = $payload['lines'][0]['data_hash'] ?? null;
                $out[] = $payload;
            }
            respond(200, ['date' => $date, 'receipts' => $out]);

        case $method === 'GET' && $parts[0] === 'summary' && count($parts) === 1:
            require_login();
            $from = (string)($_GET['from'] ?? date('Y-m-d'));
            $to   = (string)($_GET['to'] ?? date('Y-m-d'));
            $st = db()->prepare(
                'SELECT DATE(sale_time) AS d, COUNT(DISTINCT receipt_no) AS receipts,
                        COUNT(*) AS line_count, COALESCE(SUM(subtotal_cents),0) AS total_cents
                 FROM sales WHERE DATE(sale_time) BETWEEN ? AND ?
                 GROUP BY DATE(sale_time) ORDER BY d'
            );
            $st->execute([$from, $to]);
            $rows = $st->fetchAll();
            $grandCents = 0;
            foreach ($rows as &$r) {
                $r['total'] = cents_to_peso((int)$r['total_cents']);
                $grandCents += (int)$r['total_cents'];
            }
            unset($r);

            $prod = (int)db()->query('SELECT COUNT(*) FROM products WHERE is_active = 1')->fetchColumn();
            $anchor = db()->query(
                "SELECT anchor_date, merkle_root, tx_hash, chain, status, tx_count, grand_total_cents
                 FROM anchors WHERE status <> 'failed' ORDER BY anchor_date DESC LIMIT 1"
            )->fetch();
            if ($anchor) {
                $anchor['grand_total'] = cents_to_peso((int)$anchor['grand_total_cents']);
            }

            respond(200, [
                'from'   => $from,
                'to'     => $to,
                'days'   => $rows,
                'grand_total' => cents_to_peso($grandCents),
                'grand_total_cents' => $grandCents,
                'active_products' => $prod,
                'latest_anchor' => $anchor ?: null,
            ]);

        /* ---------------------------------------------------------- */
        /* Anchoring (cron / signer worker)                            */
        /* ---------------------------------------------------------- */
        case $method === 'GET' && $parts[0] === 'anchors' && ($parts[1] ?? '') === 'pending' && count($parts) === 2:
            require_anchor_secret();
            $rows = db()->query(
                "SELECT anchor_date, merkle_root, grand_total_cents, tx_count
                 FROM anchors WHERE status = 'pending' ORDER BY anchor_date LIMIT 10"
            )->fetchAll();
            foreach ($rows as &$r) {
                $r['grand_total'] = cents_to_peso((int)$r['grand_total_cents']);
            }
            unset($r);
            respond(200, ['anchors' => $rows]);

        case $method === 'POST' && $parts[0] === 'anchors' && ($parts[1] ?? '') === 'confirm' && count($parts) === 2:
            require_anchor_secret();
            $b = body();
            $date = (string)($b['date'] ?? '');
            $txHash = trim((string)($b['tx_hash'] ?? ''));
            $chain = trim((string)($b['chain'] ?? 'polygon'));
            $status = in_array($b['status'] ?? 'anchored', ['anchored', 'failed'], true) ? $b['status'] : 'anchored';
            if ($date === '') {
                respond(400, ['error' => 'date required']);
            }
            $st = db()->prepare('UPDATE anchors SET tx_hash = ?, chain = ?, status = ?, anchored_at = NOW() WHERE anchor_date = ?');
            $st->execute([$status === 'anchored' ? $txHash : null, $chain, $status, $date]);
            respond(200, ['ok' => true]);

        /* ---------------------------------------------------------- */
        /* Public (no auth) transparency endpoints                     */
        /* ---------------------------------------------------------- */
        case $method === 'GET' && $parts[0] === 'verify' && isset($parts[1]) && count($parts) === 2:
            $ref = (string)$parts[1];
            if (preg_match('/^[a-f0-9]{64}$/i', $ref)) {
                $st = db()->prepare('SELECT * FROM sales WHERE data_hash = ?');
                $st->execute([strtolower($ref)]);
            } else {
                $st = db()->prepare('SELECT * FROM sales WHERE receipt_no = ?');
                $st->execute([strtoupper($ref)]);
            }
            $lines = $st->fetchAll();
            if (!$lines) {
                respond(404, ['error' => 'Not found', 'verified' => false]);
            }

            $day = substr($lines[0]['sale_time'], 0, 10);

            // Recompute hashes for EVERY line of that day from the stored
            // fields. Any tampering changes the recomputed day root.
            $dayLines = db()->prepare('SELECT * FROM sales WHERE DATE(sale_time) = ? ORDER BY id');
            $dayLines->execute([$day]);
            $allDay = $dayLines->fetchAll();

            $allOk = true;
            $dayHashes = [];
            foreach ($allDay as $l) {
                $expect = hash_sale_line(
                    $l['receipt_no'],
                    $l['product_id'] === null ? null : (int)$l['product_id'],
                    $l['product_name'],
                    (int)$l['price_cents'],
                    (int)$l['quantity'],
                    (int)$l['subtotal_cents'],
                    $l['sale_time'],
                    $l['cashier_id'] === null ? null : (int)$l['cashier_id'],
                    (int)$l['id']
                );
                if ($expect !== $l['data_hash']) {
                    $allOk = false;
                }
                $dayHashes[] = $expect;
            }

            sort($dayHashes, SORT_STRING);
            $dayRoot = merkle_root($dayHashes);

            $outLines = [];
            foreach ($lines as $l) {
                $expect = hash_sale_line(
                    $l['receipt_no'],
                    $l['product_id'] === null ? null : (int)$l['product_id'],
                    $l['product_name'],
                    (int)$l['price_cents'],
                    (int)$l['quantity'],
                    (int)$l['subtotal_cents'],
                    $l['sale_time'],
                    $l['cashier_id'] === null ? null : (int)$l['cashier_id'],
                    (int)$l['id']
                );
                $row = sale_out($l);
                $row['hash_ok'] = ($expect === $l['data_hash']);
                $outLines[] = $row;
            }

            $st = db()->prepare('SELECT status, tx_hash, chain, anchor_date, merkle_root, grand_total_cents FROM anchors WHERE anchor_date = ?');
            $st->execute([$day]);
            $anchor = $st->fetch();
            if ($anchor) {
                $anchor['grand_total'] = cents_to_peso((int)$anchor['grand_total_cents']);
            }

            $onChainMatch = null;
            if ($anchor && $anchor['status'] === 'anchored') {
                $onChainMatch = ($anchor['merkle_root'] === $dayRoot);
                $allOk = $allOk && $onChainMatch;
            }

            $receiptTotalCents = 0;
            foreach ($lines as $l) {
                $receiptTotalCents += (int)$l['subtotal_cents'];
            }

            respond(200, [
                'verified'      => $allOk,
                'merkle_root'   => $dayRoot,
                'on_chain_match'=> $onChainMatch,
                'receipt_no'    => $lines[0]['receipt_no'],
                'sale_time'     => $lines[0]['sale_time'],
                'grand_total'   => cents_to_peso($receiptTotalCents),
                'lines'         => $outLines,
                'anchor'        => $anchor ?: null,
            ]);

        case $method === 'GET' && $parts[0] === 'anchors' && ($parts[1] ?? '') === 'latest' && count($parts) === 2:
            $a = db()->query(
                "SELECT anchor_date, merkle_root, tx_hash, chain, status, tx_count, grand_total_cents
                 FROM anchors WHERE status <> 'failed' ORDER BY anchor_date DESC LIMIT 1"
            )->fetch();
            if ($a) {
                $a['grand_total'] = cents_to_peso((int)$a['grand_total_cents']);
            }
            respond(200, ['anchor' => $a ?: null]);

        default:
            respond(404, ['error' => 'Not found']);
    }
} catch (Throwable $e) {
    respond_error($e);
}