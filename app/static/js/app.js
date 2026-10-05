// Global Application State
const STATE = {
  activeRole: 'Buyer',
  token: null,
  user: null,
  cart: [],
  currentScannerTarget: null, // 'buyer' or 'shipper'
  html5QrScanner: null,
  selectedReviewOrderId: null,
  selectedReviewProductId: null,
  selectedDisputeOrderId: null,
  cachedOrders: []
};

// Test credentials for instant 1-click role switching
const ROLE_ACCOUNTS = {
  Buyer:   { email: 'buyer@customer.vn',   password: 'Password123!', name: 'Phạm Thị Khách Hàng (VIP Buyer)' },
  Shop:    { email: 'shop1@techstore.vn',  password: 'Password123!', name: 'Nguyễn Văn Shop (TechStore)' },
  Shipper: { email: 'shipper@fastship.vn', password: 'Password123!', name: 'Lê Văn Shipper (FastShip)' },
  Admin:   { email: 'admin@ecommerce.vn',  password: 'Password123!', name: 'Quản Trị Viên Hệ Thống' }
};

// ----------------- Initialization & Role Switching -----------------
document.addEventListener("DOMContentLoaded", () => {
  loadBuyerProducts(); // Tự động tải sản phẩm khi vừa vào trang
});
  
  // Try loading saved cart
  const savedCart = localStorage.getItem('escrow_cart');
  if (savedCart) {
    try { STATE.cart = JSON.parse(savedCart); } catch(e){}
  }
  updateCartBadge();

  // Switch to default role: Buyer
  await switchRole('Buyer');
});

async function switchRole(role) {
  STATE.activeRole = role;
  
  // Highlight active role pill
  ['Buyer', 'Shop', 'Shipper', 'Admin'].forEach(r => {
    const btn = document.getElementById(`role-btn-${r}`);
    if (r === role) {
      btn.className = "px-3 py-1.5 text-xs font-semibold rounded-lg transition-all flex items-center gap-1.5 bg-indigo-600 text-white shadow";
    } else {
      btn.className = "px-3 py-1.5 text-xs font-semibold rounded-lg transition-all flex items-center gap-1.5 text-slate-300 hover:text-white hover:bg-slate-700";
    }
  });

  // Switch views
  ['Buyer', 'Shop', 'Shipper', 'Admin'].forEach(r => {
    const view = document.getElementById(`view-${r}`);
    if (view) {
      if (r === role) view.classList.remove('hidden');
      else view.classList.add('hidden');
    }
  });

  // Auto-login as the selected test account
  const creds = ROLE_ACCOUNTS[role];
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: creds.email, password: creds.password })
    });
    if (!res.ok) throw new Error("Login failed");
    const data = await res.json();
    STATE.token = data.access_token;
    STATE.user = data;

    document.getElementById('nav-user-name').innerText = data.full_name;
    document.getElementById('nav-user-role').innerText = `${data.role} • ${data.email}`;

    // Load initial data for that role
    if (role === 'Buyer') {
      loadBuyerProducts();
      loadBuyerOrders();
    } else if (role === 'Shop') {
      loadShopData();
    } else if (role === 'Shipper') {
      loadShipperData();
    } else if (role === 'Admin') {
      loadAdminData();
    }

    showToast(`Đã chuyển sang vai trò: ${role}`, 'success');
  } catch (err) {
    showToast(`Lỗi đăng nhập vai trò ${role}: ${err.message}`, 'error');
  }

  setTimeout(() => { if (window.lucide) lucide.createIcons(); }, 100);
}

// ----------------- MODULE 7: BUYER DISCOVERY & CART -----------------
function switchBuyerTab(tab) {
  const mBtn = document.getElementById('tab-buyer-market');
  const oBtn = document.getElementById('tab-buyer-orders');
  const mSec = document.getElementById('buyer-tab-market');
  const oSec = document.getElementById('buyer-tab-orders');

  if (tab === 'market') {
    mBtn.className = "px-4 py-2 text-sm font-semibold rounded-xl bg-indigo-50 text-indigo-700 border border-indigo-200";
    oBtn.className = "px-4 py-2 text-sm font-semibold rounded-xl text-slate-600 hover:bg-slate-100 relative";
    mSec.classList.remove('hidden');
    oSec.classList.add('hidden');
  } else {
    oBtn.className = "px-4 py-2 text-sm font-semibold rounded-xl bg-indigo-50 text-indigo-700 border border-indigo-200 relative";
    mBtn.className = "px-4 py-2 text-sm font-semibold rounded-xl text-slate-600 hover:bg-slate-100";
    oSec.classList.remove('hidden');
    mSec.classList.add('hidden');
    loadBuyerOrders();
  }
}

