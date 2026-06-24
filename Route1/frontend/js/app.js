/**
 * app.js — Route 1 front-end logic
 *
 * Responsibilities:
 *  - Tab navigation
 *  - Login / Register forms → FastAPI auth endpoints
 *  - Crop request form → FastAPI crop endpoints
 *  - Farmer browse view with filters
 */

"use strict";

// ── Configuration ────────────────────────────────────────────────────────────
const API_BASE = "http://localhost:8000"; // Change to your deployed API URL

// ── State ────────────────────────────────────────────────────────────────────
let authState = {
  token: localStorage.getItem("r1_token") || null,
  userType: localStorage.getItem("r1_userType") || null,
  userId: localStorage.getItem("r1_userId") || null,
  email: localStorage.getItem("r1_email") || null,
};

// ── DOM refs ─────────────────────────────────────────────────────────────────
const tabBtns = document.querySelectorAll(".tab-btn");
const tabPanels = document.querySelectorAll(".tab-panel");
const dashboardTab = document.getElementById("dashboardTab");
const userBadge = document.getElementById("userBadge");
const logoutBtn = document.getElementById("logoutBtn");

// Auth
const showLoginBtn = document.getElementById("showLoginBtn");
const showRegisterBtn = document.getElementById("showRegisterBtn");
const loginFormEl = document.getElementById("loginFormEl");
const registerFormEl = document.getElementById("registerFormEl");
const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");
const loginError = document.getElementById("loginError");
const registerError = document.getElementById("registerError");
const registerSuccess = document.getElementById("registerSuccess");
const orgNameGroup = document.getElementById("orgNameGroup");
const userTypeRadios = document.querySelectorAll("input[name='userType']");

// Dashboard
const orgView = document.getElementById("orgView");
const farmerView = document.getElementById("farmerView");
const cropRequestForm = document.getElementById("cropRequestForm");
const cropError = document.getElementById("cropError");
const cropSuccess = document.getElementById("cropSuccess");
const myRequestsList = document.getElementById("myRequestsList");
const refreshMyRequestsBtn = document.getElementById("refreshMyRequestsBtn");
const applyFiltersBtn = document.getElementById("applyFiltersBtn");
const farmerRequestsList = document.getElementById("farmerRequestsList");

// ════════════════════════════════════════════════════════════════════════════
// Helpers
// ════════════════════════════════════════════════════════════════════════════

function showMsg(el, msg, isError = true) {
  el.textContent = msg;
  el.classList.remove("hidden");
  if (isError) {
    el.classList.add("error-msg");
    el.classList.remove("success-msg");
  } else {
    el.classList.add("success-msg");
    el.classList.remove("error-msg");
  }
}

function hideMsg(el) { el.classList.add("hidden"); }

async function apiFetch(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...options.headers };
  if (authState.token) headers["Authorization"] = `Bearer ${authState.token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const msg = data.detail || `Error ${res.status}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

function formatDate(isoString) {
  return new Date(isoString).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric",
  });
}

function statusBadge(status) {
  const labels = { pending: "Pending", matched: "Matched", fulfilled: "Fulfilled" };
  return `<span class="status-badge status-${status}">${labels[status] ?? status}</span>`;
}

// ════════════════════════════════════════════════════════════════════════════
// Tab navigation
// ════════════════════════════════════════════════════════════════════════════

function switchTab(target) {
  tabBtns.forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === target);
    btn.setAttribute("aria-selected", btn.dataset.tab === target);
  });
  tabPanels.forEach(panel => {
    panel.classList.toggle("active", panel.id === `tab-${target}`);
  });

  if (target === "dashboard") {
    renderDashboard();
  }
}

tabBtns.forEach(btn => {
  btn.addEventListener("click", () => {
    if (!btn.disabled) switchTab(btn.dataset.tab);
  });
});

// ════════════════════════════════════════════════════════════════════════════
// Auth toggle (login ↔ register)
// ════════════════════════════════════════════════════════════════════════════

showLoginBtn.addEventListener("click", () => {
  loginForm.classList.remove("hidden");
  registerForm.classList.add("hidden");
  showLoginBtn.classList.add("active");
  showRegisterBtn.classList.remove("active");
});

showRegisterBtn.addEventListener("click", () => {
  registerForm.classList.remove("hidden");
  loginForm.classList.add("hidden");
  showRegisterBtn.classList.add("active");
  showLoginBtn.classList.remove("active");
});

