/**
 * app.js — Route 1 Single-Page Application
 *
 * Architecture:
 *   - Global `App` object holds auth state and all page/API logic.
 *   - `App.navigate(page)` fetches the HTML component from /components/
 *     and injects it into #app, then calls the page's init function.
 *   - All backend calls go through `App.api(method, path, body)` which
 *     automatically attaches the Bearer token header.
 *   - Messaging endpoint is polled every 8 s when the messaging page is open.
 */

// Backend API base URL. On localhost we hit the local dev server; on any other
// host (e.g. GitHub Pages) we hit the deployed AWS backend below.
// ── Fill in your AWS backend's HTTPS URL once deployed. It MUST be https:// —
//    GitHub Pages is served over HTTPS and browsers block http:// (mixed content).
const PROD_API_BASE = "https://YOUR-AWS-BACKEND-URL";   // e.g. https://api.route1app.com
const API_BASE =
    (location.hostname === "localhost" || location.hostname === "127.0.0.1")
        ? "http://localhost:8000"
        : PROD_API_BASE;

// Google Sign-In: paste your OAuth 2.0 "Web application" client ID here.
// Must match GOOGLE_CLIENT_ID in the backend .env. Leave blank to hide the
// "Sign in with Google" buttons entirely.
const GOOGLE_CLIENT_ID = "398142413341-n6glr5jnmh60li4nmefnh5fdehr3u00p.apps.googleusercontent.com";

/* ═══════════════════════════════════════════════════════════════════════════════
   STATE
   ═══════════════════════════════════════════════════════════════════════════════ */