async function loadBuyerProducts() {
  const q = document.getElementById('buyer-search-input').value.trim();
  const cat = document.getElementById('buyer-category-select').value;
  let url = `/api/discovery/products?buyer_lat=21.0360&buyer_lon=105.7950&sort_by=distance`;
  if (q) url += `&q=${encodeURIComponent(q)}`;
  if (cat && cat !== 'ALL') url += `&category=${encodeURIComponent(cat)}`;

  try {
    const res = await fetch(url);
    const products = await res.json();
    const container = document.getElementById('buyer-products-grid');
    container.innerHTML = '';

    if (products.length === 0) {
      container.innerHTML = `<div class="col-span-3 text-center py-12 text-slate-400">Không tìm thấy sản phẩm nào phù hợp</div>`;
      return;
    }

    products.forEach(p => {
      const card = document.createElement('div');
      card.className = "bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm hover:shadow-md transition-all flex flex-col justify-between";
      card.innerHTML = `
        <div>
          <div class="h-44 bg-slate-100 relative overflow-hidden">
            <img src="${p.images || 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500'}" alt="${p.name}" class="w-full h-full object-cover">
            <span class="absolute top-2.5 right-2.5 bg-slate-900/80 backdrop-blur-md text-white px-2.5 py-0.5 rounded-full text-[11px] font-semibold">
              ${p.category}
            </span>
            ${p.distance_km !== null ? `
              <span class="absolute bottom-2.5 left-2.5 bg-indigo-600/90 text-white px-2 py-0.5 rounded-lg text-[10px] font-semibold flex items-center gap-1">
                📍 Cách bạn: ${p.distance_km} km
              </span>
            ` : ''}
          </div>
          <div class="p-4 space-y-2">
            <div class="text-[11px] text-slate-500 font-medium flex items-center gap-1">
              <i data-lucide="store" class="w-3 h-3 text-indigo-500"></i> ${p.shop_name || 'Shop Chính Hãng'}
            </div>
            <h4 class="font-bold text-slate-900 text-sm leading-snug line-clamp-2">${p.name}</h4>
            <p class="text-xs text-slate-500 line-clamp-2">${p.description || ''}</p>
          </div>
        </div>
        <div class="p-4 pt-0 border-t border-slate-100 flex items-center justify-between mt-2">
          <div>
            <div class="text-[10px] text-slate-400 uppercase font-semibold">Giá niêm yết</div>
            <div class="text-base font-extrabold text-indigo-600">${formatCurrency(p.price)}</div>
          </div>
          <button onclick="addToCart(${p.id}, '${escapeHtml(p.name)}', ${p.price}, ${p.shop_id}, '${escapeHtml(p.shop_name || '')}')" 
                  class="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 transition">
            <i data-lucide="shopping-cart" class="w-3.5 h-3.5"></i> Thêm vào giỏ
          </button>
        </div>
      `;
      container.appendChild(card);
    });

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    showToast("Lỗi tải danh sách sản phẩm: " + err.message, "error");
  }
}

function addToCart(productId, name, price, shopId, shopName) {
  const existing = STATE.cart.find(it => it.product_id === productId);
  if (existing) {
    existing.quantity += 1;
  } else {
    STATE.cart.push({
      product_id: productId,
      name: name,
      price: price,
      shop_id: shopId,
      shop_name: shopName,
      quantity: 1
    });
  }
  localStorage.setItem('escrow_cart', JSON.stringify(STATE.cart));
  updateCartBadge();
  showToast(`Đã thêm "${name}" vào giỏ hàng`, 'success');
}

function updateCartBadge() {
  const count = STATE.cart.reduce((sum, it) => sum + it.quantity, 0);
  const badge = document.getElementById('cart-item-count');
  if (badge) badge.innerText = count;
}

function openCartModal() {
  const modal = document.getElementById('cart-modal');
  const container = document.getElementById('cart-items-container');
  container.innerHTML = '';

  if (STATE.cart.length === 0) {
    container.innerHTML = `<div class="text-center py-6 text-slate-400 text-xs">Giỏ hàng của bạn đang trống</div>`;
    document.getElementById('cart-subtotal').innerText = '0 đ';
    document.getElementById('cart-total-amount').innerText = '0 đ';
  } else {
    let subtotal = 0;
    STATE.cart.forEach((it, idx) => {
      subtotal += it.price * it.quantity;
      const row = document.createElement('div');
      row.className = "pt-2 flex items-center justify-between text-xs";
      row.innerHTML = `
        <div class="space-y-0.5">
          <div class="font-bold text-slate-900">${it.name}</div>
          <div class="text-[11px] text-slate-500">${it.shop_name} • ${formatCurrency(it.price)} x ${it.quantity}</div>
        </div>
        <div class="flex items-center gap-3">
          <span class="font-bold text-slate-900">${formatCurrency(it.price * it.quantity)}</span>
          <button onclick="removeFromCart(${idx})" class="text-rose-500 hover:text-rose-700 font-bold px-2 py-1">✕</button>
        </div>
      `;
      container.appendChild(row);
    });

    document.getElementById('cart-subtotal').innerText = formatCurrency(subtotal);
    document.getElementById('cart-total-amount').innerText = formatCurrency(subtotal);
  }

  modal.classList.remove('hidden');
  if (window.lucide) lucide.createIcons();
}

function closeCartModal() {
  document.getElementById('cart-modal').classList.add('hidden');
}

function removeFromCart(idx) {
  STATE.cart.splice(idx, 1);
  localStorage.setItem('escrow_cart', JSON.stringify(STATE.cart));
  updateCartBadge();
  openCartModal(); // Refresh modal
}

