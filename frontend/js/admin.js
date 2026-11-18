const API_BASE = window.KALAKRITI_API_BASE;
let adminToken = localStorage.getItem("kalakriti_admin_token") || "";
let adminArtisans = [];

document.addEventListener("DOMContentLoaded", () => {
  if (adminToken) {
    showAdminDashboard();
  }
});

function showToast(msg) {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 3200);
}

function escapeHtml(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[char]);
}

async function handleAdminLogin(e) {
  e.preventDefault();
  const email = document.getElementById("admin-email").value;
  const password = document.getElementById("admin-password").value;

  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, portal: "admin" })
  });
  const data = await res.json();

  if (!res.ok) {
    showToast(data.error || "Invalid Admin Credentials");
    return;
  }

  adminToken = data.token;
  localStorage.setItem("kalakriti_admin_token", adminToken);
  showToast("Admin authenticated successfully");
  showAdminDashboard();
}

function showAdminDashboard() {
  document.getElementById("admin-login-section").classList.add("hidden");
  document.getElementById("admin-dashboard-section").classList.remove("hidden");
  document.getElementById("admin-logout-btn").classList.remove("hidden");
  loadAllAdminData();
}

function adminLogout() {
  fetch(`${API_BASE}/auth/logout`, {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken}` }
  }).catch(() => {});
  adminToken = "";
  localStorage.removeItem("kalakriti_admin_token");
  document.getElementById("admin-login-section").classList.remove("hidden");
  document.getElementById("admin-dashboard-section").classList.add("hidden");
  document.getElementById("admin-logout-btn").classList.add("hidden");
  showToast("Admin logged out");
}

function switchAdminTab(tabName, btn) {
  document.querySelectorAll(".admin-panel").forEach(p => p.classList.add("hidden"));
  document.querySelectorAll(".admin-tabs .tab-btn").forEach(b => b.classList.remove("active"));
  document.getElementById(`admin-tab-${tabName}`).classList.remove("hidden");
  btn.classList.add("active");
}

async function loadAllAdminData() {
  await Promise.all([loadReports(), loadUsers(), loadOrders()]);
  await loadProducts();
}

// 1. Generate Reports
async function loadReports() {
  const res = await fetch(`${API_BASE}/admin/reports`, {
    headers: { Authorization: `Bearer ${adminToken}` }
  });
  if (res.status === 401) {
    adminLogout();
    return;
  }
  const data = await res.json();
  const s = data.summary;

  document.getElementById("admin-kpi-grid").innerHTML = `
    <div class="kpi-card"><h4>Total Revenue</h4><div class="kpi-val">₹${s.total_revenue}</div></div>
    <div class="kpi-card"><h4>Total Orders</h4><div class="kpi-val">${s.total_orders}</div></div>
    <div class="kpi-card"><h4>Registered Artisans</h4><div class="kpi-val">${s.total_artisans}</div></div>
    <div class="kpi-card"><h4>Registered Customers</h4><div class="kpi-val">${s.total_customers}</div></div>
    <div class="kpi-card"><h4>Listed Handcrafts</h4><div class="kpi-val">${s.total_products}</div></div>
  `;

  document.getElementById("report-category-tbody").innerHTML = data.category_breakdown.map(c => `
    <tr>
      <td>${c.category}</td>
      <td>${c.product_count}</td>
      <td>${c.total_stock || 0}</td>
    </tr>
  `).join("");

  document.getElementById("report-artisan-tbody").innerHTML = data.artisan_performance.map(a => `
    <tr>
      <td>${a.artisan_name}</td>
      <td>${a.location || "-"}</td>
      <td>${a.units_sold}</td>
      <td><strong>₹${a.total_sales}</strong></td>
    </tr>
  `).join("");
}

async function downloadSalesCSV() {
  const res = await fetch(`${API_BASE}/admin/reports/export`, {
    headers: { Authorization: `Bearer ${adminToken}` }
  });
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "kalakriti_sales_report.csv";
  a.click();
  showToast("CSV report downloaded");
}

// 2. Manage Users (Artisans & Customers)
async function loadUsers() {
  const res = await fetch(`${API_BASE}/admin/users`, {
    headers: { Authorization: `Bearer ${adminToken}` }
  });
  const users = await res.json();
  adminArtisans = users.filter(u => u.role === "artisan");
  document.getElementById("admin-new-artisan").innerHTML = `
    <option value="">Select an artisan</option>
    ${adminArtisans.filter(a => a.is_active).map(a => `
      <option value="${a.id}">${escapeHtml(a.name)}</option>
    `).join("")}
  `;

  document.getElementById("admin-users-tbody").innerHTML = users.map(u => `
    <tr>
      <td>#${u.id}</td>
      <td>${u.name}</td>
      <td>${u.email}</td>
      <td><strong>${u.role.toUpperCase()}</strong></td>
      <td>${u.location || "-"} ${u.craft_specialty ? `(${u.craft_specialty})` : ""}</td>
      <td>
        <span class="status-badge ${u.is_active ? "status-active" : "status-inactive"}">
          ${u.is_active ? "Active" : "Suspended"}
        </span>
      </td>
      <td>
        ${u.role !== "admin"
          ? `<button class="btn-secondary btn-sm" onclick="toggleUserStatus(${u.id})">
               ${u.is_active ? "Suspend" : "Activate"}
             </button>`
          : "—"}
      </td>
    </tr>
  `).join("");
}

async function toggleUserStatus(userId) {
  const res = await fetch(`${API_BASE}/admin/users/${userId}/toggle`, {
    method: "PUT",
    headers: { Authorization: `Bearer ${adminToken}` }
  });
  if (res.ok) {
    showToast("User status updated");
    loadUsers();
  }
}

// 3. Manage Products
async function loadProducts() {
  const res = await fetch(`${API_BASE}/admin/products`, {
    headers: { Authorization: `Bearer ${adminToken}` }
  });
  if (res.status === 401) {
    adminLogout();
    return;
  }
  const products = await res.json();

  document.getElementById("admin-products-tbody").innerHTML = products.map(p => `
    <tr>
      <td>#${p.id}</td>
      <td>
        <img src="${escapeHtml(p.image_url)}" class="thumb-sm" alt="${escapeHtml(p.title)}" />
        <input type="url" id="admin-image-url-${p.id}" value="${escapeHtml(p.image_url)}" placeholder="Photo URL" aria-label="Photo URL for ${escapeHtml(p.title)}" />
        <input type="file" id="admin-image-file-${p.id}" accept="image/*" aria-label="Upload photo for ${escapeHtml(p.title)}" />
      </td>
      <td><input type="text" id="admin-title-${p.id}" value="${escapeHtml(p.title)}" required aria-label="Craft title for product ${p.id}" /></td>
      <td>
        <select id="admin-artisan-${p.id}" aria-label="Artisan for product ${p.id}">
          ${adminArtisans.map(a => `
            <option value="${a.id}" ${a.id === p.artisan_id ? "selected" : ""}>
              ${escapeHtml(a.name)}${a.is_active ? "" : " (Suspended)"}
            </option>
          `).join("")}
        </select>
      </td>
      <td><input type="text" id="admin-category-${p.id}" value="${escapeHtml(p.category)}" required aria-label="Category for product ${p.id}" /></td>
      <td><input type="number" id="admin-price-${p.id}" value="${escapeHtml(p.price)}" min="0.01" step="0.01" required aria-label="Price for product ${p.id}" /></td>
      <td><input type="number" id="admin-stock-${p.id}" value="${escapeHtml(p.stock)}" min="0" step="1" required aria-label="Stock for product ${p.id}" /></td>
      <td>
        <select id="admin-availability-${p.id}" aria-label="Availability for product ${p.id}">
          <option value="1" ${p.is_available ? "selected" : ""}>Available</option>
          <option value="0" ${!p.is_available ? "selected" : ""}>Unavailable</option>
        </select>
      </td>
      <td>
        <button class="btn-primary btn-sm" onclick="adminUpdateProduct(${p.id})">Save Changes</button>
        <button class="btn-danger btn-sm" onclick="adminDeleteProduct(${p.id})">Delete</button>
      </td>
    </tr>
  `).join("");
}

async function adminAddProduct(e) {
  e.preventDefault();
  const formData = new FormData();
  formData.append("artisan_id", document.getElementById("admin-new-artisan").value);
  formData.append("title", document.getElementById("admin-new-title").value);
  formData.append("category", document.getElementById("admin-new-category").value);
  formData.append("price", document.getElementById("admin-new-price").value);
  formData.append("stock", document.getElementById("admin-new-stock").value);
  formData.append("is_available", document.getElementById("admin-new-availability").value);
  formData.append("image_url", document.getElementById("admin-new-image-url").value);
  formData.append("description", document.getElementById("admin-new-description").value);
  const imageFile = document.getElementById("admin-new-image-file").files[0];
  if (imageFile) formData.append("image", imageFile);

  const res = await fetch(`${API_BASE}/admin/products`, {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken}` },
    body: formData
  });
  const data = await res.json();
  if (!res.ok) {
    showToast(data.error || "Failed to add product");
    return;
  }

  document.getElementById("admin-add-product-form").reset();
  showToast(`Product #${data.id} added`);
  await Promise.all([loadProducts(), loadReports()]);
}

