# Route 1

> Minnesota food rescue marketplace — connecting farmers, food organizations, and consumers so locally-grown produce reaches communities who need it most.

---

## Overview

Route 1 is a three-sided marketplace built on FastAPI + MySQL (AWS RDS) with a vanilla-JS single-page application frontend.

| User type | What they do |
|---|---|
| **Farmer** | List available crop inventory with pricing, transport flags, and donation eligibility |
| **Organization** | Browse farmer listings; post wishlist items as donation opportunities; link farmers to each request |
| **Consumer** | Browse farmers; fund donation opportunities (individually or as a group); earn reward points |

Organizations have a sub-type: `restaurant`, `grocery_store`, or `food_shelf`. Only food shelves see the "donation only" filter by default; all other org types can still filter manually.

---

## Features

### Core marketplace
- Farmer crop inventory management (CRUD)
- Browse farmers by crop type, region, price, and transport availability
- Direct messaging between any two users

### Profile Settings *(all roles)*
- Edit personal info: full name, organisation name, city, region, and phone
- Consumers can configure donation notification preferences with optional price-range filters

### Organisation Wishlist
- Organisations post crop requests as donation opportunities (name, quantity, total funding target)
- Each wishlist item can be linked to one or more farmers who produce that crop
- Supports standard individual funding or group-donation mode

### Consumer Donation Flow
- Consumers browse open donation opportunities on a dedicated **Donation Opportunities** tab
- **Donate Now** modal: choose a linked farmer, enter amount, see projected points before confirming
- Donations are immediately set to `confirmed` status (Stripe integration point included via `payment_reference` column)
- Donating updates the wishlist item's `amount_donated` and auto-transitions its status to `funded` when the goal is reached

### Group Donation
- Organisations can flag a wishlist item as a group donation and set a target donor count
- Consumers join via a **Join Group Donation** modal showing live progress (amount pledged, donors remaining)
- When the final participant joins and the pledge total meets the goal, all participant donations are confirmed in one transaction and points are awarded to each donor

### Points & Rewards
- **Rule:** every $20 donated = 100 points (floor division — $35 → 100 pts, $40 → 200 pts)
- Three reward tiers: 🌱 **500 pts** · ⭐ **1,500 pts** · 🏆 **3,000 pts**
- All points events are stored in an immutable `points_ledger` table (one row per confirmed donation)
- Dedicated **My Rewards** page with an animated vertical progress bar, tier unlock badges, stat cards, and full history

---

## Project Structure

