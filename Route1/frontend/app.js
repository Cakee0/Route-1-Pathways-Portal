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
const PROD_API_BASE = "https://api.route1pathways.app";   // AWS EC2 backend (Caddy HTTPS)
const API_BASE =
    (location.hostname === "localhost" || location.hostname === "127.0.0.1")
        ? "http://localhost:8000"
        : PROD_API_BASE;

// Google Sign-In: paste your OAuth 2.0 "Web application" client ID here.
// Must match GOOGLE_CLIENT_ID in the backend .env. Leave blank to hide the
// "Sign in with Google" buttons entirely.
const GOOGLE_CLIENT_ID = "398142413341-n6glr5jnmh60li4nmefnh5fdehr3u00p.apps.googleusercontent.com";

// Listing-detail map: cities are geocoded through the free OSM Nominatim API
// (cached in localStorage, ~1 request/sec per their usage policy). When a city
// can't be geocoded we fall back to the approximate center of the farmer's
// Minnesota region below; if that's missing too, the farmer gets no marker.
const NOMINATIM_BASE = "https://nominatim.openstreetmap.org/search";
const REGION_CENTROIDS = {
    "Twin Cities Metro":   { lat: 44.98, lng: -93.30 },
    "Central Minnesota":   { lat: 45.60, lng: -94.40 },
    "Southern Minnesota":  { lat: 43.85, lng: -93.40 },
    "Northern Minnesota":  { lat: 47.40, lng: -92.80 },
    "Northwest Minnesota": { lat: 47.80, lng: -95.90 },
    "Southwest Minnesota": { lat: 44.10, lng: -95.60 },
    "Southeast Minnesota": { lat: 43.95, lng: -92.30 },
};
const MN_CENTER = { lat: 46.3, lng: -94.2 };

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
        if (res.status === 401 && this.token) {
            // JWT expired (60-min lifetime, no refresh) — same steps as logout()
            this._clearAuth();
            this._renderNav();
            this.navigate("login");
            this.showToast("Your session expired — please log in again.", "error");
            throw new Error("Session expired.");
        }
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
        window.addEventListener("hashchange", () => {
            if (location.hash === this._lastAppliedHash) return; // set by navigate(); already applied
            this._routeFromHash();
        });
        this._routeFromHash();
    },

    /* ═══════════════════════════════════════════════════════════════════════════
       NAVIGATION
       Hash routing: every view has a URL (#/, #/login, #/register, …) so the
       browser Back button works and pages can be linked/bookmarked.
       ═══════════════════════════════════════════════════════════════════════════ */
    _hashFor(page, register = false, opts = {}) {
        if (register) return "#/register";
        if (page === "listing_detail") return "#/listing/" + opts.listingId;
        const map = {
            landing: "#/",
            about: "#/about",
            contact: "#/contact",
            login: "#/login",
            farmer_dashboard: "#/dashboard",
            org_dashboard: "#/dashboard",
            consumer_dashboard: "#/dashboard",
            messaging: "#/messages",
            profile_settings: "#/profile",
            points_rewards: "#/points",
            wishlist_manage: "#/wishlist",
        };
        return map[page] || "#/";
    },

    _routeFromHash() {
        const h = location.hash || "#/";
        const loggedIn = !!(this.token && this.user);

        // Stripe redirects the browser back here after hosted checkout. These
        // screens render directly (no HTML component) and, for success, poll
        // the donation until the webhook confirms it.
        if (h.startsWith("#/donation/success")) {
            return this._renderDonationResult("success", this._hashQuery(h));
        }
        if (h.startsWith("#/donation/cancel")) {
            return this._renderDonationResult("cancel", this._hashQuery(h));
        }

        const listingMatch = h.match(/^#\/listing\/(\d+)$/);
        if (listingMatch) {
            return loggedIn
                ? this.navigate("listing_detail", { listingId: parseInt(listingMatch[1], 10) })
                : this.navigate("login");
        }
        if (h === "#/login") return loggedIn ? this._navigateToHomeDashboard() : this.navigate("login");
        if (h === "#/register") return loggedIn ? this._navigateToHomeDashboard() : this.navigate("login", { register: true });
        if (h === "#/about") return this.navigate("about");
        if (h === "#/contact") return this.navigate("contact");
        if (h === "#/messages") return loggedIn ? this.navigate("messaging") : this.navigate("login");
        if (h === "#/profile") return loggedIn ? this.navigate("profile_settings") : this.navigate("login");
        if (h === "#/points") return loggedIn ? this.navigate("points_rewards") : this.navigate("login");
        if (h === "#/wishlist") return loggedIn ? this.navigate("wishlist_manage") : this.navigate("login");
        // "#/", "#/dashboard", and anything unrecognized → home
        return loggedIn ? this._navigateToHomeDashboard() : this.navigate("landing");
    },

    async navigate(page, opts = {}) {
        // Stop any active messaging poll
        if (this.messagingPollTimer) {
            clearInterval(this.messagingPollTimer);
            this.messagingPollTimer = null;
        }

        // Tear down the listing-detail map (its container is about to be removed;
        // Leaflet throws "container already initialized" on revisit otherwise)
        if (this._listingMap) {
            this._listingMap.remove();
            this._listingMap = null;
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
            listing_detail: "components/listing_detail.html",
            messaging: "components/messaging.html",
            profile_settings: "components/profile_settings.html",
            points_rewards: "components/points_rewards.html",
            wishlist_manage: "components/wishlist_manage.html",
        };

        const htmlPath = componentMap[page];
        if (!htmlPath) { console.error("Unknown page:", page); return; }

        const appEl = document.getElementById("app");
        try {
            // Versioned URL does the cache-busting; letting the HTTP cache work
            // makes repeat navigations instant (was cache: "no-store")
            const res = await fetch(htmlPath + "?v=20260711");
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            appEl.innerHTML = await res.text();
            appEl.classList.toggle("is-landing", page === "landing");
            this._track("/" + page);
        } catch (e) {
            appEl.classList.remove("is-landing");
            appEl.innerHTML = `
        <div class="load-error">
          <h2>We couldn't load that page</h2>
          <p>It's probably a connection hiccup — check your internet and try again.</p>
          <div class="load-error-actions">
            <button class="btn btn-primary" id="loadRetryBtn">Try again</button>
            <button class="btn btn-secondary" id="loadHomeBtn">Go to home</button>
          </div>
        </div>`;
            document.getElementById("loadRetryBtn")
                ?.addEventListener("click", () => this.navigate(page, opts));
            document.getElementById("loadHomeBtn")
                ?.addEventListener("click", () =>
                    (this.token && this.user) ? this._navigateToHomeDashboard() : this.navigate("landing"));
            return;
        }

        // Per-view title + URL (history entry) so Back/bookmarks/sharing work
        const titles = {
            landing: "Route 1 Pathways — Minnesota Food Rescue Marketplace",
            about: "About us — Route 1 Pathways",
            contact: "Contact us — Route 1 Pathways",
            login: "Log in — Route 1 Pathways",
            farmer_dashboard: "Farmer dashboard — Route 1 Pathways",
            org_dashboard: "Browse listings & wishlist — Route 1 Pathways",
            consumer_dashboard: "Browse listings — Route 1 Pathways",
            listing_detail: "Listing details — Route 1 Pathways",
            messaging: "Messages — Route 1 Pathways",
            profile_settings: "Profile settings — Route 1 Pathways",
            points_rewards: "My points — Route 1 Pathways",
            wishlist_manage: "Wishlist — Route 1 Pathways",
        };
        document.title = opts.register
            ? "Create your free account — Route 1 Pathways"
            : (titles[page] || "Route 1 Pathways");
        const targetHash = this._hashFor(page, !!opts.register, opts);
        this._lastAppliedHash = targetHash;
        if (location.hash !== targetHash) location.hash = targetHash;

        // Call page init
        const inits = {
            landing: () => this.initLanding(),
            about: () => this.initAbout(),
            contact: () => this.initContact(),
            login: () => this.initLogin(),
            farmer_dashboard: () => this.initFarmerDashboard(),
            org_dashboard: () => this.initBrowseDashboard("org"),
            consumer_dashboard: () => this.initConsumerDashboard(),
            listing_detail: () => this.initListingDetail(opts.listingId),
            messaging: () => this.initMessaging(),
            profile_settings: () => this.initProfileSettings(),
            points_rewards: () => this.initPointsRewards(),
            wishlist_manage: () => this.initWishlistManage(),
        };
        inits[page]?.();

        // Scroll-reveal for any page that marks furniture with .reveal
        // (progressive enhancement — content stays visible without JS)
        this._initReveals();

        // Deep-linked register (#/register): open the Create Account tab, and say
        // so if the tab isn't there instead of silently landing on the login form.
        if (opts.register && page === "login") {
            const tab = document.getElementById("showRegisterTab");
            if (tab) tab.click();
            else this.showToast('Use the "Create Account" tab above to sign up.', "error");
        }
    },

    // Every "create account" entry point funnels through here
    openRegister() {
        return this.navigate("login", { register: true });
    },

    /* ═══════════════════════════════════════════════════════════════════════════
       ACCESSIBLE MODALS
       One open/close pair for every overlay: dialog semantics, Esc to close,
       focus moved in on open and returned on close, Tab kept inside.
       ═══════════════════════════════════════════════════════════════════════════ */
    _openModal(id) {
        const overlay = document.getElementById(id);
        if (!overlay) return;
        if (this._modalKeyHandler) {
            document.removeEventListener("keydown", this._modalKeyHandler);
            this._modalKeyHandler = null;
        }
        overlay.setAttribute("role", "dialog");
        overlay.setAttribute("aria-modal", "true");
        const heading = overlay.querySelector("h1, h2, h3");
        if (heading) {
            if (!heading.id) heading.id = `${id}Title`;
            overlay.setAttribute("aria-labelledby", heading.id);
        }
        overlay.classList.remove("hidden");

        this._modalReturnFocus = document.activeElement;
        this._modalKeyHandler = (e) => {
            if (e.key === "Escape") { e.preventDefault(); this._closeModal(id); return; }
            if (e.key !== "Tab") return;
            const focusables = [...overlay.querySelectorAll(
                'button, [href], input:not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])'
            )].filter(el => !el.disabled && el.offsetParent);
            if (!focusables.length) return;
            const first = focusables[0], last = focusables[focusables.length - 1];
            if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
            else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
        };
        document.addEventListener("keydown", this._modalKeyHandler);

        const target = overlay.querySelector('input:not([type="hidden"]), select, textarea, button');
        target?.focus();
    },

    _closeModal(id) {
        const overlay = document.getElementById(id);
        if (overlay) overlay.classList.add("hidden");
        if (this._modalKeyHandler) {
            document.removeEventListener("keydown", this._modalKeyHandler);
            this._modalKeyHandler = null;
        }
        this._modalReturnFocus?.focus?.();
        this._modalReturnFocus = null;
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
                .addEventListener("click", () => this.openRegister());
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
    /* ═══════════════════════════════════════════════════════════════════════════
       ANALYTICS (GoatCounter — see index.html; no-op if blocked or not loaded)
       ═══════════════════════════════════════════════════════════════════════════ */
    _track(path, isEvent = false) {
        try {
            if (window.goatcounter && window.goatcounter.count) {
                window.goatcounter.count({ path, event: isEvent });
            }
        } catch { /* analytics must never break the app */ }
    },

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
        document.getElementById("aboutCreateBtn")
            ?.addEventListener("click", () => this.openRegister());
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
        // CTAs are real links (#/register, #/login) — hash routing handles them.
        // Scroll reveals are wired site-wide by _initReveals() in navigate().
    },

    // Scroll-reveal (progressive enhancement; CSS handles reduced-motion).
    // Any page fragment can opt in by putting .reveal on its furniture.
    _initReveals() {
        const root = document.getElementById("app");
        const reveals = root?.querySelectorAll(".reveal");
        if (!root || !reveals?.length || !("IntersectionObserver" in window)) return;
        root.classList.add("js-reveal");
        const io = new IntersectionObserver((entries) => {
            entries.forEach(e => {
                if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
            });
        }, { threshold: 0.15 });
        reveals.forEach(el => io.observe(el));
    },

    initLogin() {
        const loginTab = document.getElementById("showLoginTab");
        const registerTab = document.getElementById("showRegisterTab");
        const loginPanel = document.getElementById("loginPanel");
        const regPanel = document.getElementById("registerPanel");

        const selectTab = (on, off, showPanel, hidePanel) => {
            on.classList.add("active");
            off.classList.remove("active");
            on.setAttribute("aria-selected", "true");
            off.setAttribute("aria-selected", "false");
            showPanel.classList.remove("hidden");
            hidePanel.classList.add("hidden");
        };
        loginTab.addEventListener("click", () => selectTab(loginTab, registerTab, loginPanel, regPanel));
        registerTab.addEventListener("click", () => selectTab(registerTab, loginTab, regPanel, loginPanel));

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
                const isFarmer = selected === "farmer";
                document.getElementById("orgSubtypeGroup").classList.toggle("hidden", !isOrg);
                document.getElementById("orgNameGroup").classList.toggle("hidden", isConsumer);
                if (isFarmer) {
                    document.getElementById("orgNameLabel").textContent = "Farm Name";
                } else if (isOrg) {
                    document.getElementById("orgNameLabel").textContent = "Organization Name";
                }
                // Location is required for farmers (the browse map depends on it)
                document.getElementById("regCityReq")?.classList.toggle("hidden", !isFarmer);
                document.getElementById("regRegionReq")?.classList.toggle("hidden", !isFarmer);
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
            const regPassword = document.getElementById("regPassword").value;
            if (regPassword.length < 8) {
                errEl.textContent = "Password must be at least 8 characters.";
                errEl.classList.remove("hidden");
                return;
            }
            if (userType === "farmer"
                && (!document.getElementById("regCity").value.trim()
                    || !document.getElementById("regRegion").value)) {
                errEl.textContent = "Farmers must provide their Minnesota city and region so buyers can find them.";
                errEl.classList.remove("hidden");
                return;
            }

            const payload = {
                email: document.getElementById("regEmail").value.trim(),
                password: regPassword,
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
                const gType = document.querySelector("input[name='gUserType']:checked")?.value;
                document.getElementById("gOrgSubtypeGroup").classList.toggle("hidden", gType !== "organization");
                document.getElementById("gLocationGroup")?.classList.toggle("hidden", gType !== "farmer");
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
        const gCity = document.getElementById("gCity")?.value.trim() || null;
        const gRegion = document.getElementById("gRegion")?.value || null;
        if (userType === "farmer" && (!gCity || !gRegion)) {
            errEl.textContent = "Farmers must provide their Minnesota city and region so buyers can find them.";
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
                location_city: userType === "farmer" ? gCity : null,
                location_region: userType === "farmer" ? gRegion : null,
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
                quantity_available: parseFloat(document.getElementById("cropQty").value),
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
                this._closeModal("editCropModal")
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
                quantity_available: parseFloat(document.getElementById("editCropQty").value),
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
                this._closeModal("editCropModal");
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
        this._openModal("editCropModal");
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
            heading.textContent = "Browse Crop Listings";
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

        // Restore the last-used filters (e.g. returning from a listing detail
        // page), then load
        const saved = this._browseFilters;
        if (saved) {
            const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v || ""; };
            setVal("filterCrop", saved.crop);
            setVal("filterRegion", saved.region);
            setVal("filterCity", saved.city);
            setVal("filterMinPrice", saved.minPrice);
            setVal("filterMaxPrice", saved.maxPrice);
            const tEl = document.getElementById("filterTransport");
            if (tEl) tEl.checked = !!saved.transport;
            const dEl = document.getElementById("filterDonation");
            if (dEl) dEl.checked = !!saved.donation;
        }
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

        // Remembered so returning from a listing detail page restores the search
        this._browseFilters = { crop, region, city, minPrice, maxPrice, transport, donation };

        const qs = params.toString();

        try {
            const listings = await this.api("GET", `/listings${qs ? "?" + qs : ""}`);
            loading.classList.add("hidden");

            if (!listings || listings.length === 0) {
                empty.classList.remove("hidden");
                if (count) count.textContent = "No results";
                return;
            }
            if (count) count.textContent = `${listings.length} listing${listings.length === 1 ? "" : "s"} found`;

            grid.innerHTML = listings.map(l => this._renderListingCard(l)).join("");
        } catch (err) {
            loading.classList.add("hidden");
            this.showToast(`Browse failed: ${err.message}`, "error");
        }
    },

    _renderListingCard(l) {
        const crop = this._esc(l.crop_name);
        const qty = `${this._esc(l.quantity_available)} ${this._esc(l.quantity_unit)}`;
        const price = l.price_per_unit != null
            ? `$${Number(l.price_per_unit).toFixed(2)} / ${this._esc(l.quantity_unit)}`
            : "Price on request";
        const farm = this._esc(l.farm_name || l.farmer_name || "Local farmer");
        const location = [this._esc(l.location_city || ""), this._esc(l.location_region || "")]
            .filter(Boolean).join(", ");
        const snippet = l.description
            ? this._esc(l.description.length > 90 ? l.description.slice(0, 90) + "…" : l.description)
            : "";

        const badges = [];
        if (l.donation_eligible) badges.push('<span class="badge badge-green">🎁 Donation eligible</span>');
        if (l.can_provide_transport) badges.push('<span class="badge badge-amber">🚚 Can transport</span>');

        return `
      <a class="farmer-card listing-card" href="#/listing/${l.id}"
        aria-label="${crop}, ${qty}, ${this._esc(price)}, from ${farm}">
        <div class="farmer-card-header">
          <h4>${crop} · ${qty}</h4>
          <div class="listing-price">${price}</div>
        </div>
        <div class="farmer-card-body">
          ${snippet ? `<p class="listing-snippet">${snippet}</p>` : ""}
          ${badges.length ? `<div class="listing-badges">${badges.join("")}</div>` : ""}
          <div class="listing-farmer-line">🌾 ${farm}${location ? ` · 📍 ${location}` : ""}</div>
        </div>
      </a>`;
    },

    /* ═══════════════════════════════════════════════════════════════════════════
       PAGE: LISTING DETAIL (#/listing/<id>)
       Full info on one crop listing, with the farmer's info below it.
       ═══════════════════════════════════════════════════════════════════════════ */
    async initListingDetail(id) {
        const loading = document.getElementById("listingLoading");
        const errBox = document.getElementById("listingError");
        const content = document.getElementById("listingContent");

        const goBack = () => this._navigateToHomeDashboard();
        document.getElementById("listingBackBtn")?.addEventListener("click", goBack);
        document.getElementById("listingErrorBackBtn")?.addEventListener("click", goBack);

        try {
            const l = await this.api("GET", `/listings/${id}`);
            loading.classList.add("hidden");
            document.title = `${l.crop_name} — Route 1 Pathways`;
            content.innerHTML = this._renderListingDetail(l);
            content.classList.remove("hidden");

            document.getElementById("msgFarmerBtn")?.addEventListener("click", () => {
                this.pendingMessageTo = {
                    id: l.farmer.id,
                    name: l.farmer.full_name || l.farmer.organization_name || "Farmer",
                };
                this.navigate("messaging");
            });

            // Fill in the map beside the listing (not awaited — the page is
            // already usable; the panel stays hidden if the map can't load)
            this._initListingMap(l);
        } catch (err) {
            loading.classList.add("hidden");
            errBox.classList.remove("hidden");
        }
    },

    _renderListingDetail(l) {
        const crop = this._esc(l.crop_name);
        const qty = `${this._esc(l.quantity_available)} ${this._esc(l.quantity_unit)}`;
        const price = l.price_per_unit != null
            ? `$${Number(l.price_per_unit).toFixed(2)} / ${this._esc(l.quantity_unit)}`
            : "Price on request";
        const listed = l.created_at
            ? new Date(l.created_at).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })
            : "";

        const badges = [];
        if (l.donation_eligible) badges.push('<span class="badge badge-green">🎁 Donation eligible</span>');
        if (l.can_provide_transport) badges.push('<span class="badge badge-amber">🚚 Can provide transport</span>');
        if (l.needs_transport) badges.push('<span class="badge badge-gray">📦 Needs transport</span>');

        const f = l.farmer;
        const farmerName = this._esc(f.full_name || f.organization_name || "Farmer");
        const farmName = f.organization_name ? this._esc(f.organization_name) : "";
        const location = [this._esc(f.location_city || ""), this._esc(f.location_region || "")]
            .filter(Boolean).join(", ") || "Location not specified";

        return `
      <div class="card">
        <h2 class="listing-title">${crop}</h2>
        <div class="listing-detail-meta">
          <div class="listing-detail-row">
            <span class="listing-detail-label">Quantity</span>
            <span class="listing-detail-value">${qty}</span>
          </div>
          <div class="listing-detail-row">
            <span class="listing-detail-label">Price</span>
            <span class="listing-detail-value listing-price">${price}</span>
          </div>
        </div>
        ${badges.length ? `<div class="listing-badges">${badges.join("")}</div>` : ""}
        <p class="listing-description">${l.description ? this._esc(l.description) : "No description provided."}</p>
        ${listed ? `<p class="listing-listed-date">Listed ${listed}</p>` : ""}
      </div>

      <div class="card" aria-labelledby="listingFarmerHeading">
        <h3 id="listingFarmerHeading" class="listing-farmer-heading">About the farmer</h3>
        <div class="listing-detail-meta">
          <div class="listing-detail-row">
            <span class="listing-detail-label">Name</span>
            <span class="listing-detail-value">${farmerName}</span>
          </div>
          ${farmName && farmName !== farmerName ? `
          <div class="listing-detail-row">
            <span class="listing-detail-label">Farm / business</span>
            <span class="listing-detail-value">${farmName}</span>
          </div>` : ""}
          <div class="listing-detail-row">
            <span class="listing-detail-label">Location</span>
            <span class="listing-detail-value">📍 ${location}</span>
          </div>
          ${f.phone ? `
          <div class="listing-detail-row">
            <span class="listing-detail-label">Phone</span>
            <span class="listing-detail-value"><a href="tel:${this._esc(f.phone)}">📞 ${this._esc(f.phone)}</a></span>
          </div>` : ""}
        </div>
        <div class="listing-detail-actions">
          <button class="btn btn-primary" id="msgFarmerBtn">💬 Message Farmer</button>
        </div>
      </div>`;
    },

    /* ── Listing-detail map ──────────────────────────────────────────────────
       Leaflet + OSM tiles, loaded lazily only on this page. Farmer cities are
       geocoded via Nominatim (throttled + cached); markers link to listings. */
    _loadLeaflet() {
        if (this._leafletPromise) return this._leafletPromise;
        this._leafletPromise = new Promise((resolve, reject) => {
            if (window.L) return resolve(window.L);
            const fail = (msg) => { this._leafletPromise = null; reject(new Error(msg)); };

            const css = document.createElement("link");
            css.rel = "stylesheet";
            css.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
            css.integrity = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=";
            css.crossOrigin = "";
            document.head.appendChild(css);

            const js = document.createElement("script");
            js.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
            js.integrity = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=";
            js.crossOrigin = "";
            js.onload = () => window.L ? resolve(window.L) : fail("Leaflet loaded without window.L");
            js.onerror = () => fail("Leaflet script failed to load");
            setTimeout(() => { if (!window.L) fail("Leaflet load timed out"); }, 10000);
            document.head.appendChild(js);
        });
        return this._leafletPromise;
    },

    _geoCacheGet(key) {
        try {
            const raw = localStorage.getItem(key);
            if (raw) return JSON.parse(raw);
        } catch { /* private mode / quota — fall through to memory */ }
        return this._geoMem?.[key] ?? null;
    },

    _geoCacheSet(key, val) {
        try {
            localStorage.setItem(key, JSON.stringify(val));
        } catch {
            (this._geoMem ||= {})[key] = val;
        }
    },

    async _geocodeCity(city) {
        const name = (city || "").trim();
        if (!name) return null;
        const key = "r1_geo:" + name.toLowerCase();
        const cached = this._geoCacheGet(key);
        if (cached) {
            if (cached.lat != null) return { lat: cached.lat, lng: cached.lng };
            if (cached.miss && Date.now() - (cached.t || 0) < 86400000) return null; // retry misses after 24h
        }

        // Serialize requests ≥1.1s apart (Nominatim usage policy: max 1/sec)
        const run = async () => {
            const wait = 1100 - (Date.now() - (this._geoLastAt || 0));
            if (wait > 0) await new Promise(r => setTimeout(r, wait));
            this._geoLastAt = Date.now();
            const url = `${NOMINATIM_BASE}?format=json&limit=1&countrycodes=us`
                + `&state=Minnesota&city=${encodeURIComponent(name)}`;
            const res = await fetch(url, { headers: { Accept: "application/json" } });
            if (!res.ok) throw new Error(`geocode HTTP ${res.status}`);
            return res.json();
        };
        const p = (this._geoQueue || Promise.resolve()).then(run);
        this._geoQueue = p.catch(() => {}); // keep the queue alive after failures

        try {
            const results = await p;
            if (results && results.length) {
                const pos = { lat: parseFloat(results[0].lat), lng: parseFloat(results[0].lon) };
                if (Number.isFinite(pos.lat) && Number.isFinite(pos.lng)) {
                    this._geoCacheSet(key, pos);
                    return pos;
                }
            }
        } catch { /* network / rate limit → treat as a miss */ }
        this._geoCacheSet(key, { miss: true, t: Date.now() });
        return null;
    },

    async _initListingMap(l) {
        try {
            const [L, listings] = await Promise.all([
                this._loadLeaflet(),
                this.api("GET", "/listings"),
            ]);
            const alive = () => this.currentPage === "listing_detail"
                && !!document.getElementById("listingMap");
            if (!alive()) return;

            // Group listings by farmer; make sure the current farmer is present
            const farmers = new Map();
            (listings || []).forEach(item => {
                let f = farmers.get(item.farmer_id);
                if (!f) {
                    f = {
                        id: item.farmer_id,
                        name: item.farm_name || item.farmer_name || "Local farmer",
                        city: item.location_city,
                        region: item.location_region,
                        listings: [],
                    };
                    farmers.set(item.farmer_id, f);
                }
                f.listings.push(item);
            });
            if (!farmers.has(l.farmer.id)) {
                farmers.set(l.farmer.id, {
                    id: l.farmer.id,
                    name: l.farmer.organization_name || l.farmer.full_name || "Local farmer",
                    city: l.farmer.location_city,
                    region: l.farmer.location_region,
                    listings: [],
                });
            }

            // Locate the current farmer first so the map centers on them
            const current = farmers.get(l.farmer.id);
            const curPos = (await this._geocodeCity(current.city))
                || REGION_CENTROIDS[current.region] || null;
            if (!alive()) return;

            const map = L.map("listingMap", { scrollWheelZoom: true });
            this._listingMap = map;
            L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                maxZoom: 18,
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            }).addTo(map);
            map.setView(
                curPos ? [curPos.lat, curPos.lng] : [MN_CENTER.lat, MN_CENTER.lng],
                curPos ? 9 : 6,
            );
            document.getElementById("listingMapPanel").classList.remove("hidden");
            map.invalidateSize(); // the container was display:none during setup

            // Once the user pans/zooms, stop reframing the map under them
            let userMoved = false;
            const el = map.getContainer();
            ["pointerdown", "wheel"].forEach(ev =>
                el.addEventListener(ev, () => { userMoved = true; }, { once: true, passive: true }));

            // Markers grouped by rounded coordinate (same city ⇒ one marker)
            const groups = new Map();
            const addMarker = (pos, farmer, isCurrent) => {
                const gKey = pos.lat.toFixed(3) + "," + pos.lng.toFixed(3);
                let g = groups.get(gKey);
                if (!g) { g = { pos, farmers: [], isCurrent: false, marker: null }; groups.set(gKey, g); }
                if (isCurrent) { g.farmers.unshift(farmer); g.isCurrent = true; }
                else g.farmers.push(farmer);
                this._renderMapGroup(L, map, g, l);
                return g;
            };

            const currentGroup = curPos ? addMarker(curPos, current, true) : null;

            // Resolve the rest; markers trickle in as cities geocode. Cap fresh
            // network lookups per page view to stay well inside Nominatim limits.
            let netBudget = 20;
            for (const f of farmers.values()) {
                if (f.id === current.id) continue;
                if (!alive()) return;
                let pos = null;
                if (f.city) {
                    const peek = this._geoCacheGet("r1_geo:" + f.city.trim().toLowerCase());
                    const isFresh = peek && (peek.lat != null
                        || (peek.miss && Date.now() - (peek.t || 0) < 86400000));
                    if (isFresh || netBudget > 0) {
                        if (!isFresh) netBudget--;
                        pos = await this._geocodeCity(f.city);
                    }
                }
                pos = pos || REGION_CENTROIDS[f.region] || null;
                if (!alive()) return;
                if (pos) addMarker(pos, f, false);
            }

            if (groups.size === 0) {
                // Nothing plottable at all — hide the panel again
                document.getElementById("listingMapPanel")?.classList.add("hidden");
                map.remove();
                this._listingMap = null;
                return;
            }
            if (!userMoved && groups.size > 1) {
                const bounds = L.latLngBounds([...groups.values()].map(g => [g.pos.lat, g.pos.lng]));
                map.fitBounds(bounds, { maxZoom: 10, padding: [30, 30] });
            }
            // Open the highlighted popup once the fitBounds animation settles —
            // opening mid-animation makes auto-pan miss and the popup clips
            if (currentGroup && !userMoved) {
                setTimeout(() => {
                    if (this._listingMap === map) currentGroup.marker.openPopup();
                }, 400);
            }
        } catch {
            // CDN blocked / API error / geocode outage — page works without the map
            document.getElementById("listingMapPanel")?.classList.add("hidden");
        }
    },

    _renderMapGroup(L, map, g, l) {
        const popupHtml = g.farmers.map(f => {
            const loc = [f.city, f.region].filter(Boolean).join(", ");
            const items = f.listings.map(item => {
                const label = `${this._esc(item.crop_name)} — ${this._esc(item.quantity_available)} ${this._esc(item.quantity_unit)}`;
                if (item.id === l.id) {
                    return `<div class="map-pop-listing is-current">${label} <em>(this listing)</em></div>`;
                }
                const price = item.price_per_unit != null
                    ? ` · $${Number(item.price_per_unit).toFixed(2)}` : "";
                return `<a class="map-pop-listing" href="#/listing/${item.id}">${label}${price}</a>`;
            }).join("");
            return `<div class="map-pop-farmer">
                <strong>🌾 ${this._esc(f.name)}</strong>
                ${loc ? `<div class="map-pop-loc">📍 ${this._esc(loc)}</div>` : ""}
                ${items}
            </div>`;
        }).join("");

        const size = g.isCurrent ? 26 : 18;
        const icon = L.divIcon({
            className: "",
            html: `<div class="map-marker${g.isCurrent ? " map-marker-current" : ""}"></div>`,
            iconSize: [size, size],
            iconAnchor: [size / 2, size / 2],
        });

        if (g.marker) {
            g.marker.setIcon(icon);
            g.marker.setPopupContent(popupHtml);
        } else {
            g.marker = L.marker([g.pos.lat, g.pos.lng], {
                icon,
                title: g.farmers.map(f => f.name).join(", "),
                keyboard: true,
            }).addTo(map).bindPopup(popupHtml, {
                maxHeight: 220,
                autoPanPadding: [24, 24],
            });
        }
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
            .addEventListener("click", () => this._closeModal("donateModal"));
        // Group Donate modal — close
        document.getElementById("closeGroupDonateModal")
            .addEventListener("click", () => this._closeModal("groupDonateModal"));
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
            this._openModal("donateModal");

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
        const btn = document.getElementById("confirmDonateBtn");
        const farmerId = parseInt(document.getElementById("donateSelectFarmer").value);
        const amount = parseFloat(document.getElementById("donateAmount").value);

        if (!farmerId || isNaN(amount) || amount <= 0) {
            errEl.textContent = "Please enter a valid contribution amount.";
            errEl.classList.remove("hidden");
            return;
        }
        errEl.classList.add("hidden");

        // Guard against a double-submit while the request/redirect is in flight.
        const origLabel = btn ? btn.textContent : null;
        if (btn) { btn.disabled = true; btn.textContent = "Redirecting to secure checkout…"; }

        try {
            const result = await this.api("POST", "/donations/", {
                wishlist_item_id: itemId,
                farmer_id: farmerId,
                amount,
            });
            // Hand off to Stripe's hosted payment page. The donation stays
            // pending until the webhook confirms it on the /donation/success
            // screen — do NOT show points or update progress here.
            window.location.href = result.checkout_url;
        } catch (err) {
            if (btn) { btn.disabled = false; btn.textContent = origLabel; }
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
        this._openModal("groupDonateModal");

        const btn = document.getElementById("confirmGroupDonateBtn");
        const newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);
        newBtn.addEventListener("click", () => this._submitGroupDonation(gdId));
    },

    async _submitGroupDonation(gdId) {
        const errEl = document.getElementById("groupDonateError");
        const btn = document.getElementById("confirmGroupDonateBtn");
        const amount = parseFloat(document.getElementById("groupDonateAmount").value);

        if (isNaN(amount) || amount <= 0) {
            errEl.textContent = "Please enter a valid contribution amount.";
            errEl.classList.remove("hidden");
            return;
        }
        errEl.classList.add("hidden");

        const origLabel = btn ? btn.textContent : null;
        if (btn) { btn.disabled = true; btn.textContent = "Redirecting to secure checkout…"; }

        try {
            const result = await this.api("POST", "/donations/group/join", {
                group_donation_id: gdId,
                amount,
            });
            // Charge-at-join: redirect to Stripe. The group's progress updates
            // only after the webhook confirms payment on /donation/success.
            window.location.href = result.checkout_url;
        } catch (err) {
            if (btn) { btn.disabled = false; btn.textContent = origLabel; }
            errEl.textContent = err.message;
            errEl.classList.remove("hidden");
        }
    },

    // ── Post-checkout result (Stripe redirect target) ─────────────────────────

    // Parse a "?a=b&c=d" query string out of a hash like
    // "#/donation/success?donation_id=12&kind=individual".
    _hashQuery(hash) {
        const params = {};
        const qi = hash.indexOf("?");
        if (qi >= 0) {
            new URLSearchParams(hash.slice(qi + 1)).forEach((v, k) => { params[k] = v; });
        }
        return params;
    },

    _renderDonationResult(kind, params) {
        // Tear down anything navigate() would (poll timers, the listing map).
        if (this.messagingPollTimer) { clearInterval(this.messagingPollTimer); this.messagingPollTimer = null; }
        if (this._listingMap) { this._listingMap.remove(); this._listingMap = null; }
        this.currentPage = "donation_result";

        const appEl = document.getElementById("app");
        appEl.classList.remove("is-landing");
        const backBtn = `<button class="btn btn-primary" id="drHomeBtn">Back to browsing</button>`;

        if (kind === "cancel") {
            document.title = "Payment canceled — Route 1 Pathways";
            appEl.innerHTML = `
        <div class="load-error donation-result">
          <span style="font-size:2.5rem">🧺</span>
          <h2>Payment canceled</h2>
          <p>No charge was made. Your contribution wasn't completed — you can try again whenever you're ready.</p>
          <div class="load-error-actions">${backBtn}</div>
        </div>`;
            document.getElementById("drHomeBtn")
                ?.addEventListener("click", () => this._navigateToHomeDashboard());
            return;
        }

        // success — show a spinner, then poll the donation for webhook confirmation
        document.title = "Confirming your contribution — Route 1 Pathways";
        appEl.innerHTML = `
      <div class="load-error donation-result" id="drCard">
        <div class="spinner" style="margin:0 auto"></div>
        <h2>Confirming your contribution…</h2>
        <p>Hang tight — we're checking with our payment provider. This usually takes just a few seconds.</p>
      </div>`;

        const donationId = parseInt(params.donation_id, 10);
        if (!donationId) { this._renderDonationConfirmed(null, params.kind); return; }
        this._pollDonationConfirmation(donationId)
            .then(d => this._renderDonationConfirmed(d, params.kind));
    },

    async _pollDonationConfirmation(donationId) {
        // Poll for ~25s. The webhook usually confirms within a couple seconds;
        // if it's slow the "payment received, finalizing" message covers it.
        const deadline = Date.now() + 25000;
        let last = null;
        while (Date.now() < deadline) {
            try {
                const d = await this.api("GET", `/donations/${donationId}`);
                last = d;
                if (d.status === "confirmed" || d.status === "refunded") return d;
            } catch {
                // 401 is handled inside api() (redirects to login); stop polling.
                return last;
            }
            await new Promise(r => setTimeout(r, 2000));
        }
        return last;
    },

    _renderDonationConfirmed(donation, kind) {
        const card = document.getElementById("drCard");
        if (!card) return;   // user navigated away (or session expired mid-poll)
        const backBtn = `<button class="btn btn-primary" id="drHomeBtn">Back to browsing</button>`;
        const pointsBtn = `<button class="btn btn-secondary" id="drPointsBtn">View my points</button>`;

        if (donation && donation.status === "confirmed") {
            this._track(kind === "group" ? "group-pledge" : "donation-completed", true);
            document.title = "Thank you — Route 1 Pathways";
            const pts = donation.points_earned || 0;
            const ptsLine = pts > 0
                ? `<p>You earned <span class="badge badge-amber">+${pts} points</span> 🎯</p>`
                : "";
            card.innerHTML = `
        <span style="font-size:2.5rem">🌾</span>
        <h2>Thank you for your contribution!</h2>
        <p>Your payment went through and your contribution is confirmed.</p>
        ${ptsLine}
        <div class="load-error-actions">${backBtn}${pts > 0 ? pointsBtn : ""}</div>`;
            document.getElementById("drPointsBtn")
                ?.addEventListener("click", () => this.navigate("points_rewards"));
        } else if (donation && donation.status === "refunded") {
            document.title = "Contribution refunded — Route 1 Pathways";
            card.innerHTML = `
        <span style="font-size:2.5rem">↩️</span>
        <h2>Contribution refunded</h2>
        <p>This contribution was refunded. If that's unexpected, please get in touch and we'll help.</p>
        <div class="load-error-actions">${backBtn}</div>`;
        } else {
            // Still pending / timed out — payment likely succeeded but the
            // webhook hasn't landed yet. Never tell them to pay again.
            document.title = "Payment received — Route 1 Pathways";
            card.innerHTML = `
        <span style="font-size:2.5rem">⏳</span>
        <h2>Payment received</h2>
        <p>Thanks! We're still finalizing your contribution — it'll appear in your donation history shortly. There's no need to pay again.</p>
        <div class="load-error-actions">${backBtn}</div>`;
        }
        document.getElementById("drHomeBtn")
            ?.addEventListener("click", () => this._navigateToHomeDashboard());
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

        // Location is required for farmers (the browse map depends on it)
        const isFarmer = user.user_type === "farmer";
        document.getElementById("profileCityReq")?.classList.toggle("hidden", !isFarmer);
        document.getElementById("profileRegionReq")?.classList.toggle("hidden", !isFarmer);

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

        if (this.user?.user_type === "farmer" && (!payload.location_city || !payload.location_region)) {
            errEl.textContent = "Farmers must have a Minnesota city and region — buyers use it to find you.";
            errEl.classList.remove("hidden");
            return;
        }

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
              <span class="muted points-hist-desc">${e.description || "Donation"}</span>
            </div>
            <span class="muted num">${new Date(e.created_at).toLocaleDateString()}</span>
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
                this._closeModal("wishlistDetailModal")
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
            quantity_needed: parseFloat(document.getElementById("wlQty").value),
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
            this._orgWishlistItems = items;   // cache for the fulfill modal

            // Cancel button listeners
            grid.querySelectorAll(".cancel-wishlist-btn").forEach(btn => {
                btn.addEventListener("click", () => this._cancelWishlistItem(parseInt(btn.dataset.id)));
            });
            // Mark-fulfilled button listeners
            grid.querySelectorAll(".fulfill-wishlist-btn").forEach(btn => {
                btn.addEventListener("click", () => this._openFulfillModal(parseInt(btn.dataset.id)));
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
          ${["open", "funded"].includes(item.status)
                ? `<button class="btn btn-primary btn-sm fulfill-wishlist-btn" data-id="${item.id}">✓ Mark Fulfilled</button>`
                : ""}
          ${item.status === "open"
                ? `<button class="btn btn-danger btn-sm cancel-wishlist-btn" data-id="${item.id}">Cancel Item</button>`
                : ""}
        </div>
      </div>`;
    },

    /* Fulfillment modal — records actual pounds delivered (MPCA impact metric)
       and is the only way an item transitions to "fulfilled". */
    _openFulfillModal(itemId) {
        const item = (this._orgWishlistItems || []).find(i => i.id === itemId);
        if (!item) return;

        const modal = document.getElementById("wishlistDetailModal");
        const content = document.getElementById("wishlistDetailContent");
        if (!modal || !content) return;

        const farmerOptions = (item.farmers || []).map(f =>
            `<option value="${f.farmer_id}">${this._esc(f.full_name || f.farm_name || "Farmer #" + f.farmer_id)}</option>`
        ).join("");

        content.innerHTML = `
      <h3>Mark "${this._esc(item.crop_name)}" Fulfilled</h3>
      <p class="muted">Record the delivery. Pounds delivered feeds our food-rescue
        impact reporting, so please estimate as accurately as you can.</p>
      <form id="fulfillFormEl" novalidate>
        <div class="form-group">
          <label for="fulfillFarmer">Delivered by *</label>
          <select id="fulfillFarmer" required>${farmerOptions}</select>
        </div>
        <div class="form-group">
          <label for="fulfillPounds">Pounds of food delivered *</label>
          <input type="number" id="fulfillPounds" min="0.01" step="any"
                 placeholder="e.g. ${item.quantity_unit === "lbs" ? this._esc(item.quantity_needed) : "150"}" required />
        </div>
        <div class="form-group">
          <label for="fulfillNotes">Notes (optional)</label>
          <input type="text" id="fulfillNotes" maxlength="512" placeholder="e.g. Delivered fresh on Tuesday" />
        </div>
        <p class="error-msg hidden" id="fulfillError"></p>
        <div class="form-actions">
          <button type="submit" class="btn btn-primary">Record Delivery</button>
        </div>
      </form>`;

        content.querySelector("#fulfillFormEl").addEventListener("submit", async e => {
            e.preventDefault();
            const errEl = content.querySelector("#fulfillError");
            errEl.classList.add("hidden");

            const pounds = parseFloat(content.querySelector("#fulfillPounds").value);
            const farmerId = parseInt(content.querySelector("#fulfillFarmer").value);
            if (!farmerId) {
                errEl.textContent = "No linked farmer to attribute this delivery to.";
                errEl.classList.remove("hidden");
                return;
            }
            if (!pounds || pounds <= 0) {
                errEl.textContent = "Please enter the pounds delivered.";
                errEl.classList.remove("hidden");
                return;
            }

            try {
                await this.api("POST", `/wishlist/${itemId}/fulfill`, {
                    farmer_id: farmerId,
                    pounds_delivered: pounds,
                    notes: content.querySelector("#fulfillNotes").value.trim() || null,
                });
                this._closeModal("wishlistDetailModal");
                this.showToast(`Recorded ${pounds} lbs delivered. Thank you! 🌾`, "success");
                this._loadMyWishlist();
            } catch (err) {
                errEl.textContent = err.message;
                errEl.classList.remove("hidden");
            }
        });

        this._openModal("wishlistDetailModal");
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
