<?php
/**
 * Daily transparency anchor worker - CLI / cron.
 *
 * Computes the Merkle root of each day's sales, plus the grand total and
 * line count, then stores an `anchors` row with status 'pending'.
 * The Python signer (web/signer/sign.py) picks up 'pending' rows, puts the
 * root on-chain (Polygon/BNB), then calls the confirm endpoint.
 *
 * Usage (from web/):
 *   php cron/daily_anchor.php                       # anchor YESTERDAY
 *   php cron/daily_anchor.php 2026-09-21            # anchor a specific day
 *   php cron/daily_anchor.php --today --force       # anchor today (only if you accept
 *                                                   #   that no more sales can be added)
 *
 * A day that is already 'anchored' is IMMUTABLE: its root/total are never
 * overwritten. Re-anchoring a closed day is therefore safe.
 *
 * Cron example (MonsterASP cPanel, run 5 min after midnight):
 *   cd /home/youruser/public_html/web && php cron/daily_anchor.php
 */

require_once __DIR__ . '/../api/helpers.php';

$target = null;
$isToday = false;
$force = false;
foreach ($argv as $a) {
    if (preg_match('/^\d{4}-\d{2}-\d{2}$/', $a)) {
        $target = $a;
    }
    if ($a === '--today') {
        $isToday = true;
    }
    if ($a === '--force') {
        $force = true;
    }
}
if (!$target) {
    $target = $isToday ? date('Y-m-d') : date('Y-m-d', strtotime('-1 day')); // yesterday by default
}

// Accept target via env too (some hosts dislike argv on cron)
$target = getenv('ANCHOR_DATE') ? getenv('ANCHOR_DATE') : $target;

// Refuse to anchor the current (still-open) day unless explicitly forced.
if ($target === date('Y-m-d') && !$force) {
    fwrite(STDOUT, "[" . date('c') . "] $target is today and still open; refusing (use --force to override).\n");
    exit(0);
}

$pdo = db();

// ---------------------------------------------------------------------
function merkle_root_from_db(PDO $pdo, string $day): ?string
{
    $st = $pdo->prepare('SELECT data_hash FROM sales WHERE DATE(sale_time) = ? ORDER BY data_hash');
    $st->execute([$day]);
    $hashes = $st->fetchAll(PDO::FETCH_COLUMN);
    if (count($hashes) === 0) {
        return null;
    }
    sort($hashes, SORT_STRING);
    return merkle_root($hashes);
}
// ---------------------------------------------------------------------

$root = merkle_root_from_db($pdo, $target);

if ($root === null) {
    fwrite(STDOUT, "[" . date('c') . "] $target: no sales, skipping.\n");
    exit(0);
}

$st = $pdo->prepare(
    'SELECT COUNT(*) AS n, COALESCE(SUM(subtotal_cents),0) AS total_cents
     FROM sales WHERE DATE(sale_time) = ?'
);
$st->execute([$target]);
$agg = $st->fetch();

$st = $pdo->prepare(
    'INSERT INTO anchors (anchor_date, merkle_root, tx_count, grand_total_cents, status)
     VALUES (?, ?, ?, ?, "pending")
     ON DUPLICATE KEY UPDATE
        merkle_root       = IF(status = "anchored", merkle_root,       VALUES(merkle_root)),
        tx_count          = IF(status = "anchored", tx_count,          VALUES(tx_count)),
        grand_total_cents = IF(status = "anchored", grand_total_cents, VALUES(grand_total_cents)),
        status            = IF(status = "anchored", "anchored",        "pending")'
);
$st->execute([$target, $root, (int)$agg['n'], (int)$agg['total_cents']]);

$current = $pdo->prepare('SELECT status, merkle_root FROM anchors WHERE anchor_date = ?');
$current->execute([$target]);
$row = $current->fetch();

fwrite(STDOUT, sprintf(
    "[%s] %s rooted= %s lines=%d total=%s status=%s%s\n",
    date('c'), $target, $row['merkle_root'], (int)$agg['n'], cents_to_peso((int)$agg['total_cents']),
    $row['status'],
    $row['status'] === 'anchored' && $row['merkle_root'] !== $root ? ' (kept existing anchored root)' : ''
));