```
Route1/
├── backend/
│   ├── main.py                   # FastAPI app entry-point; registers all routers
│   ├── database.py               # SQLAlchemy engine + session factory (AWS RDS MySQL)
│   ├── models/
│   │   ├── __init__.py           # Re-exports all model classes
│   │   ├── user.py               # User model (farmer / organization / consumer)
│   │   ├── crop_inventory.py     # FarmerCropInventory model
│   │   ├── messaging.py          # Message model + make_conversation_id()
│   │   ├── wishlist.py           # WishlistItem, WishlistFarmerLink
│   │   ├── donation.py           # Donation, GroupDonation, GroupDonationParticipant
│   │   ├── points.py             # PointsLedger, calculate_points(), TIER_THRESHOLDS
│   │   └── notification_prefs.py # NotificationPreferences (1-to-1 with users)
│   ├── schemas/
│   │   ├── __init__.py           # Re-exports all schema classes
│   │   ├── auth.py               # Register / login / me schemas
│   │   ├── farmers.py            # CropListingCreate / Update / Response
│   │   ├── browse.py             # FarmerListingResponse, CropSummary
│   │   ├── messaging.py          # MessageCreate / Response, ConversationSummary
│   │   ├── wishlist.py           # WishlistItemCreate/Update/Response, FarmerSummary
│   │   ├── donations.py          # DonateRequest, DonationResponse, GroupDonationResponse
│   │   ├── points.py             # PointsLedgerEntry, TierInfo, PointsSummaryResponse
│   │   └── notifications.py      # NotificationPrefsUpdate/Response, ProfileUpdateRequest
│   ├── routers/
│   │   ├── auth.py               # POST /auth/register, POST /auth/login, GET /auth/me
│   │   ├── farmers.py            # POST/GET/PUT/DELETE /farmers/crops
│   │   ├── organizations.py      # GET /organizations/browse
│   │   ├── consumers.py          # GET /consumers/browse
│   │   ├── messaging.py          # POST /messages, GET conversations, PUT read
│   │   ├── profiles.py           # GET/PATCH /profiles/me, GET/PATCH /profiles/me/notifications
│   │   ├── wishlist.py           # CRUD /wishlist/, GET /wishlist/mine
│   │   ├── donations.py          # POST /donations/, /donations/group/join, GET /donations/mine
│   │   └── points.py             # GET /points/me
│   ├── utils/
│   │   └── security.py           # bcrypt + JWT helpers
│   ├── requirements.txt
│   └── schemas.sql               # Idempotent DDL for all 10 tables (auto-run on startup)
└── frontend/
    ├── index.html                # SPA shell; content injected by app.js
    ├── styles.css                # Design system + new component styles
    ├── app.js                    # SPA logic: routing, auth state, API calls
    └── components/
        ├── login.html            # Auth page (login + register panels)
        ├── farmer_dashboard.html # Crop inventory CRUD
        ├── org_dashboard.html    # Browse with filters (org)
        ├── consumer_dashboard.html  # Browse tab + Donation Opportunities tab + modals
        ├── messaging.html        # Conversation list + message thread
        ├── profile_settings.html # Profile form + notification prefs + points mini-card
        ├── points_rewards.html   # Animated vertical progress bar, tier badges, history
        └── wishlist_manage.html  # Create wishlist items, link farmers, manage requests
```

---

## Database

- **AWS RDS MySQL 8.0** instance (`dbsivamysql` / database `mysqlRouteOne`)
- `schemas.sql` is executed automatically on every startup — fully idempotent (`CREATE TABLE IF NOT EXISTS`)
- All tables use `InnoDB` engine and `utf8mb4` charset

| Table | Purpose |
|---|---|
| `users` | Credentials, role (`farmer`/`organization`/`consumer`), org sub-type, MN location |
| `farmer_crop_inventory` | Crop listings — quantity, price, transport flags, donation flag |
| `messages` | Direct messages; conversation keyed by `"min_id:max_id"` |
| `wishlist_items` | Org donation opportunities — crop name, quantity, funding target, status |
| `wishlist_farmer_links` | Many-to-many: which farmers are linked to each wishlist item |
| `group_donations` | Aggregates co-funding: total required, amount pledged, donor count/goal |
| `donations` | Individual consumer donations with status and payment reference |
| `group_donation_participants` | Per-consumer pledge record within a group donation |
| `points_ledger` | Immutable points history — one row per confirmed donation |
| `notification_preferences` | Per-user notification toggles and price-range filters (1-to-1 with users) |

---

## Backend Setup

### 1. Prerequisites
- Python 3.11+
- AWS RDS MySQL instance (`mysqlRouteOne` database already created)

### 2. Install dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

Create a `.env` file in `backend/` with at least:

```
DB_HOST=<your-rds-endpoint>
DB_PORT=3306
DB_NAME=mysqlRouteOne
DB_USER=<username>
DB_PASSWORD=<password>
SECRET_KEY=<random-32-byte-hex>
```

Optionally set `RDS_SSL_CA=/path/to/global-bundle.pem` to enable full SSL certificate verification against the RDS CA bundle.

### 4. Run the server

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

All 10 database tables are created/verified automatically on startup.  
Interactive API docs: `http://localhost:8000/docs`

---

## Frontend Setup

The frontend is a **static website** — no build step required.

```bash
cd frontend
python -m http.server 3000
# Visit http://localhost:3000
```

The `API_BASE` constant at the top of `frontend/app.js` defaults to `http://localhost:8000`. Change it to your deployed API URL for production.

