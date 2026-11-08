-- ============================================================================
-- Restaurant Ordering & Delivery Management System
-- PostgreSQL 16 schema (v1.0)
--
-- Run on a fresh database:
--   createdb restaurant
--   psql -d restaurant -f docs/schema.sql
--
-- Conventions:
--   * snake_case, plural-free table names prefixed by Django app label
--     (accounts_, menu_, orders_, payments_, delivery_, promotions_, notifications_)
--   * BIGSERIAL primary keys
--   * money = NUMERIC(12,2); never FLOAT
--   * timestamptz for all timestamps
--   * order/payment history is immutable (no hard deletes of orders)
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- Enumerated types
-- ----------------------------------------------------------------------------
CREATE TYPE user_role          AS ENUM ('CUSTOMER', 'STAFF', 'RIDER', 'ADMIN');
CREATE TYPE order_status       AS ENUM (
    'PENDING', 'CONFIRMED', 'PREPARING', 'READY_FOR_PICKUP',
    'OUT_FOR_DELIVERY', 'DELIVERED', 'CANCELLED'
);
CREATE TYPE payment_method     AS ENUM ('CARD', 'CASH');
CREATE TYPE payment_status     AS ENUM ('PENDING', 'SUCCESS', 'FAILED', 'REFUNDED');
CREATE TYPE delivery_status    AS ENUM ('ASSIGNED', 'IN_TRANSIT', 'DELIVERED', 'FAILED', 'CANCELLED');
CREATE TYPE discount_type      AS ENUM ('PERCENTAGE', 'FIXED');
CREATE TYPE notification_channel AS ENUM ('IN_APP', 'EMAIL', 'SMS');
CREATE TYPE review_rating      AS ENUM ('VERY_BAD', 'BAD', 'OKAY', 'GOOD', 'EXCELLENT');

-- ----------------------------------------------------------------------------
-- Shared updated_at trigger
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 1. ACCOUNTS
-- ============================================================================