// ----------------- MODULE 5 & 6: CHECKOUT & MULTI-VENDOR ESCROW -----------------
async function submitCheckout() {
  if (STATE.cart.length === 0) {
    showToast("Giỏ hàng đang trống", "error");
    return;
  }

  const addr = document.getElementById('checkout-address').value.trim();
  const phone = document.getElementById('checkout-phone').value.trim();
  const payMethod = document.getElementById('checkout-payment-method').value;

  if (!addr || !phone) {
    showToast("Vui lòng điền đủ địa chỉ và số điện thoại", "error");
    return;
  }

  const payload = {
    items: STATE.cart.map(it => ({ product_id: it.product_id, quantity: it.quantity })),
    shipping_address: addr,
    phone: phone,
    buyer_latitude: 21.0360,
    buyer_longitude: 105.7950,
    payment_method: payMethod
  };

  try {
    const res = await fetch('/api/orders/checkout', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${STATE.token}`
      },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Checkout thất bại");
    }

    const data = await res.json();
    closeCartModal();
    STATE.cart = [];
    localStorage.removeItem('escrow_cart');
    updateCartBadge();

    showToast(data.message, "success");
    switchBuyerTab('orders');
  } catch (err) {
    showToast("Lỗi thanh toán: " + err.message, "error");
  }
}

// ----------------- MODULE 4: BUYER ORDERS & SAFE VERIFICATION -----------------
async function loadBuyerOrders() {
  try {
    const res = await fetch('/api/buyer/orders', {
      headers: { 'Authorization': `Bearer ${STATE.token}` }
    });
    const orders = await res.json();
    STATE.cachedOrders = orders;
    
    const countBadge = document.getElementById('buyer-orders-badge');
    if (countBadge) countBadge.innerText = orders.length;

    const container = document.getElementById('buyer-orders-list');
    container.innerHTML = '';

    if (orders.length === 0) {
      container.innerHTML = `<div class="bg-white p-8 rounded-2xl border text-center text-slate-400 text-xs">Bạn chưa có đơn hàng nào</div>`;
      return;
    }

    orders.forEach(ord => {
      const item = document.createElement('div');
      item.className = "bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4";
      
      // Status badge and timeline
      let statusBadge = '';
      if (ord.status === 'PENDING') statusBadge = `<span class="badge-pending px-2.5 py-1 rounded-full text-xs font-bold">Chờ Thanh Toán</span>`;
      else if (ord.status === 'PAID_ESCROW') statusBadge = `<span class="bg-indigo-100 text-indigo-800 border border-indigo-200 px-2.5 py-1 rounded-full text-xs font-bold">🛡️ Ký Quỹ Escrow Đã Tạm Giữ</span>`;
      else if (ord.status === 'PACKED') statusBadge = `<span class="badge-packed px-2.5 py-1 rounded-full text-xs font-bold">📦 Đã Đóng Gói (Đã Dán Tem QR)</span>`;
      else if (ord.status === 'IN_TRANSIT') statusBadge = `<span class="badge-transit px-2.5 py-1 rounded-full text-xs font-bold">🚚 Đang Giao Tới Bạn</span>`;
      else if (ord.status === 'DELIVERED_VERIFIED') statusBadge = `<span class="badge-verified px-2.5 py-1 rounded-full text-xs font-bold">✅ ĐÃ XÁC THỰC CHÍNH HÃNG</span>`;
      else if (ord.status === 'DISPUTED') statusBadge = `<span class="badge-disputed px-2.5 py-1 rounded-full text-xs font-bold">⚠️ Đang Khiếu Nại (Khóa Escrow)</span>`;

      // Visual state step indicator
      const steps = [
        { label: "Đặt Hàng", active: true },
        { label: "Ký Quỹ Tạm Giữ", active: ['PAID_ESCROW', 'PACKED', 'IN_TRANSIT', 'DELIVERED_VERIFIED'].includes(ord.status) },
        { label: "Đóng Tem QR", active: ['PACKED', 'IN_TRANSIT', 'DELIVERED_VERIFIED'].includes(ord.status) },
        { label: "Đang Vận Chuyển", active: ['IN_TRANSIT', 'DELIVERED_VERIFIED'].includes(ord.status) },
        { label: "Quét QR Nhận Hàng", active: ord.status === 'DELIVERED_VERIFIED' }
      ];

      const stepsHtml = steps.map((s, idx) => `
        <div class="flex-1 flex flex-col items-center">
          <div class="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${s.active ? 'bg-emerald-600 text-white' : 'bg-slate-200 text-slate-500'}">
            ${s.active ? '✓' : idx + 1}
          </div>
          <span class="text-[10px] font-medium mt-1 text-center ${s.active ? 'text-slate-900 font-bold' : 'text-slate-400'}">${s.label}</span>
        </div>
      `).join('');

      item.innerHTML = `
        <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b pb-3">
          <div>
            <div class="flex items-center gap-2">
              <span class="font-mono font-bold text-slate-900 text-sm">Đơn Hàng #${ord.id}</span>
              <span class="text-xs text-slate-500">• ${ord.shop_name}</span>
            </div>
            <div class="text-[11px] text-slate-400">Ngày đặt: ${new Date(ord.created_at).toLocaleString('vi-VN')}</div>
          </div>
          <div>${statusBadge}</div>
        </div>

        <!-- 5-Step Visual State Indicator -->
        <div class="flex items-center justify-between py-2 border-b border-slate-100">
          ${stepsHtml}
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div>
            <div class="text-slate-500 font-medium mb-1">Sản phẩm:</div>
            <div class="space-y-1">
              ${ord.items.map(it => `
                <div class="flex justify-between text-slate-800">
                  <span>${it.product_name} x${it.quantity}</span>
                  <span class="font-semibold">${formatCurrency(it.unit_price * it.quantity)}</span>
                </div>
              `).join('')}
            </div>
            <div class="pt-2 mt-2 border-t flex justify-between font-bold text-slate-900">
              <span>Tổng thanh toán (gồm ship):</span>
              <span class="text-indigo-600">${formatCurrency(ord.final_amount)}</span>
            </div>
          </div>

          <div class="bg-slate-50 p-3 rounded-xl border border-slate-200 space-y-1.5">
            <div class="font-bold text-slate-700 flex items-center justify-between">
              <span>Bảo Vệ Người Nhận & Ký Quỹ</span>
              <span class="text-[10px] text-emerald-600 font-semibold">Bảo mật thông tin</span>
            </div>
            <div class="text-slate-600">SĐT nhận: <span class="font-mono text-indigo-600 font-semibold">${ord.masked_phone || '091****005'}</span></div>
            <div class="text-slate-600">Địa chỉ giao: <span class="text-slate-800">${ord.shipping_address}</span></div>
            <div class="text-slate-600">Ký quỹ: <span class="font-semibold text-emerald-600">${ord.payment_method} (Đang tạm giữ)</span></div>
          </div>
        </div>

        <!-- Action Bar for Buyer -->
        <div class="pt-2 flex flex-wrap items-center justify-end gap-2 border-t">
          ${ord.status === 'IN_TRANSIT' ? `
            <button onclick="triggerDirectVerification(${ord.id}, '${ord.package ? ord.package.qr_code_data : ''}')" 
                    class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow">
              <i data-lucide="qr-code" class="w-4 h-4"></i> Xác Thực Nhận Hàng & Giải Ngân Tiền Cho Shop
            </button>
          ` : ''}

          ${ord.status === 'DELIVERED_VERIFIED' ? `
            <button onclick="openReviewModal(${ord.id}, ${ord.items[0]?.product_id || 1})" 
                    class="px-3.5 py-1.5 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-xs font-semibold flex items-center gap-1">
              <i data-lucide="star" class="w-3.5 h-3.5"></i> Đánh Giá Sản Phẩm
            </button>
          ` : ''}

          ${['IN_TRANSIT', 'DELIVERED_VERIFIED'].includes(ord.status) ? `
            <button onclick="openDisputeModal(${ord.id})" 
                    class="px-3.5 py-1.5 bg-rose-50 text-rose-600 hover:bg-rose-100 rounded-xl text-xs font-semibold flex items-center gap-1 border border-rose-200">
              <i data-lucide="alert-circle" class="w-3.5 h-3.5"></i> Khiếu Nại Tráo Hàng / Hỏng Tem
            </button>
          ` : ''}
        </div>
      `;
      container.appendChild(item);
    });

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    showToast("Lỗi tải đơn hàng: " + err.message, "error");
  }
}

// ----------------- MODULE 2: SHOP (SELLER) LOGIC -----------------
function switchShopTab(tab) {
  const oBtn = document.getElementById('tab-shop-orders');
  const pBtn = document.getElementById('tab-shop-products');
  const oSec = document.getElementById('shop-tab-orders');
  const pSec = document.getElementById('shop-tab-products');

  if (tab === 'orders') {
    oBtn.className = "px-4 py-2 font-bold text-sm rounded-xl bg-indigo-600 text-white shadow";
    pBtn.className = "px-4 py-2 font-semibold text-sm rounded-xl text-slate-600 hover:bg-slate-100";
    oSec.classList.remove('hidden');
    pSec.classList.add('hidden');
  } else {
    pBtn.className = "px-4 py-2 font-bold text-sm rounded-xl bg-indigo-600 text-white shadow";
    oBtn.className = "px-4 py-2 font-semibold text-sm rounded-xl text-slate-600 hover:bg-slate-100";
    pSec.classList.remove('hidden');
    oSec.classList.add('hidden');
    loadShopProducts();
  }
}

async function loadShopData() {
  try {
    // 1. Profile & Wallet
    const resProfile = await fetch('/api/shop/profile', {
      headers: { 'Authorization': `Bearer ${STATE.token}` }
    });
    if (resProfile.ok) {
      const p = await resProfile.json();
      document.getElementById('shop-name-display').innerText = p.shop_name;
      document.getElementById('shop-address-display').innerText = p.address;
      document.getElementById('shop-wallet-balance').innerText = formatCurrency(p.wallet_balance);
      document.getElementById('shop-commission-rate').innerText = `${Math.round(p.commission_rate * 100)}%`;
    }

    // 2. Orders
    const resOrders = await fetch('/api/shop/orders', {
      headers: { 'Authorization': `Bearer ${STATE.token}` }
    });
    const orders = await resOrders.json();
    const container = document.getElementById('shop-orders-list');
    container.innerHTML = '';

    if (orders.length === 0) {
      container.innerHTML = `<div class="bg-white p-8 rounded-2xl border text-center text-slate-400 text-xs">Chưa có đơn hàng nào</div>`;
      return;
    }

    orders.forEach(ord => {
      const card = document.createElement('div');
      card.className = "bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-3";
      
      const isPacked = ord.status !== 'PENDING' && ord.status !== 'PAID_ESCROW';

      card.innerHTML = `
        <div class="flex justify-between items-center border-b pb-2.5">
          <div>
            <span class="font-mono font-bold text-slate-900 text-sm">Đơn Hàng #${ord.id}</span>
            <span class="text-xs text-slate-500">• Trạng thái: <b class="text-indigo-600">${ord.status}</b></span>
          </div>
          <div class="text-right">
            <div class="text-xs font-extrabold text-slate-900">${formatCurrency(ord.final_amount)}</div>
            <div class="text-[10px] text-slate-400">Ký Quỹ: ${ord.payment_method}</div>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div>
            <div class="text-slate-500 font-medium">Chi tiết hàng xuất kho:</div>
            <div class="mt-1 space-y-1">
              ${ord.items.map(it => `<div>• Sản phẩm #${it.product_id} (SL: ${it.quantity})</div>`).join('')}
            </div>
            <div class="mt-2 text-slate-600">Địa chỉ giao: <span class="font-medium">${ord.shipping_address}</span></div>
          </div>

          <div class="flex flex-col justify-end items-end gap-2">
            ${!isPacked ? `
              <button onclick="packOrder(${ord.id})" 
                      class="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow">
                <i data-lucide="package" class="w-4 h-4"></i> Đóng Gói & Xuất Tem QR Chống Tráo Hàng
              </button>
            ` : `
              <div class="flex items-center gap-2">
                <span class="text-xs font-bold text-emerald-600 bg-emerald-50 px-3 py-1.5 rounded-lg border border-emerald-200">
                  ✓ Đã niêm phong tem QR
                </span>
                <button onclick="viewWaybill(${ord.id})" class="px-3 py-1.5 bg-slate-900 text-white rounded-xl text-xs font-semibold flex items-center gap-1">
                  <i data-lucide="printer" class="w-3.5 h-3.5"></i> Xem Tem Vận Đơn
                </button>
              </div>
            `}
          </div>
        </div>
      `;
      container.appendChild(card);
    });

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    showToast("Lỗi tải dữ liệu Shop: " + err.message, "error");
  }
}

async function packOrder(orderId) {
  try {
    const res = await fetch(`/api/shop/orders/${orderId}/pack`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${STATE.token}` }
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Đóng gói thất bại");
    }
    const data = await res.json();
    showToast("Đã đóng gói thành công và mã hóa tem QR!", "success");
    loadShopData();
    viewWaybill(orderId);
  } catch (err) {
    showToast("Lỗi đóng gói: " + err.message, "error");
  }
}