### Navigation (role-based)
| Role | Nav links shown |
|---|---|
| Farmer | Dashboard, Messages, ⚙ Profile |
| Organization | Dashboard, Manage Wishlist, Messages, ⚙ Profile |
| Consumer | Dashboard, My Rewards, Messages, ⚙ Profile |

---

## API Endpoints

### Auth
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | No | Create account (farmer / organization / consumer) |
| POST | `/auth/login` | No | Returns JWT token |
| GET | `/auth/me` | Yes | Current user profile |

### Farmer — Crop Inventory
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/farmers/crops` | Farmer | Add a crop listing |
| GET | `/farmers/crops` | Farmer | List own crop inventory |
| PUT | `/farmers/crops/{id}` | Farmer | Update a listing |
| DELETE | `/farmers/crops/{id}` | Farmer | Remove a listing |

### Browse (Organizations & Consumers)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/organizations/browse` | Org | Browse farmers with filters |
| GET | `/consumers/browse` | Consumer | Browse farmers with filters |

Query parameters for browse: `crop_type`, `location_region`, `location_city`, `min_price`, `max_price`, `has_transport` (bool), `donation_only` (bool).

### Messaging
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/messages` | Yes | Send a message |
| GET | `/messages/conversations` | Yes | List all conversations with unread counts |
| GET | `/messages/conversations/{conv_id}` | Yes | Fetch full message thread (auto-marks as read) |
| PUT | `/messages/{msg_id}/read` | Yes | Mark a single message as read |

### Profiles
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/profiles/me` | Yes | Get current user's profile |
| PATCH | `/profiles/me` | Yes | Update name, city, region, phone |
| GET | `/profiles/me/notifications` | Consumer | Get notification preferences |
| PATCH | `/profiles/me/notifications` | Consumer | Update notification toggles and price range |

### Wishlist
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/wishlist/` | Org | Create a wishlist item (donation opportunity) |
| GET | `/wishlist/` | Consumer | Browse all open wishlist items |
| GET | `/wishlist/mine` | Org | List own wishlist items |
| GET | `/wishlist/{item_id}` | Yes | Get a single wishlist item with farmers and group status |
| PATCH | `/wishlist/{item_id}` | Org | Update a wishlist item |
| DELETE | `/wishlist/{item_id}` | Org | Cancel (soft-delete) a wishlist item |

### Donations
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/donations/` | Consumer | Make an individual donation toward a wishlist item |
| POST | `/donations/group/join` | Consumer | Pledge to a group donation |
| GET | `/donations/group/{gd_id}` | Yes | Get group donation status and participants |
| GET | `/donations/mine` | Consumer | List own donation history |

### Points & Rewards
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/points/me` | Consumer | Get total points, current tier, next tier, and full history |

---

## Points & Rewards Reference

| Donated | Points earned |
|---|---|
| $0 – $19.99 | 0 pts |
| $20 – $39.99 | 100 pts |
| $40 – $59.99 | 200 pts |
| every additional $20 | +100 pts |

| Tier | Threshold |
|---|---|
| 🌱 Seedling | 500 pts |
| ⭐ Harvest Star | 1,500 pts |
| 🏆 Community Champion | 3,000 pts |

---

## Minnesota Regions

Dropdown values used in registration and browse filters:

`Twin Cities Metro`, `Southeast MN`, `Southwest MN`, `Central MN`, `Northeast MN`, `Northwest MN`, `North Central MN`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JavaScript (no framework) |
| Backend | Python 3.11, FastAPI 0.111, Uvicorn |
| ORM | SQLAlchemy 2.0 |
| Database | AWS RDS MySQL 8.0 (`mysqlRouteOne`) |
| Auth | JWT (python-jose) + bcrypt (passlib) |

---

## Roadmap

- [ ] WebSocket real-time messaging (replace polling)
- [ ] Email / push notifications via AWS SES (notification preference hooks already in place)
- [ ] Stripe payment gateway integration (`payment_reference` column ready in `donations` table)
- [ ] Admin dashboard — fulfillment tracking, user management
- [ ] Map view for nearby farmers (Minnesota-scoped)
- [ ] Reward redemption catalogue for accumulated points
