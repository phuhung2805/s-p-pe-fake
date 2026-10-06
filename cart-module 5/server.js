const express = require('express');
const path = require('path');
const cart = require('./cartService');
const orders = require('./orderService');

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Giả lập đăng nhập: gửi header x-user-id (mặc định 1). Thực tế thay bằng JWT/session.
app.use('/api', (req, _res, next) => { req.userId = Number(req.header('x-user-id') || 1); next(); });

const wrap = fn => (req, res) => {
  try { res.json(fn(req) ?? { ok: true }); }
  catch (e) {
    if (e.status) return res.status(e.status).json({ error: e.message, ...e.extra });
    console.error(e); res.status(500).json({ error: 'Lỗi hệ thống' });
  }
};
const addr = req => ({ text: req.query.address || 'Thái Nguyên', remote: req.query.remote === '1' });

// ---- Giỏ hàng ----
app.get('/api/cart',               wrap(r => cart.getCart(r.userId)));
app.post('/api/cart/items',        wrap(r => cart.addItem(r.userId, r.body.variant_id, r.body.quantity)));
app.patch('/api/cart/items/:id',   wrap(r => cart.updateItem(r.userId, +r.params.id, r.body)));
app.delete('/api/cart/items/:id',  wrap(r => cart.removeItem(r.userId, +r.params.id)));
app.patch('/api/cart/select',      wrap(r => cart.selectBulk(r.userId, r.body)));
app.get('/api/cart/summary',       wrap(r => cart.calcSummary(r.userId, addr(r))));

// ---- Thanh toán & đơn hàng ----
app.post('/api/checkout',          wrap(r => orders.checkout(r.userId, r.body)));
app.get('/api/orders',             wrap(r => orders.listOrders(r.userId)));
app.get('/api/orders/:id',         wrap(r => orders.getOrder(r.userId, +r.params.id)));
// Demo: thực tế mỗi actor có API/xác thực riêng (shop portal, webhook vận chuyển...)
app.patch('/api/orders/:id/status', wrap(r =>
  orders.changeStatus(+r.params.id, r.body.to, r.body.actor_type, r.body.actor_id, r.body.note)));

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`http://localhost:${PORT}`));
