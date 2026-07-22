-- =============================================================================
-- schemas.sql — AWS RDS MySQL 8.0+ table definitions for Route 1 (v2)
--
-- Run manually:
--   mysql -h <RDS_HOST> -u admin -p mysqlRouteOne < schemas.sql
-- Or executed automatically by database.py on every app startup (idempotent).
--
-- All statements use CREATE TABLE IF NOT EXISTS / ALTER TABLE … IF NOT EXISTS
-- so this file is safe to run on an already-initialized database.
-- =============================================================================

-- NOTE: No USE/CREATE DATABASE here.
-- The target database is set via DB_NAME in .env and DATABASE_URL in database.py.

-- =============================================================================
-- Table 1 : users
--
-- Three roles:
--   farmer       — adds crop listings, receives messages
--   organization — restaurant / grocery_store / food_shelf, browses farmers
--   consumer     — individual (chef, family, caterer), browses farmers
-- =============================================================================
CREATE TABLE IF NOT EXISTS `users` (
    `id`                INT          NOT NULL AUTO_INCREMENT,
    `email`             VARCHAR(255) NOT NULL,
    -- NULL for "Sign in with Google" accounts (no password set).
    `hashed_password`   VARCHAR(255) NULL,
    -- Google account subject id (set when a user links / signs in with Google).
    `google_id`         VARCHAR(255) NULL,

    -- Role fields
    `user_type`         ENUM('farmer', 'organization', 'consumer') NOT NULL,
    `org_subtype`       ENUM('restaurant', 'grocery_store', 'food_shelf') NULL,

    -- Profile fields
    `full_name`         VARCHAR(255) NULL,
    `organization_name` VARCHAR(255) NULL,   -- farm name for farmers, org name for orgs
    `location_city`     VARCHAR(100) NULL,   -- Minnesota city
    `location_region`   VARCHAR(100) NULL,   -- MN region (e.g. Twin Cities Metro)
    `phone`             VARCHAR(30)  NULL,
    `is_active`         TINYINT(1)   NOT NULL DEFAULT 1,
    `created_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_users_email`      (`email`),
    UNIQUE KEY `uq_users_google_id`  (`google_id`),
    KEY       `ix_users_email`       (`email`),
    KEY       `ix_users_user_type`   (`user_type`),
    KEY       `ix_users_location`    (`location_region`, `location_city`)
)   ENGINE  = InnoDB
    CHARSET = utf8mb4
    COLLATE = utf8mb4_unicode_ci;


-- =============================================================================
-- Table 2 : farmer_crop_inventory
--
-- Each row is one crop item a farmer has available (or in excess).
-- is_available = 0 soft-deletes the row from browse results.
-- price_per_unit NULL means "price on request".
-- =============================================================================
CREATE TABLE IF NOT EXISTS `farmer_crop_inventory` (
    `id`                    INT           NOT NULL AUTO_INCREMENT,
    `farmer_id`             INT           NOT NULL,

    `crop_name`             VARCHAR(255)  NOT NULL,
    -- Numeric so impact totals can be aggregated (MPCA reporting).
    `quantity_available`    DECIMAL(10,2) NOT NULL,
    `quantity_unit`         VARCHAR(50)   NOT NULL DEFAULT 'lbs',
    `price_per_unit`        DECIMAL(10,2) NULL,
    `description`           TEXT          NULL,

    `can_provide_transport` TINYINT(1)    NOT NULL DEFAULT 0,
    `needs_transport`       TINYINT(1)    NOT NULL DEFAULT 0,
    `donation_eligible`     TINYINT(1)    NOT NULL DEFAULT 0,
    `is_available`          TINYINT(1)    NOT NULL DEFAULT 1,

    `created_at`            DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`            DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                          ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (`id`),
    KEY `ix_crop_farmer_id`  (`farmer_id`),
    KEY `ix_crop_name`       (`crop_name`),
    KEY `ix_crop_available`  (`is_available`),

    CONSTRAINT `fk_crop_farmer`
        FOREIGN KEY (`farmer_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
)   ENGINE  = InnoDB
    CHARSET = utf8mb4
    COLLATE = utf8mb4_unicode_ci;


