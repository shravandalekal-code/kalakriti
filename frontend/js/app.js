const API_BASE = window.KALAKRITI_API_BASE;

let currentUser = JSON.parse(localStorage.getItem("kalakriti_user") || "null");
let authToken = localStorage.getItem("kalakriti_token") || "";
let cart = JSON.parse(localStorage.getItem("kalakriti_cart") || "[]");
let allProductsCache = [];

document.addEventListener("DOMContentLoaded", () => {
  updateAuthUI();
  updateCartUI();
  loadProducts();
});

function showToast(msg) {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 3200);
}

function showSection(sectionName) {
  document.getElementById("section-marketplace").classList.add("hidden");
  document.getElementById("section-customer-orders").classList.add("hidden");
  document.getElementById("section-artisan-dashboard").classList.add("hidden");
  document.getElementById("hero-banner").classList.toggle("hidden", sectionName !== "marketplace");

  document.querySelectorAll(".nav-btn").forEach(btn => btn.classList.remove("active"));

  if (sectionName === "marketplace") {
    document.getElementById("section-marketplace").classList.remove("hidden");
    document.getElementById("nav-marketplace").classList.add("active");
    loadProducts();
  } else if (sectionName === "customer-orders") {
    document.getElementById("section-customer-orders").classList.remove("hidden");
    document.getElementById("nav-orders").classList.add("active");
    loadCustomerOrders();
  } else if (sectionName === "artisan-dashboard") {
    document.getElementById("section-artisan-dashboard").classList.remove("hidden");
    document.getElementById("nav-artisan").classList.add("active");
    loadArtisanWorkspace();
  }
}

// -------------------- AUTHENTICATION (CUSTOMER & ARTISAN) --------------------
function updateAuthUI() {
  const navAuth = document.getElementById("nav-auth");
  const navArtisanAuth = document.getElementById("nav-artisan-auth");
  const userPill = document.getElementById("user-pill");
  const navArtisan = document.getElementById("nav-artisan");
  const navOrders = document.getElementById("nav-orders");

  if (currentUser && authToken) {
    navAuth.classList.add("hidden");
    navArtisanAuth.classList.add("hidden");
    userPill.classList.remove("hidden");
    document.getElementById("user-greeting").textContent = `${currentUser.name} (${currentUser.role})`;

    if (currentUser.role === "artisan") {
      navArtisan.classList.remove("hidden");
      navOrders.classList.add("hidden");
    } else {
      navOrders.classList.remove("hidden");
      navArtisan.classList.add("hidden");
    }
  } else {
    navAuth.classList.remove("hidden");
    navArtisanAuth.classList.remove("hidden");
    userPill.classList.add("hidden");
    navArtisan.classList.add("hidden");
    navOrders.classList.add("hidden");
  }
}

function openAuthModal() {
  switchAuthTab("register");
  document.getElementById("auth-modal").classList.remove("hidden");
}

function closeAuthModal() {
  document.getElementById("auth-modal").classList.add("hidden");
}

function switchAuthTab(tab) {
  document.getElementById("tab-login").classList.toggle("active", tab === "login");
  document.getElementById("tab-register").classList.toggle("active", tab === "register");
  document.getElementById("public-login-form").classList.toggle("hidden", tab !== "login");
  document.getElementById("public-register-form").classList.toggle("hidden", tab !== "register");
}

function openArtisanAuthModal() {
  switchArtisanAuthTab("register");
  document.getElementById("artisan-auth-modal").classList.remove("hidden");
}

function closeArtisanAuthModal() {
  document.getElementById("artisan-auth-modal").classList.add("hidden");
}

function switchArtisanAuthTab(tab) {
  document.getElementById("artisan-tab-login").classList.toggle("active", tab === "login");
  document.getElementById("artisan-tab-register").classList.toggle("active", tab === "register");
  document.getElementById("artisan-login-form").classList.toggle("hidden", tab !== "login");
  document.getElementById("artisan-register-form").classList.toggle("hidden", tab !== "register");
}

async function signInUser(e, emailInputId, passwordInputId, portal, modalId) {
  e.preventDefault();
  const email = document.getElementById(emailInputId).value;
  const password = document.getElementById(passwordInputId).value;

  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, portal })
  });
  const data = await res.json();
  if (!res.ok) {
    showToast(data.error || "Login failed");
    return;
  }

  currentUser = data.user;
  authToken = data.token;
  localStorage.setItem("kalakriti_user", JSON.stringify(currentUser));
  localStorage.setItem("kalakriti_token", authToken);

  document.getElementById(modalId).classList.add("hidden");
  updateAuthUI();
  showToast(`Welcome back, ${currentUser.name}!`);

  if (currentUser.role === "artisan") {
    showSection("artisan-dashboard");
  }
}

