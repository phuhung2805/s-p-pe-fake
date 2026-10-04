// Global Application State
const STATE = {
  activeRole: null,
  token: localStorage.getItem('escrow_token') || null,
  user: null,
  config: null,
  cart: [],
  shipperFilter: 'all',
  shipperTransits: [],
  currentScannerTarget: null, // 'buyer' or 'shipper'
  html5QrScanner: null,
  selectedReviewOrderId: null,
  selectedReviewProductId: null,
  selectedDisputeOrderId: null,
  cachedOrders: []
};

// ----------------- Initialization & Role Switching -----------------
document.addEventListener('DOMContentLoaded', async () => {
  if (window.lucide) lucide.createIcons();
  
  // Try loading saved cart
  const savedCart = localStorage.getItem('escrow_cart');
  if (savedCart) {
    try { STATE.cart = JSON.parse(savedCart); } catch(e){}
  }
  updateCartBadge();
  initSearchAutocomplete();

  // Load runtime configuration (no hardcoded values in the client)
  await loadAppConfig();

  // Resume an existing session, otherwise start in guest mode
  if (STATE.token && await restoreSession()) return;
  startGuest();
});

// ----------------- AUTHENTICATION (Module 1) -----------------
async function loadAppConfig() {
  try {
    const res = await fetch('/api/config');
    if (res.ok) STATE.config = await res.json();
  } catch (e) { /* fall back to built-in defaults */ }
  if (STATE.config && STATE.config.site_name) {
    const brand = document.getElementById('brand-name');
    if (brand) brand.innerText = STATE.config.site_name;
    document.title = `${STATE.config.site_name} - Escrow Anti-Tamper`;
  }
}

function defaultLocation() {
  const loc = (STATE.config && STATE.config.default_location) || {};
  return { lat: loc.lat != null ? loc.lat : 21.0285, lon: loc.lon != null ? loc.lon : 105.8542 };
}

async function restoreSession() {
  try {
    const res = await fetch('/api/auth/me', { headers: { 'Authorization': `Bearer ${STATE.token}` } });
    if (!res.ok) { clearSession(); return false; }
    STATE.user = await res.json();
    enterApp();
    return true;
  } catch (e) {
    clearSession();
    return false;
  }
}

function clearSession() {
  STATE.token = null;
  STATE.user = null;
  localStorage.removeItem('escrow_token');
}

function saveSession(data) {
  STATE.token = data.access_token;
  STATE.user = data;
  localStorage.setItem('escrow_token', data.access_token);
}

function setAuthUI(loggedIn) {
  const guest = document.getElementById('nav-guest-area');
  const userArea = document.getElementById('nav-user-area');
  const roleBadge = document.getElementById('nav-role-badge');
  const roleText = document.getElementById('nav-role-text');
  if (guest) {
    guest.classList.toggle('hidden', loggedIn);
    guest.classList.toggle('flex', !loggedIn);
  }
  if (userArea) {
    userArea.classList.toggle('hidden', !loggedIn);
    userArea.classList.toggle('flex', loggedIn);
  }
  if (roleBadge) roleBadge.classList.toggle('hidden', !loggedIn);
  if (roleText) roleText.innerText = loggedIn && STATE.user ? STATE.user.role : 'Khách';
}

function openAuthModal(tab) {
  showAuthTab(tab || 'login');
  const el = document.getElementById('auth-screen');
  el.classList.remove('hidden');
  el.classList.add('flex');
  if (window.lucide) lucide.createIcons();
}

function closeAuthModal() {
  const el = document.getElementById('auth-screen');
  el.classList.add('hidden');
  el.classList.remove('flex');
}

function showAppShell() {
  const header = document.getElementById('app-header');
  const main = document.getElementById('app-main');
  if (header) header.classList.remove('hidden');
  if (main) main.classList.remove('hidden');
}

// Public helpers used by header buttons
function openAuthTab(tab) { openAuthModal(tab); }
function showAuthScreen(tab) { openAuthModal(tab || 'login'); }
function hideAuthScreen() { closeAuthModal(); }

function showAuthTab(tab) {
  const isLogin = tab === 'login';
  document.getElementById('login-form').classList.toggle('hidden', !isLogin);
  document.getElementById('register-form').classList.toggle('hidden', isLogin);
  const onCls = 'py-2 text-xs font-bold rounded-lg bg-brand-600 text-white transition';
  const offCls = 'py-2 text-xs font-bold rounded-lg text-slate-400 hover:text-white transition';
  document.getElementById('auth-tab-login').className = isLogin ? onCls : offCls;
  document.getElementById('auth-tab-register').className = isLogin ? offCls : onCls;
  clearAuthError('login');
  clearAuthError('register');
  if (window.lucide) lucide.createIcons();
}

function togglePassword(inputId, btn) {
  const input = document.getElementById(inputId);
  const show = input.type === 'password';
  input.type = show ? 'text' : 'password';
  btn.innerHTML = `<i data-lucide="${show ? 'eye-off' : 'eye'}" class="w-4 h-4"></i>`;
  if (window.lucide) lucide.createIcons();
}

function showAuthError(which, message) {
  const el = document.getElementById(which + '-error');
  if (!el) return;
  el.innerText = message;
  el.classList.remove('hidden');
}

function clearAuthError(which) {
  const el = document.getElementById(which + '-error');
  if (el) { el.innerText = ''; el.classList.add('hidden'); }
}