-- Custom Django user (AbstractUser + role + phone)
CREATE TABLE accounts_user (
    id               BIGSERIAL PRIMARY KEY,
    password         VARCHAR(128) NOT NULL,
    last_login       TIMESTAMPTZ,
    is_superuser     BOOLEAN NOT NULL DEFAULT FALSE,
    username         VARCHAR(150) NOT NULL UNIQUE,
    first_name       VARCHAR(150) NOT NULL DEFAULT '',
    last_name        VARCHAR(150) NOT NULL DEFAULT '',
    email            VARCHAR(254) NOT NULL UNIQUE,
    phone            VARCHAR(20),
    role             user_role NOT NULL DEFAULT 'CUSTOMER',
    is_staff         BOOLEAN NOT NULL DEFAULT FALSE,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    is_email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    date_joined      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_user_role  ON accounts_user (role);
CREATE INDEX idx_user_email ON accounts_user (email);
CREATE TRIGGER trg_user_updated BEFORE UPDATE ON accounts_user
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Customer-specific data (one-to-one with a CUSTOMER user)
CREATE TABLE accounts_customerprofile (
    id               BIGSERIAL PRIMARY KEY,
    user_id          BIGINT NOT NULL UNIQUE REFERENCES accounts_user (id) ON DELETE CASCADE,
    default_address_id BIGINT,                 -- FK added after accounts_address
    loyalty_points   INT NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_customerprofile_updated BEFORE UPDATE ON accounts_customerprofile
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Saved delivery addresses
CREATE TABLE accounts_address (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES accounts_user (id) ON DELETE CASCADE,
    label       VARCHAR(50) NOT NULL DEFAULT 'Home',
    line1       VARCHAR(255) NOT NULL,
    line2       VARCHAR(255),
    city        VARCHAR(100) NOT NULL,
    state       VARCHAR(100) NOT NULL,
    postal_code VARCHAR(20),
    country     VARCHAR(100) NOT NULL DEFAULT 'Nigeria',
    latitude    NUMERIC(9,6),
    longitude   NUMERIC(9,6),
    is_default  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_address_user ON accounts_address (user_id);
CREATE TRIGGER trg_address_updated BEFORE UPDATE ON accounts_address
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE accounts_customerprofile
    ADD CONSTRAINT fk_customer_default_address
    FOREIGN KEY (default_address_id) REFERENCES accounts_address (id) ON DELETE SET NULL;

-- Rider-specific data (one-to-one with a RIDER user)
CREATE TABLE accounts_riderprofile (
    id             BIGSERIAL PRIMARY KEY,
    user_id        BIGINT NOT NULL UNIQUE REFERENCES accounts_user (id) ON DELETE CASCADE,
    vehicle_type   VARCHAR(50) NOT NULL DEFAULT 'MOTORCYCLE',
    plate_number   VARCHAR(20),
    is_available   BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified    BOOLEAN NOT NULL DEFAULT FALSE,
    current_lat    NUMERIC(9,6),
    current_lng    NUMERIC(9,6),
    last_seen      TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_rider_available ON accounts_riderprofile (is_available, is_verified);
CREATE TRIGGER trg_riderprofile_updated BEFORE UPDATE ON accounts_riderprofile
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- 2. MENU
-- ============================================================================

CREATE TABLE menu_category (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    slug        VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    image       VARCHAR(500),
    sort_order  INT NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_category_updated BEFORE UPDATE ON menu_category
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE menu_fooditem (
    id              BIGSERIAL PRIMARY KEY,
    category_id     BIGINT NOT NULL REFERENCES menu_category (id) ON DELETE RESTRICT,
    name            VARCHAR(150) NOT NULL,
    slug            VARCHAR(170) NOT NULL UNIQUE,
    description     TEXT,
    price           NUMERIC(12,2) NOT NULL CHECK (price >= 0),
    image           VARCHAR(500),
    is_available    BOOLEAN NOT NULL DEFAULT TRUE,
    is_featured     BOOLEAN NOT NULL DEFAULT FALSE,   -- special meals / daily offers
    prep_time_minutes INT NOT NULL DEFAULT 20 CHECK (prep_time_minutes >= 0),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_fooditem_category  ON menu_fooditem (category_id);
CREATE INDEX idx_fooditem_available ON menu_fooditem (is_available);
CREATE TRIGGER trg_fooditem_updated BEFORE UPDATE ON menu_fooditem
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- 3. PROMOTIONS & CAMPAIGNS
-- ============================================================================

CREATE TABLE promotions_campaign (
    id             BIGSERIAL PRIMARY KEY,
    title          VARCHAR(150) NOT NULL,
    slug           VARCHAR(170) NOT NULL UNIQUE,
    description    TEXT,
    banner_image   VARCHAR(500),
    discount_type  discount_type NOT NULL DEFAULT 'PERCENTAGE',
    discount_value NUMERIC(12,2) NOT NULL CHECK (discount_value >= 0),
    start_date     TIMESTAMPTZ NOT NULL,
    end_date       TIMESTAMPTZ NOT NULL,
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id  BIGINT REFERENCES accounts_user (id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_campaign_dates CHECK (end_date > start_date)
);
CREATE INDEX idx_campaign_active_window ON promotions_campaign (is_active, start_date, end_date);
CREATE TRIGGER trg_campaign_updated BEFORE UPDATE ON promotions_campaign
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Which food items a campaign applies to (M2M)
CREATE TABLE promotions_campaign_items (
    id          BIGSERIAL PRIMARY KEY,
    campaign_id BIGINT NOT NULL REFERENCES promotions_campaign (id) ON DELETE CASCADE,
    fooditem_id BIGINT NOT NULL REFERENCES menu_fooditem (id) ON DELETE CASCADE,
    UNIQUE (campaign_id, fooditem_id)
);

CREATE TABLE promotions_promocode (
    id               BIGSERIAL PRIMARY KEY,
    code             VARCHAR(50) NOT NULL UNIQUE,
    campaign_id      BIGINT REFERENCES promotions_campaign (id) ON DELETE SET NULL,
    discount_type    discount_type NOT NULL DEFAULT 'PERCENTAGE',
    discount_value   NUMERIC(12,2) NOT NULL CHECK (discount_value >= 0),
    min_order_amount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (min_order_amount >= 0),
    max_uses         INT CHECK (max_uses IS NULL OR max_uses >= 0),
    used_count       INT NOT NULL DEFAULT 0 CHECK (used_count >= 0),
    valid_from       TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_until      TIMESTAMPTZ,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_promocode_updated BEFORE UPDATE ON promotions_promocode
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- 4. CART
-- ============================================================================

CREATE TABLE orders_cart (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES accounts_user (id) ON DELETE CASCADE,
    session_key VARCHAR(64),                  -- for guest carts
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_cart_owner CHECK (user_id IS NOT NULL OR session_key IS NOT NULL)
);
CREATE INDEX idx_cart_user    ON orders_cart (user_id);
CREATE INDEX idx_cart_session ON orders_cart (session_key);
CREATE TRIGGER trg_cart_updated BEFORE UPDATE ON orders_cart
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE orders_cartitem (
    id          BIGSERIAL PRIMARY KEY,
    cart_id     BIGINT NOT NULL REFERENCES orders_cart (id) ON DELETE CASCADE,
    fooditem_id BIGINT NOT NULL REFERENCES menu_fooditem (id) ON DELETE CASCADE,
    quantity    INT NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_price  NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0),
    UNIQUE (cart_id, fooditem_id)
);

-- ============================================================================
-- 5. ORDERS
-- ============================================================================

CREATE TABLE orders_order (
    id                  BIGSERIAL PRIMARY KEY,
    reference           VARCHAR(24) NOT NULL UNIQUE,   -- e.g. ORD-20261105-8F3A2C
    customer_id         BIGINT NOT NULL REFERENCES accounts_user (id) ON DELETE RESTRICT,
    address_id          BIGINT REFERENCES accounts_address (id) ON DELETE SET NULL,
    promo_code_id       BIGINT REFERENCES promotions_promocode (id) ON DELETE SET NULL,
    status              order_status NOT NULL DEFAULT 'PENDING',
    payment_method      payment_method NOT NULL DEFAULT 'CARD',
    subtotal            NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    discount_total      NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (discount_total >= 0),
    delivery_fee        NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (delivery_fee >= 0),
    total               NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (total >= 0),
    -- delivery address snapshot (preserved even if address is edited/deleted)
    delivery_line1      VARCHAR(255),
    delivery_city       VARCHAR(100),
    delivery_state      VARCHAR(100),
    notes               TEXT,
    placed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_at        TIMESTAMPTZ,
    delivered_at        TIMESTAMPTZ,
    cancelled_at        TIMESTAMPTZ,
    cancellation_reason TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_order_customer ON orders_order (customer_id, placed_at DESC);
CREATE INDEX idx_order_status   ON orders_order (status);
CREATE INDEX idx_order_placed   ON orders_order (placed_at DESC);
CREATE TRIGGER trg_order_updated BEFORE UPDATE ON orders_order
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE orders_orderitem (
    id          BIGSERIAL PRIMARY KEY,
    order_id    BIGINT NOT NULL REFERENCES orders_order (id) ON DELETE CASCADE,
    fooditem_id BIGINT REFERENCES menu_fooditem (id) ON DELETE SET NULL,
    name_snapshot VARCHAR(150) NOT NULL,      -- immutable record of what was sold
    unit_price  NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0),
    quantity    INT NOT NULL CHECK (quantity > 0),
    line_total  NUMERIC(12,2) NOT NULL CHECK (line_total >= 0)
);
CREATE INDEX idx_orderitem_order ON orders_orderitem (order_id);

-- Full audit trail of every status transition
CREATE TABLE orders_orderstatushistory (
    id            BIGSERIAL PRIMARY KEY,
    order_id      BIGINT NOT NULL REFERENCES orders_order (id) ON DELETE CASCADE,
    status        order_status NOT NULL,
    changed_by_id BIGINT REFERENCES accounts_user (id) ON DELETE SET NULL,
    note          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_status_history_order ON orders_orderstatushistory (order_id, created_at);

-- ============================================================================
-- 6. PAYMENTS
-- ============================================================================

CREATE TABLE payments_payment (
    id                  BIGSERIAL PRIMARY KEY,
    order_id            BIGINT NOT NULL REFERENCES orders_order (id) ON DELETE RESTRICT,
    reference           VARCHAR(64) NOT NULL UNIQUE,
    provider            VARCHAR(30) NOT NULL DEFAULT 'PAYSTACK',
    amount              NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    currency            VARCHAR(3) NOT NULL DEFAULT 'NGN',
    status              payment_status NOT NULL DEFAULT 'PENDING',
    authorization_url   VARCHAR(500),
    provider_reference  VARCHAR(100),
    paid_at             TIMESTAMPTZ,
    raw_response        JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_payment_order  ON payments_payment (order_id);
CREATE INDEX idx_payment_status ON payments_payment (status);
CREATE TRIGGER trg_payment_updated BEFORE UPDATE ON payments_payment
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- 7. DELIVERY & LIVE LOCATION
-- ============================================================================

CREATE TABLE delivery_delivery (
    id            BIGSERIAL PRIMARY KEY,
    order_id      BIGINT NOT NULL UNIQUE REFERENCES orders_order (id) ON DELETE RESTRICT,
    rider_id      BIGINT REFERENCES accounts_riderprofile (id) ON DELETE SET NULL,
    status        delivery_status NOT NULL DEFAULT 'ASSIGNED',
    assigned_at   TIMESTAMPTZ,
    picked_up_at  TIMESTAMPTZ,
    delivered_at  TIMESTAMPTZ,
    current_lat   NUMERIC(9,6),
    current_lng   NUMERIC(9,6),
    eta_minutes   INT CHECK (eta_minutes IS NULL OR eta_minutes >= 0),
    distance_km   NUMERIC(7,2) CHECK (distance_km IS NULL OR distance_km >= 0),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_delivery_rider  ON delivery_delivery (rider_id, status);
CREATE INDEX idx_delivery_status ON delivery_delivery (status);
CREATE TRIGGER trg_delivery_updated BEFORE UPDATE ON delivery_delivery
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- GPS ping history (pruned after delivery completes)
CREATE TABLE delivery_riderlocation (
    id          BIGSERIAL PRIMARY KEY,
    delivery_id BIGINT NOT NULL REFERENCES delivery_delivery (id) ON DELETE CASCADE,
    rider_id    BIGINT NOT NULL REFERENCES accounts_riderprofile (id) ON DELETE CASCADE,
    latitude    NUMERIC(9,6) NOT NULL,
    longitude   NUMERIC(9,6) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_riderlocation_delivery ON delivery_riderlocation (delivery_id, recorded_at DESC);
CREATE INDEX idx_riderlocation_rider    ON delivery_riderlocation (rider_id, recorded_at DESC);

-- ============================================================================
-- 8. NOTIFICATIONS
-- ============================================================================

CREATE TABLE notifications_notification (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES accounts_user (id) ON DELETE CASCADE,
    order_id   BIGINT REFERENCES orders_order (id) ON DELETE SET NULL,
    title      VARCHAR(150) NOT NULL,
    message    TEXT NOT NULL,
    channel    notification_channel NOT NULL DEFAULT 'IN_APP',
    is_read    BOOLEAN NOT NULL DEFAULT FALSE,
    sent_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notification_user ON notifications_notification (user_id, is_read, created_at DESC);

-- ============================================================================
-- 9. CUSTOMER REVIEWS
--
-- One review per delivered order. Customers rate the food and the service
-- separately on a 5-point scale (VERY_BAD, BAD, OKAY, GOOD, EXCELLENT) and
-- can leave a comment about either. `overall_rating` is derived/stored for
-- quick reporting.
-- ============================================================================

CREATE TABLE reviews_review (
    id             BIGSERIAL PRIMARY KEY,
    order_id       BIGINT NOT NULL UNIQUE REFERENCES orders_order (id) ON DELETE CASCADE,
    customer_id    BIGINT NOT NULL REFERENCES accounts_user (id) ON DELETE CASCADE,
    overall_rating review_rating NOT NULL,
    food_rating    review_rating NOT NULL,
    service_rating review_rating NOT NULL,
    comment        TEXT,                       -- "was the food and service good?"
    is_visible     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_review_customer ON reviews_review (customer_id, created_at DESC);
CREATE INDEX idx_review_rating   ON reviews_review (overall_rating);
CREATE TRIGGER trg_review_updated BEFORE UPDATE ON reviews_review
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- 10. REPORTING VIEW (convenience for admin dashboards)
-- ============================================================================

CREATE VIEW vw_order_summary AS
SELECT
    o.id,
    o.reference,
    o.status,
    o.payment_method,
    o.total,
    o.placed_at,
    o.delivered_at,
    u.id   AS customer_id,
    u.email AS customer_email,
    d.id   AS delivery_id,
    d.status AS delivery_status,
    r.id   AS rider_id,
    ru.email AS rider_email
FROM orders_order o
JOIN accounts_user u       ON u.id = o.customer_id
LEFT JOIN delivery_delivery d ON d.order_id = o.id
LEFT JOIN accounts_riderprofile r ON r.id = d.rider_id
LEFT JOIN accounts_user ru ON ru.id = r.user_id;

-- Daily revenue / order counts
CREATE VIEW vw_daily_sales AS
SELECT
    date_trunc('day', placed_at) AS day,
    COUNT(*) FILTER (WHERE status <> 'CANCELLED')                     AS orders_count,
    COUNT(*) FILTER (WHERE status = 'CANCELLED')                      AS cancelled_count,
    COALESCE(SUM(total) FILTER (WHERE status = 'DELIVERED'), 0)       AS revenue
FROM orders_order
GROUP BY date_trunc('day', placed_at);

-- Average ratings per food item (numeric score 1..5 for aggregation)
CREATE VIEW vw_food_ratings AS
SELECT
    f.id            AS fooditem_id,
    f.name          AS fooditem_name,
    COUNT(r.id)     AS review_count,
    ROUND(AVG(
        CASE r.food_rating
            WHEN 'VERY_BAD'  THEN 1
            WHEN 'BAD'       THEN 2
            WHEN 'OKAY'      THEN 3
            WHEN 'GOOD'      THEN 4
            WHEN 'EXCELLENT' THEN 5
        END
    ), 2) AS avg_food_rating
FROM menu_fooditem f
JOIN orders_orderitem oi ON oi.fooditem_id = f.id
JOIN reviews_review r    ON r.order_id = oi.order_id AND r.is_visible
GROUP BY f.id, f.name;

COMMIT;

-- ============================================================================
-- DJANGO MODEL MAPPING (for reference)
-- ----------------------------------------------------------------------------
-- accounts.User              -> accounts_user            (AbstractUser + role/phone)
-- accounts.CustomerProfile   -> accounts_customerprofile
-- accounts.Address           -> accounts_address
-- accounts.RiderProfile      -> accounts_riderprofile
-- menu.Category              -> menu_category
-- menu.FoodItem              -> menu_fooditem
-- promotions.Campaign        -> promotions_campaign (+ promotions_campaign_items M2M)
-- promotions.PromoCode       -> promotions_promocode
-- orders.Cart                -> orders_cart
-- orders.CartItem            -> orders_cartitem
-- orders.Order               -> orders_order
-- orders.OrderItem           -> orders_orderitem
-- orders.OrderStatusHistory  -> orders_orderstatushistory
-- payments.Payment           -> payments_payment
-- delivery.Delivery          -> delivery_delivery
-- delivery.RiderLocation     -> delivery_riderlocation
-- notifications.Notification -> notifications_notification
-- reviews.Review             -> reviews_review           (overall/food/service + comment)
--
-- NOTE: When scaffolding Django, prefer `makemigrations` from models so that
-- Django's auth/contenttypes/admin tables are created too. Treat this file as
-- the authoritative reference for the domain tables and constraints.
-- ============================================================================
