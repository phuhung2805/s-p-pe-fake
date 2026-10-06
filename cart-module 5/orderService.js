// Checkout (tách đơn theo shop) và Order Timeline
const db = require('./db');
const { HttpError, getCartId, calcSummary } = require('./cartService');
const status = require('./orderStatus');

function writeHistory(orderId, from, to, actorType, actorId, note) {
  db.prepare(`INSERT INTO order_status_history (order_id, from_status, to_status, actor_type, actor_id, note)
              VALUES (?,?,?,?,?,?)`).run(orderId, from, to, actorType, actorId ?? null, note ?? null);
}

// POST /checkout — toàn bộ chạy trong MỘT transaction
const checkout = db.transaction((userId, { address, payment_method = 'COD', expected_total }) => {
  if (!address || !address.text) throw new HttpError(400, 'Thiếu địa chỉ giao hàng');
  if (!['COD', 'ONLINE'].includes(payment_method)) throw new HttpError(400, 'Phương thức thanh toán không hợp lệ');

  // 1. Tính lại giá & tồn kho ngay lúc thanh toán
  const summary = calcSummary(userId, address);
  if (summary.shops.length === 0) throw new HttpError(400, 'Chưa chọn sản phẩm nào để thanh toán');
  if (expected_total !== undefined && expected_total !== summary.grand_total) {
    throw new HttpError(409, 'Giá hoặc tồn kho đã thay đổi, vui lòng kiểm tra lại', { summary });
  }

  // 2. Trừ/khóa tồn kho (điều kiện stock >= qty chống bán vượt)
  for (const s of summary.shops) for (const i of s.items) {
    const r = db.prepare('UPDATE variants SET stock = stock - ? WHERE id = ? AND stock >= ?').run(i.qty, i.variant_id, i.qty);
    if (r.changes === 0) throw new HttpError(409, `"${i.name}" vừa hết hàng`, { summary: calcSummary(userId, address) });
  }

  // 3. Đơn tổng + các đơn con
  const online = payment_method === 'ONLINE';
  const groupId = db.prepare(`INSERT INTO order_groups (user_id, grand_total, payment_method, payment_status, shipping_address_snapshot)
    VALUES (?,?,?,?,?)`).run(userId, summary.grand_total, payment_method, online ? 'UNPAID' : 'COD_PENDING', JSON.stringify(address)).lastInsertRowid;

  const firstStatus = online ? 'PENDING_PAYMENT' : 'PENDING_CONFIRM';
  const orders = summary.shops.map((s, idx) => {
    const code = `OD${Date.now().toString(36).toUpperCase()}${groupId}${idx}`;
    const orderId = db.prepare(`INSERT INTO orders (order_group_id, shop_id, order_code, subtotal, shipping_fee, discount, total, status)
      VALUES (?,?,?,?,?,?,?,?)`).run(groupId, s.shop_id, code, s.subtotal, s.shipping_fee, s.discount, s.total, firstStatus).lastInsertRowid;
    // 4. Chốt giá (price snapshot)
    for (const i of s.items) db.prepare(`INSERT INTO order_items
      (order_id, variant_id, product_name_snapshot, unit_price_snapshot, quantity, line_total) VALUES (?,?,?,?,?,?)`)
      .run(orderId, i.variant_id, i.name, i.price, i.qty, i.line_total);
    // 5. Dòng timeline đầu tiên
    writeHistory(orderId, null, firstStatus, 'SYSTEM', null, 'Đơn hàng được tạo');
    return { id: orderId, order_code: code, shop_id: s.shop_id, total: s.total };
  });

  // 6. Chỉ xóa các dòng ĐÃ CHỌN, dòng chưa chọn ở lại giỏ
  const ids = summary.shops.flatMap(s => s.items.map(i => i.cart_item_id));
  db.prepare(`DELETE FROM cart_items WHERE cart_id = ? AND id IN (${ids.map(() => '?').join(',')})`).run(getCartId(userId), ...ids);

  return { order_group_id: groupId, grand_total: summary.grand_total, orders };
});

function listOrders(userId) {
  return db.prepare(`
    SELECT o.*, s.name AS shop_name, g.payment_method FROM orders o
    JOIN order_groups g ON g.id = o.order_group_id JOIN shops s ON s.id = o.shop_id
    WHERE g.user_id = ? ORDER BY o.id DESC`).all(userId)
    .map(o => ({ ...o, status_label: status.LABELS[o.status] }));
}

function getOrder(userId, orderId) {
  const o = db.prepare(`SELECT o.*, s.name AS shop_name, g.payment_method, g.shipping_address_snapshot AS address
    FROM orders o JOIN order_groups g ON g.id = o.order_group_id JOIN shops s ON s.id = o.shop_id
    WHERE o.id = ? AND g.user_id = ?`).get(orderId, userId);
  if (!o) throw new HttpError(404, 'Không tìm thấy đơn hàng');
  const items = db.prepare('SELECT * FROM order_items WHERE order_id = ?').all(orderId);
  // Mốc mới nhất ở trên cùng
  const timeline = db.prepare('SELECT * FROM order_status_history WHERE order_id = ? ORDER BY id DESC').all(orderId)
    .map(h => ({ ...h, to_label: status.LABELS[h.to_status] }));
  return { ...o, address: JSON.parse(o.address), status_label: status.LABELS[o.status],
    items, timeline, next_options: status.nextOptions(o.status) };
}

// Đổi trạng thái: kiểm tra transition + ghi history cùng transaction
const changeStatus = db.transaction((orderId, to, actorType, actorId, note) => {
  const o = db.prepare('SELECT * FROM orders WHERE id = ?').get(orderId);
  if (!o) throw new HttpError(404, 'Không tìm thấy đơn hàng');
  const err = status.check(o.status, to, actorType);
  if (err) throw new HttpError(422, err);
  if (status.NEEDS_NOTE.includes(to) && !(note && note.trim())) throw new HttpError(400, 'Cần nhập lý do cho thao tác này');

  db.prepare('UPDATE orders SET status = ? WHERE id = ?').run(to, orderId);
  writeHistory(orderId, o.status, to, actorType, actorId, note);

  if (to === 'CANCELLED') { // hoàn lại tồn kho
    for (const i of db.prepare('SELECT variant_id, quantity FROM order_items WHERE order_id = ?').all(orderId))
      db.prepare('UPDATE variants SET stock = stock + ? WHERE id = ?').run(i.quantity, i.variant_id);
  }
});

module.exports = { checkout, listOrders, getOrder, changeStatus };
