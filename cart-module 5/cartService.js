// Nghiệp vụ giỏ hàng: lấy giỏ, chọn/bỏ chọn, tính tiền tách theo shop
const db = require('./db');

class HttpError extends Error {
  constructor(status, message, extra = {}) { super(message); this.status = status; this.extra = extra; }
}

function getCartId(userId) {
  let c = db.prepare('SELECT id FROM carts WHERE user_id = ?').get(userId);
  if (!c) c = { id: db.prepare('INSERT INTO carts (user_id) VALUES (?)').run(userId).lastInsertRowid };
  return c.id;
}
const touch = (cartId) => db.prepare("UPDATE carts SET updated_at = datetime('now') WHERE id = ?").run(cartId);

// Lý do không thể mua (null = mua được)
function unavailableReason(r) {
  if (r.shop_status !== 'ACTIVE') return 'Shop đã bị khóa';
  if (r.variant_status !== 'ACTIVE') return 'Sản phẩm đã bị ẩn';
  if (r.stock <= 0) return 'Hết hàng';
  if (r.quantity > r.stock) return `Chỉ còn ${r.stock} sản phẩm`;
  return null;
}

function loadRows(userId) {
  const cartId = getCartId(userId);
  return db.prepare(`
    SELECT ci.id, ci.shop_id, ci.variant_id, ci.quantity, ci.is_selected,
           v.name, v.price, v.stock, v.weight_g, v.status AS variant_status,
           s.name AS shop_name, s.status AS shop_status, s.ship_base, s.ship_per_kg
    FROM cart_items ci
    JOIN variants v ON v.id = ci.variant_id
    JOIN shops s ON s.id = ci.shop_id
    WHERE ci.cart_id = ? ORDER BY ci.shop_id, ci.id`).all(cartId);
}

// Phí ship tính RIÊNG từng shop: phí cơ bản + phí theo kg (+ phụ phí vùng xa)
function calcShipping(row, totalWeightG, address) {
  const kg = Math.max(1, Math.ceil(totalWeightG / 1000));
  const remote = address && address.remote ? 10000 : 0;
  return row.ship_base + row.ship_per_kg * (kg - 1) + remote;
}

// Voucher của shop: chọn voucher giảm nhiều nhất thỏa điều kiện tối thiểu
function bestVoucher(shopId, subtotal) {
  return db.prepare(`SELECT code, discount FROM vouchers
    WHERE shop_id = ? AND min_subtotal <= ? ORDER BY discount DESC LIMIT 1`).get(shopId, subtotal);
}

// GET /cart: nhóm theo shop, kèm trạng thái chọn của từng shop
function getCart(userId) {
  const groups = new Map();
  for (const r of loadRows(userId)) {
    if (!groups.has(r.shop_id)) groups.set(r.shop_id, { shop_id: r.shop_id, shop_name: r.shop_name,
      shop_locked: r.shop_status !== 'ACTIVE', items: [] });
    const reason = unavailableReason(r);
    groups.get(r.shop_id).items.push({
      id: r.id, variant_id: r.variant_id, name: r.name, price: r.price, quantity: r.quantity,
      stock: r.stock, is_selected: !!r.is_selected, available: !reason, unavailable_reason: reason,
      line_total: r.price * r.quantity });
  }
  const shops = [...groups.values()].map(g => {
    const ok = g.items.filter(i => i.available);
    return { ...g, all_selected: ok.length > 0 && ok.every(i => i.is_selected) };
  });
  const ok = shops.flatMap(s => s.items).filter(i => i.available);
  return { shops, all_selected: ok.length > 0 && ok.every(i => i.is_selected) };
}