function handlePublicLogin(e) {
  return signInUser(e, "login-email", "login-password", "public", "auth-modal");
}

function handleArtisanLogin(e) {
  return signInUser(e, "artisan-login-email", "artisan-login-password", "artisan", "artisan-auth-modal");
}

async function registerUser(e, payload, modalId) {
  e.preventDefault();
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!res.ok) {
    showToast(data.error || "Registration failed");
    return;
  }

  currentUser = data.user;
  authToken = data.token;
  localStorage.setItem("kalakriti_user", JSON.stringify(currentUser));
  localStorage.setItem("kalakriti_token", authToken);

  document.getElementById(modalId).classList.add("hidden");
  updateAuthUI();
  showToast("Account created successfully!");

  if (currentUser.role === "artisan") {
    showSection("artisan-dashboard");
  }
}

function handlePublicRegister(e) {
  const payload = {
    role: "customer",
    name: document.getElementById("reg-name").value,
    email: document.getElementById("reg-email").value,
    password: document.getElementById("reg-password").value,
    location: document.getElementById("reg-location").value
  };
  return registerUser(e, payload, "auth-modal");
}

function handleArtisanRegister(e) {
  const payload = {
    role: "artisan",
    name: document.getElementById("artisan-reg-name").value,
    email: document.getElementById("artisan-reg-email").value,
    password: document.getElementById("artisan-reg-password").value,
    craft_specialty: document.getElementById("artisan-reg-specialty").value,
    location: document.getElementById("artisan-reg-location").value,
    phone: document.getElementById("artisan-reg-phone").value,
    bio: document.getElementById("artisan-reg-bio").value
  };
  return registerUser(e, payload, "artisan-auth-modal");
}

async function logoutUser() {
  await fetch(`${API_BASE}/auth/logout`, {
    method: "POST",
    headers: { Authorization: `Bearer ${authToken}` }
  }).catch(() => {});
  currentUser = null;
  authToken = "";
  localStorage.removeItem("kalakriti_user");
  localStorage.removeItem("kalakriti_token");
  updateAuthUI();
  showSection("marketplace");
  showToast("Logged out");
}

// -------------------- CUSTOMER FLOW: BROWSE, SEARCH/FILTER, DETAILS, CART, ORDER --------------------
async function loadProducts() {
  const search = document.getElementById("search-input").value;
  const category = document.getElementById("category-filter").value;
  const maxPrice = document.getElementById("max-price-filter").value;

  const params = new URLSearchParams();
  if (search) params.append("search", search);
  if (category && category !== "All") params.append("category", category);
  if (maxPrice) params.append("max_price", maxPrice);

  const res = await fetch(`${API_BASE}/products?${params.toString()}`);
  const products = await res.json();
  allProductsCache = products;

  const grid = document.getElementById("product-grid");
  if (!products.length) {
    grid.innerHTML = `<div class="card"><p>No handcrafts found matching your filter criteria.</p></div>`;
    return;
  }

  grid.innerHTML = products.map(p => `
    <div class="product-card">
      <img src="${p.image_url}" alt="${p.title}" class="product-img" />
      <div class="product-body">
        <span class="product-cat">${p.category}</span>
        <h3 class="product-title">${p.title}</h3>
        <p class="product-artisan">By ${p.artisan_name} • ${p.artisan_location || "India"}</p>
        <div class="product-footer">
          <span class="price-tag">₹${p.price}</span>
          <div class="card-actions">
            <button class="btn-secondary btn-sm" onclick="viewProductDetails(${p.id})">Details</button>
            <button class="btn-primary btn-sm" onclick="addToCart(${p.id})">+ Cart</button>
          </div>
        </div>
      </div>
    </div>
  `).join("");
}

function resetFilters() {
  document.getElementById("search-input").value = "";
  document.getElementById("category-filter").value = "All";
  document.getElementById("max-price-filter").value = "";
  loadProducts();
}

async function viewProductDetails(productId) {
  const res = await fetch(`${API_BASE}/products/${productId}`);
  const p = await res.json();
  if (!res.ok) return;

  document.getElementById("product-detail-body").innerHTML = `
    <div class="artisan-grid">
      <img src="${p.image_url}" alt="${p.title}" style="width:100%; border-radius:8px; max-height:300px; object-fit:cover;" />
      <div>
        <span class="product-cat">${p.category}</span>
        <h2>${p.title}</h2>
        <p class="price-tag" style="margin:8px 0;">₹${p.price}</p>
        <p>${p.description}</p>
        <hr style="margin:12px 0; border:none; border-top:1px solid #e7e5e4;" />
        <p><strong>Artisan:</strong> ${p.artisan_name} (${p.craft_specialty || "Handcraft"})</p>
        <p><strong>Origin:</strong> ${p.artisan_location || "Local Workshop"}</p>
        <p><strong>In Stock:</strong> ${p.stock} units</p>
        <button class="btn-primary full-width mt-10" onclick="addToCart(${p.id}); closeProductModal();">Add to Cart</button>
      </div>
    </div>
  `;
  document.getElementById("product-detail-modal").classList.remove("hidden");
}

