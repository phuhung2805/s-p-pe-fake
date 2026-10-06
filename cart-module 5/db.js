// Kết nối SQLite, tạo schema và dữ liệu mẫu
const Database = require('better-sqlite3');
const fs = require('fs');
const FILE = process.env.DB_FILE || 'shop.db';
if (process.argv.includes('--reset') && fs.existsSync(FILE)) fs.unlinkSync(FILE);

const db = new Database(FILE);
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS shops (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ACTIVE',          -- ACTIVE | LOCKED
  ship_base INTEGER NOT NULL DEFAULT 15000,       -- phí ship cơ bản
  ship_per_kg INTEGER NOT NULL DEFAULT 5000       -- phí mỗi kg
);

CREATE TABLE IF NOT EXISTS variants (
  id INTEGER PRIMARY KEY, shop_id INTEGER NOT NULL REFERENCES shops(id),
  name TEXT NOT NULL, price INTEGER NOT NULL, stock INTEGER NOT NULL,
  weight_g INTEGER NOT NULL DEFAULT 300,
  status TEXT NOT NULL DEFAULT 'ACTIVE'           -- ACTIVE | HIDDEN
);

CREATE TABLE IF NOT EXISTS vouchers (
  id INTEGER PRIMARY KEY, shop_id INTEGER NOT NULL REFERENCES shops(id),
  code TEXT NOT NULL, discount INTEGER NOT NULL, min_subtotal INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS carts (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cart_items (
  id INTEGER PRIMARY KEY, cart_id INTEGER NOT NULL REFERENCES carts(id),
  shop_id INTEGER NOT NULL REFERENCES shops(id),
  variant_id INTEGER NOT NULL REFERENCES variants(id),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  is_selected INTEGER NOT NULL DEFAULT 1,
  added_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (cart_id, variant_id)
);
CREATE INDEX IF NOT EXISTS idx_cart_items ON cart_items(cart_id, shop_id);

CREATE TABLE IF NOT EXISTS order_groups (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
  grand_total INTEGER NOT NULL, payment_method TEXT NOT NULL, payment_status TEXT NOT NULL,
  shipping_address_snapshot TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY, order_group_id INTEGER NOT NULL REFERENCES order_groups(id),
  shop_id INTEGER NOT NULL REFERENCES shops(id), order_code TEXT NOT NULL UNIQUE,
  subtotal INTEGER NOT NULL, shipping_fee INTEGER NOT NULL, discount INTEGER NOT NULL,
  total INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS order_items (
  id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
  variant_id INTEGER NOT NULL, product_name_snapshot TEXT NOT NULL,
  unit_price_snapshot INTEGER NOT NULL, quantity INTEGER NOT NULL, line_total INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS order_status_history (
  id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
  from_status TEXT, to_status TEXT NOT NULL,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('CUSTOMER','SHOP','SYSTEM','CARRIER')),
  actor_id INTEGER, note TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_history ON order_status_history(order_id, created_at);

-- Append-only: cấm sửa/xóa lịch sử trạng thái
CREATE TRIGGER IF NOT EXISTS history_no_update BEFORE UPDATE ON order_status_history
BEGIN SELECT RAISE(ABORT, 'order_status_history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS history_no_delete BEFORE DELETE ON order_status_history
BEGIN SELECT RAISE(ABORT, 'order_status_history is append-only'); END;
`);

// ---- Dữ liệu mẫu ----
if (db.prepare('SELECT COUNT(*) c FROM users').get().c === 0) {
  db.exec(`
  INSERT INTO users VALUES (1, 'Nguyễn Văn A');
  INSERT INTO carts (id, user_id) VALUES (1, 1);
  INSERT INTO shops VALUES (12, 'Shop Áo Thun', 'ACTIVE', 15000, 5000),
                           (15, 'Shop Phụ Kiện', 'ACTIVE', 12000, 6000),
                           (18, 'Shop Giày Dép', 'ACTIVE', 20000, 7000),
                           (19, 'Shop Đã Khóa', 'LOCKED', 10000, 5000);
  INSERT INTO variants VALUES
    (101, 12, 'Áo thun basic - M', 150000, 50, 250, 'ACTIVE'),
    (102, 12, 'Áo thun basic - L', 150000, 0,  250, 'ACTIVE'),
    (220, 15, 'Ốp lưng iPhone',     90000, 30, 100, 'ACTIVE'),
    (221, 15, 'Cáp sạc Type-C',     60000, 40, 80,  'ACTIVE'),
    (330, 18, 'Giày sneaker 42',   450000, 10, 900, 'ACTIVE'),
    (440, 19, 'Mũ lưỡi trai',       70000, 10, 150, 'ACTIVE');
  INSERT INTO vouchers VALUES (1, 15, 'PK10', 10000, 80000), (2, 12, 'AT30', 30000, 500000);
  INSERT INTO cart_items (cart_id, shop_id, variant_id, quantity, is_selected) VALUES
    (1, 12, 101, 2, 1), (1, 12, 102, 1, 0), (1, 15, 220, 1, 1),
    (1, 15, 221, 1, 1), (1, 18, 330, 1, 0), (1, 19, 440, 1, 0);
  `);
}
module.exports = db;
if (require.main === module) console.log('Database sẵn sàng:', FILE);