async function viewWaybill(orderId) {
  try {
    const res = await fetch(`/api/discovery/waybill/${orderId}`);
    if (!res.ok) throw new Error("Không thể tải thông tin vận đơn");
    const wb = await res.json();

    document.getElementById('wb-code').innerText = wb.waybill_id;
    document.getElementById('wb-shop-name').innerText = wb.sender.shop_name;
    document.getElementById('wb-shop-addr').innerText = wb.sender.address;

    document.getElementById('wb-buyer-name').innerText = wb.recipient.name;
    document.getElementById('wb-buyer-phone').innerText = wb.recipient.masked_phone;
    document.getElementById('wb-buyer-addr').innerText = wb.recipient.masked_address;

    document.getElementById('wb-qr-img').src = wb.anti_tamper_qr.qr_image_base64 || '';
    document.getElementById('wb-hash').innerText = `HMAC-SIG: ${wb.anti_tamper_qr.security_hash || 'N/A'}`;
    document.getElementById('wb-amount').innerText = formatCurrency(wb.final_amount);
    document.getElementById('wb-payment-method').innerText = wb.payment_method;

    document.getElementById('waybill-modal').classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    showToast("Lỗi hiển thị vận đơn: " + err.message, "error");
  }
}

function closeWaybillModal() {
  document.getElementById('waybill-modal').classList.add('hidden');
}