function setAuthLoading(which, loading, idleText) {
  const btn = document.getElementById(which + '-submit');
  const txt = document.getElementById(which + '-submit-text');
  if (!btn) return;
  btn.disabled = loading;
  if (txt) txt.innerText = loading ? 'Đang xử lý...' : idleText;
}

async function parseAuthResponse(res) {
  try { return await res.json(); } catch (e) { return {}; }
}

async function doLogin(e) {
  e.preventDefault();
  clearAuthError('login');
  setAuthLoading('login', true, 'Đăng nhập');
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: document.getElementById('login-email').value.trim(),
        password: document.getElementById('login-password').value
      })
    });
    const data = await parseAuthResponse(res);
    if (!res.ok) throw new Error(data.detail || 'Đăng nhập thất bại');
    saveSession(data);
    enterApp();
    showToast(`Chào mừng ${data.full_name}!`, 'success');
  } catch (err) {
    showAuthError('login', err.message);
  } finally {
    setAuthLoading('login', false, 'Đăng nhập');
  }
}

async function doRegister(e) {
  e.preventDefault();
  clearAuthError('register');
  const password = document.getElementById('reg-password').value;
  if (password !== document.getElementById('reg-confirm').value) {
    showAuthError('register', 'Mật khẩu xác nhận không khớp.');
    return;
  }
  setAuthLoading('register', true, 'Đăng ký tài khoản');
  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        full_name: document.getElementById('reg-name').value.trim(),
        email: document.getElementById('reg-email').value.trim(),
        phone: document.getElementById('reg-phone').value.trim() || null,
        role: document.getElementById('reg-role').value,
        password
      })
    });
    const data = await parseAuthResponse(res);
    if (!res.ok) throw new Error(data.detail || 'Đăng ký thất bại');
    saveSession(data);
    enterApp();
    showToast('Đăng ký tài khoản thành công!', 'success');
  } catch (err) {
    showAuthError('register', err.message);
  } finally {
    setAuthLoading('register', false, 'Đăng ký tài khoản');
  }
}

function doLogout() {
  clearSession();
  STATE.activeRole = null;
  showToast('Đã đăng xuất khỏi hệ thống', 'info');
  startGuest();
}

function requireAuth() {
  if (STATE.token && STATE.user) return true;
  openAuthModal('login');
  showToast('Vui lòng đăng nhập để tiếp tục', 'info');
  return false;
}

function enterApp() {
  closeAuthModal();
  showAppShell();
  const user = STATE.user || {};
  const role = user.role || 'Buyer';
  STATE.activeRole = role;
  setAuthUI(true);
  document.getElementById('nav-user-name').innerText = user.full_name || '';
  document.getElementById('nav-user-role').innerText = `${user.role || ''} • ${user.email || ''}`;
  applyRoleUI(role);
  loadCategories();
  loadRoleData(role);
  if (window.lucide) lucide.createIcons();
}

function startGuest() {
  hideAuthScreen();
  showAppShell();
  setAuthUI(false);
  applyRoleUI('Buyer');
  loadCategories();
  loadBuyerProducts();
  if (window.lucide) lucide.createIcons();
}

function applyRoleUI(role) {
  ['Buyer', 'Shop', 'Shipper', 'Admin'].forEach(r => {
    const view = document.getElementById(`view-${r}`);
    if (view) view.classList.toggle('hidden', r !== role);
  });
  setTimeout(() => { if (window.lucide) lucide.createIcons(); }, 50);
}

function loadRoleData(role) {
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
}

// ----------------- SEARCH AUTOCOMPLETE (Module 7) -----------------
let _searchDebounce = null;

function initSearchAutocomplete() {
  const input = document.getElementById('buyer-search-input');
  const box = document.getElementById('search-suggestions');
  if (!input || !box) return;

  input.addEventListener('input', () => {
    clearTimeout(_searchDebounce);
    const q = input.value.trim();
    if (q.length < 2) { box.classList.add('hidden'); return; }
    _searchDebounce = setTimeout(() => fetchSuggestions(q), 300);
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { box.classList.add('hidden'); loadBuyerProducts(); }
    else if (e.key === 'Escape') { box.classList.add('hidden'); }
  });
  document.addEventListener('click', (e) => {
    if (e.target !== input && !box.contains(e.target)) box.classList.add('hidden');
  });
}

async function fetchSuggestions(q) {
  const box = document.getElementById('search-suggestions');
  if (!box) return;
  try {
    const res = await fetch(`/api/discovery/products?q=${encodeURIComponent(q)}`);
    const products = await res.json();
    const names = [...new Set(products.map(p => p.name))].slice(0, 6);
    if (!names.length) { box.classList.add('hidden'); return; }
    box.innerHTML = names.map((n, i) =>
      `<button type="button" data-i="${i}" class="w-full text-left px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 border-b border-slate-100 last:border-0 flex items-center gap-2">
        <i data-lucide="search" class="w-3.5 h-3.5 text-slate-400"></i>${escapeHtml(n)}</button>`
    ).join('');
    box.querySelectorAll('button').forEach((b) => {
      b.onclick = () => {
        document.getElementById('buyer-search-input').value = names[b.dataset.i];
        box.classList.add('hidden');
        loadBuyerProducts();
      };
    });
    box.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
  } catch (e) { /* ignore */ }
}