-- =============================================================================
-- Table 3 : messages
--
-- Direct-messaging between any two users.
-- conversation_id = "LOWER_USER_ID:HIGHER_USER_ID" (no join table needed).
-- is_read tracks unread counts per recipient.
-- =============================================================================
CREATE TABLE IF NOT EXISTS `messages` (
    `id`              INT         NOT NULL AUTO_INCREMENT,
    `conversation_id` VARCHAR(50) NOT NULL,
    `sender_id`       INT         NOT NULL,
    `receiver_id`     INT         NOT NULL,
    `content`         TEXT        NOT NULL,
    `is_read`         TINYINT(1)  NOT NULL DEFAULT 0,
    `created_at`      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (`id`),
    KEY `ix_msg_conversation` (`conversation_id`),
    KEY `ix_msg_sender`       (`sender_id`),
    KEY `ix_msg_receiver`     (`receiver_id`),
    KEY `ix_msg_created`      (`created_at`),

    CONSTRAINT `fk_msg_sender`
        FOREIGN KEY (`sender_id`)   REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_msg_receiver`
        FOREIGN KEY (`receiver_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
)   ENGINE  = InnoDB
    CHARSET = utf8mb4
    COLLATE = utf8mb4_unicode_ci;


-- =============================================================================
-- Column migrations — safe to re-run (error 1060 duplicate column is ignored
-- in database.py).  Add one ALTER TABLE per missing column.
-- =============================================================================

-- v2: add all columns that may be missing from older versions of the users table.
-- Each ALTER is executed separately. database.py silently ignores error 1060
-- (column already exists) so these are fully idempotent.
ALTER TABLE `users`
    ADD COLUMN `org_subtype` ENUM('restaurant', 'grocery_store', 'food_shelf') NULL
    AFTER `user_type`;

ALTER TABLE `users`
    ADD COLUMN `full_name` VARCHAR(255) NULL
    AFTER `org_subtype`;

ALTER TABLE `users`
    ADD COLUMN `organization_name` VARCHAR(255) NULL
    AFTER `full_name`;

ALTER TABLE `users`
    ADD COLUMN `location_city` VARCHAR(100) NULL
    AFTER `organization_name`;

ALTER TABLE `users`
    ADD COLUMN `location_region` VARCHAR(100) NULL
    AFTER `location_city`;

ALTER TABLE `users`
    ADD COLUMN `phone` VARCHAR(30) NULL
    AFTER `location_region`;

ALTER TABLE `users`
    ADD COLUMN `is_active` TINYINT(1) NOT NULL DEFAULT 1
    AFTER `phone`;

ALTER TABLE `users`
    ADD COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    AFTER `is_active`;

-- Google sign-in: allow password-less accounts and store the Google subject id.
-- MODIFY is naturally idempotent. The ADD COLUMN / ADD UNIQUE KEY raise 1060 /
-- 1061 on re-run, which database.py ignores.
ALTER TABLE `users`
    MODIFY COLUMN `hashed_password` VARCHAR(255) NULL;

ALTER TABLE `users`
    ADD COLUMN `google_id` VARCHAR(255) NULL
    AFTER `hashed_password`;

ALTER TABLE `users`
    ADD UNIQUE KEY `uq_users_google_id` (`google_id`);

-- v3 (MPCA impact reporting): quantities become numeric so pounds can be
-- SUM()ed. Legacy free-text values that aren't parseable are zeroed first so
-- the MODIFY can't fail. Both UPDATEs are no-ops once the columns are DECIMAL.
UPDATE `farmer_crop_inventory`
    SET `quantity_available` = 0
    WHERE `quantity_available` NOT REGEXP '^[0-9]+(\\.[0-9]+)?$';