async function loadShopProducts() {
  try {
    const res = await fetch('/api/shop/products', {
      headers: { 'Authorization': `Bearer ${STATE.token}` }
    });
    const prods = await res.json();
    const container = document.getElementById('shop-products-list');
    container.innerHTML = '';

    prods.forEach(p => {
      const card = document.createElement('div');
      card.className = "bg-white p-4 rounded-2xl border border-slate-200 shadow-sm space-y-2 text-xs";
      card.innerHTML = `
        <div class="h-32 bg-slate-100 rounded-xl overflow-hidden">
          <img src="${p.images || 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500'}" class="w-full h-full object-cover">
        </div>
        <div class="font-bold text-slate-900 text-sm truncate">${p.name}</div>
        <div class="flex justify-between text-slate-500">
          <span>Tồn kho: <b class="text-slate-900">${p.stock_quantity}</b></span>
          <span class="font-extrabold text-indigo-600">${formatCurrency(p.price)}</span>
        </div>
      `;
      container.appendChild(card);
    });
  } catch(err){}
}

function openAddProductModal() {
  document.getElementById('add-product-modal').classList.remove('hidden');
}
function closeAddProductModal() {
  document.getElementById('add-product-modal').classList.add('hidden');
}
async function submitCreateProduct() {
  const name = document.getElementById('prod-name').value.trim();
  const price = parseFloat(document.getElementById('prod-price').value);
  const stock = parseInt(document.getElementById('prod-stock').value);
  const cat = document.getElementById('prod-category').value;
  const desc = document.getElementById('prod-desc').value.trim();

  if (!name || isNaN(price) || isNaN(stock)) {
    showToast("Vui lòng điền đủ tên, giá và số lượng kho", "error");
    return;
  }

  try {
    const res = await fetch('/api/shop/products', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${STATE.token}`
      },
      body: JSON.stringify({
        name: name,
        price: price,
        stock_quantity: stock,
        category: cat,
        description: desc
      })
    });
    if (!res.ok) throw new Error("Không thể tạo sản phẩm");
    showToast("Đã thêm sản phẩm thành công", "success");
    closeAddProductModal();
    loadShopProducts();
  } catch (err) {
    showToast("Lỗi: " + err.message, "error");
  }
}

// ----------------- MODULE 3: SHIPPER DISPATCH LOGIC -----------------
async function loadShipperData() {
  try {
    // 1. Available to pickup
    const resAvail = await fetch('/api/shipper/available-packages', {
      headers: { 'Authorization': `Bearer ${STATE.token}` }
    });
    const avail = await resAvail.json();
    document.getElementById('shipper-available-count').innerText = avail.length;
    const availList = document.getElementById('shipper-available-list');
    availList.innerHTML = '';

    if (avail.length === 0) {
      availList.innerHTML = `<div class="bg-white p-6 rounded-2xl border text-center text-slate-400 text-xs">Không có kiện hàng chờ lấy</div>`;
    } else {
      avail.forEach(pkg => {
        const item = document.createElement('div');
        item.className = "bg-white p-4 rounded-2xl border border-slate-200 shadow-sm space-y-2 text-xs";
        item.innerHTML = `
          <div class="flex justify-between items-center">
            <span class="font-bold text-slate-900">Kiện Hàng #${pkg.package_id} (Đơn #${pkg.order_id})</span>
            <span class="badge-packed px-2 py-0.5 rounded-full font-bold text-[10px]">Chờ Lấy Tại Kho</span>
          </div>
          <div class="text-slate-600">Kho Shop: <b class="text-slate-900">${pkg.shop_name}</b> (${pkg.shop_address})</div>
          <div class="text-slate-600">Giao đến: <span class="text-slate-800">${pkg.delivery_address}</span></div>
          <div class="pt-2 flex justify-between items-center border-t">
            <span class="font-semibold text-slate-900">Thu hộ: ${formatCurrency(pkg.final_amount)}</span>
            <button onclick="triggerDirectShipperPickup('${pkg.qr_code_data}')" 
                    class="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold flex items-center gap-1 shadow">
              <i data-lucide="scan" class="w-3.5 h-3.5"></i> Quét Nhận Hàng (Handshake 1)
            </button>
          </div>
        `;
        availList.appendChild(item);
      });
    }

    // 2. Active transit deliveries
    const resTransit = await fetch('/api/shipper/active-deliveries', {
      headers: { 'Authorization': `Bearer ${STATE.token}` }
    });
    const transits = await resTransit.json();
    document.getElementById('shipper-transit-count').innerText = transits.length;
    const transitList = document.getElementById('shipper-transit-list');
    transitList.innerHTML = '';

    if (transits.length === 0) {
      transitList.innerHTML = `<div class="bg-white p-6 rounded-2xl border text-center text-slate-400 text-xs">Hiện không có đơn đang giao</div>`;
    } else {
      transits.forEach(t => {
        const item = document.createElement('div');
        item.className = "bg-white p-4 rounded-2xl border border-slate-200 shadow-sm space-y-2 text-xs";
        const isDelivered = t.package_status === 'DELIVERED';
        item.innerHTML = `
          <div class="flex justify-between items-center">
            <span class="font-bold text-slate-900">Kiện Hàng #${t.package_id} (Đơn #${t.order_id})</span>
            <span class="${isDelivered ? 'badge-verified' : 'badge-transit'} px-2 py-0.5 rounded-full font-bold text-[10px]">
              ${isDelivered ? 'Đã Giao An Toàn' : 'Đang Đi Giao'}
            </span>
          </div>
          <div class="text-slate-600">Khách nhận: <span class="font-mono text-indigo-600 font-semibold">${t.masked_phone}</span></div>
          <div class="text-slate-600">Địa chỉ: <span class="text-slate-800">${t.delivery_address}</span></div>
          ${!isDelivered ? `
            <div class="p-2 bg-amber-50 rounded-lg border border-amber-200 text-amber-800 text-[11px]">
              ℹ️ Khi tới nơi, nhờ Khách Hàng mở app quét mã QR trên hộp để hoàn tất giao hàng & giải ngân tiền!
            </div>
          ` : `
            <div class="text-[11px] text-emerald-600 font-semibold">✓ Khách đã quét QR xác thực tại điểm giao</div>
          `}
        `;
        transitList.appendChild(item);
      });
    }

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    showToast("Lỗi tải dữ liệu Shipper: " + err.message, "error");
  }
}

// ----------------- MODULE 10: ADMIN DASHBOARD LOGIC -----------------
function switchAdminTab(tab) {
  const aBtn = document.getElementById('tab-admin-audit');
  const dBtn = document.getElementById('tab-admin-disputes');
  const fBtn = document.getElementById('tab-admin-fraud');

  const aSec = document.getElementById('admin-tab-audit');
  const dSec = document.getElementById('admin-tab-disputes');
  const fSec = document.getElementById('admin-tab-fraud');

  [aBtn, dBtn, fBtn].forEach(b => b.className = "px-4 py-2 font-semibold text-sm rounded-xl text-slate-600 hover:bg-slate-100");
  [aSec, dSec, fSec].forEach(s => s.classList.add('hidden'));

  if (tab === 'audit') {
    aBtn.className = "px-4 py-2 font-bold text-sm rounded-xl bg-slate-900 text-white shadow";
    aSec.classList.remove('hidden');
    loadAdminAuditLogs();
  } else if (tab === 'disputes') {
    dBtn.className = "px-4 py-2 font-bold text-sm rounded-xl bg-slate-900 text-white shadow";
    dSec.classList.remove('hidden');
    loadAdminDisputes();
  } else if (tab === 'fraud') {
    fBtn.className = "px-4 py-2 font-bold text-sm rounded-xl bg-slate-900 text-white shadow";
    fSec.classList.remove('hidden');
    loadAdminFraudUsers();
  }
}

async function loadAdminData() {
  try {
    // 1. KPI Metrics
    const resMetrics = await fetch('/api/admin/metrics', {
      headers: { 'Authorization': `Bearer ${STATE.token}` }
    });
    if (resMetrics.ok) {
      const m = await resMetrics.json();
      document.getElementById('admin-gmv').innerText = formatCurrency(m.total_gmv);
      document.getElementById('admin-commission').innerText = formatCurrency(m.total_commission);
      document.getElementById('admin-safe-rate').innerText = `${m.safe_delivery_rate}%`;
      document.getElementById('admin-dispute-count').innerText = `${m.dispute_count} vụ (${m.flagged_fraud_count} cảnh báo)`;
    }

    // 2. Default Audit Tab
    loadAdminAuditLogs();
  } catch (err) {
    showToast("Lỗi tải dữ liệu Quản trị: " + err.message, "error");
  }
}

async function loadAdminAuditLogs() {
  try {
    const res = await fetch('/api/admin/audit-logs?limit=40', {
      headers: { 'Authorization': `Bearer ${STATE.token}` }
    });
    const logs = await res.json();
    const table = document.getElementById('admin-audit-table');
    table.innerHTML = '';

    logs.forEach(log => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-slate-50";
      
      let badgeClass = "text-slate-600 bg-slate-100";
      if (log.event_type.includes('TAMPER') || log.event_type.includes('DISPUTE')) badgeClass = "text-rose-700 bg-rose-100";
      else if (log.event_type.includes('DELIVERY') || log.event_type.includes('RELEASED')) badgeClass = "text-emerald-700 bg-emerald-100";
      else if (log.event_type.includes('PICKUP')) badgeClass = "text-purple-700 bg-purple-100";
      else if (log.event_type.includes('TOKEN')) badgeClass = "text-blue-700 bg-blue-100";

      tr.innerHTML = `
        <td class="py-2.5 px-3 text-slate-500">${new Date(log.created_at).toLocaleTimeString('vi-VN')}</td>
        <td class="py-2.5 px-3">
          <span class="px-2 py-0.5 rounded font-bold text-[10px] ${badgeClass}">${log.event_type}</span>
        </td>
        <td class="py-2.5 px-3 font-semibold text-slate-900">#${log.order_id || 'N/A'}</td>
        <td class="py-2.5 px-3 text-slate-600">User #${log.user_id || 'Sys'}</td>
        <td class="py-2.5 px-3 text-[11px] text-slate-500 max-w-xs truncate">${log.details || ''}</td>
      `;
      table.appendChild(tr);
    });
  } catch(err){}
}

async function loadAdminDisputes() {
  try {
    const res = await fetch('/api/disputes', {
      headers: { 'Authorization': `Bearer ${STATE.token}` }
    });
    const disputes = await res.json();
    const container = document.getElementById('admin-disputes-list');
    container.innerHTML = '';

    if (disputes.length === 0) {
      container.innerHTML = `<div class="p-6 text-center text-slate-400 text-xs">Hiện không có khiếu nại nào</div>`;
      return;
    }

    disputes.forEach(d => {
      const card = document.createElement('div');
      card.className = "p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-2 text-xs";
      card.innerHTML = `
        <div class="flex justify-between items-center">
          <span class="font-bold text-slate-900">Khiếu nại Đơn Hàng #${d.order_id} - ${d.reporter_name}</span>
          <span class="badge-disputed px-2 py-0.5 rounded font-bold text-[10px]">${d.status}</span>
        </div>
        <div class="text-rose-700 font-semibold">Lý do: ${d.reason}</div>
        <div class="text-slate-600">Ghi chú bằng chứng: ${d.notes || 'Không có ghi chú thêm'}</div>
        ${d.status === 'OPEN' ? `
          <div class="pt-2 flex gap-2 border-t">
            <button onclick="resolveDisputeAdmin(${d.id}, 'REFUND_BUYER')" class="px-3 py-1.5 bg-rose-600 text-white rounded-lg font-bold">
              Hoàn Tiền Cho Khách
            </button>
            <button onclick="resolveDisputeAdmin(${d.id}, 'RELEASE_TO_SHOP')" class="px-3 py-1.5 bg-emerald-600 text-white rounded-lg font-bold">
              Bác Khiếu Nại & Giải Ngân Cho Shop
            </button>
            <button onclick="resolveDisputeAdmin(${d.id}, 'FLAG_FRAUD')" class="px-3 py-1.5 bg-slate-900 text-white rounded-lg font-bold">
              Đánh Dấu Lừa Đảo (Flag Fraud)
            </button>
          </div>
        ` : `<div class="text-emerald-600 font-semibold">Đã xử lý lúc ${new Date(d.resolved_at).toLocaleString('vi-VN')}</div>`}
      `;
      container.appendChild(card);
    });
  } catch(err){}
}

async function resolveDisputeAdmin(disputeId, action) {
  try {
    const res = await fetch(`/api/disputes/${disputeId}/resolve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${STATE.token}`
      },
      body: JSON.stringify({
        status: action === 'FLAG_FRAUD' ? 'FRAUD_FLAGGED' : 'RESOLVED',
        action: action,
        admin_notes: `Trọng tài sàn xử lý hành động: ${action}`
      })
    });
    if (!res.ok) throw new Error("Lỗi khi xử lý");
    showToast("Đã xử lý tranh chấp và điều phối tiền Escrow thành công", "success");
    loadAdminDisputes();
    loadAdminData();
  } catch(err) {
    showToast(err.message, "error");
  }
}

async function loadAdminFraudUsers() {
  try {
    const res = await fetch('/api/admin/flagged-users', {
      headers: { 'Authorization': `Bearer ${STATE.token}` }
    });
    const users = await res.json();
    const container = document.getElementById('admin-fraud-list');
    container.innerHTML = '';

    if (users.length === 0) {
      container.innerHTML = `<div class="p-6 text-center text-slate-400 text-xs">Không có tài khoản nào bị cảnh báo gian lận</div>`;
      return;
    }

    users.forEach(u => {
      const card = document.createElement('div');
      card.className = "p-4 rounded-xl border border-rose-200 bg-rose-50/50 flex justify-between items-center text-xs";
      card.innerHTML = `
        <div>
          <div class="font-bold text-slate-900">${u.full_name} (${u.role})</div>
          <div class="text-slate-500">${u.email} • SĐT: ${u.phone || 'N/A'}</div>
          <div class="text-rose-600 font-extrabold mt-1">⚠️ Fraud Score: ${u.fraud_score} điểm</div>
        </div>
        <button onclick="resetFraudScoreAdmin(${u.id})" class="px-3 py-1.5 bg-slate-900 text-white rounded-lg font-semibold">
          Reset Điểm
        </button>
      `;
      container.appendChild(card);
    });
  } catch(err){}
}

async function resetFraudScoreAdmin(userId) {
  try {
    await fetch(`/api/admin/users/${userId}/reset-fraud-score`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${STATE.token}` }
    });
    showToast("Đã reset điểm gian lận về 0", "success");
    loadAdminFraudUsers();
  } catch(err){}
}