// ----------------- MODULE 7: BUYER DISCOVERY & CART -----------------
function switchBuyerTab(tab) {
  const mBtn = document.getElementById('tab-buyer-market');
  const oBtn = document.getElementById('tab-buyer-orders');
  const mSec = document.getElementById('buyer-tab-market');
  const oSec = document.getElementById('buyer-tab-orders');

  if (tab === 'market') {
    mBtn.className = "px-4 py-2 text-sm font-semibold rounded-xl bg-brand-50 text-brand-700 border border-brand-200";
    oBtn.className = "px-4 py-2 text-sm font-semibold rounded-xl text-slate-600 hover:bg-slate-100 relative";
    mSec.classList.remove('hidden');
    oSec.classList.add('hidden');
  } else {
    oBtn.className = "px-4 py-2 text-sm font-semibold rounded-xl bg-brand-50 text-brand-700 border border-brand-200 relative";
    mBtn.className = "px-4 py-2 text-sm font-semibold rounded-xl text-slate-600 hover:bg-slate-100";
    oSec.classList.remove('hidden');
    mSec.classList.add('hidden');
    loadBuyerOrders();
  }
}

async function loadBuyerProducts() {
  const q = document.getElementById('buyer-search-input').value.trim();
  const cat = document.getElementById('buyer-category-select').value;
  const minPrice = document.getElementById('buyer-min-price').value;
  const maxPrice = document.getElementById('buyer-max-price').value;
  const sortBy = document.getElementById('buyer-sort').value;
  const loc = defaultLocation();
  const params = new URLSearchParams({ buyer_lat: loc.lat, buyer_lon: loc.lon, sort_by: sortBy });
  if (q) params.set('q', q);
  if (cat && cat !== 'ALL') params.set('category', cat);
  if (minPrice) params.set('min_price', minPrice);
  if (maxPrice) params.set('max_price', maxPrice);

  const container = document.getElementById('buyer-products-grid');
  container.innerHTML = Array.from({ length: 3 }).map(() => `<div class="bg-white rounded-2xl border border-slate-200 overflow-hidden"><div class="h-44 skeleton"></div><div class="p-4 space-y-2"><div class="h-4 w-2/3 skeleton rounded"></div><div class="h-3 w-full skeleton rounded"></div><div class="h-3 w-1/2 skeleton rounded"></div></div></div>`).join('');

  try {
    const res = await fetch(`/api/discovery/products?${params.toString()}`);
    const products = await res.json();
    container.innerHTML = '';

    if (products.length === 0) {
      container.innerHTML = `<div class="col-span-3 text-center py-14 text-slate-400"><i data-lucide="search-x" class="w-10 h-10 mx-auto mb-2 text-slate-300"></i><p class="text-sm">Không tìm thấy sản phẩm nào phù hợp.</p></div>`;
      if (window.lucide) lucide.createIcons();
      return;
    }

    products.forEach(p => {
      const out = p.stock_quantity <= 0;
      const low = p.stock_quantity > 0 && p.stock_quantity <= 5;
      const stockBadge = out
        ? `<span class="text-[10px] font-bold text-rose-600 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded-full">Hết hàng</span>`
        : (low
          ? `<span class="text-[10px] font-bold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">Sắp hết — còn ${p.stock_quantity}</span>`
          : `<span class="text-[10px] font-semibold text-emerald-600">Còn ${p.stock_quantity}</span>`);
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
              <span class="absolute bottom-2.5 left-2.5 bg-brand-600/90 text-white px-2 py-0.5 rounded-lg text-[10px] font-semibold flex items-center gap-1">
                <i data-lucide="map-pin" class="w-3 h-3"></i> Cách bạn: ${p.distance_km} km
              </span>
            ` : ''}
          </div>
          <div class="p-4 space-y-2">
            <div class="text-[11px] text-slate-500 font-medium flex items-center gap-1">
              <i data-lucide="store" class="w-3 h-3 text-brand-500"></i> ${p.shop_name || 'Shop Chính Hãng'}
            </div>
            <h4 class="font-bold text-slate-900 text-sm leading-snug line-clamp-2">${p.name}</h4>
            <p class="text-xs text-slate-500 line-clamp-2">${p.description || ''}</p>
          </div>
        </div>
        <div class="p-4 pt-0 border-t border-slate-100 flex items-center justify-between mt-2">
          <div>
            <div class="text-[10px] text-slate-400 uppercase font-semibold">Giá niêm yết</div>
            <div class="text-base font-extrabold text-brand-600">${formatCurrency(p.price)}</div>
            <div class="mt-1">${stockBadge}</div>
          </div>
          <button ${out ? 'disabled' : ''} onclick="addToCart(${p.id}, '${escapeHtml(p.name)}', ${p.price}, ${p.shop_id}, '${escapeHtml(p.shop_name || '')}')" 
                  class="px-3.5 py-2 ${out ? 'bg-slate-300 cursor-not-allowed' : 'bg-slate-900 hover:bg-slate-800'} text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 transition">
            <i data-lucide="shopping-cart" class="w-3.5 h-3.5"></i> ${out ? 'Hết hàng' : 'Thêm vào giỏ'}
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
  if (!requireAuth()) return;
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
      quantity: 1,
      selected: true
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
  if (!requireAuth()) return;
  const modal = document.getElementById('cart-modal');
  const container = document.getElementById('cart-items-container');
  container.innerHTML = '';

  if (STATE.cart.length === 0) {
    container.innerHTML = `<div class="text-center py-8 text-slate-400 text-xs"><i data-lucide="shopping-cart" class="w-8 h-8 mx-auto mb-2 text-slate-300"></i>Giỏ hàng của bạn đang trống</div>`;
    document.getElementById('cart-subtotal').innerText = '0 đ';
    document.getElementById('cart-shipping-fee').innerText = '0 đ';
    document.getElementById('cart-total-amount').innerText = '0 đ';
    modal.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
    return;
  }

  let subtotal = 0;
  const byShop = {};
  STATE.cart.forEach((it, idx) => {
    if (it.selected === undefined) it.selected = true;
    const row = document.createElement('div');
    row.className = "py-2.5 flex items-center gap-3 text-xs";
    row.innerHTML = `
      <input type="checkbox" ${it.selected ? 'checked' : ''} onchange="toggleCartItem(${idx})" class="w-4 h-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500">
      <div class="flex-1 space-y-0.5 ${it.selected ? '' : 'opacity-50'}">
        <div class="font-bold text-slate-900">${it.name}</div>
        <div class="text-[11px] text-slate-500">${it.shop_name} • ${formatCurrency(it.price)} × ${it.quantity}</div>
      </div>
      <div class="font-bold text-slate-900">${formatCurrency(it.price * it.quantity)}</div>
      <button onclick="removeFromCart(${idx})" class="text-rose-500 hover:text-rose-700 p-1"><i data-lucide="x" class="w-3.5 h-3.5"></i></button>
    `;
    container.appendChild(row);
    if (it.selected) {
      subtotal += it.price * it.quantity;
      byShop[it.shop_name] = (byShop[it.shop_name] || 0) + it.price * it.quantity;
    }
  });

  const shopNames = Object.keys(byShop);
  const shipPerShop = 15000;
  const shipping = shopNames.length * shipPerShop;
  const breakdown = document.createElement('div');
  breakdown.className = 'mt-3 p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1.5 text-[11px]';
  breakdown.innerHTML = `<div class="font-bold text-slate-700 mb-1 flex items-center gap-1"><i data-lucide="split" class="w-3.5 h-3.5"></i> Tách tiền theo từng Shop</div>` +
    (shopNames.length ? shopNames.map(name =>
      `<div class="flex justify-between text-slate-600"><span>${name}</span><span class="font-semibold text-slate-900">${formatCurrency(byShop[name])} <span class="text-slate-400 font-normal">+ ship ~${formatCurrency(shipPerShop)}</span></span></div>`
    ).join('') : '<div class="text-slate-400">Chưa chọn sản phẩm nào</div>');
  container.appendChild(breakdown);

  document.getElementById('cart-subtotal').innerText = formatCurrency(subtotal);
  document.getElementById('cart-shipping-fee').innerText = `~${formatCurrency(shipping)}`;
  document.getElementById('cart-total-amount').innerText = formatCurrency(subtotal + shipping);

  modal.classList.remove('hidden');
  if (window.lucide) lucide.createIcons();
}

function toggleCartItem(idx) {
  if (STATE.cart[idx]) STATE.cart[idx].selected = !STATE.cart[idx].selected;
  localStorage.setItem('escrow_cart', JSON.stringify(STATE.cart));
  openCartModal();
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
  if (!requireAuth()) return;
  const selected = STATE.cart.filter(it => it.selected !== false);
  if (selected.length === 0) {
    showToast("Vui lòng chọn ít nhất 1 sản phẩm để thanh toán", "error");
    return;
  }

  const addr = document.getElementById('checkout-address').value.trim();
  const phone = document.getElementById('checkout-phone').value.trim();
  const payMethod = document.getElementById('checkout-payment-method').value;

  if (!addr || !phone) {
    showToast("Vui lòng điền đủ địa chỉ và số điện thoại", "error");
    return;
  }

  const loc = defaultLocation();
  const payload = {
    items: selected.map(it => ({ product_id: it.product_id, quantity: it.quantity })),
    shipping_address: addr,
    phone: phone,
    buyer_latitude: loc.lat,
    buyer_longitude: loc.lon,
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
    STATE.cart = STATE.cart.filter(it => it.selected === false);
    if (STATE.cart.length === 0) localStorage.removeItem('escrow_cart');
    else localStorage.setItem('escrow_cart', JSON.stringify(STATE.cart));
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
      else if (ord.status === 'PAID_ESCROW') statusBadge = `<span class="bg-brand-100 text-brand-800 border border-brand-200 px-2.5 py-1 rounded-full text-xs font-bold">Ký Quỹ Escrow Đã Tạm Giữ</span>`;
      else if (ord.status === 'PACKED') statusBadge = `<span class="badge-packed px-2.5 py-1 rounded-full text-xs font-bold">Đã Đóng Gói (Đã Dán Tem QR)</span>`;
      else if (ord.status === 'IN_TRANSIT') statusBadge = `<span class="badge-transit px-2.5 py-1 rounded-full text-xs font-bold">Đang Giao Tới Bạn</span>`;
      else if (ord.status === 'DELIVERED_VERIFIED') statusBadge = `<span class="badge-verified px-2.5 py-1 rounded-full text-xs font-bold">ĐÃ XÁC THỰC CHÍNH HÃNG</span>`;
      else if (ord.status === 'DISPUTED') statusBadge = `<span class="badge-disputed px-2.5 py-1 rounded-full text-xs font-bold">Đang Khiếu Nại (Khóa Escrow)</span>`;
      else if (ord.status === 'DELIVERY_FAILED') statusBadge = `<span class="badge-disputed px-2.5 py-1 rounded-full text-xs font-bold">Giao Không Thành Công</span>`;

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
            ${s.active ? '<i data-lucide="check" class="w-3 h-3"></i>' : idx + 1}
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
              <span class="text-brand-600">${formatCurrency(ord.final_amount)}</span>
            </div>
          </div>

          <div class="bg-slate-50 p-3 rounded-xl border border-slate-200 space-y-1.5">
            <div class="font-bold text-slate-700 flex items-center justify-between">
              <span>Bảo Vệ Người Nhận & Ký Quỹ</span>
              <span class="text-[10px] text-emerald-600 font-semibold">Bảo mật thông tin</span>
            </div>
            <div class="text-slate-600">SĐT nhận: <span class="font-mono text-brand-600 font-semibold">${ord.masked_phone || '091****005'}</span></div>
            <div class="text-slate-600">Địa chỉ giao: <span class="text-slate-800">${ord.shipping_address}</span></div>
            <div class="text-slate-600">Ký quỹ: <span class="font-semibold text-emerald-600">${ord.payment_method} (Đang tạm giữ)</span></div>
          </div>
        </div>

        <!-- Order Status Timeline (history) -->
        <details class="group">
          <summary class="cursor-pointer text-xs font-semibold text-slate-600 hover:text-brand-600 flex items-center gap-1 select-none">
            <i data-lucide="history" class="w-3.5 h-3.5"></i> Lịch sử trạng thái đơn hàng
          </summary>
          <div class="order-timeline mt-3" data-order-id="${ord.id}"></div>
        </details>

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
    loadOrderTimelines(orders);
  } catch (err) {
    showToast("Lỗi tải đơn hàng: " + err.message, "error");
  }
}

async function loadOrderTimelines(orders) {
  for (const ord of orders) {
    const el = document.querySelector(`.order-timeline[data-order-id="${ord.id}"]`);
    if (!el) continue;
    try {
      const res = await fetch(`/api/orders/${ord.id}/timeline`, { headers: { 'Authorization': `Bearer ${STATE.token}` } });
      if (!res.ok) continue;
      const events = await res.json();
      el.innerHTML = events.map((e, i) => {
        const last = i === events.length - 1;
        const danger = ['TAMPER_DETECTED', 'DISPUTE_FILED', 'DELIVERY_FAILED'].includes(e.type);
        const color = danger ? 'bg-rose-500' : (last ? 'bg-brand-600' : 'bg-emerald-500');
        return `<div class="relative pl-7 ${last ? '' : 'pb-4 tl-line'}">
          <span class="absolute left-1 top-1 w-3 h-3 rounded-full ${color} ring-4 ring-white"></span>
          <div class="text-xs font-semibold text-slate-900">${e.label}</div>
          <div class="text-[10px] text-slate-400">${e.at ? new Date(e.at).toLocaleString('vi-VN') : ''}</div>
        </div>`;
      }).join('');
    } catch (e) { /* ignore */ }
  }
}

// ----------------- MODULE 2: SHOP (SELLER) LOGIC -----------------
function switchShopTab(tab) {
  const oBtn = document.getElementById('tab-shop-orders');
  const pBtn = document.getElementById('tab-shop-products');
  const oSec = document.getElementById('shop-tab-orders');
  const pSec = document.getElementById('shop-tab-products');

  if (tab === 'orders') {
    oBtn.className = "px-4 py-2 font-bold text-sm rounded-xl bg-brand-600 text-white shadow";
    pBtn.className = "px-4 py-2 font-semibold text-sm rounded-xl text-slate-600 hover:bg-slate-100";
    oSec.classList.remove('hidden');
    pSec.classList.add('hidden');
  } else {
    pBtn.className = "px-4 py-2 font-bold text-sm rounded-xl bg-brand-600 text-white shadow";
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
            <span class="text-xs text-slate-500">• Trạng thái: <b class="text-brand-600">${ord.status}</b></span>
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
                      class="px-4 py-2.5 bg-brand-600 hover:bg-brand-700 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow">
                <i data-lucide="package" class="w-4 h-4"></i> Đóng Gói & Xuất Tem QR Chống Tráo Hàng
              </button>
            ` : `
              <div class="flex items-center gap-2">
                <span class="text-xs font-bold text-emerald-600 bg-emerald-50 px-3 py-1.5 rounded-lg border border-emerald-200">
                  <i data-lucide="check" class="w-3.5 h-3.5 inline"></i> Đã niêm phong tem QR
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
          <span class="font-extrabold text-brand-600">${formatCurrency(p.price)}</span>
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
                    class="px-3.5 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-bold flex items-center gap-1 shadow">
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
    STATE.shipperTransits = await resTransit.json();
    applyShipperFilter();
    renderShipperTransits();

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    showToast("Lỗi tải dữ liệu Shipper: " + err.message, "error");
  }
}

function switchShipperFilter(tab) {
  STATE.shipperFilter = tab;
  applyShipperFilter();
  renderShipperTransits();
  if (window.lucide) lucide.createIcons();
}

function applyShipperFilter() {
  const tab = STATE.shipperFilter || 'all';
  const ids = { all: 'shipper-filter-all', picking: 'shipper-filter-picking', delivering: 'shipper-filter-delivering', delivered: 'shipper-filter-delivered' };
  Object.entries(ids).forEach(([key, id]) => {
    const btn = document.getElementById(id);
    if (!btn) return;
    btn.className = key === tab
      ? "px-3.5 py-2 text-xs font-bold rounded-xl bg-slate-900 text-white shadow"
      : "px-3.5 py-2 text-xs font-semibold rounded-xl text-slate-600 hover:bg-slate-100";
  });
  const colAvail = document.getElementById('shipper-col-available');
  const colTransit = document.getElementById('shipper-col-transit');
  if (colAvail) colAvail.classList.toggle('hidden', !(tab === 'all' || tab === 'picking'));
  if (colTransit) colTransit.classList.toggle('hidden', tab === 'picking');
}

function renderShipperTransits() {
  const all = STATE.shipperTransits || [];
  const tab = STATE.shipperFilter || 'all';
  let list = all;
  if (tab === 'delivering') list = all.filter(t => t.package_status === 'PICKED_UP');
  else if (tab === 'delivered') list = all.filter(t => t.package_status === 'DELIVERED');

  const transitList = document.getElementById('shipper-transit-list');
  if (!transitList) return;
  const countEl = document.getElementById('shipper-transit-count');
  if (countEl) countEl.innerText = list.length;
  transitList.innerHTML = '';

  if (list.length === 0) {
    transitList.innerHTML = `<div class="bg-white p-6 rounded-2xl border text-center text-slate-400 text-xs">Không có đơn phù hợp bộ lọc</div>`;
    return;
  }

  list.forEach(t => {
    const item = document.createElement('div');
    item.className = "bg-white p-4 rounded-2xl border border-slate-200 shadow-sm space-y-2 text-xs";
    const isDelivered = t.package_status === 'DELIVERED';
    const isFailed = t.order_status === 'DELIVERY_FAILED';
    const badge = isDelivered ? 'badge-verified' : (isFailed ? 'badge-disputed' : 'badge-transit');
    const badgeText = isDelivered ? 'Đã Giao An Toàn' : (isFailed ? 'Giao Không Thành Công' : 'Đang Đi Giao');
    item.innerHTML = `
      <div class="flex justify-between items-center">
        <span class="font-bold text-slate-900">Kiện Hàng #${t.package_id} (Đơn #${t.order_id})</span>
        <span class="${badge} px-2 py-0.5 rounded-full font-bold text-[10px]">${badgeText}</span>
      </div>
      <div class="text-slate-600">Khách nhận: <span class="font-mono text-brand-600 font-semibold">${t.masked_phone || '***'}</span></div>
      <div class="text-slate-600">Địa chỉ: <span class="text-slate-800">${t.delivery_address}</span></div>
      ${isDelivered ? `<div class="text-[11px] text-emerald-600 font-semibold"><i data-lucide="check" class="w-3 h-3 inline"></i> Khách đã quét QR xác thực</div>` : ''}
      ${(!isDelivered && !isFailed) ? `<div class="p-2 bg-amber-50 rounded-lg border border-amber-200 text-amber-800 text-[11px]">Nhờ Khách quét mã QR trên hộp để hoàn tất giao hàng.</div>` : ''}
      <div class="pt-2 border-t flex flex-wrap gap-2">
        ${(!isDelivered && !isFailed) ? `
          <button onclick="reportDeliveryFailed(${t.order_id})" class="px-3 py-1.5 bg-rose-50 text-rose-600 border border-rose-200 rounded-lg font-semibold flex items-center gap-1">
            <i data-lucide="x-circle" class="w-3.5 h-3.5"></i> Báo giao không thành công
          </button>` : ''}
        ${isFailed ? `
          <button onclick="resumeDelivery(${t.order_id})" class="px-3 py-1.5 bg-brand-600 text-white rounded-lg font-semibold flex items-center gap-1">
            <i data-lucide="rotate-ccw" class="w-3.5 h-3.5"></i> Tiếp tục giao
          </button>` : ''}
      </div>
    `;
    transitList.appendChild(item);
  });
}

async function reportDeliveryFailed(orderId) {
  const reason = prompt('Lý do giao không thành công?', 'Khách không nghe máy / dời lịch hẹn');
  if (reason === null) return;
  try {
    const res = await fetch(`/api/shipper/orders/${orderId}/report-failed`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${STATE.token}` },
      body: JSON.stringify({ reason: reason || 'Không rõ' }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Lỗi');
    showToast('Đã ghi nhận giao không thành công', 'success');
    loadShipperData();
  } catch (e) { showToast(e.message, 'error'); }
}

async function resumeDelivery(orderId) {
  try {
    const res = await fetch(`/api/shipper/orders/${orderId}/resume-delivery`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${STATE.token}` },
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Lỗi');
    showToast('Đã tiếp tục giao hàng', 'success');
    loadShipperData();
  } catch (e) { showToast(e.message, 'error'); }
}

// ----------------- MODULE 10: ADMIN DASHBOARD LOGIC -----------------
const ADMIN_TABS = {
  audit: ['tab-admin-audit', 'admin-tab-audit', () => loadAdminAuditLogs()],
  users: ['tab-admin-users', 'admin-tab-users', () => loadAdminUsers()],
  categories: ['tab-admin-categories', 'admin-tab-categories', () => loadAdminCategories()],
  disputes: ['tab-admin-disputes', 'admin-tab-disputes', () => loadAdminDisputes()],
  fraud: ['tab-admin-fraud', 'admin-tab-fraud', () => loadAdminFraudUsers()],
};

function switchAdminTab(tab) {
  Object.values(ADMIN_TABS).forEach(([btnId, secId]) => {
    const btn = document.getElementById(btnId);
    const sec = document.getElementById(secId);
    if (btn) btn.className = "px-3.5 py-2 font-semibold text-sm rounded-xl text-slate-600 hover:bg-slate-100";
    if (sec) sec.classList.add('hidden');
  });
  const active = ADMIN_TABS[tab];
  if (!active) return;
  const [btnId, secId, loader] = active;
  const btn = document.getElementById(btnId);
  const sec = document.getElementById(secId);
  if (btn) btn.className = "px-3.5 py-2 font-bold text-sm rounded-xl bg-slate-900 text-white shadow";
  if (sec) sec.classList.remove('hidden');
  loader();
  if (window.lucide) lucide.createIcons();
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
          <div class="text-rose-600 font-extrabold mt-1">Fraud Score: ${u.fraud_score} điểm</div>
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
  if (!requireAuth()) return;
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
    <i data-lucide="scan" class="w-5 h-5 text-brand-600"></i>
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

function playBeep() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (Ctx) {
      const ctx = new Ctx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = 880;
      osc.connect(gain); gain.connect(ctx.destination);
      gain.gain.setValueAtTime(0.18, ctx.currentTime);
      osc.start();
      osc.stop(ctx.currentTime + 0.15);
    }
    if (navigator.vibrate) navigator.vibrate(120);
  } catch (e) { /* ignore */ }
}

async function onQRScanned(qrToken) {
  playBeep();
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
    showToast(`Xác thực thành công — đã giải ngân ${formatCurrency(data.net_payout)} cho Shop`, 'success');
    loadBuyerOrders();
  } catch (err) {
    showToast('Cảnh báo an toàn: ' + err.message, 'error');
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
  if (!requireAuth()) return;
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
  if (!requireAuth()) return;
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
    showToast('Khiếu nại đã được ghi nhận — tiền ký quỹ đã được đóng băng.', 'success');
    closeDisputeModal();
    loadBuyerOrders();
  } catch(err) {
    showToast(err.message, "error");
  }
}

// ----------------- CATALOG & ADMIN MANAGEMENT -----------------
async function loadCategories() {
  try {
    const res = await fetch('/api/categories');
    if (!res.ok) return;
    const cats = await res.json();
    const buyerSel = document.getElementById('buyer-category-select');
    if (buyerSel) {
      const current = buyerSel.value;
      buyerSel.innerHTML = '<option value="ALL">Tất cả danh mục</option>' +
        cats.map(c => `<option value="${c.name}">${c.name}</option>`).join('');
      buyerSel.value = current || 'ALL';
    }
    const prodSel = document.getElementById('prod-category');
    if (prodSel) {
      prodSel.innerHTML = cats.map(c => `<option value="${c.name}">${c.name}</option>`).join('');
    }
  } catch (e) { /* silent */ }
}

async function loadAdminUsers() {
  try {
    const res = await fetch('/api/admin/users', { headers: { 'Authorization': `Bearer ${STATE.token}` } });
    const users = await res.json();
    const countEl = document.getElementById('admin-users-count');
    if (countEl) countEl.innerText = users.length;
    const tbody = document.getElementById('admin-users-table');
    tbody.innerHTML = '';
    const roleBadge = {
      Admin: 'bg-rose-100 text-rose-700', Shop: 'bg-brand-100 text-brand-700',
      Shipper: 'bg-amber-100 text-amber-700', Buyer: 'bg-emerald-100 text-emerald-700'
    };
    users.forEach(u => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-slate-50';
      tr.innerHTML = `
        <td class="py-2.5 px-3 font-mono text-slate-500">#${u.id}</td>
        <td class="py-2.5 px-3 font-semibold text-slate-900">${u.full_name}</td>
        <td class="py-2.5 px-3 text-slate-600">${u.email}</td>
        <td class="py-2.5 px-3"><span class="px-2 py-0.5 rounded font-bold text-[10px] ${roleBadge[u.role] || 'bg-slate-100 text-slate-600'}">${u.role}</span></td>
        <td class="py-2.5 px-3 font-bold ${u.fraud_score > 0 ? 'text-rose-600' : 'text-slate-400'}">${u.fraud_score}</td>
        <td class="py-2.5 px-3 text-slate-500">${u.created_at ? new Date(u.created_at).toLocaleDateString('vi-VN') : ''}</td>
      `;
      tbody.appendChild(tr);
    });
    if (window.lucide) lucide.createIcons();
  } catch (e) { showToast('Lỗi tải người dùng: ' + e.message, 'error'); }
}

async function loadAdminCategories() {
  try {
    const res = await fetch('/api/categories/all', { headers: { 'Authorization': `Bearer ${STATE.token}` } });
    const cats = await res.json();
    const container = document.getElementById('admin-categories-list');
    container.innerHTML = '';
    if (!cats.length) {
      container.innerHTML = `<div class="col-span-3 text-center py-8 text-slate-400 text-xs">Chưa có danh mục nào</div>`;
      return;
    }
    cats.forEach(c => {
      const card = document.createElement('div');
      card.className = 'bg-slate-50 rounded-xl border border-slate-200 p-4 space-y-2 text-xs';
      card.innerHTML = `
        <div class="flex justify-between items-start">
          <div>
            <div class="font-bold text-slate-900">${c.name}</div>
            <div class="font-mono text-[10px] text-slate-400">/${c.slug}</div>
          </div>
          <span class="px-2 py-0.5 rounded-full font-bold text-[10px] ${c.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-500'}">${c.is_active ? 'Hoạt động' : 'Đang ẩn'}</span>
        </div>
        <p class="text-slate-500 line-clamp-2 min-h-[1rem]">${c.description || ''}</p>
        <div class="text-slate-500 flex items-center gap-1"><i data-lucide="package" class="w-3 h-3"></i> ${c.product_count} sản phẩm</div>
        <div class="pt-2 border-t flex gap-2">
          <button onclick="openCategoryModal(${c.id}, '${escapeHtml(c.name)}', '${escapeHtml(c.description || '')}', ${c.is_active})" class="px-2.5 py-1.5 rounded-lg bg-slate-900 text-white font-semibold flex items-center gap-1"><i data-lucide="pencil" class="w-3 h-3"></i> Sửa</button>
          <button onclick="toggleCategoryActive(${c.id}, ${!c.is_active})" class="px-2.5 py-1.5 rounded-lg bg-white border font-semibold text-slate-700">${c.is_active ? 'Ẩn' : 'Hiện'}</button>
          <button onclick="deleteCategory(${c.id})" class="px-2.5 py-1.5 rounded-lg bg-rose-50 text-rose-600 font-semibold ml-auto">Xoá</button>
        </div>
      `;
      container.appendChild(card);
    });
    if (window.lucide) lucide.createIcons();
  } catch (e) { showToast('Lỗi tải danh mục: ' + e.message, 'error'); }
}

function openCategoryModal(id, name, description, active) {
  document.getElementById('category-id').value = id || '';
  document.getElementById('category-name').value = name || '';
  document.getElementById('category-desc').value = description || '';
  document.getElementById('category-active').checked = active === undefined ? true : !!active;
  document.getElementById('category-modal-title').innerText = id ? 'Sửa danh mục' : 'Thêm danh mục';
  document.getElementById('category-modal').classList.remove('hidden');
  if (window.lucide) lucide.createIcons();
}

function closeCategoryModal() {
  document.getElementById('category-modal').classList.add('hidden');
}

async function submitCategory() {
  const id = document.getElementById('category-id').value;
  const payload = {
    name: document.getElementById('category-name').value.trim(),
    description: document.getElementById('category-desc').value.trim() || null,
    is_active: document.getElementById('category-active').checked,
  };
  if (!payload.name) { showToast('Vui lòng nhập tên danh mục', 'error'); return; }
  try {
    const res = await fetch(id ? `/api/categories/${id}` : '/api/categories', {
      method: id ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${STATE.token}` },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Lưu thất bại');
    closeCategoryModal();
    showToast(id ? 'Đã cập nhật danh mục' : 'Đã thêm danh mục', 'success');
    loadAdminCategories();
    loadCategories();
  } catch (e) { showToast(e.message, 'error'); }
}

async function toggleCategoryActive(id, active) {
  try {
    const res = await fetch(`/api/categories/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${STATE.token}` },
      body: JSON.stringify({ is_active: active }),
    });
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || 'Lỗi'); }
    showToast('Đã cập nhật trạng thái danh mục', 'success');
    loadAdminCategories();
    loadCategories();
  } catch (e) { showToast(e.message, 'error'); }
}