const App = {
    token: localStorage.getItem("r1_token"),
    user: JSON.parse(localStorage.getItem("r1_user") || "null"),
    currentPage: null,
    messagingConvId: null,
    messagingPollTimer: null,
    pendingMessageTo: null,   // {id, name} — set when navigating from browse → messages

    // ── Persist auth ──────────────────────────────────────────────────────────
    _saveAuth(token, user) {
        this.token = token;
        this.user = user;
        localStorage.setItem("r1_token", token);
        localStorage.setItem("r1_user", JSON.stringify(user));
    },
    _clearAuth() {
        this.token = null;
        this.user = null;
        localStorage.removeItem("r1_token");
        localStorage.removeItem("r1_user");
    },

    // ── Fetch wrapper ──────────────────────────────────────────────────────────
    async api(method, path, body = null) {
        const opts = {
            method,
            headers: { "Content-Type": "application/json" },
        };
        if (this.token) opts.headers["Authorization"] = `Bearer ${this.token}`;
        if (body) opts.body = JSON.stringify(body);

        const res = await fetch(`${API_BASE}${path}`, opts);
        if (res.status === 204) return null;
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
        return data;
    },

    // Login form uses OAuth2 password flow (form-encoded, not JSON)
    async apiLoginForm(email, password) {
        const form = new URLSearchParams({ username: email, password });
        const res = await fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: form,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || "Login failed.");
        return data;
    },

    /* ═══════════════════════════════════════════════════════════════════════════
       INIT
       ═══════════════════════════════════════════════════════════════════════════ */
    init() {
        this._renderNav();
        if (this.token && this.user) {
            this._navigateToHomeDashboard();
        } else {
            this.navigate("landing");
        }
    },

    /* ═══════════════════════════════════════════════════════════════════════════
       NAVIGATION
       ═══════════════════════════════════════════════════════════════════════════ */
    async navigate(page) {
        // Stop any active messaging poll
        if (this.messagingPollTimer) {
            clearInterval(this.messagingPollTimer);
            this.messagingPollTimer = null;
        }

        this.currentPage = page;
        this._updateNavActive(page);

        const componentMap = {
            landing: "components/landing.html",
            about: "components/about.html",
            contact: "components/contact.html",
            login: "components/login.html",
            farmer_dashboard: "components/farmer_dashboard.html",
            org_dashboard: "components/org_dashboard.html",
            consumer_dashboard: "components/consumer_dashboard.html",
            messaging: "components/messaging.html",
            profile_settings: "components/profile_settings.html",
            points_rewards: "components/points_rewards.html",
            wishlist_manage: "components/wishlist_manage.html",
        };

        const htmlPath = componentMap[page];
        if (!htmlPath) { console.error("Unknown page:", page); return; }

        try {
            const html = await fetch(htmlPath + "?v=20260331", { cache: "no-store" }).then(r => r.text());
            document.getElementById("app").innerHTML = html;
        } catch (e) {
            document.getElementById("app").innerHTML =
                `<div class="main-content"><p class="error-msg">Failed to load page: ${e.message}</p></div>`;
            return;
        }

        // Call page init
        const inits = {
            landing: () => this.initLanding(),
            about: () => this.initAbout(),
            contact: () => this.initContact(),
            login: () => this.initLogin(),
            farmer_dashboard: () => this.initFarmerDashboard(),
            org_dashboard: () => this.initBrowseDashboard("org"),
            consumer_dashboard: () => this.initConsumerDashboard(),
            messaging: () => this.initMessaging(),
            profile_settings: () => this.initProfileSettings(),
            points_rewards: () => this.initPointsRewards(),
            wishlist_manage: () => this.initWishlistManage(),
        };
        inits[page]?.();
    },

    _navigateToHomeDashboard() {
        const type = this.user?.user_type;
        if (type === "farmer") this.navigate("farmer_dashboard");
        else if (type === "organization") this.navigate("org_dashboard");
        else if (type === "consumer") this.navigate("consumer_dashboard");
        else this.navigate("login");
    },

    /* ═══════════════════════════════════════════════════════════════════════════
       NAV BAR
       ═══════════════════════════════════════════════════════════════════════════ */
    _renderNav() {
        const header = document.getElementById("siteHeader");
        if (!header) return;

        if (!this.user) {
            header.innerHTML = `
        <div class="header-inner">
          <div class="brand" id="brandLogo">
            <span class="brand-icon">🌾</span>
            <div class="brand-text">
              <span class="brand-name">Route&nbsp;<strong>1</strong></span>
              <span class="brand-sub">Pathways</span>
            </div>
          </div>
          <nav class="nav-links">
            <button class="nav-link" data-page="about">About us</button>
            <button class="nav-link" data-page="contact">Contact us</button>
          </nav>
          <div class="header-spacer"></div>
          <div class="header-user">
            <button class="nav-link" id="navLoginBtn">Log in</button>
            <button class="btn btn-sm" id="navRegisterBtn">Create free account</button>
          </div>
        </div>`;
            document.getElementById("brandLogo")
                .addEventListener("click", () => this.navigate("landing"));
            header.querySelectorAll(".nav-link[data-page]").forEach(btn =>
                btn.addEventListener("click", () => this.navigate(btn.dataset.page))
            );
            document.getElementById("navLoginBtn")
                .addEventListener("click", () => this.navigate("login"));
            document.getElementById("navRegisterBtn")
                .addEventListener("click", async () => {
                    await this.navigate("login");
                    document.getElementById("showRegisterTab")?.click();
                });
            return;
        }

        const displayName = this.user.full_name || this.user.organization_name || this.user.email;
        const dashPage = this.user.user_type === "farmer" ? "farmer_dashboard"
            : this.user.user_type === "organization" ? "org_dashboard"
                : "consumer_dashboard";

        // Extra nav links per role
        const extraLinks = this.user.user_type === "organization"
            ? `<button class="nav-link" data-page="wishlist_manage">Wishlist</button>`
            : this.user.user_type === "consumer"
                ? `<button class="nav-link" data-page="points_rewards">My Points</button>`
                : "";

        header.innerHTML = `
      <div class="header-inner">
        <div class="brand" id="brandLogo">
          <span class="brand-icon">🌾</span>
          <div class="brand-text">
            <span class="brand-name">Route&nbsp;<strong>1</strong></span>
            <span class="brand-sub">Pathways</span>
          </div>
        </div>
        <nav class="nav-links">
          <button class="nav-link" data-page="${dashPage}">Dashboard</button>
          <button class="nav-link" data-page="messaging">
            Messages <span class="nav-badge hidden" id="unreadBadge">0</span>
          </button>
          ${extraLinks}
        </nav>
        <div class="header-spacer"></div>
        <div class="header-user">
          <span class="user-chip" title="${this.user.email}">${displayName}</span>
          <button class="btn btn-sm btn-ghost nav-link" data-page="profile_settings">⚙️ Profile</button>
          <button class="btn btn-sm btn-ghost" id="logoutBtn">Logout</button>
        </div>
      </div>`;

        header.querySelector("#brandLogo")
            .addEventListener("click", () => this._navigateToHomeDashboard());
        header.querySelectorAll(".nav-link[data-page]").forEach(btn =>
            btn.addEventListener("click", () => this.navigate(btn.dataset.page))
        );
        header.querySelector("#logoutBtn")
            .addEventListener("click", () => this.logout());

        this._refreshUnreadBadge();
    },

    _updateNavActive(page) {
        document.querySelectorAll(".nav-link[data-page]").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.page === page);
        });
    },

    async _refreshUnreadBadge() {
        if (!this.token) return;
        try {
            const convs = await this.api("GET", "/messages/conversations");
            const unread = convs.reduce((acc, c) => acc + (c.unread_count || 0), 0);
            const badge = document.getElementById("unreadBadge");
            if (!badge) return;
            if (unread > 0) { badge.textContent = unread; badge.classList.remove("hidden"); }
            else { badge.classList.add("hidden"); }
        } catch { /* silent */ }
    },

    /* ═══════════════════════════════════════════════════════════════════════════
       LOGOUT
       ═══════════════════════════════════════════════════════════════════════════ */
    logout() {
        this._clearAuth();
        this._renderNav();
        this.navigate("login");
        this.showToast("Logged out successfully.", "success");
    },

    /* ═══════════════════════════════════════════════════════════════════════════
       TOAST
       ═══════════════════════════════════════════════════════════════════════════ */
    showToast(msg, type = "success") {
        const el = document.getElementById("toast");
        if (!el) return;
        el.textContent = msg;
        el.className = `toast-${type}`;
        el.classList.remove("toast-hide");
        setTimeout(() => el.classList.add("toast-hide"), 3500);
    },

    /* ═══════════════════════════════════════════════════════════════════════════
       PAGE: LOGIN
       ═══════════════════════════════════════════════════════════════════════════ */
    initAbout() {
        window.scrollTo(0, 0);
        document.getElementById("aboutCreateBtn")?.addEventListener("click", async () => {
            await this.navigate("login");
            document.getElementById("showRegisterTab")?.click();
        });
    },

    initContact() {
        window.scrollTo(0, 0);
        const form = document.getElementById("contactFormEl");
        if (!form) return;
        // Where contact messages go (front-end mailto hand-off; no backend needed)
        const CONTACT_EMAIL = "vedtheamigo@gmail.com";
        form.addEventListener("submit", (e) => {
            e.preventDefault();
            const name = document.getElementById("contactName").value.trim();
            const email = document.getElementById("contactEmail").value.trim();
            const message = document.getElementById("contactMessage").value.trim();
            const errEl = document.getElementById("contactError");
            const okEl = document.getElementById("contactSuccess");
            errEl.classList.add("hidden");
            okEl.classList.add("hidden");

            if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                errEl.textContent = "Please enter a valid email so we can reply.";
                errEl.classList.remove("hidden");
                return;
            }
            if (!message) {
                errEl.textContent = "Please add a message.";
                errEl.classList.remove("hidden");
                return;
            }

            const subject = encodeURIComponent(`Route 1 Pathways — message from ${name || email}`);
            const body = encodeURIComponent(`${message}\n\n— ${name || "A visitor"} (${email})`);
            window.location.href = `mailto:${CONTACT_EMAIL}?subject=${subject}&body=${body}`;

            okEl.classList.remove("hidden");
            form.reset();
        });
    },

    initLanding() {
        // Both "Create free account" buttons → register tab on the existing login screen
        const goRegister = async () => {
            await this.navigate("login");
            document.getElementById("showRegisterTab")?.click();
        };
        document.getElementById("landingCreateBtn")?.addEventListener("click", goRegister);
        document.getElementById("landingCreateBtn2")?.addEventListener("click", goRegister);
        // "Log in" → login screen as-is
        document.getElementById("landingLoginBtn")?.addEventListener("click", () => this.navigate("login"));

        // Scroll-reveal (progressive enhancement; CSS handles reduced-motion)
        const root = document.querySelector(".landing");
        const reveals = document.querySelectorAll(".landing .reveal");
        if (root && reveals.length && "IntersectionObserver" in window) {
            root.classList.add("js-reveal");
            const io = new IntersectionObserver((entries) => {
                entries.forEach(e => {
                    if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
                });
            }, { threshold: 0.15 });
            reveals.forEach(el => io.observe(el));
        }
    },

    initLogin() {
        const loginTab = document.getElementById("showLoginTab");
        const registerTab = document.getElementById("showRegisterTab");
        const loginPanel = document.getElementById("loginPanel");
        const regPanel = document.getElementById("registerPanel");

        loginTab.addEventListener("click", () => {
            loginTab.classList.add("active");
            registerTab.classList.remove("active");
            loginPanel.classList.remove("hidden");
            regPanel.classList.add("hidden");
        });
        registerTab.addEventListener("click", () => {
            registerTab.classList.add("active");
            loginTab.classList.remove("active");
            regPanel.classList.remove("hidden");
            loginPanel.classList.add("hidden");
        });

        // Login form
        document.getElementById("loginFormEl").addEventListener("submit", async e => {
            e.preventDefault();
            const email = document.getElementById("loginEmail").value.trim();
            const password = document.getElementById("loginPassword").value;
            const errEl = document.getElementById("loginError");
            errEl.classList.add("hidden");
            try {
                const data = await this.apiLoginForm(email, password);
                this._saveAuth(data.access_token, {
                    id: data.user_id,
                    email: data.email,
                    user_type: data.user_type,
                    org_subtype: data.org_subtype,
                    full_name: null,
                    organization_name: null,
                });
                // Fetch full profile to get name
                const profile = await this.api("GET", "/auth/me");
                this._saveAuth(data.access_token, profile);
                this._renderNav();
                this._navigateToHomeDashboard();
            } catch (err) {
                errEl.textContent = err.message;
                errEl.classList.remove("hidden");
            }
        });

        // Register — show/hide org fields based on user type selection
        document.querySelectorAll("input[name='userType']").forEach(radio => {
            radio.addEventListener("change", () => {
                const selected = document.querySelector("input[name='userType']:checked")?.value;
                const isOrg = selected === "organization";
                const isConsumer = selected === "consumer";
                document.getElementById("orgSubtypeGroup").classList.toggle("hidden", !isOrg);
                document.getElementById("orgNameGroup").classList.toggle("hidden", isConsumer);
                if (selected === "farmer") {
                    document.getElementById("orgNameLabel").textContent = "Farm Name";
                } else if (isOrg) {
                    document.getElementById("orgNameLabel").textContent = "Organization Name";
                }
            });
        });

        // Register form
        document.getElementById("registerFormEl").addEventListener("submit", async e => {
            e.preventDefault();
            const errEl = document.getElementById("registerError");
            errEl.classList.add("hidden");

            const userType = document.querySelector("input[name='userType']:checked")?.value;
            const orgSubtype = document.getElementById("orgSubtype").value || null;

            if (!userType) {
                errEl.textContent = "Please select a user type.";
                errEl.classList.remove("hidden");
                return;
            }
            if (userType === "organization" && !orgSubtype) {
                errEl.textContent = "Please select an organization type.";
                errEl.classList.remove("hidden");
                return;
            }

            const payload = {
                email: document.getElementById("regEmail").value.trim(),
                password: document.getElementById("regPassword").value,
                user_type: userType,
                org_subtype: orgSubtype,
                full_name: document.getElementById("regFullName").value.trim() || null,
                organization_name: userType !== "consumer"
                    ? document.getElementById("regOrgName").value.trim() || null
                    : null,
                location_city: document.getElementById("regCity").value.trim() || null,
                location_region: document.getElementById("regRegion").value || null,
                phone: document.getElementById("regPhone").value.trim() || null,
            };

            try {
                await this.api("POST", "/auth/register", payload);
                this.showToast("Account created! Please sign in.", "success");
                // Switch to login tab
                loginTab.click();
                document.getElementById("loginEmail").value = payload.email;
            } catch (err) {
                errEl.textContent = err.message;
                errEl.classList.remove("hidden");
            }
        });

        // Google sign-in (renders into the login + register panels)
        this._initGoogleSignIn();

        // Google role-selection step (new Google users only)
        document.querySelectorAll("input[name='gUserType']").forEach(radio => {
            radio.addEventListener("change", () => {
                const isOrg = document.querySelector("input[name='gUserType']:checked")?.value === "organization";
                document.getElementById("gOrgSubtypeGroup").classList.toggle("hidden", !isOrg);
            });
        });
        document.getElementById("googleCompleteFormEl")?.addEventListener("submit", e => {
            e.preventDefault();
            this._submitGoogleRegistration();
        });
    },

    /* ═══════════════════════════════════════════════════════════════════════════
       GOOGLE SIGN-IN
       ═══════════════════════════════════════════════════════════════════════════ */
    _initGoogleSignIn() {
        if (!GOOGLE_CLIENT_ID) {
            // Not configured → hide the divider + button so the page looks normal.
            document.querySelectorAll(".auth-divider, .google-signin")
                .forEach(el => el.classList.add("hidden"));
            return;
        }

        const render = () => {
            if (!window.google?.accounts?.id) return false;
            window.google.accounts.id.initialize({
                client_id: GOOGLE_CLIENT_ID,
                callback: (resp) => this._handleGoogleCredential(resp.credential),
            });
            [["googleLoginBtn", "signin_with"], ["googleRegisterBtn", "signup_with"]]
                .forEach(([id, text]) => {
                    const el = document.getElementById(id);
                    if (el) {
                        el.innerHTML = "";
                        window.google.accounts.id.renderButton(el, {
                            theme: "outline", size: "large", width: 320,
                            text, logo_alignment: "center",
                        });
                    }
                });
            return true;
        };

        // The GSI script loads async; retry briefly until it's ready.
        if (!render()) {
            let tries = 0;
            const t = setInterval(() => {
                if (render() || ++tries > 40) clearInterval(t);
            }, 100);
        }
    },

    async _handleGoogleCredential(credential) {
        if (!credential) return;
        this._pendingGoogleCredential = credential;
        try {
            const data = await this.api("POST", "/auth/google", { credential });
            if (data.needs_registration) {
                // New Google user — reveal the role picker.
                this._showGoogleCompletePanel(data.full_name);
            } else {
                await this._loginWithToken(data);
            }
        } catch (err) {
            this.showToast(`Google sign-in failed: ${err.message}`, "error");
        }
    },

    _showGoogleCompletePanel(fullName) {
        document.getElementById("loginPanel")?.classList.add("hidden");
        document.getElementById("registerPanel")?.classList.add("hidden");
        const sub = document.getElementById("googleCompleteSub");
        if (sub && fullName) sub.textContent = `Welcome, ${fullName}! Tell us how you'll use Route 1 Pathways.`;
        document.getElementById("googleCompletePanel")?.classList.remove("hidden");
    },

    async _submitGoogleRegistration() {
        const errEl = document.getElementById("googleCompleteError");
        errEl.classList.add("hidden");

        const userType = document.querySelector("input[name='gUserType']:checked")?.value;
        const orgSubtype = document.getElementById("gOrgSubtype").value || null;

        if (!userType) {
            errEl.textContent = "Please choose an account type.";
            errEl.classList.remove("hidden");
            return;
        }
        if (userType === "organization" && !orgSubtype) {
            errEl.textContent = "Please select an organization type.";
            errEl.classList.remove("hidden");
            return;
        }
        if (!this._pendingGoogleCredential) {
            errEl.textContent = "Your Google session expired. Please sign in with Google again.";
            errEl.classList.remove("hidden");
            return;
        }

        try {
            const data = await this.api("POST", "/auth/google/complete", {
                credential: this._pendingGoogleCredential,
                user_type: userType,
                org_subtype: orgSubtype,
            });
            await this._loginWithToken(data);
        } catch (err) {
            errEl.textContent = err.message;
            errEl.classList.remove("hidden");
        }
    },

    // Persist a token payload, fetch the full profile, then enter the dashboard.
    async _loginWithToken(data) {
        this._pendingGoogleCredential = null;
        this._saveAuth(data.access_token, {
            id: data.user_id,
            email: data.email,
            user_type: data.user_type,
            org_subtype: data.org_subtype,
            full_name: null,
            organization_name: null,
        });
        try {
            const profile = await this.api("GET", "/auth/me");
            this._saveAuth(data.access_token, profile);
        } catch { /* keep minimal user if profile fetch fails */ }
        this._renderNav();
        this._navigateToHomeDashboard();
    },

    /* ═══════════════════════════════════════════════════════════════════════════
       PAGE: FARMER DASHBOARD
       ═══════════════════════════════════════════════════════════════════════════ */
    initFarmerDashboard() {
        const fname = this.user.full_name || this.user.organization_name || "Farmer";
        const subtitle = document.getElementById("farmerSubtitle");
        if (subtitle) subtitle.textContent = `Welcome, ${fname}! Manage your available produce.`;

        // Load crops
        this._loadMyCrops();

        // Toggle add crop form
        const addBtn = document.getElementById("toggleAddCropBtn");
        const cancelBtn = document.getElementById("cancelAddCropBtn");
        const addForm = document.getElementById("addCropForm");
        addBtn.addEventListener("click", () => addForm.classList.remove("hidden"));
        cancelBtn.addEventListener("click", () => addForm.classList.add("hidden"));

        // Submit new crop
        document.getElementById("addCropFormEl").addEventListener("submit", async e => {
            e.preventDefault();
            const errEl = document.getElementById("addCropError");
            errEl.classList.add("hidden");
            const price = document.getElementById("cropPrice").value;
            const payload = {
                crop_name: document.getElementById("cropName").value.trim(),
                quantity_available: document.getElementById("cropQty").value.trim(),
                quantity_unit: document.getElementById("cropUnit").value,
                price_per_unit: price ? parseFloat(price) : null,
                description: document.getElementById("cropDesc").value.trim() || null,
                can_provide_transport: document.getElementById("canTransport").checked,
                needs_transport: document.getElementById("needTransport").checked,
                donation_eligible: document.getElementById("donationEligible").checked,
            };
            try {
                await this.api("POST", "/farmers/crops", payload);
                this.showToast("Crop listing added!", "success");
                addForm.classList.add("hidden");
                document.getElementById("addCropFormEl").reset();
                this._loadMyCrops();
            } catch (err) {
                errEl.textContent = err.message;
                errEl.classList.remove("hidden");
            }
        });

        // Edit modal close
        document.getElementById("closeEditModal")
            .addEventListener("click", () =>
                document.getElementById("editCropModal").classList.add("hidden")
            );

        // Edit modal submit
        document.getElementById("editCropFormEl").addEventListener("submit", async e => {
            e.preventDefault();
            const errEl = document.getElementById("editCropError");
            errEl.classList.add("hidden");
            const cropId = parseInt(document.getElementById("editCropId").value);
            const price = document.getElementById("editCropPrice").value;
            const payload = {
                crop_name: document.getElementById("editCropName").value.trim(),
                quantity_available: document.getElementById("editCropQty").value.trim(),
                quantity_unit: document.getElementById("editCropUnit").value,
                price_per_unit: price ? parseFloat(price) : null,
                description: document.getElementById("editCropDesc").value.trim() || null,
                can_provide_transport: document.getElementById("editCanTransport").checked,
                needs_transport: document.getElementById("editNeedTransport").checked,
                donation_eligible: document.getElementById("editDonationEligible").checked,
                is_available: document.getElementById("editIsAvailable").checked,
            };
            try {
                await this.api("PUT", `/farmers/crops/${cropId}`, payload);
                this.showToast("Listing updated!", "success");
                document.getElementById("editCropModal").classList.add("hidden");
                this._loadMyCrops();
            } catch (err) {
                errEl.textContent = err.message;
                errEl.classList.remove("hidden");
            }
        });
    },

    async _loadMyCrops() {
        const loading = document.getElementById("cropListLoading");
        const empty = document.getElementById("cropListEmpty");
        const table = document.getElementById("cropListTable");
        const tbody = document.getElementById("cropTableBody");
        if (!loading) return;

        loading.classList.remove("hidden");
        empty.classList.add("hidden");
        table.classList.add("hidden");

        try {
            const crops = await this.api("GET", "/farmers/crops");
            loading.classList.add("hidden");

            if (!crops || crops.length === 0) {
                empty.classList.remove("hidden");
                return;
            }

            tbody.innerHTML = crops.map(c => `
        <tr>
          <td><strong>${this._esc(c.crop_name)}</strong></td>
          <td>${this._esc(c.quantity_available)} ${this._esc(c.quantity_unit)}</td>
          <td>${c.price_per_unit != null ? `$${parseFloat(c.price_per_unit).toFixed(2)}` : "<em>On request</em>"}</td>
          <td>${c.can_provide_transport ? "✅ Can provide" : c.needs_transport ? "🚛 Needs help" : "—"}</td>
          <td>${c.donation_eligible ? '<span class="badge badge-amber">Eligible</span>' : "—"}</td>
          <td>${c.is_available
                    ? '<span class="badge badge-green">Active</span>'
                    : '<span class="badge badge-gray">Inactive</span>'}</td>
          <td>
            <button class="btn btn-sm btn-secondary" onclick="App._openEditModal(${c.id})">Edit</button>
            <button class="btn btn-sm btn-danger"    onclick="App._deleteCrop(${c.id})">Delete</button>
          </td>
        </tr>`).join("");
            table.classList.remove("hidden");

            // Store crops on window for modal access
            window._farmerCrops = crops;
        } catch (err) {
            loading.classList.add("hidden");
            this.showToast(`Failed to load crops: ${err.message}`, "error");
        }
    },

    _openEditModal(cropId) {
        const crop = (window._farmerCrops || []).find(c => c.id === cropId);
        if (!crop) return;
        document.getElementById("editCropId").value = crop.id;
        document.getElementById("editCropName").value = crop.crop_name;
        document.getElementById("editCropQty").value = crop.quantity_available;
        document.getElementById("editCropUnit").value = crop.quantity_unit;
        document.getElementById("editCropPrice").value = crop.price_per_unit ?? "";
        document.getElementById("editCropDesc").value = crop.description ?? "";
        document.getElementById("editCanTransport").checked = crop.can_provide_transport;
        document.getElementById("editNeedTransport").checked = crop.needs_transport;
        document.getElementById("editDonationEligible").checked = crop.donation_eligible;
        document.getElementById("editIsAvailable").checked = crop.is_available;
        document.getElementById("editCropModal").classList.remove("hidden");
    },

    async _deleteCrop(cropId) {
        if (!confirm("Delete this crop listing?")) return;
        try {
            await this.api("DELETE", `/farmers/crops/${cropId}`);
            this.showToast("Listing deleted.", "success");
            this._loadMyCrops();
        } catch (err) {
            this.showToast(`Delete failed: ${err.message}`, "error");
        }
    },

    /* ═══════════════════════════════════════════════════════════════════════════
       PAGE: BROWSE DASHBOARD (org + consumer share the same init)
       ═══════════════════════════════════════════════════════════════════════════ */
    initBrowseDashboard(role) {
        const user = this.user;
        // Expose org sub-type to CSS for the role-plate accent (visual only)
        document.body.dataset.orgSubtype = (role === "org" && user.org_subtype) ? user.org_subtype : "";
        // Set heading context
        const heading = document.getElementById("browseHeading");
        const subtitle = document.getElementById("browseSubtitle");
        if (heading) {
            heading.textContent = "Browse Minnesota Farmers";
            if (subtitle && role === "org") {
                const orgLabel = { restaurant: "Restaurant", grocery_store: "Grocery Store", food_shelf: "Food Shelf" }[user.org_subtype] || "Organization";
                subtitle.textContent = `Viewing as: ${orgLabel}`;
            }
        }

        // Show donation filter only for food shelves (orgs)
        const donationGroup = document.getElementById("donationFilterGroup");
        if (donationGroup) {
            const showDonation = (role === "consumer") || (user.org_subtype === "food_shelf");
            donationGroup.classList.toggle("hidden", !showDonation);
        }

        // Load with empty filters on init
        this._runBrowse(role);

        document.getElementById("applyFiltersBtn")
            .addEventListener("click", () => this._runBrowse(role));

        document.getElementById("clearFiltersBtn").addEventListener("click", () => {
            document.getElementById("filterCrop").value = "";
            document.getElementById("filterRegion").value = "";
            document.getElementById("filterCity").value = "";
            document.getElementById("filterMinPrice").value = "";
            document.getElementById("filterMaxPrice").value = "";
            document.getElementById("filterTransport").checked = false;
            const donEl = document.getElementById("filterDonation");
            if (donEl) donEl.checked = false;
            this._runBrowse(role);
        });
    },

    async _runBrowse(role) {
        const loading = document.getElementById("browseLoading");
        const empty = document.getElementById("browseEmpty");
        const grid = document.getElementById("farmerGrid");
        const count = document.getElementById("resultCount");

        loading.classList.remove("hidden");
        empty.classList.add("hidden");
        grid.innerHTML = "";

        const params = new URLSearchParams();
        const crop = document.getElementById("filterCrop")?.value.trim();
        const region = document.getElementById("filterRegion")?.value;
        const city = document.getElementById("filterCity")?.value.trim();
        const minPrice = document.getElementById("filterMinPrice")?.value;
        const maxPrice = document.getElementById("filterMaxPrice")?.value;
        const transport = document.getElementById("filterTransport")?.checked;
        const donation = document.getElementById("filterDonation")?.checked;

        if (crop) params.set("crop_type", crop);
        if (region) params.set("location_region", region);
        if (city) params.set("location_city", city);
        if (minPrice) params.set("min_price", minPrice);
        if (maxPrice) params.set("max_price", maxPrice);
        if (transport) params.set("has_transport", "true");
        if (donation) params.set("donation_only", "true");

        const endpoint = role === "org" ? "/organizations/browse" : "/consumers/browse";
        const qs = params.toString();

        try {
            const farmers = await this.api("GET", `${endpoint}${qs ? "?" + qs : ""}`);
            loading.classList.add("hidden");

            if (!farmers || farmers.length === 0) {
                empty.classList.remove("hidden");
                if (count) count.textContent = "No results";
                return;
            }
            if (count) count.textContent = `${farmers.length} farmer${farmers.length === 1 ? "" : "s"} found`;

            grid.innerHTML = farmers.map(f => this._renderFarmerCard(f)).join("");

            // Attach message-farmer button listeners
            grid.querySelectorAll(".msg-farmer-btn").forEach(btn => {
                btn.addEventListener("click", () => {
                    this.pendingMessageTo = { id: parseInt(btn.dataset.farmerId), name: btn.dataset.farmerName };
                    this.navigate("messaging");
                });
            });
        } catch (err) {
            loading.classList.add("hidden");
            this.showToast(`Browse failed: ${err.message}`, "error");
        }
    },

    _renderFarmerCard(farmer) {
        const name = this._esc(farmer.full_name || farmer.organization_name || "Unnamed Farmer");
        const city = this._esc(farmer.location_city || "");
        const region = this._esc(farmer.location_region || "");
        const location = [city, region].filter(Boolean).join(", ") || "Location not specified";

        const cropChips = farmer.crops.slice(0, 6).map(c => {
            const label = `${this._esc(c.crop_name)} · ${this._esc(c.quantity_available)} ${this._esc(c.quantity_unit)}`;
            const cls = c.donation_eligible ? "crop-chip donation" : "crop-chip";
            return `<span class="${cls}">${label}</span>`;
        }).join("") + (farmer.crops.length > 6
            ? `<span class="crop-chip">+${farmer.crops.length - 6} more</span>` : "");

        const meta = [];
        if (farmer.crops.some(c => c.can_provide_transport)) meta.push("🚚 Can transport");
        if (farmer.crops.some(c => c.donation_eligible)) meta.push("🎁 Donation options");
        if (farmer.phone) meta.push(`📞 ${this._esc(farmer.phone)}`);

        return `
      <div class="farmer-card">
        <div class="farmer-card-header">
          <h4>${name}</h4>
          <div class="farmer-location">📍 ${location}</div>
        </div>
        <div class="farmer-card-body">
          <div class="crop-chips">${cropChips}</div>
          ${meta.length ? `<div class="farmer-meta">${meta.map(m => `<span>${m}</span>`).join("")}</div>` : ""}
          <div class="farmer-card-actions">
            <button class="btn btn-primary msg-farmer-btn"
              data-farmer-id="${farmer.id}"
              data-farmer-name="${name}">
              💬 Message Farmer
            </button>
          </div>
        </div>
      </div>`;
    },

    /* ═══════════════════════════════════════════════════════════════════════════
       PAGE: MESSAGING
       ═══════════════════════════════════════════════════════════════════════════ */
    initMessaging() {
        this._loadConversations();

        document.getElementById("refreshConvsBtn")
            .addEventListener("click", () => this._loadConversations());

        document.getElementById("sendMessageBtn")
            .addEventListener("click", () => this._sendMessage());

        document.getElementById("messageInput")
            .addEventListener("keydown", e => {
                if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    this._sendMessage();
                }
            });

        // If coming from browse with a pre-selected farmer, start conversation
        if (this.pendingMessageTo) {
            const { id, name } = this.pendingMessageTo;
            this.pendingMessageTo = null;
            this._openConversationWith(id, name);
        }

        // Poll for new messages every 8 s
        this.messagingPollTimer = setInterval(() => {
            if (this.messagingConvId) this._loadMessages(this.messagingConvId, false);
            this._refreshUnreadBadge();
        }, 8000);
    },

    async _loadConversations() {
        const loading = document.getElementById("convsLoading");
        const empty = document.getElementById("convsEmpty");
        const list = document.getElementById("conversationsList");
        if (!loading) return;

        loading.classList.remove("hidden");
        empty.classList.add("hidden");
        list.innerHTML = "";

        try {
            const convs = await this.api("GET", "/messages/conversations");
            loading.classList.add("hidden");
            if (!convs || convs.length === 0) { empty.classList.remove("hidden"); return; }

            list.innerHTML = convs.map(c => {
                const time = c.last_message_at
                    ? new Date(c.last_message_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                    : "";
                return `
          <li class="conv-item" data-conv-id="${this._esc(c.conversation_id)}"
              data-other-id="${c.other_user_id}"
              data-other-name="${this._esc(c.other_user_name || `User ${c.other_user_id}`)}">
            <div class="conv-name">${this._esc(c.other_user_name || `User ${c.other_user_id}`)}</div>
            <div class="conv-preview">${this._esc(c.last_message || "")}</div>
            <div class="conv-meta">
              <span>${time}</span>
              ${c.unread_count > 0
                        ? `<span class="unread-dot" title="${c.unread_count} unread"></span>`
                        : ""}
            </div>
          </li>`;
            }).join("");

            list.querySelectorAll(".conv-item").forEach(item => {
                item.addEventListener("click", () => {
                    list.querySelectorAll(".conv-item").forEach(i => i.classList.remove("active"));
                    item.classList.add("active");
                    this.messagingConvId = item.dataset.convId;
                    document.getElementById("threadPartnerName").textContent =
                        item.dataset.otherName;
                    this._loadMessages(item.dataset.convId);
                });
            });
        } catch (err) {
            loading.classList.add("hidden");
            this.showToast("Could not load conversations.", "error");
        }
    },

    async _openConversationWith(farmerId, farmerName) {
        // Derive conversation ID deterministically
        const myId = this.user.id;
        const convId = [myId, farmerId].sort((a, b) => a - b).join(":");

        document.getElementById("noConvSelected").classList.add("hidden");
        document.getElementById("messageThread").classList.remove("hidden");
        document.getElementById("threadPartnerName").textContent = farmerName;
        this.messagingConvId = convId;
        this._loadMessages(convId);
    },

    async _loadMessages(convId, scroll = true) {
        const noConv = document.getElementById("noConvSelected");
        const thread = document.getElementById("messageThread");
        const loading = document.getElementById("msgsLoading");
        const msgList = document.getElementById("messagesList");
        if (!thread) return;

        noConv.classList.add("hidden");
        thread.classList.remove("hidden");
        if (loading) loading.classList.remove("hidden");

        try {
            const msgs = await this.api("GET", `/messages/conversations/${convId}`);
            if (loading) loading.classList.add("hidden");
            if (!msgs) return;

            const myId = this.user.id;
            msgList.innerHTML = msgs.map(m => {
                const sent = m.sender_id === myId;
                const time = new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
                return `
          <div class="msg-bubble ${sent ? "sent" : "received"}">
            ${this._esc(m.content)}
            <div class="msg-meta">${time}</div>
          </div>`;
            }).join("");

            if (scroll) {
                const scroll_el = document.getElementById("messagesScroll");
                if (scroll_el) scroll_el.scrollTop = scroll_el.scrollHeight;
            }
            this._refreshUnreadBadge();
        } catch (err) {
            if (loading) loading.classList.add("hidden");
        }
    },

    async _sendMessage() {
        const input = document.getElementById("messageInput");
        const content = input?.value.trim();
        const convId = this.messagingConvId;
        if (!content || !convId) return;

        // Derive receiver from conversation ID
        const [idA, idB] = convId.split(":").map(Number);
        const receiverId = idA === this.user.id ? idB : idA;

        try {
            await this.api("POST", "/messages", { receiver_id: receiverId, content });
            input.value = "";
            this._loadMessages(convId);
            this._refreshUnreadBadge();
        } catch (err) {
            this.showToast(`Send failed: ${err.message}`, "error");
        }
    },

    /* ═══════════════════════════════════════════════════════════════════════════
       PAGE: CONSUMER DASHBOARD (browse farmers + donation opportunities)
       ═══════════════════════════════════════════════════════════════════════════ */
    initConsumerDashboard() {
        // Set up view tab switching first
        document.querySelectorAll(".consumer-tab").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".consumer-tab").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                const view = btn.dataset.view;
                document.getElementById("viewBrowse").classList.toggle("hidden", view !== "browse");
                document.getElementById("viewDonate").classList.toggle("hidden", view !== "donate");
                if (view === "donate") this._loadDonationOpportunities();
            });
        });

        // Then call the existing browse init (farmers tab)
        this.initBrowseDashboard("consumer");

        // Donation Opportunities
        this._loadDonationOpportunities();

        document.getElementById("applyDonateFilters")
            .addEventListener("click", () => this._loadDonationOpportunities());
        document.getElementById("clearDonateFilters").addEventListener("click", () => {
            document.getElementById("donateFilterCrop").value = "";
            document.getElementById("donateFilterMaxAmt").value = "";
            document.getElementById("donateFilterGroupOnly").checked = false;
            this._loadDonationOpportunities();
        });

        // Donate Now modal — close
        document.getElementById("closeDonateModal")
            .addEventListener("click", () => document.getElementById("donateModal").classList.add("hidden"));
        // Group Donate modal — close
        document.getElementById("closeGroupDonateModal")
            .addEventListener("click", () => document.getElementById("groupDonateModal").classList.add("hidden"));
    },

    async _loadDonationOpportunities() {
        const loading = document.getElementById("donationsLoading");
        const empty = document.getElementById("donationsEmpty");
        const grid = document.getElementById("donationOppsGrid");
        if (!grid) return;

        loading?.classList.remove("hidden");
        empty?.classList.add("hidden");
        grid.innerHTML = "";

        const params = new URLSearchParams();
        const crop = document.getElementById("donateFilterCrop")?.value.trim();
        const maxAmt = document.getElementById("donateFilterMaxAmt")?.value;
        const grpOnly = document.getElementById("donateFilterGroupOnly")?.checked;
        if (crop) params.set("crop_name", crop);
        if (maxAmt) params.set("max_amount", maxAmt);
        if (grpOnly) params.set("group_only", "true");

        try {
            const qs = params.toString();
            const items = await this.api("GET", `/wishlist/${qs ? "?" + qs : ""}`);
            loading?.classList.add("hidden");
            if (!items || items.length === 0) { empty?.classList.remove("hidden"); return; }
            grid.innerHTML = items.map(item => this._renderDonationCard(item)).join("");

            // Attach Donate Now buttons
            grid.querySelectorAll(".donate-now-btn").forEach(btn => {
                btn.addEventListener("click", () => this._openDonateModal(parseInt(btn.dataset.itemId)));
            });
            // Attach Join Group buttons
            grid.querySelectorAll(".join-group-btn").forEach(btn => {
                btn.addEventListener("click", () => this._openGroupDonateModal(parseInt(btn.dataset.gdId), btn.dataset));
            });
        } catch (err) {
            loading?.classList.add("hidden");
            this.showToast(`Failed to load donation opportunities: ${err.message}`, "error");
        }
    },

    _renderDonationCard(item) {
        const orgName = this._esc(item.organization_name || "Organization");
        const cropName = this._esc(item.crop_name);
        const farmers = item.farmers.map(f =>
            `<span class="crop-chip">${this._esc(f.full_name || f.farm_name || "Farmer #" + f.farmer_id)}</span>`
        ).join("");
        const donated = parseFloat(item.amount_donated).toFixed(2);
        const total = parseFloat(item.total_amount_required).toFixed(2);
        const pct = Math.min(100, Math.round((item.amount_donated / item.total_amount_required) * 100));

        let groupBlock = "";
        if (item.is_group_donation && item.group_donation) {
            const gd = item.group_donation;
            groupBlock = `
        <div class="group-badge">👥 Group Donation</div>
        <div class="group-progress" style="margin:.5rem 0;">
          <div class="group-progress-bar">
            <div class="group-progress-fill" style="width:${pct}%"></div>
          </div>
          <div class="group-progress-labels">
            <span>${gd.donors_count} donor(s)</span>
            <span>${gd.donors_remaining} more needed</span>
          </div>
        </div>`;
        }

        const actionBtn = item.is_group_donation && item.group_donation
            ? `<button class="btn btn-primary join-group-btn"
              data-gd-id="${item.group_donation.id}"
              data-crop-name="${this._esc(item.crop_name)}"
              data-org-name="${this._esc(item.organization_name)}"
              data-pledged="${item.group_donation.amount_pledged}"
              data-total="${item.group_donation.total_required}"
              data-donor-count="${item.group_donation.donors_count}"
              data-donors-needed="${item.group_donation.donors_needed}"
              data-donors-remaining="${item.group_donation.donors_remaining}">
              👥 Join Group Donation
            </button>`
            : `<button class="btn btn-primary donate-now-btn" data-item-id="${item.id}">
              🎁 Donate Now
           </button>`;

        return `
      <div class="donation-card">
        <div class="donation-card-header">
          <div>
            <span class="donation-org">${orgName}</span>
            <h4 class="donation-crop">${cropName}</h4>
          </div>
          <div class="donation-amount-badge">$${total}</div>
        </div>
        <div class="donation-card-body">
          <div class="donate-farmers-row">
            <span class="muted" style="font-size:.8rem;">Linked Farmers:</span>
            <div class="crop-chips">${farmers || "<span class='muted'>TBD</span>"}</div>
          </div>
          ${item.notes ? `<p class="donation-notes">${this._esc(item.notes)}</p>` : ""}
          ${groupBlock}
          <div class="donation-progress-row">
            <div class="donation-bar-wrap">
              <div class="donation-bar-fill" style="width:${pct}%"></div>
            </div>
            <span class="muted">$${donated} of $${total} donated (${pct}%)</span>
          </div>
        </div>
        <div class="donation-card-footer">
          ${actionBtn}
        </div>
      </div>`;
    },

    // ── Donate Now modal ─────────────────────────────────────────────────────

    async _openDonateModal(itemId) {
        try {
            const item = await this.api("GET", `/wishlist/${itemId}`);
            window._donateItem = item;

            document.getElementById("dCropName").textContent = item.crop_name;
            document.getElementById("dOrgName").textContent = item.organization_name;
            document.getElementById("dTotalAmt").textContent = parseFloat(item.total_amount_required).toFixed(2);
            document.getElementById("dAmtDonated").textContent = parseFloat(item.amount_donated).toFixed(2);
            const remaining = Math.max(0, item.total_amount_required - item.amount_donated);
            document.getElementById("dAmtRemaining").textContent = remaining.toFixed(2);

            // Populate farmer selector
            const sel = document.getElementById("donateSelectFarmer");
            sel.innerHTML = item.farmers.map(f =>
                `<option value="${f.farmer_id}">${this._esc(f.full_name || f.farm_name || "Farmer #" + f.farmer_id)}</option>`
            ).join("");

            document.getElementById("donateAmount").value = "";
            document.getElementById("donateError").classList.add("hidden");
            document.getElementById("donateModal").classList.remove("hidden");

            // Wire confirm button (replace to avoid duplicate listeners)
            const btn = document.getElementById("confirmDonateBtn");
            const newBtn = btn.cloneNode(true);
            btn.parentNode.replaceChild(newBtn, btn);
            newBtn.addEventListener("click", () => this._submitDonation(item.id));
        } catch (err) {
            this.showToast(`Could not load donation item: ${err.message}`, "error");
        }
    },

    async _submitDonation(itemId) {
        const errEl = document.getElementById("donateError");
        const farmerId = parseInt(document.getElementById("donateSelectFarmer").value);
        const amount = parseFloat(document.getElementById("donateAmount").value);

        if (!farmerId || isNaN(amount) || amount <= 0) {
            errEl.textContent = "Please enter a valid donation amount.";
            errEl.classList.remove("hidden");
            return;
        }
        errEl.classList.add("hidden");

        try {
            const result = await this.api("POST", "/donations/", {
                wishlist_item_id: itemId,
                farmer_id: farmerId,
                amount,
            });
            document.getElementById("donateModal").classList.add("hidden");
            this.showToast(
                `Donation confirmed! You earned ${result.points_earned} points 🎯`,
                "success"
            );
            this._loadDonationOpportunities();
        } catch (err) {
            errEl.textContent = err.message;
            errEl.classList.remove("hidden");
        }
    },

    // ── Group Donation modal ──────────────────────────────────────────────────

    _openGroupDonateModal(gdId, data) {
        window._pendingGdId = gdId;

        document.getElementById("gdCropName").textContent = data.cropName || "";
        document.getElementById("gdOrgName").textContent = data.orgName || "";
        document.getElementById("gdPledged").textContent = parseFloat(data.pledged || 0).toFixed(2);
        document.getElementById("gdTotal").textContent = parseFloat(data.total || 0).toFixed(2);
        document.getElementById("gdDonorCount").textContent = data.donorCount || "0";
        document.getElementById("gdDonorNeeded").textContent = data.donorsNeeded || "0";
        document.getElementById("gdDonorRemaining").textContent = data.donorsRemaining || "0";

        const pct = parseFloat(data.total) > 0
            ? Math.min(100, Math.round((parseFloat(data.pledged) / parseFloat(data.total)) * 100))
            : 0;
        document.getElementById("gdProgressFill").style.width = pct + "%";

        document.getElementById("groupDonateAmount").value = "";
        document.getElementById("groupDonateError").classList.add("hidden");
        document.getElementById("groupDonateModal").classList.remove("hidden");

        const btn = document.getElementById("confirmGroupDonateBtn");
        const newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);
        newBtn.addEventListener("click", () => this._submitGroupDonation(gdId));
    },

    async _submitGroupDonation(gdId) {
        const errEl = document.getElementById("groupDonateError");
        const amount = parseFloat(document.getElementById("groupDonateAmount").value);

        if (isNaN(amount) || amount <= 0) {
            errEl.textContent = "Please enter a valid pledge amount.";
            errEl.classList.remove("hidden");
            return;
        }
        errEl.classList.add("hidden");

        try {
            await this.api("POST", "/donations/group/join", {
                group_donation_id: gdId,
                amount,
            });
            document.getElementById("groupDonateModal").classList.add("hidden");
            this.showToast("You joined the group donation! Points will be awarded when fully funded. 🎯", "success");
            this._loadDonationOpportunities();
        } catch (err) {
            errEl.textContent = err.message;
            errEl.classList.remove("hidden");
        }
    },

    /* ═══════════════════════════════════════════════════════════════════════════
       PAGE: PROFILE SETTINGS
       ═══════════════════════════════════════════════════════════════════════════ */
    async initProfileSettings() {
        const user = this.user;
        if (!user) return;

        // Set subtitle
        const roleLabel = { farmer: "Farmer", organization: "Organization", consumer: "Consumer" }[user.user_type] || "User";
        document.getElementById("profileSubtitle").textContent = `${roleLabel} account settings`;

        // Show org name field for orgs and farmers (farm name)
        const orgNameGroup = document.getElementById("orgNameGroup");
        orgNameGroup.classList.toggle("hidden", user.user_type === "consumer");

        // Fill sidebar
        document.getElementById("profileEmail").textContent = user.email;
        document.getElementById("profileRole").textContent = roleLabel;
        document.getElementById("profileSince").textContent = "—";

        // Load full profile from API
        try {
            const profile = await this.api("GET", "/profiles/me");
            document.getElementById("profileFullName").value = profile.full_name || "";
            document.getElementById("profileOrgName").value = profile.organization_name || "";
            document.getElementById("profileCity").value = profile.location_city || "";
            document.getElementById("profileRegion").value = profile.location_region || "";
            document.getElementById("profilePhone").value = profile.phone || "";
        } catch { /* pre-fill from cache */ }

        // Show notification preferences only for consumers
        if (user.user_type === "consumer") {
            document.getElementById("notifPrefsCard").classList.remove("hidden");
            document.getElementById("profilePointsCard").classList.remove("hidden");
            this._loadNotificationPrefs();
            this._loadMiniPointsSummary();
        }

        // Save profile
        document.getElementById("saveProfileBtn")
            .addEventListener("click", () => this._saveProfile());

        // Donation notification toggle shows/hides price range
        document.getElementById("donationNotifToggle")
            .addEventListener("change", e => {
                document.getElementById("donationPriceRange")
                    .classList.toggle("hidden", !e.target.checked);
            });

        // Save notification prefs
        document.getElementById("saveNotifPrefsBtn")
            ?.addEventListener("click", () => this._saveNotifPrefs());

        // Points shortcut
        document.getElementById("goToPointsBtn")
            ?.addEventListener("click", () => this.navigate("points_rewards"));
    },

    async _saveProfile() {
        const successEl = document.getElementById("profileSuccess");
        const errEl = document.getElementById("profileError");
        successEl.classList.add("hidden");
        errEl.classList.add("hidden");

        const payload = {
            full_name: document.getElementById("profileFullName").value.trim() || null,
            organization_name: document.getElementById("profileOrgName").value.trim() || null,
            location_city: document.getElementById("profileCity").value.trim() || null,
            location_region: document.getElementById("profileRegion").value || null,
            phone: document.getElementById("profilePhone").value.trim() || null,
        };

        try {
            const updated = await this.api("PATCH", "/profiles/me", payload);
            // Update cached user
            this._saveAuth(this.token, { ...this.user, ...updated });
            this._renderNav();
            successEl.classList.remove("hidden");
        } catch (err) {
            errEl.textContent = err.message;
            errEl.classList.remove("hidden");
        }
    },

    async _loadNotificationPrefs() {
        try {
            const prefs = await this.api("GET", "/profiles/me/notifications");
            document.getElementById("donationNotifToggle").checked = prefs.donation_notifications_enabled;
            document.getElementById("groupDonationNotifToggle").checked = prefs.group_donation_notifications_enabled;
            document.getElementById("donationMinPrice").value = prefs.donation_min_price ?? "";
            document.getElementById("donationMaxPrice").value = prefs.donation_max_price ?? "";
            // Show price range if notifications enabled
            document.getElementById("donationPriceRange")
                .classList.toggle("hidden", !prefs.donation_notifications_enabled);
        } catch { /* ignore — defaults are false */ }
    },

    async _saveNotifPrefs() {
        const successEl = document.getElementById("notifSuccess");
        const errEl = document.getElementById("notifError");
        successEl.classList.add("hidden");
        errEl.classList.add("hidden");

        const minPrice = document.getElementById("donationMinPrice").value;
        const maxPrice = document.getElementById("donationMaxPrice").value;

        const payload = {
            donation_notifications_enabled: document.getElementById("donationNotifToggle").checked,
            donation_min_price: minPrice ? parseFloat(minPrice) : null,
            donation_max_price: maxPrice ? parseFloat(maxPrice) : null,
            group_donation_notifications_enabled: document.getElementById("groupDonationNotifToggle").checked,
        };

        try {
            await this.api("PATCH", "/profiles/me/notifications", payload);
            successEl.classList.remove("hidden");
        } catch (err) {
            errEl.textContent = err.message;
            errEl.classList.remove("hidden");
        }
    },

    async _loadMiniPointsSummary() {
        try {
            const data = await this.api("GET", "/points/me");
            document.getElementById("profilePointsTotal").textContent = data.total_points;
        } catch { /* ignore */ }
    },

    /* ═══════════════════════════════════════════════════════════════════════════
       PAGE: POINTS & REWARDS
       ═══════════════════════════════════════════════════════════════════════════ */
    async initPointsRewards() {
        const loading = document.getElementById("pointsLoading");
        const empty = document.getElementById("pointsEmpty");
        const hist = document.getElementById("pointsHistory");

        try {
            const data = await this.api("GET", "/points/me");
            loading?.classList.add("hidden");

            const total = data.total_points;
            document.getElementById("pointsTotalLabel").textContent = `You have ${total} points`;
            document.getElementById("totalPointsDisplay").textContent = total.toLocaleString();
            document.getElementById("historyCount").textContent = `${data.history.length} transaction(s)`;

            // Determine current tier
            const reached = data.tiers.filter(t => t.reached);
            const currentTier = reached.length > 0
                ? `Tier ${reached[reached.length - 1].tier}` : "None";
            document.getElementById("currentTierDisplay").textContent = currentTier;
            document.getElementById("ptsToNextDisplay").textContent = data.next_tier_pts
                ? (data.next_tier_pts - total).toLocaleString() + " pts"
                : "Max tier!";

            // Update tier rows
            data.tiers.forEach(t => {
                const row = document.getElementById(`tierRow${t.tier}`);
                const circle = document.getElementById(`tier${t.tier}Circle`);
                const status = document.getElementById(`tier${t.tier}Status`);
                if (t.reached) {
                    row?.classList.add("tier-reached");
                    circle?.classList.add("tier-circle-reached");
                    if (status) status.innerHTML = `<span class="badge badge-green">Unlocked ✓</span>`;
                } else {
                    if (status) status.innerHTML = `<span class="badge badge-gray">Locked</span>`;
                }
            });

            // Vertical bar fill
            // Bar spans 0 → max tier (3000 pts)
            const maxPts = 3000;
            const fillPct = Math.min(100, Math.round((total / maxPts) * 100));
            const barFill = document.getElementById("vbarFill");
            if (barFill) {
                // Animate fill
                barFill.style.height = "0%";
                requestAnimationFrame(() => {
                    barFill.style.transition = "height 1.2s cubic-bezier(.4,0,.2,1)";
                    barFill.style.height = fillPct + "%";
                });
            }

            // Next tier hint
            const hintEl = document.getElementById("nextTierHint");
            if (hintEl) {
                hintEl.querySelector("span").textContent = data.next_tier_pts
                    ? `${(data.next_tier_pts - total).toLocaleString()} more points to Tier ${reached.length + 1}!`
                    : "🏆 You've reached the highest tier!";
            }

            // History
            if (!data.history.length) {
                empty?.classList.remove("hidden");
            } else {
                hist?.classList.remove("hidden");
                hist.innerHTML = data.history.map(e => `
          <div class="points-history-row">
            <div>
              <strong class="points-hist-pts">+${e.points} pts</strong>
              <span class="muted" style="margin-left:.5rem;">${e.description || "Donation"}</span>
            </div>
            <span class="muted">${new Date(e.created_at).toLocaleDateString()}</span>
          </div>`).join("");
            }
        } catch (err) {
            loading?.classList.add("hidden");
            this.showToast(`Failed to load points: ${err.message}`, "error");
        }
    },

    /* ═══════════════════════════════════════════════════════════════════════════
       PAGE: WISHLIST MANAGE (Organization)
       ═══════════════════════════════════════════════════════════════════════════ */
    initWishlistManage() {
        // Cache of all farmers fetched from the server
        this._wishlistFarmerCache = null;

        // Toggle add form — pre-load farmers the first time it opens
        const addBtn = document.getElementById("toggleAddWishlistBtn");
        const cancelBtn = document.getElementById("cancelAddWishlistBtn");
        const addForm = document.getElementById("addWishlistForm");
        addBtn.addEventListener("click", () => {
            addForm.classList.remove("hidden");
            this._preloadFarmersForWishlist();
        });
        cancelBtn.addEventListener("click", () => addForm.classList.add("hidden"));

        // Group donation toggle shows donors_needed
        document.getElementById("wlIsGroupDonation").addEventListener("change", e => {
            document.getElementById("wlDonorsNeededGroup").classList.toggle("hidden", !e.target.checked);
        });

        // Farmer search — filter the cached list on input or button click
        document.getElementById("farmerSearchInput")
            .addEventListener("input", () => this._filterFarmersForWishlist());
        document.getElementById("searchFarmersBtn")
            .addEventListener("click", () => {
                // Clear cache so newly-registered farmers are always fetched fresh
                this._wishlistFarmerCache = null;
                this._preloadFarmersForWishlist();
            });
        document.getElementById("farmerSearchInput")
            .addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); this._filterFarmersForWishlist(); } });

        // Submit wishlist item
        document.getElementById("addWishlistFormEl")
            .addEventListener("submit", e => { e.preventDefault(); this._submitWishlistItem(); });

        // Modal close
        document.getElementById("closeWishlistDetailModal")
            .addEventListener("click", () =>
                document.getElementById("wishlistDetailModal").classList.add("hidden")
            );

        // Load existing items
        this._loadMyWishlist();
    },

    // Pre-load ALL farmers from the server once and cache them.
    async _preloadFarmersForWishlist() {
        const resultsEl = document.getElementById("farmerSearchResults");
        if (this._wishlistFarmerCache !== null) {
            // Already loaded — just show the full list
            this._renderFarmerSearchResults(this._wishlistFarmerCache, "");
            return;
        }
        resultsEl.innerHTML = `<p class="muted" style="padding:.5rem .9rem">Loading farmers…</p>`;
        resultsEl.classList.remove("hidden");
        try {
            const farmers = await this.api("GET", "/farmers/search");
            this._wishlistFarmerCache = Array.isArray(farmers) ? farmers : [];
            this._renderFarmerSearchResults(this._wishlistFarmerCache, "");
        } catch (err) {
            resultsEl.innerHTML = `<p class="muted" style="padding:.5rem .9rem;color:var(--red)">Could not load farmers: ${this._esc(err.message)}</p>`;
        }
    },

    // Filter the cached farmer list by the current input value.
    _filterFarmersForWishlist() {
        if (!this._wishlistFarmerCache) {
            // Cache not loaded yet — trigger pre-load which will show results when done
            this._preloadFarmersForWishlist();
            return;
        }
        const query = document.getElementById("farmerSearchInput").value.trim().toLowerCase();
        const filtered = query
            ? this._wishlistFarmerCache.filter(f => {
                const name = (f.full_name || f.organization_name || "").toLowerCase();
                const city = (f.location_city || "").toLowerCase();
                const region = (f.location_region || "").toLowerCase();
                return name.includes(query) || city.includes(query) || region.includes(query);
            })
            : this._wishlistFarmerCache;
        this._renderFarmerSearchResults(filtered, query);
    },

    _renderFarmerSearchResults(farmers, query) {
        const resultsEl = document.getElementById("farmerSearchResults");
        if (!farmers.length) {
            resultsEl.innerHTML = query
                ? `<p class="muted" style="padding:.5rem .9rem">No farmers match "${this._esc(query)}".</p>`
                : `<p class="muted" style="padding:.5rem .9rem">No farmers registered yet.</p>`;
        } else {
            resultsEl.innerHTML = farmers.map(f => {
                const name = this._esc(f.full_name || f.organization_name || "Farmer #" + f.id);
                const location = this._esc(f.location_city || f.location_region || "");
                return `<div class="farmer-search-result" data-id="${f.id}" data-name="${name}">
                  <strong>${name}</strong>
                  <span class="muted">${location}</span>
                </div>`;
            }).join("");
            resultsEl.querySelectorAll(".farmer-search-result").forEach(row => {
                row.addEventListener("click", () => this._addFarmerToWishlist(
                    parseInt(row.dataset.id), row.dataset.name
                ));
            });
        }
        resultsEl.classList.remove("hidden");
    },

    _addFarmerToWishlist(farmerId, farmerName) {
        const existing = JSON.parse(document.getElementById("wlFarmerIds").value);
        if (existing.includes(farmerId)) return;

        const updated = [...existing, farmerId];
        document.getElementById("wlFarmerIds").value = JSON.stringify(updated);

        const chip = document.createElement("span");
        chip.className = "crop-chip farmer-chip";
        chip.dataset.id = farmerId;
        chip.innerHTML = `${this._esc(farmerName)} <button type="button" class="chip-remove" data-id="${farmerId}">✕</button>`;
        chip.querySelector(".chip-remove").addEventListener("click", () => {
            chip.remove();
            const ids = JSON.parse(document.getElementById("wlFarmerIds").value)
                .filter(id => id !== farmerId);
            document.getElementById("wlFarmerIds").value = JSON.stringify(ids);
        });
        document.getElementById("selectedFarmers").appendChild(chip);
        document.getElementById("farmerSearchResults").classList.add("hidden");
    },

    async _submitWishlistItem() {
        const errEl = document.getElementById("addWishlistError");
        errEl.classList.add("hidden");

        const farmerIds = JSON.parse(document.getElementById("wlFarmerIds").value);
        if (!farmerIds.length) {
            errEl.textContent = "Please select at least one farmer.";
            errEl.classList.remove("hidden");
            return;
        }

        const isGroup = document.getElementById("wlIsGroupDonation").checked;
        const donorsNeeded = parseInt(document.getElementById("wlDonorsNeeded").value);
        if (isGroup && (!donorsNeeded || donorsNeeded < 2)) {
            errEl.textContent = "Group donations require at least 2 donors needed.";
            errEl.classList.remove("hidden");
            return;
        }

        const payload = {
            crop_name: document.getElementById("wlCropName").value.trim(),
            quantity_needed: document.getElementById("wlQty").value.trim(),
            quantity_unit: document.getElementById("wlUnit").value,
            total_amount_required: parseFloat(document.getElementById("wlAmount").value),
            notes: document.getElementById("wlNotes").value.trim() || null,
            is_group_donation: isGroup,
            farmer_ids: farmerIds,
            donors_needed: isGroup ? donorsNeeded : undefined,
        };

        try {
            await this.api("POST", "/wishlist/", payload);
            this.showToast("Wishlist item created!", "success");
            document.getElementById("addWishlistForm").classList.add("hidden");
            document.getElementById("addWishlistFormEl").reset();
            document.getElementById("wlFarmerIds").value = "[]";
            document.getElementById("selectedFarmers").innerHTML = "";
            this._loadMyWishlist();
        } catch (err) {
            errEl.textContent = err.message;
            errEl.classList.remove("hidden");
        }
    },

    async _loadMyWishlist() {
        const loading = document.getElementById("wishlistLoading");
        const empty = document.getElementById("wishlistEmpty");
        const grid = document.getElementById("wishlistGrid");
        if (!grid) return;

        loading?.classList.remove("hidden");
        empty?.classList.add("hidden");
        grid.innerHTML = "";

        try {
            const items = await this.api("GET", "/wishlist/mine");
            loading?.classList.add("hidden");

            if (!items || !items.length) {
                empty?.classList.remove("hidden");
                return;
            }

            grid.innerHTML = items.map(item => this._renderWishlistOrgCard(item)).join("");

            // Cancel button listeners
            grid.querySelectorAll(".cancel-wishlist-btn").forEach(btn => {
                btn.addEventListener("click", () => this._cancelWishlistItem(parseInt(btn.dataset.id)));
            });
        } catch (err) {
            loading?.classList.add("hidden");
            this.showToast(`Failed to load wishlist: ${err.message}`, "error");
        }
    },

    _renderWishlistOrgCard(item) {
        const donated = parseFloat(item.amount_donated).toFixed(2);
        const total = parseFloat(item.total_amount_required).toFixed(2);
        const pct = Math.min(100, Math.round((item.amount_donated / item.total_amount_required) * 100));
        const farmers = item.farmers.map(f =>
            `<span class="crop-chip">${this._esc(f.full_name || f.farm_name || "Farmer #" + f.farmer_id)}</span>`
        ).join("");

        const statusClass = { open: "badge-green", funded: "badge-amber", fulfilled: "badge-green", cancelled: "badge-gray" }[item.status] || "badge-gray";

        let groupBlock = "";
        if (item.is_group_donation && item.group_donation) {
            const gd = item.group_donation;
            groupBlock = `<div class="group-badge">👥 Group: ${gd.donors_count}/${gd.donors_needed} donors · $${parseFloat(gd.amount_pledged).toFixed(2)}/$${parseFloat(gd.total_required).toFixed(2)} pledged</div>`;
        }

        return `
      <div class="wishlist-card">
        <div class="wishlist-card-header">
          <h4>${this._esc(item.crop_name)}</h4>
          <span class="badge ${statusClass}">${item.status}</span>
        </div>
        <p class="muted">${this._esc(item.quantity_needed)} ${this._esc(item.quantity_unit)}</p>
        ${item.notes ? `<p class="donation-notes">${this._esc(item.notes)}</p>` : ""}
        <div class="crop-chips" style="margin:.5rem 0;">${farmers || "<span class='muted'>No farmers linked</span>"}</div>
        ${groupBlock}
        <div class="donation-bar-wrap" style="margin:.5rem 0;">
          <div class="donation-bar-fill" style="width:${pct}%"></div>
        </div>
        <p class="muted">$${donated} / $${total} funded (${pct}%)</p>
        <div class="form-actions" style="margin-top:.75rem;">
          ${item.status === "open"
                ? `<button class="btn btn-danger btn-sm cancel-wishlist-btn" data-id="${item.id}">Cancel Item</button>`
                : ""}
        </div>
      </div>`;
    },

    async _cancelWishlistItem(itemId) {
        if (!confirm("Cancel this wishlist item? This cannot be undone.")) return;
        try {
            await this.api("DELETE", `/wishlist/${itemId}`);
            this.showToast("Wishlist item cancelled.", "success");
            this._loadMyWishlist();
        } catch (err) {
            this.showToast(`Cancel failed: ${err.message}`, "error");
        }
    },

    /* ═══════════════════════════════════════════════════════════════════════════
       UTILITIES
       ═══════════════════════════════════════════════════════════════════════════ */
    _esc(str) {
        if (str == null) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    },
};

// Bootstrap on DOM ready
document.addEventListener("DOMContentLoaded", () => App.init());