// ----------------- QR SCANNER & VERIFICATION -----------------
function openBuyerScannerModal() {
  STATE.currentScannerTarget = 'buyer';
  document.getElementById('scanner-title').innerHTML = `
    <i data-lucide="shield-check" class="w-5 h-5 text-emerald-600"></i>
    Khách Hàng Quét Tem QR Nhận Hàng (Handshake 2)
  `;
  document.getElementById('scanner-modal').classList.remove('hidden');
  startWebcamScanner();
}

function openShipperScannerModal() {
  STATE.currentScannerTarget = 'shipper';
  document.getElementById('scanner-title').innerHTML = `
    <i data-lucide="scan" class="w-5 h-5 text-indigo-600"></i>
    Shipper Quét Tem QR Lấy Hàng (Handshake 1)
  `;
  document.getElementById('scanner-modal').classList.remove('hidden');
  startWebcamScanner();
}

function closeScannerModal() {
  stopWebcamScanner();
  document.getElementById('scanner-modal').classList.add('hidden');
}

function startWebcamScanner() {
  const statusEl = document.getElementById('scanner-status');
  statusEl.innerText = "Đang khởi động camera máy quét...";

  try {
    if (STATE.html5QrScanner) {
      STATE.html5QrScanner.clear();
    }

    STATE.html5QrScanner = new Html5Qrcode("qr-reader");
    Html5Qrcode.getCameras().then(devices => {
      if (devices && devices.length) {
        const cameraId = devices[0].id;
        STATE.html5QrScanner.start(
          cameraId,
          { fps: 10, qrbox: { width: 220, height: 220 } },
          (decodedText) => {
            // Success QR Scan
            onQRScanned(decodedText);
          },
          (errorMessage) => {
            // scanning loop, no action needed
          }
        ).then(() => {
          statusEl.innerText = "Hướng camera về phía mã QR trên tem kiện hàng";
        }).catch(err => {
          statusEl.innerText = "Không thể mở camera (" + err + "). Bạn có thể dán mã token test ở ô bên dưới.";
        });
      } else {
        statusEl.innerText = "Không tìm thấy camera. Bạn có thể dán mã token test ở ô bên dưới.";
      }
    }).catch(err => {
      statusEl.innerText = "Camera không khả dụng. Bạn có thể dán mã token test ở ô bên dưới.";
    });
  } catch (err) {
    statusEl.innerText = "Lỗi thư viện quét QR. Vui lòng dán chuỗi token ở ô bên dưới.";
  }
  if (window.lucide) lucide.createIcons();
}