async function deleteCategory(id) {
  if (!confirm('Bạn chắc chắn muốn xoá/ẩn danh mục này?')) return;
  try {
    const res = await fetch(`/api/categories/${id}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${STATE.token}` },
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Lỗi');
    showToast(data.message || 'Đã xử lý danh mục', 'success');
    loadAdminCategories();
    loadCategories();
  } catch (e) { showToast(e.message, 'error'); }
}

function onPaymentMethodChange(value) {
  if (value === 'COD') {
    const modal = document.getElementById('cod-warning-modal');
    if (modal) {
      modal.classList.remove('hidden');
      if (window.lucide) lucide.createIcons();
    }
  }
}

function closeCodWarning() {
  const modal = document.getElementById('cod-warning-modal');
  if (modal) modal.classList.add('hidden');
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
  const icons = { success: 'check-circle-2', error: 'x-circle', info: 'info' };
  const colors = { success: 'text-emerald-400', error: 'text-rose-400', info: 'text-slate-300' };
  iconEl.setAttribute('data-lucide', icons[type] || 'info');
  iconEl.setAttribute('class', `w-4 h-4 ${colors[type] || colors.info}`);
  if (window.lucide) lucide.createIcons();

  toast.classList.remove('translate-y-20', 'opacity-0');
  setTimeout(() => {
    toast.classList.add('translate-y-20', 'opacity-0');
  }, 3500);
}