ALTER TABLE `farmer_crop_inventory`
    MODIFY COLUMN `quantity_available` DECIMAL(10,2) NOT NULL;

UPDATE `wishlist_items`
    SET `quantity_needed` = 0
    WHERE `quantity_needed` NOT REGEXP '^[0-9]+(\\.[0-9]+)?$';

ALTER TABLE `wishlist_items`
    MODIFY COLUMN `quantity_needed` DECIMAL(10,2) NOT NULL;

-- v4: one pledge per consumer per group donation. Dedupe first (keep the
-- earliest row) so the ADD UNIQUE KEY can never fail on existing data; the
-- DELETE is a no-op on every later run and the 1061 duplicate-key-name error
-- from the re-run ALTER is ignored by database.py.
DELETE gdp_dup FROM `group_donation_participants` gdp_dup
    INNER JOIN `group_donation_participants` gdp_keep
        ON  gdp_dup.group_donation_id = gdp_keep.group_donation_id
        AND gdp_dup.consumer_id       = gdp_keep.consumer_id
        AND gdp_dup.id                > gdp_keep.id;

ALTER TABLE `group_donation_participants`
    ADD UNIQUE KEY `uq_gdp_group_consumer` (`group_donation_id`, `consumer_id`);

-- v5: location is required for farmer accounts (enforced in Pydantic + the UI;
-- the listing-detail map needs every farmer to have a plottable location).
-- Backfill legacy farmers with no location to Plymouth (Twin Cities Metro).
-- Both UPDATEs are no-ops on every later run. No NOT NULL constraint is added
-- because the columns stay optional for organizations and consumers.
UPDATE `users`
    SET `location_city` = 'Plymouth'
    WHERE `user_type` = 'farmer'
      AND (`location_city` IS NULL OR TRIM(`location_city`) = '');

UPDATE `users`
    SET `location_region` = 'Twin Cities Metro'
    WHERE `user_type` = 'farmer'
      AND (`location_region` IS NULL OR TRIM(`location_region`) = '');

-- v6 (Stripe payments): donations now carry a real Stripe reference and are
-- confirmed by webhook, not on creation. Add the Stripe columns; each ADD
-- raises 1060/1061 on re-run, which database.py ignores. Existing `donations`
-- rows keep NULL Stripe fields and their current status (they predate payments).
ALTER TABLE `donations`
    ADD COLUMN `stripe_session_id` VARCHAR(255) NULL
    AFTER `payment_reference`;

ALTER TABLE `donations`
    ADD COLUMN `stripe_payment_intent_id` VARCHAR(255) NULL
    AFTER `stripe_session_id`;

ALTER TABLE `donations`
    ADD COLUMN `currency` CHAR(3) NOT NULL DEFAULT 'usd'
    AFTER `amount`;

-- The webhook looks a donation up by its Checkout Session id; index it.
ALTER TABLE `donations`
    ADD UNIQUE KEY `uq_don_stripe_session` (`stripe_session_id`);