async function adminUpdateProduct(id) {
  const artisanId = document.getElementById(`admin-artisan-${id}`).value;
  const price = document.getElementById(`admin-price-${id}`).value;
  const imageUrl = document.getElementById(`admin-image-url-${id}`).value;
  const imageFile = document.getElementById(`admin-image-file-${id}`).files[0];
  const title = document.getElementById(`admin-title-${id}`).value;
  const category = document.getElementById(`admin-category-${id}`).value;
  const stock = document.getElementById(`admin-stock-${id}`).value;
  const isAvailable = document.getElementById(`admin-availability-${id}`).value;
  const formData = new FormData();
  formData.append("artisan_id", artisanId);
  formData.append("title", title);
  formData.append("category", category);
  formData.append("price", price);
  formData.append("stock", stock);
  formData.append("image_url", imageUrl);
  formData.append("is_available", isAvailable);
  if (imageFile) formData.append("image", imageFile);

  const res = await fetch(`${API_BASE}/artisan/products/${id}`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${adminToken}`
    },
    body: formData
  });
  const data = await res.json();
  if (!res.ok) {
    showToast(data.error || "Failed to update product");
    return;
  }

  showToast("Product updated");
  await Promise.all([loadProducts(), loadReports()]);
}

async function adminDeleteProduct(id) {
  if (!confirm("Permanently delete this product?")) return;
  const res = await fetch(`${API_BASE}/artisan/products/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${adminToken}` }
  });
  if (res.ok) {
    showToast("Product deleted");
    loadProducts();
    loadReports();
  }
}

// 4. View & Update Orders
async function loadOrders() {
  const res = await fetch(`${API_BASE}/admin/orders`, {
    headers: { Authorization: `Bearer ${adminToken}` }
  });
  const orders = await res.json();

  document.getElementById("admin-orders-tbody").innerHTML = orders.map(o => `
    <tr>
      <td>#${o.id}</td>
      <td>${o.customer_name}<br /><small>${o.customer_email}</small></td>
      <td>${o.items.map(i => `${i.product_title} (×${i.quantity})`).join("<br />")}</td>
      <td><strong>₹${o.total_amount}</strong></td>
      <td>${o.shipping_address}</td>
      <td><span class="status-badge">${o.status}</span></td>
      <td>
        <select onchange="updateOrderStatus(${o.id}, this.value)" style="margin:0; width:130px;">
          ${["Pending", "Confirmed", "Shipped", "Delivered", "Cancelled"].map(st =>
            `<option value="${st}" ${o.status === st ? "selected" : ""}>${st}</option>`
          ).join("")}
        </select>
      </td>
    </tr>
  `).join("");
}

async function updateOrderStatus(orderId, status) {
  const res = await fetch(`${API_BASE}/admin/orders/${orderId}/status`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${adminToken}`
    },
    body: JSON.stringify({ status })
  });
  if (res.ok) {
    showToast(`Order #${orderId} updated to ${status}`);
    loadOrders();
    loadReports();
  }
}