function stopWebcamScanner() {
  if (STATE.html5QrScanner) {
    STATE.html5QrScanner.stop().then(() => {
      STATE.html5QrScanner.clear();
      STATE.html5QrScanner = null;
    }).catch(e => {});
  }
}

async function onQRScanned(qrToken) {
  stopWebcamScanner();
  closeScannerModal();

  if (STATE.currentScannerTarget === 'shipper') {
    await submitShipperPickup(qrToken);
  } else {
    await submitBuyerVerification(qrToken);
  }
}

async function triggerDirectShipperPickup(qrToken) {
  await submitShipperPickup(qrToken);
}

async function triggerDirectVerification(orderId, qrToken) {
  // If token is already present, verify directly
  if (qrToken) {
    await submitBuyerVerification(qrToken);
  } else {
    // Open scanner modal
    openBuyerScannerModal();
  }
}

async function submitShipperPickup(qrToken) {
  try {
    const res = await fetch('/api/shipper/handshake-pickup', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${STATE.token}`
      },
      body: JSON.stringify({ qr_token: qrToken })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Xác thực thất bại");
    }

    const data = await res.json();
    showToast(data.message, "success");
    loadShipperData();
  } catch (err) {
    showToast("Lỗi quét nhận hàng: " + err.message, "error");
  }
}

async function submitBuyerVerification(qrToken) {
  try {
    const res = await fetch('/api/buyer/verify-package', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${STATE.token}`
      },
      body: JSON.stringify({ qr_token: qrToken })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Xác thực gói hàng thất bại");
    }

    const data = await res.json();
    alert(`🎉 XÁC THỰC THÀNH CÔNG!\n\n${data.message}\n\n• Kiện hàng: #${data.package_id}\n• Trạng thái: ${data.order_status}\n• Tiền ký quỹ Escrow: Đã giải ngân cho Shop (+${formatCurrency(data.net_payout)})`);
    loadBuyerOrders();
  } catch (err) {
    alert("❌ CẢNH BÁO AN TOÀN:\n\n" + err.message);
  }
}