-- =============================================================================
-- Table 12 : crop_orders  (v7 — direct consumer purchase of a crop listing)
--
-- Distinct from donations. A consumer requests a quantity + delivery address;
-- the farmer approves; the consumer then pays via Stripe. Money is platform-
-- collected (farmer paid out manually). No points are awarded for purchases.
--
-- Status lifecycle:
--   pending_farmer → approved → paid
--                  ↘ declined            (farmer said no)
--   pending_farmer/approved → cancelled  (consumer backed out before paying)
--   paid → refunded                      (future)
-- =============================================================================
CREATE TABLE IF NOT EXISTS `crop_orders` (
    `id`               INT           NOT NULL AUTO_INCREMENT,
    `consumer_id`      INT           NOT NULL,
    `farmer_id`        INT           NOT NULL,
    `crop_id`          INT           NOT NULL,

    -- Snapshot at request time (the listing may change afterwards).
    `quantity`         DECIMAL(10,2) NOT NULL,
    `quantity_unit`    VARCHAR(50)   NOT NULL DEFAULT 'lbs',
    `unit_price`       DECIMAL(10,2) NOT NULL,
    `total_amount`     DECIMAL(10,2) NOT NULL,
    `currency`         CHAR(3)       NOT NULL DEFAULT 'usd',

    -- Delivery details captured at request time.
    `delivery_name`    VARCHAR(255)  NOT NULL,
    `delivery_address` TEXT          NOT NULL,
    `delivery_phone`   VARCHAR(30)   NULL,
    `delivery_notes`   TEXT          NULL,

    -- Who moves the crop. Proposed by the consumer; confirmed when the farmer
    -- approves the order (or declined if they can't do it).
    `delivery_method`  ENUM('farmer_delivers','consumer_pickup')
                       NOT NULL DEFAULT 'farmer_delivers',

    `status` ENUM('pending_farmer','approved','paid','declined','cancelled','refunded')
             NOT NULL DEFAULT 'pending_farmer',

    -- Stripe references (set when the consumer pays after approval).
    `stripe_session_id`        VARCHAR(255) NULL,
    `stripe_payment_intent_id` VARCHAR(255) NULL,

    `created_at`       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                     ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_order_stripe_session` (`stripe_session_id`),
    KEY `ix_order_consumer` (`consumer_id`),
    KEY `ix_order_farmer`   (`farmer_id`),
    KEY `ix_order_crop`     (`crop_id`),
    KEY `ix_order_status`   (`status`),

    CONSTRAINT `fk_order_consumer`
        FOREIGN KEY (`consumer_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_order_farmer`
        FOREIGN KEY (`farmer_id`)   REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_order_crop`
        FOREIGN KEY (`crop_id`) REFERENCES `farmer_crop_inventory` (`id`) ON DELETE CASCADE
)   ENGINE  = InnoDB
    CHARSET = utf8mb4
    COLLATE = utf8mb4_unicode_ci;

-- v8: record who delivers each order. Added here (after the crop_orders CREATE)
-- so existing rows get the default; the 1060 duplicate-column error on a fresh
-- DB (where the CREATE above already added it) is ignored by database.py.
ALTER TABLE `crop_orders`
    ADD COLUMN `delivery_method` ENUM('farmer_delivers','consumer_pickup')
    NOT NULL DEFAULT 'farmer_delivers'
    AFTER `delivery_notes`;


-- =============================================================================
-- Future tables (stubs for reference — not created yet)
-- =============================================================================

-- notifications : id, user_id, type ENUM('message','match','system'), payload JSON,
--                 is_read TINYINT, created_at DATETIME
-- donor_accounts : id, user_id, preferred_crop_categories VARCHAR(512),
--                  notes TEXT, created_at DATETIME

-- =============================================================================
-- Table 4 : wishlist_items
--
-- Organizations post the crops they need as donation opportunities.
-- Consumers fund them. Farmers fulfil them by shipping the crop to the org.
-- =============================================================================
CREATE TABLE IF NOT EXISTS `wishlist_items` (
    `id`                    INT           NOT NULL AUTO_INCREMENT,
    `organization_id`       INT           NOT NULL,

    -- What is needed
    `crop_name`             VARCHAR(255)  NOT NULL,
    -- Numeric so impact totals can be aggregated (MPCA reporting).
    `quantity_needed`       DECIMAL(10,2) NOT NULL,
    `quantity_unit`         VARCHAR(50)   NOT NULL DEFAULT 'lbs',
    `total_amount_required` DECIMAL(10,2) NOT NULL,

    -- Optional context
    `notes`                 TEXT          NULL,

    -- State
    `status`                ENUM('open','funded','fulfilled','cancelled')
                            NOT NULL DEFAULT 'open',
    `is_group_donation`     TINYINT(1)    NOT NULL DEFAULT 0,
    `amount_donated`        DECIMAL(10,2) NOT NULL DEFAULT 0.00,

    `created_at`            DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`            DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                          ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (`id`),
    KEY `ix_wishlist_org`    (`organization_id`),
    KEY `ix_wishlist_crop`   (`crop_name`),
    KEY `ix_wishlist_status` (`status`),

    CONSTRAINT `fk_wishlist_org`
        FOREIGN KEY (`organization_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
)   ENGINE  = InnoDB
    CHARSET = utf8mb4
    COLLATE = utf8mb4_unicode_ci;


-- =============================================================================
-- Table 5 : wishlist_farmer_links
--
-- Many-to-many association: which farmers are linked to each wishlist item.
-- A wishlist item can be fulfilled by any one of the linked farmers.
-- =============================================================================
CREATE TABLE IF NOT EXISTS `wishlist_farmer_links` (
    `id`               INT      NOT NULL AUTO_INCREMENT,
    `wishlist_item_id` INT      NOT NULL,
    `farmer_id`        INT      NOT NULL,
    `created_at`       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (`id`),
    KEY `ix_wfl_wishlist` (`wishlist_item_id`),
    KEY `ix_wfl_farmer`   (`farmer_id`),

    CONSTRAINT `fk_wfl_wishlist`
        FOREIGN KEY (`wishlist_item_id`) REFERENCES `wishlist_items` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_wfl_farmer`
        FOREIGN KEY (`farmer_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
)   ENGINE  = InnoDB
    CHARSET = utf8mb4
    COLLATE = utf8mb4_unicode_ci;


-- =============================================================================
-- Table 6 : group_donations
--
-- Aggregates multiple-consumer co-funding for one wishlist item.
-- One-to-one with wishlist_items (unique on wishlist_item_id).
-- Must be created before `donations` (FK reference below).
-- =============================================================================
CREATE TABLE IF NOT EXISTS `group_donations` (
    `id`               INT           NOT NULL AUTO_INCREMENT,
    `wishlist_item_id` INT           NOT NULL,

    `total_required`   DECIMAL(10,2) NOT NULL,    -- mirrors wishlist item total
    `amount_pledged`   DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    `donors_needed`    INT           NOT NULL,     -- target number of donors
    `donors_count`     INT           NOT NULL DEFAULT 0,

    `status`           ENUM('open','funded','completed','failed')
                       NOT NULL DEFAULT 'open',

    `created_at`       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                     ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_gd_wishlist` (`wishlist_item_id`),
    KEY `ix_gd_status` (`status`),

    CONSTRAINT `fk_gd_wishlist`
        FOREIGN KEY (`wishlist_item_id`) REFERENCES `wishlist_items` (`id`) ON DELETE CASCADE
)   ENGINE  = InnoDB
    CHARSET = utf8mb4
    COLLATE = utf8mb4_unicode_ci;


-- =============================================================================
-- Table 7 : donations
--
-- One consumer's individual donation toward a wishlist item.
-- group_donation_id is NULL for individual donations.
-- =============================================================================
CREATE TABLE IF NOT EXISTS `donations` (
    `id`                INT           NOT NULL AUTO_INCREMENT,
    `consumer_id`       INT           NOT NULL,
    `farmer_id`         INT           NOT NULL,
    `wishlist_item_id`  INT           NOT NULL,
    `amount`            DECIMAL(10,2) NOT NULL,

    `status`            ENUM('pending','confirmed','refunded')
                        NOT NULL DEFAULT 'pending',

    `group_donation_id` INT           NULL,           -- NULL = individual donation
    `payment_reference` VARCHAR(255)  NULL,           -- Stripe / gateway reference

    `created_at`        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                      ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (`id`),
    KEY `ix_don_consumer`  (`consumer_id`),
    KEY `ix_don_farmer`    (`farmer_id`),
    KEY `ix_don_wishlist`  (`wishlist_item_id`),
    KEY `ix_don_group`     (`group_donation_id`),

    CONSTRAINT `fk_don_consumer`
        FOREIGN KEY (`consumer_id`)       REFERENCES `users`          (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_don_farmer`
        FOREIGN KEY (`farmer_id`)         REFERENCES `users`          (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_don_wishlist`
        FOREIGN KEY (`wishlist_item_id`)  REFERENCES `wishlist_items` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_don_group`
        FOREIGN KEY (`group_donation_id`) REFERENCES `group_donations` (`id`) ON DELETE SET NULL
)   ENGINE  = InnoDB
    CHARSET = utf8mb4
    COLLATE = utf8mb4_unicode_ci;


-- =============================================================================
-- Table 8 : group_donation_participants
--
-- Tracks each consumer who has pledged to a group donation.
-- donation_id is NULL until the group is confirmed/funded.
-- =============================================================================
CREATE TABLE IF NOT EXISTS `group_donation_participants` (
    `id`                INT           NOT NULL AUTO_INCREMENT,
    `group_donation_id` INT           NOT NULL,
    `consumer_id`       INT           NOT NULL,
    `donation_id`       INT           NULL,           -- set when group funded
    `amount_pledged`    DECIMAL(10,2) NOT NULL,
    `joined_at`         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (`id`),
    KEY `ix_gdp_group`    (`group_donation_id`),
    KEY `ix_gdp_consumer` (`consumer_id`),
    KEY `ix_gdp_donation` (`donation_id`),

    CONSTRAINT `fk_gdp_group`
        FOREIGN KEY (`group_donation_id`) REFERENCES `group_donations` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_gdp_consumer`
        FOREIGN KEY (`consumer_id`)       REFERENCES `users`           (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_gdp_donation`
        FOREIGN KEY (`donation_id`)       REFERENCES `donations`       (`id`) ON DELETE SET NULL
)   ENGINE  = InnoDB
    CHARSET = utf8mb4
    COLLATE = utf8mb4_unicode_ci;


-- =============================================================================
-- Table 9 : points_ledger
--
-- Immutable record of every points-earning event for a consumer.
-- One row per confirmed Donation ($20 = 100 pts).
-- =============================================================================
CREATE TABLE IF NOT EXISTS `points_ledger` (
    `id`           INT           NOT NULL AUTO_INCREMENT,
    `consumer_id`  INT           NOT NULL,
    `donation_id`  INT           NOT NULL,
    `points`       INT           NOT NULL,
    `amount_basis` DECIMAL(10,2) NOT NULL,   -- donation amount used to calculate points
    `description`  VARCHAR(512)  NULL,
    `created_at`   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_pl_donation` (`donation_id`),   -- one ledger entry per donation
    KEY `ix_pl_consumer` (`consumer_id`),

    CONSTRAINT `fk_pl_consumer`
        FOREIGN KEY (`consumer_id`) REFERENCES `users`     (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_pl_donation`
        FOREIGN KEY (`donation_id`) REFERENCES `donations` (`id`) ON DELETE CASCADE
)   ENGINE  = InnoDB
    CHARSET = utf8mb4
    COLLATE = utf8mb4_unicode_ci;


-- =============================================================================
-- Table 10 : notification_preferences
--
-- Per-user notification settings (1-to-1 with users).
-- Consumers set price ranges and toggle donation / group-donation alerts.
-- =============================================================================
CREATE TABLE IF NOT EXISTS `notification_preferences` (
    `id`                                  INT           NOT NULL AUTO_INCREMENT,
    `user_id`                             INT           NOT NULL,

    -- Consumer: individual donation notifications
    `donation_notifications_enabled`      TINYINT(1)    NOT NULL DEFAULT 0,
    `donation_min_price`                  DECIMAL(10,2) NULL,    -- NULL = no lower bound
    `donation_max_price`                  DECIMAL(10,2) NULL,    -- NULL = no upper bound

    -- Consumer: group donation notifications
    `group_donation_notifications_enabled` TINYINT(1)   NOT NULL DEFAULT 0,

    `created_at`                          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`                          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                          ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_np_user` (`user_id`),
    KEY `ix_np_user` (`user_id`),

    CONSTRAINT `fk_np_user`
        FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
)   ENGINE  = InnoDB
    CHARSET = utf8mb4
    COLLATE = utf8mb4_unicode_ci;


-- =============================================================================
-- Table 11 : fulfillments
--
-- One row per recorded delivery of a wishlist item — the source of truth for
-- MPCA grant impact metrics. `pounds_delivered` is entered by the organization
-- when it marks an item fulfilled, regardless of the listing's display unit.
--
--   Pounds rescued in a period:
--     SELECT SUM(pounds_delivered) FROM fulfillments
--     WHERE delivered_at BETWEEN :from AND :to
-- =============================================================================
CREATE TABLE IF NOT EXISTS `fulfillments` (
    `id`                 INT           NOT NULL AUTO_INCREMENT,
    `wishlist_item_id`   INT           NOT NULL,
    `organization_id`    INT           NOT NULL,   -- org that received + recorded it
    `farmer_id`          INT           NOT NULL,   -- farmer who delivered

    -- Grant metric: actual pounds of food delivered.
    `pounds_delivered`   DECIMAL(12,2) NOT NULL,

    -- Optional context in the listing's original unit (e.g. 4 crates).
    `quantity_delivered` DECIMAL(10,2) NULL,
    `quantity_unit`      VARCHAR(50)   NULL,

    `notes`              VARCHAR(512)  NULL,
    `delivered_at`       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `created_at`         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (`id`),
    KEY `ix_ful_wishlist`  (`wishlist_item_id`),
    KEY `ix_ful_org`       (`organization_id`),
    KEY `ix_ful_farmer`    (`farmer_id`),
    KEY `ix_ful_delivered` (`delivered_at`),

    CONSTRAINT `fk_ful_wishlist`
        FOREIGN KEY (`wishlist_item_id`) REFERENCES `wishlist_items` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_ful_org`
        FOREIGN KEY (`organization_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_ful_farmer`
        FOREIGN KEY (`farmer_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
)   ENGINE  = InnoDB
    CHARSET = utf8mb4
    COLLATE = utf8mb4_unicode_ci;


-- =============================================================================
-- v4 (human profiles): every account can carry a face and a story.
--
-- Identity used to be a name string, so a farmer, a food shelf and a donor all
-- rendered identically. These four columns are what the profile pages, listing
-- cards and conversation list read from. All NULL-able — an empty profile falls
-- back to an initials avatar, never a broken image.
-- =============================================================================

ALTER TABLE `users`
    ADD COLUMN `avatar_url` VARCHAR(512) NULL
    AFTER `organization_name`;

ALTER TABLE `users`
    ADD COLUMN `tagline` VARCHAR(140) NULL
    AFTER `avatar_url`;

ALTER TABLE `users`
    ADD COLUMN `bio` TEXT NULL
    AFTER `tagline`;

ALTER TABLE `users`
    ADD COLUMN `year_started` SMALLINT NULL
    AFTER `bio`;


-- =============================================================================
-- v5: donations gain an `expired` status.
--
-- Abandoned checkouts are normal — someone opens Stripe and closes the tab —
-- but there was no state for it, so those rows sat `pending` forever and could
-- only be cleared by hand. `expired` is distinct from `refunded`, which means
-- money actually moved and came back.
--
-- MODIFY is naturally idempotent, so this is safe to re-run.
-- =============================================================================

ALTER TABLE `donations`
    MODIFY COLUMN `status` ENUM('pending', 'confirmed', 'refunded', 'expired')
    NOT NULL DEFAULT 'pending';