function closeProductModal() {
  document.getElementById("product-detail-modal").classList.add("hidden");
}

function toggleCartDrawer() {
  document.getElementById("cart-drawer").classList.toggle("hidden");
  updateCartUI();
}

function addToCart(productId) {
  const prod = allProductsCache.find(p => p.id === productId);
  if (!prod) return;

  const existing = cart.find(item => item.product_id === productId);
  if (existing) {
    if (existing.quantity < prod.stock) {
      existing.quantity += 1;
    } else {
      showToast("Maximum available stock reached");
      return;
    }
  } else {
    cart.push({
      product_id: prod.id,
      title: prod.title,
      price: prod.price,
      quantity: 1
    });
  }
  saveCart();
  showToast(`Added "${prod.title}" to cart`);
}

function removeFromCart(productId) {
  cart = cart.filter(item => item.product_id !== productId);
  saveCart();
}

function saveCart() {
  localStorage.setItem("kalakriti_cart", JSON.stringify(cart));
  updateCartUI();
}

function updateCartUI() {
  const totalQty = cart.reduce((sum, i) => sum + i.quantity, 0);
  const totalAmt = cart.reduce((sum, i) => sum + i.price * i.quantity, 0);

  document.getElementById("cart-count").textContent = totalQty;
  document.getElementById("cart-total-amount").textContent = `₹${totalAmt.toFixed(2)}`;

  const container = document.getElementById("cart-items-container");
  if (!cart.length) {
    container.innerHTML = `<p class="muted">Your shopping cart is empty.</p>`;
    return;
  }

  container.innerHTML = cart.map(item => `
    <div class="cart-item">
      <div>
        <strong>${item.title}</strong><br />
        <small>₹${item.price} × ${item.quantity}</small>
      </div>
      <div>
        <strong>₹${item.price * item.quantity}</strong>
        <button class="btn-danger btn-sm" onclick="removeFromCart(${item.product_id})">×</button>
      </div>
    </div>
  `).join("");
}