function fillSampleQRToken() {
  // Find a package from cached data
  if (STATE.cachedOrders.length > 0 && STATE.cachedOrders[0].package) {
    document.getElementById('manual-qr-input').value = STATE.cachedOrders[0].package.qr_code_data;
    showToast("Đã điền token từ đơn hàng test gần nhất", "success");
  } else {
    showToast("Chưa có đơn hàng mẫu nào trong bộ nhớ đệm", "info");
  }
}

function submitManualQRToken() {
  const token = document.getElementById('manual-qr-input').value.trim();
  if (!token) {
    showToast("Vui lòng dán chuỗi token QR", "error");
    return;
  }
  onQRScanned(token);
}

// ----------------- MODULE 9: REVIEW LOGIC -----------------
function openReviewModal(orderId, productId) {
  STATE.selectedReviewOrderId = orderId;
  STATE.selectedReviewProductId = productId;
  document.getElementById('review-modal').classList.remove('hidden');
}
function closeReviewModal() {
  document.getElementById('review-modal').classList.add('hidden');
}
async function submitReview() {
  const rating = parseInt(document.getElementById('review-rating').value);
  const comment = document.getElementById('review-comment').value.trim();

  try {
    const res = await fetch('/api/reviews', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${STATE.token}`
      },
      body: JSON.stringify({
        order_id: STATE.selectedReviewOrderId,
        product_id: STATE.selectedReviewProductId,
        rating: rating,
        comment: comment
      })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Không thể gửi đánh giá");
    }
    showToast("Đánh giá người mua chính hãng đã được ghi nhận!", "success");
    closeReviewModal();
  } catch(err) {
    showToast(err.message, "error");
  }
}

// ----------------- MODULE 8: DISPUTE LOGIC -----------------
function openDisputeModal(orderId) {
  STATE.selectedDisputeOrderId = orderId;
  document.getElementById('dispute-modal').classList.remove('hidden');
}
function closeDisputeModal() {
  document.getElementById('dispute-modal').classList.add('hidden');
}
async function submitDispute() {
  const reason = document.getElementById('dispute-reason').value;
  const notes = document.getElementById('dispute-notes').value.trim();

  try {
    const res = await fetch('/api/disputes', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${STATE.token}`
      },
      body: JSON.stringify({
        order_id: STATE.selectedDisputeOrderId,
        reason: reason,
        notes: notes
      })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Không thể nộp khiếu nại");
    }
    alert("⚠️ Khiếu nại đã được ghi nhận!\nTiền ký quỹ Escrow của đơn hàng này đã lập tức bị ĐÓNG BĂNG để bảo vệ quyền lợi của bạn.");
    closeDisputeModal();
    loadBuyerOrders();
  } catch(err) {
    showToast(err.message, "error");
  }
}

// ----------------- UTILS -----------------
function formatCurrency(val) {
  if (isNaN(val)) return '0 đ';
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(val);
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

function showToast(msg, type = 'info') {
  const toast = document.getElementById('toast');
  const msgEl = document.getElementById('toast-msg');
  const iconEl = document.getElementById('toast-icon');

  msgEl.innerText = msg;
  if (type === 'success') iconEl.innerText = '✅';
  else if (type === 'error') iconEl.innerText = '❌';
  else iconEl.innerText = 'ℹ️';

  toast.classList.remove('translate-y-20', 'opacity-0');
  setTimeout(() => {
    toast.classList.add('translate-y-20', 'opacity-0');
  }, 3500);
}