// Show/hide org name based on user type
userTypeRadios.forEach(radio => {
  radio.addEventListener("change", () => {
    orgNameGroup.classList.toggle("hidden", radio.value !== "organization");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// Session management
// ════════════════════════════════════════════════════════════════════════════

function saveSession(data) {
  authState = {
    token: data.access_token,
    userType: data.user_type,
    userId: String(data.user_id),
    email: data.email,
  };
  localStorage.setItem("r1_token", authState.token);
  localStorage.setItem("r1_userType", authState.userType);
  localStorage.setItem("r1_userId", authState.userId);
  localStorage.setItem("r1_email", authState.email);
}

function clearSession() {
  authState = { token: null, userType: null, userId: null, email: null };
  ["r1_token", "r1_userType", "r1_userId", "r1_email"]
    .forEach(k => localStorage.removeItem(k));
}

function applySession() {
  if (!authState.token) {
    userBadge.classList.add("hidden");
    logoutBtn.classList.add("hidden");
    return;
  }

  const label = authState.userType === "organization"
    ? "🏠 Organization"
    : authState.userType === "farmer"
      ? "👨‍🌾 Farmer"
      : "💰 Donor";

  userBadge.textContent = `${label} · ${authState.email}`;
  userBadge.classList.remove("hidden");
  logoutBtn.classList.remove("hidden");
  dashboardTab.disabled = false;
}

logoutBtn.addEventListener("click", () => {
  clearSession();
  applySession();
  switchTab("auth");
  orgView.classList.add("hidden");
  farmerView.classList.add("hidden");
});

// ════════════════════════════════════════════════════════════════════════════
// Login
// ════════════════════════════════════════════════════════════════════════════

loginFormEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideMsg(loginError);

  const email = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value;

  // FastAPI OAuth2 form expects application/x-www-form-urlencoded
  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username: email, password }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail ?? "Login failed.");

    saveSession(data);
    applySession();
    switchTab("dashboard");
  } catch (err) {
    showMsg(loginError, err.message);
  }
});

// ════════════════════════════════════════════════════════════════════════════
// Register
// ════════════════════════════════════════════════════════════════════════════

registerFormEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideMsg(registerError);
  hideMsg(registerSuccess);

  const userType = document.querySelector("input[name='userType']:checked").value;

  const payload = {
    email: document.getElementById("regEmail").value.trim(),
    password: document.getElementById("regPassword").value,
    user_type: userType,
    full_name: document.getElementById("regFullName").value.trim() || null,
    organization_name: userType === "organization"
      ? document.getElementById("regOrgName").value.trim() || null
      : null,
    address: document.getElementById("regAddress").value.trim() || null,
    city: document.getElementById("regCity").value.trim() || null,
    state: document.getElementById("regState").value.trim().toUpperCase() || null,
    zip_code: document.getElementById("regZip").value.trim() || null,
    phone: document.getElementById("regPhone").value.trim() || null,
  };

  try {
    await apiFetch("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showMsg(registerSuccess, "Account created! You can now log in.", false);
    registerFormEl.reset();
  } catch (err) {
    showMsg(registerError, err.message);
  }
});

// ════════════════════════════════════════════════════════════════════════════
// Dashboard render
// ════════════════════════════════════════════════════════════════════════════

const dashViewToggle = document.getElementById("dashViewToggle");
const showOrgViewBtn = document.getElementById("showOrgViewBtn");
const showFarmerViewBtn = document.getElementById("showFarmerViewBtn");

showOrgViewBtn.addEventListener("click", () => {
  orgView.classList.remove("hidden");
  farmerView.classList.add("hidden");
  showOrgViewBtn.classList.add("active");
  showFarmerViewBtn.classList.remove("active");
});

showFarmerViewBtn.addEventListener("click", () => {
  farmerView.classList.remove("hidden");
  orgView.classList.add("hidden");
  showFarmerViewBtn.classList.add("active");
  showOrgViewBtn.classList.remove("active");
});

function renderDashboard() {
  if (!authState.token) {
    dashViewToggle.classList.remove("hidden");
    // Default to org view on first open
    orgView.classList.remove("hidden");
    farmerView.classList.add("hidden");
    showOrgViewBtn.classList.add("active");
    showFarmerViewBtn.classList.remove("active");
    return;
  }

  dashViewToggle.classList.add("hidden");

  if (authState.userType === "organization") {
    orgView.classList.remove("hidden");
    farmerView.classList.add("hidden");
    loadMyRequests();
  } else {
    farmerView.classList.remove("hidden");
    orgView.classList.add("hidden");
  }
}

// ── Org: load my requests ─────────────────────────────────────────────────

