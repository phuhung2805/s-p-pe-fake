// Bảng chuyển trạng thái hợp lệ: from -> { to: [actor được phép] }
const TRANSITIONS = {
  PENDING_PAYMENT:  { PENDING_CONFIRM: ['SYSTEM'], CANCELLED: ['CUSTOMER', 'SYSTEM'] },
  PENDING_CONFIRM:  { PROCESSING: ['SHOP'], CANCELLED: ['CUSTOMER', 'SHOP'] },
  PROCESSING:       { SHIPPING: ['SHOP'], CANCELLED: ['SHOP'] },
  SHIPPING:         { DELIVERED: ['CARRIER'] },
  DELIVERED:        { COMPLETED: ['CUSTOMER', 'SYSTEM'], RETURN_REQUESTED: ['CUSTOMER'] },
  RETURN_REQUESTED: { REFUNDED: ['SHOP', 'SYSTEM'] },
  COMPLETED: {}, CANCELLED: {}, REFUNDED: {}
};
const LABELS = {
  PENDING_PAYMENT: 'Chờ thanh toán', PENDING_CONFIRM: 'Chờ shop xác nhận',
  PROCESSING: 'Shop đang chuẩn bị hàng', SHIPPING: 'Đang giao hàng',
  DELIVERED: 'Đã giao', COMPLETED: 'Hoàn tất', CANCELLED: 'Đã hủy',
  RETURN_REQUESTED: 'Yêu cầu trả hàng', REFUNDED: 'Đã hoàn tiền'
};
const NEEDS_NOTE = ['CANCELLED', 'RETURN_REQUESTED', 'REFUNDED'];

function nextOptions(from) {
  return Object.entries(TRANSITIONS[from] || {}).flatMap(([to, actors]) =>
    actors.map(actor => ({ to, actor, label: LABELS[to] })));
}
function check(from, to, actor) {
  const actors = (TRANSITIONS[from] || {})[to];
  if (!actors) return `Không thể chuyển từ ${from} sang ${to}`;
  if (!actors.includes(actor)) return `${actor} không có quyền chuyển ${from} → ${to}`;
  return null;
}
module.exports = { TRANSITIONS, LABELS, NEEDS_NOTE, nextOptions, check };