async function placeOrder() {
  if (!currentUser || !authToken) {
    toggleCartDrawer();
    openAuthModal();
    showToast("Please log in as a Customer to place your order.");
    return;
  }
  if (currentUser.role !== "customer") {
    showToast("Please log in with a Customer account to place orders.");
    return;
  }
  if (!cart.length) {
    showToast("Your cart is empty.");
    return;
  }

  const shipping_address = document.getElementById("checkout-address").value.trim();
  const payment_method = document.getElementById("checkout-payment").value;
  if (!shipping_address) {
    showToast("Please enter a shipping address.");
    return;
  }

  const res = await fetch(`${API_BASE}/orders`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`
    },
    body: JSON.stringify({
      items: cart.map(c => ({ product_id: c.product_id, quantity: c.quantity })),
      shipping_address,
      payment_method
    })
  });
  const data = await res.json();
  if (!res.ok) {
    showToast(data.error || "Order failed");
    return;
  }

  cart = [];
  saveCart();
  toggleCartDrawer();
  showToast(`Order #${data.order_id} placed successfully!`);
  showSection("customer-orders");
}

async function loadCustomerOrders() {
  const res = await fetch(`${API_BASE}/customer/orders`, {
    headers: { Authorization: `Bearer ${authToken}` }
  });
  const orders = await res.json();
  const container = document.getElementById("customer-orders-list");

  if (!orders.length) {
    container.innerHTML = `<div class="card"><p>You have not placed any orders yet.</p></div>`;
    return;
  }

  container.innerHTML = orders.map(o => `
    <div class="card mt-10">
      <div class="section-header">
        <strong>Order #${o.id} • ${o.created_at}</strong>
        <span class="status-badge">${o.status}</span>
      </div>
      <p><strong>Shipping Address:</strong> ${o.shipping_address} | <strong>Payment:</strong> ${o.payment_method}</p>
      <ul>
        ${o.items.map(i => `<li>${i.title} × ${i.quantity} — ₹${i.unit_price * i.quantity}</li>`).join("")}
      </ul>
      <p class="mt-10"><strong>Total Paid: ₹${o.total_amount}</strong></p>
    </div>
  `).join("");
}

// -------------------- ARTISAN FLOW: PROFILE, ADD/UPDATE PRODUCTS, PRICE & AVAILABILITY --------------------
async function loadArtisanWorkspace() {
  if (!currentUser || currentUser.role !== "artisan") return;

  // 1. Load Profile
  const profRes = await fetch(`${API_BASE}/artisan/profile`, {
    headers: { Authorization: `Bearer ${authToken}` }
  });
  const prof = await profRes.json();
  document.getElementById("art-name").value = prof.name || "";
  document.getElementById("art-specialty").value = prof.craft_specialty || "";
  document.getElementById("art-location").value = prof.location || "";
  document.getElementById("art-phone").value = prof.phone || "";
  document.getElementById("art-bio").value = prof.bio || "";

  // 2. Load Artisan Products
  const prodRes = await fetch(`${API_BASE}/artisan/products`, {
    headers: { Authorization: `Bearer ${authToken}` }
  });
  const products = await prodRes.json();
  document.getElementById("artisan-products-tbody").innerHTML = products.map(p => `
    <tr>
      <td><img src="${p.image_url}" class="thumb-sm" /></td>
      <td>${p.title}</td>
      <td>${p.category}</td>
      <td><input type="number" id="edit-price-${p.id}" value="${p.price}" style="width:90px; margin:0;" /></td>
      <td><input type="number" id="edit-stock-${p.id}" value="${p.stock}" style="width:70px; margin:0;" /></td>
      <td>
        <select id="edit-avail-${p.id}" style="width:120px; margin:0;">
          <option value="1" ${p.is_available ? "selected" : ""}>Available</option>
          <option value="0" ${!p.is_available ? "selected" : ""}>Unavailable</option>
        </select>
      </td>
      <td>
        <button class="btn-primary btn-sm" onclick="updateArtisanProduct(${p.id})">Save</button>
        <button class="btn-danger btn-sm" onclick="deleteArtisanProduct(${p.id})">Delete</button>
      </td>
    </tr>
  `).join("");

  // 3. Load Incoming Orders
  const ordRes = await fetch(`${API_BASE}/artisan/orders`, {
    headers: { Authorization: `Bearer ${authToken}` }
  });
  const orders = await ordRes.json();
  document.getElementById("artisan-orders-tbody").innerHTML = orders.length
    ? orders.map(o => `
        <tr>
          <td>#${o.order_id}</td>
          <td>${o.product_title}</td>
          <td>${o.quantity}</td>
          <td>₹${o.subtotal}</td>
          <td>${o.customer_name}</td>
          <td>${o.shipping_address}</td>
          <td><span class="status-badge">${o.status}</span></td>
        </tr>
      `).join("")
    : `<tr><td colspan="7">No orders received yet.</td></tr>`;
}

async function updateArtisanProfile(e) {
  e.preventDefault();
  const payload = {
    name: document.getElementById("art-name").value,
    craft_specialty: document.getElementById("art-specialty").value,
    location: document.getElementById("art-location").value,
    phone: document.getElementById("art-phone").value,
    bio: document.getElementById("art-bio").value
  };

  const res = await fetch(`${API_BASE}/artisan/profile`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`
    },
    body: JSON.stringify(payload)
  });
  if (res.ok) {
    showToast("Artisan profile updated!");
  }
}

async function addArtisanProduct(e) {
  e.preventDefault();
  const formData = new FormData();
  formData.append("title", document.getElementById("prod-title").value);
  formData.append("category", document.getElementById("prod-category").value);
  formData.append("price", document.getElementById("prod-price").value);
  formData.append("stock", document.getElementById("prod-stock").value);
  formData.append("is_available", document.getElementById("prod-available").value);
  formData.append("description", document.getElementById("prod-desc").value);
  formData.append("image_url", document.getElementById("prod-image-url").value);

  const fileInput = document.getElementById("prod-image-file");
  if (fileInput.files.length > 0) {
    formData.append("image", fileInput.files[0]);
  }

  const res = await fetch(`${API_BASE}/artisan/products`, {
    method: "POST",
    headers: { Authorization: `Bearer ${authToken}` },
    body: formData
  });
  const data = await res.json();
  if (!res.ok) {
    showToast(data.error || "Failed to add product");
    return;
  }

  document.getElementById("add-product-form").reset();
  showToast("Handcraft published to marketplace!");
  loadArtisanWorkspace();
}

async function updateArtisanProduct(productId) {
  const price = document.getElementById(`edit-price-${productId}`).value;
  const stock = document.getElementById(`edit-stock-${productId}`).value;
  const is_available = document.getElementById(`edit-avail-${productId}`).value;

  const res = await fetch(`${API_BASE}/artisan/products/${productId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`
    },
    body: JSON.stringify({ price, stock, is_available })
  });
  if (res.ok) {
    showToast("Price & availability updated!");
    loadArtisanWorkspace();
  }
}

async function deleteArtisanProduct(productId) {
  if (!confirm("Delete this craft listing?")) return;
  const res = await fetch(`${API_BASE}/artisan/products/${productId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${authToken}` }
  });
  if (res.ok) {
    showToast("Product removed");
    loadArtisanWorkspace();
  }
}