async function loadMyRequests() {
  myRequestsList.innerHTML = `<p class="muted">Loading…</p>`;
  try {
    const data = await apiFetch("/crops/requests");
    if (!data.length) {
      myRequestsList.innerHTML = `<p class="muted">No requests yet.</p>`;
      return;
    }
    myRequestsList.innerHTML = data.map(renderRequestItem).join("");
  } catch (err) {
    myRequestsList.innerHTML = `<p class="error-msg">${err.message}</p>`;
  }
}

function renderRequestItem(req) {
  const crops = req.crops_low_in_stock
    ? req.crops_low_in_stock.split(",").map(c =>
      `<span class="ri-crop-tag">${cropEmoji(c.trim())} ${c.trim()}</span>`
    ).join("")
    : "";

  const ntc = req.nice_to_have_crops
    ? `<p class="ri-ntc">Also needed: ${req.nice_to_have_crops}</p>`
    : "";

  return `
    <div class="request-item">
      <div class="ri-header">
        <div class="ri-crops">${crops}</div>
        ${statusBadge(req.fulfillment_status)}
      </div>
      ${ntc}
      <span class="ri-date">${formatDate(req.created_at)}</span>
    </div>`;
}

refreshMyRequestsBtn.addEventListener("click", loadMyRequests);

// ── Org: submit crop request ──────────────────────────────────────────────

cropRequestForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideMsg(cropError);
  hideMsg(cropSuccess);

  const selected = [...document.querySelectorAll("input[name='crop']:checked")]
    .map(cb => cb.value);

  if (!selected.length) {
    showMsg(cropError, "Please select at least one crop.");
    return;
  }

  const payload = {
    crops_low_in_stock: selected,
    nice_to_have_crops: document.getElementById("niceToHave").value.trim() || null,
  };

  try {
    await apiFetch("/crops/request", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showMsg(cropSuccess, "Crop request submitted successfully!", false);
    cropRequestForm.reset();
    loadMyRequests();
  } catch (err) {
    showMsg(cropError, err.message);
  }
});

// ── Farmer: browse requests ───────────────────────────────────────────────

applyFiltersBtn.addEventListener("click", loadFarmerRequests);

async function loadFarmerRequests() {
  farmerRequestsList.innerHTML = `<p class="muted">Loading…</p>`;

  const params = new URLSearchParams();
  const city = document.getElementById("filterCity").value.trim();
  const state = document.getElementById("filterState").value.trim();
  const status = document.getElementById("filterStatus").value;
  if (city) params.set("city", city);
  if (state) params.set("state", state);
  if (status) params.set("status", status);

  try {
    const data = await apiFetch(`/crops/requests?${params.toString()}`);
    if (!data.length) {
      farmerRequestsList.innerHTML = `<p class="muted">No matching requests found.</p>`;
      return;
    }
    farmerRequestsList.innerHTML = data.map(renderFarmerCard).join("");
  } catch (err) {
    farmerRequestsList.innerHTML = `<p class="error-msg">${err.message}</p>`;
  }
}

function renderFarmerCard(req) {
  const orgName = req.organization_name || "Unknown Organization";
  const location = [req.city, req.state].filter(Boolean).join(", ");
  const crops = req.crops_low_in_stock
    ? req.crops_low_in_stock.split(",").map(c =>
      `<span class="ri-crop-tag">${cropEmoji(c.trim())} ${c.trim()}</span>`
    ).join("")
    : `<span class="muted">None specified</span>`;

  const ntc = req.nice_to_have_crops
    ? `<p class="ri-ntc">Also helpful: ${req.nice_to_have_crops}</p>`
    : "";

  return `
    <div class="farmer-card">
      <div class="fc-org">${orgName}</div>
      <div class="fc-location">${location || "Location not set"}</div>
      <div class="ri-crops">${crops}</div>
      ${ntc}
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:.25rem">
        ${statusBadge(req.fulfillment_status)}
        <span class="ri-date">${formatDate(req.created_at)}</span>
      </div>
    </div>`;
}

// ── Emoji helper ──────────────────────────────────────────────────────────
function cropEmoji(crop) {
  const map = { lettuce: "🥬", cucumbers: "🥒", tomatoes: "🍅" };
  return map[crop.toLowerCase()] ?? "🌱";
}

// ════════════════════════════════════════════════════════════════════════════
// Bootstrap on load
// ════════════════════════════════════════════════════════════════════════════

applySession();

// If already logged in, go straight to dashboard
if (authState.token) {
  switchTab("dashboard");
}