function updateItem(userId, itemId, { quantity, is_selected }) {
  const cartId = getCartId(userId);
  const item = db.prepare('SELECT * FROM cart_items WHERE id = ? AND cart_id = ?').get(itemId, cartId);
  if (!item) throw new HttpError(404, 'Không tìm thấy sản phẩm trong giỏ');
  if (quantity !== undefined) {
    if (!Number.isInteger(quantity) || quantity < 1) throw new HttpError(400, 'Số lượng phải là số nguyên ≥ 1');
    const v = db.prepare('SELECT stock FROM variants WHERE id = ?').get(item.variant_id);
    if (quantity > v.stock) throw new HttpError(409, `Chỉ còn ${v.stock} sản phẩm trong kho`);
    db.prepare('UPDATE cart_items SET quantity = ? WHERE id = ?').run(quantity, itemId);
  }
  if (is_selected !== undefined) {
    db.prepare('UPDATE cart_items SET is_selected = ? WHERE id = ?').run(is_selected ? 1 : 0, itemId);
  }
  touch(cartId);
}

function addItem(userId, variantId, quantity = 1) {
  const cartId = getCartId(userId);
  const v = db.prepare('SELECT * FROM variants WHERE id = ?').get(variantId);
  if (!v) throw new HttpError(404, 'Sản phẩm không tồn tại');
  db.prepare(`INSERT INTO cart_items (cart_id, shop_id, variant_id, quantity) VALUES (?,?,?,?)
    ON CONFLICT(cart_id, variant_id) DO UPDATE SET quantity = quantity + excluded.quantity`)
    .run(cartId, v.shop_id, variantId, quantity);
  touch(cartId);
}

function removeItem(userId, itemId) {
  const cartId = getCartId(userId);
  db.prepare('DELETE FROM cart_items WHERE id = ? AND cart_id = ?').run(itemId, cartId);
  touch(cartId);
}

// PATCH /cart/select: scope = "shop" | "all"
function selectBulk(userId, { scope, shop_id, selected }) {
  const cartId = getCartId(userId);
  const sel = selected ? 1 : 0;
  // chỉ áp dụng cho dòng còn mua được
  const sql = `UPDATE cart_items SET is_selected = ? WHERE cart_id = ? AND id IN (
      SELECT ci.id FROM cart_items ci JOIN variants v ON v.id = ci.variant_id JOIN shops s ON s.id = ci.shop_id
      WHERE ci.cart_id = ? AND s.status='ACTIVE' AND v.status='ACTIVE' AND v.stock >= ci.quantity AND v.stock > 0
      ${scope === 'shop' ? 'AND ci.shop_id = ?' : ''})`;
  if (scope === 'shop') db.prepare(sql).run(sel, cartId, cartId, shop_id);
  else if (scope === 'all') db.prepare(sql).run(sel, cartId, cartId);
  else throw new HttpError(400, 'scope phải là "shop" hoặc "all"');
  touch(cartId);
}

// GET /cart/summary: chỉ tính dòng đã chọn và còn mua được
function calcSummary(userId, address = {}) {
  const selected = loadRows(userId).filter(r => r.is_selected && !unavailableReason(r));
  const byShop = new Map();
  for (const r of selected) {
    if (!byShop.has(r.shop_id)) byShop.set(r.shop_id, []);
    byShop.get(r.shop_id).push(r);
  }
  const shops = [...byShop.entries()].map(([shopId, rows]) => {
    const items = rows.map(r => ({ cart_item_id: r.id, variant_id: r.variant_id, name: r.name,
      price: r.price, qty: r.quantity, line_total: r.price * r.quantity }));
    const subtotal = items.reduce((a, i) => a + i.line_total, 0);
    const weight = rows.reduce((a, r) => a + r.weight_g * r.quantity, 0);
    const shipping_fee = calcShipping(rows[0], weight, address);
    const v = bestVoucher(shopId, subtotal);
    const discount = v ? Math.min(v.discount, subtotal) : 0;
    return { shop_id: shopId, shop_name: rows[0].shop_name, items, subtotal, shipping_fee,
      discount, voucher_code: v ? v.code : null, total: subtotal + shipping_fee - discount };
  });
  return {
    shops,
    total_items_selected: selected.reduce((a, r) => a + r.quantity, 0),
    total_shipping: shops.reduce((a, s) => a + s.shipping_fee, 0),
    grand_total: shops.reduce((a, s) => a + s.total, 0)
  };
}

module.exports = { HttpError, getCartId, getCart, updateItem, addItem, removeItem, selectBulk, calcSummary };
