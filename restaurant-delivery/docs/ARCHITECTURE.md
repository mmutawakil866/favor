# Restaurant Ordering & Delivery Management System — Technical Architecture

**Version:** 1.0
**Stack:** Django 5 · PostgreSQL 16 · Django Channels · Redis + Celery (required) · Leaflet + OpenStreetMap · Paystack · Cloudinary

---

## 1. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      Browser (HTML/CSS/JS)                    │
│   Customer · Staff · Rider · Admin dashboards                 │
│   Leaflet map (OpenStreetMap tiles) · Chart.js reports        │
└───────────────┬──────────────────────────────┬───────────────┘
                │ HTTPS (pages + JSON)         │ WSS (real-time)
                ▼                              ▼
┌──────────────────────────────┐   ┌───────────────────────────┐
│      Django (ASGI)           │   │  Django Channels Layer     │
│  · Templates (server-side)   │◄─►│  Redis (channel layer)     │
│  · DRF JSON endpoints        │   │  · order status groups     │
│  · Custom auth + RBAC        │   │  · rider location groups   │
└──────┬───────────────┬───────┘   └───────────────────────────┘
       │               │
       ▼               ▼
┌────────────┐  ┌──────────────┐
│ PostgreSQL │  │ Redis (cache)│
│  primary   │  │ + Celery     │
└────────────┘  │ broker/result│
                └──────┬───────┘
                       ▼
              ┌─────────────────┐
              │ Celery workers  │
              │ · notifications │
              │ · ETA refresh   │
              │ · report export │
              └─────────────────┘
```

**Design principle:** pages are server-rendered Django templates; interactive pieces (cart, live order status, rider map, status updates) use `fetch()` against JSON endpoints and WebSockets. This matches the PRD's plain HTML/CSS/JS frontend without requiring a SPA framework.

---

## 2. Django Project Layout

```
restaurant-delivery/
├── manage.py
├── pyproject.toml / requirements.txt
├── .env.example
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── prod.py
│   ├── urls.py
│   ├── asgi.py            # Channels routing
│   └── wsgi.py
├── apps/
│   ├── accounts/          # User, roles, profiles, addresses
│   ├── menu/              # Categories, FoodItem
│   ├── orders/            # Cart, Order, OrderItem, status history
│   ├── payments/          # Paystack integration
│   ├── delivery/          # RiderProfile, Delivery, RiderLocation
│   ├── promotions/        # Campaign, PromoCode
│   ├── notifications/     # In-app + email/SMS
│   ├── reviews/           # Customer ratings (food/service) + comments
│   ├── dashboard/         # Admin/staff/rider dashboards + reports
│   └── core/              # Base models, mixins, context processors
├── templates/
│   ├── base.html
│   ├── customer/ · staff/ · rider/ · admin/
├── static/
│   ├── css/ · js/ · img/
└── docs/
```

### App responsibilities

| App | Responsibility |
|---|---|
| `accounts` | Custom `User` (role-based), customer/rider profiles, delivery addresses |
| `menu` | Categories, food items, images, availability, daily offers |
| `orders` | Cart, checkout, order lifecycle, status transitions, history |
| `payments` | Paystack init/verify, webhooks, payment records |
| `delivery` | Rider registration, assignment, status updates, GPS pings, ETA |
| `promotions` | Campaigns, banners, discounts, scheduling, activation |
| `notifications` | Order events → in-app + email/SMS |
| `reviews` | Post-delivery ratings for food & service (Very Bad → Excellent) + comments |
| `dashboard` | Reports, analytics, role-specific dashboards |
| `core` | Timestamped/soft-delete base models, permissions, mixins |

---

## 3. Authentication & Role-Based Access Control

- **Custom user model** (`accounts.User`) with `role` enum: `customer | staff | rider | admin`.
- Add `AUTH_USER_MODEL = "accounts.User"` **before the first migration**.
- Authorization via Django groups/permissions plus role mixins:
  - `RoleRequiredMixin(role=...)` for class-based views.
  - `@role_required("staff")` decorator for function views.
  - DRF permission classes: `IsCustomer`, `IsStaff`, `IsRider`, `IsAdminRole`.
- Session auth for pages; CSRF protection on all mutating requests.
- Optional JWT (SimpleJWT) if the frontend later moves to a SPA/mobile client.

---

## 4. Request & Data Flow

### 4.1 Ordering flow
```
Browse menu ──► Add to cart (session or DB cart)
   ──► Checkout: address + payment method
   ──► Order created (status=PENDING, unique reference)
   ──► Paystack (online) or cash flag  ──► status=CONFIRMED
   ──► Staff: PREPARING ──► READY_FOR_PICKUP
   ──► Admin assigns rider ──► OUT_FOR_DELIVERY
   ──► Rider: DELIVERED
```
Every transition is written to `order_status_history` and broadcast on the order's WebSocket group.

### 4.2 Real-time order tracking
- Customer page opens `wss://.../ws/orders/<reference>/`.
- `OrderConsumer` joins group `order_<reference>`.
- On status change (view/service), the server calls `group_send` → all clients update instantly.
- Fallback: short polling endpoint if WebSocket unavailable.

### 4.3 Live rider tracking
- Rider app/page posts GPS pings every 5–10 s to `POST /api/delivery/<id>/location/` (only during `OUT_FOR_DELIVERY`).
- Server stores the latest point in `rider_locations`, broadcasts to group `delivery_<id>`.
- Customer map listens on `wss://.../ws/delivery/<id>/` and moves the marker.
- **Consent + privacy:** pings accepted only when the delivery is active and the rider has enabled sharing; location history is pruned after delivery completes.

### 4.4 Map choice
Use **Leaflet + OpenStreetMap** (free, no API key) for dev and MVP. The `maps` facade in `core` abstracts geocoding/routing so Google Maps can be swapped in later (Google Directions/Geocoding API).

---

### 4.5 Delivery fee engine

Server-side, computed at checkout and snapshotted onto the order (`delivery_fee`), never recalculated on read.

- Modes: `FLAT` (fixed fee) or `DISTANCE`.
- Distance formula: `base_fee + max(0, ceil(distance_km - base_distance_km)) × per_km_fee`, rounded to the nearest whole unit.
- `distance_km` from restaurant origin → delivery address via Haversine (Leaflet/OSM routing later for road distance).
- Reject orders beyond `max_delivery_radius_km`.
- Fall back to flat fee + flag for review when coordinates are missing.
- Free delivery when subtotal ≥ `FREE_DELIVERY_THRESHOLD` or a free-delivery promo applies.
- All thresholds/fees live in a cached, admin-editable settings model; changing them does not alter existing orders.

---

## 5. Real-Time (Channels) Design

| Consumer | Group | Payload |
|---|---|---|
| `OrderConsumer` | `order_<reference>` | `{type: "status", status, updated_at}` |
| `DeliveryConsumer` | `delivery_<id>` | `{type: "location", lat, lng, ts}` |

- Channel layer: `channels_redis.core.RedisChannelLayer`.
- ASGI served via **Daphne/Uvicorn** in production.
- Auth: session middleware + `AllowedHostsOriginValidator`; customers may only subscribe to their own orders (checked in `connect`).

---

## 6. Payment (Paystack) Design

1. `POST /api/payments/initialize/` → create `Payment` (status `PENDING`), call Paystack `/transaction/initialize`, return `authorization_url`.
2. User pays → Paystack redirects to callback URL.
3. Server `/payments/callback/` verifies via Paystack `/transaction/verify/<ref>`; on success mark `Payment.SUCCESS`, order `CONFIRMED`.
4. **Webhook** `/payments/webhook/` validates `x-paystack-signature` (HMAC SHA512 with secret key) and is idempotent — verification is the source of truth, never trust the client.
5. Cash-on-delivery: order confirmed but `Payment` stays `PENDING`/`CASH` until rider collects; mark `SUCCESS` on delivery.

Store amounts as `NUMERIC(12,2)` (or integer kobo) — never floats. All cart totals are recomputed server-side at checkout.

---

## 7. Background Tasks (Celery + Redis)

| Task | Purpose |
|---|---|
| `send_order_notification` | Email/SMS/push on status change |
| `recompute_eta` | Update delivery ETA from rider position |
| `deactivate_expired_promotions` | Scheduled campaign switch-off |
| `prune_rider_locations` | Delete pings for completed deliveries |
| `generate_report_export` | CSV/PDF for admin reports |

Redis (broker + result backend + Channels layer + cache) and Celery Beat are **required** per the PRD. Workers and the scheduler are part of every deployment; the app must fail fast and alert if Redis is unreachable rather than silently dropping notifications or real-time events.

---

## 8. Security & Non-Functional

- HTTPS only; secure/HttpOnly cookies; HSTS in production.
- CSRF on all forms; DRF session auth enforces CSRF.
- Passwords hashed with Argon2 (or PBKDF2) via Django.
- Role checks server-side on **every** endpoint — never rely on hidden UI.
- Input validation via Django forms/serializers; parameterized ORM queries (no raw SQL concatenation).
- Rate-limit auth and location endpoints (django-ratelimit / DRF throttling).
- Media: Cloudinary in production, local `MEDIA_ROOT` in dev.
- Structured logging + Sentry (optional).
- Backups: nightly `pg_dump`; order/payment records immutable (soft-archive, no hard delete).

---

## 9. Environment & Configuration

`.env` keys (never committed):
```
DJANGO_SECRET_KEY=
DJANGO_DEBUG=True
DATABASE_URL=postgres://user:pass@localhost:5432/restaurant
REDIS_URL=redis://localhost:6379/0
PAYSTACK_SECRET_KEY=
PAYSTACK_PUBLIC_KEY=
CLOUDINARY_URL=
DEFAULT_FROM_EMAIL=
```

Settings split: `base.py` → `dev.py` / `prod.py`, selected via `DJANGO_SETTINGS_MODULE`. Use `django-environ` or `python-decouple`.

---

## 10. Build Roadmap (aligned to PRD phases)

**Phase 1 — Core Ordering & Admin (MVP)**
1. **Scaffold + custom User + roles** (must precede migrations).
2. **Menu models** + admin CRUD.
3. **Cart → Checkout → Orders** with status lifecycle + history.
4. **Delivery fee engine** (flat + distance) snapshotted on orders.
5. **Staff dashboard** (status updates).
6. **Payments (Paystack)** init/verify/webhook + cancellation/payment-failure rules.
7. **Redis + Celery/Beat baseline**.

**Phase 2 — Real-Time Tracking & Promotions**
8. **Rider management + assignment + GPS pings**.
9. **Channels WebSockets** for order status + rider location.
10. **Leaflet map** for customer tracking.
11. **Promotions & campaigns** + promotional notifications.
12. **Notifications** for all order/rider events.

**Phase 3 — Feedback, Reporting & Hardening**
13. **Customer reviews** (food/service ratings + comments, post-delivery only).
14. **Reports & analytics** (incl. review averages).
15. Security, performance, observability and test hardening.

---

## 11. Key Decisions Summary

| Decision | Choice | Rationale |
|---|---|---|
| Frontend | Server-rendered + fetch/WS | Matches PRD (HTML/CSS/JS), fast to build |
| Auth | Session + custom role user | Simple, secure; JWT optional later |
| Maps | Leaflet + OSM | Free, no key, easy Google swap |
| Real-time | Channels + Redis | Native Django, supports WS |
| Payments | Paystack (server verify + webhook) | Secure, idempotent |
| Cart | DB cart for logged-in users | Survives sessions; easy to audit |
| Money | `NUMERIC(12,2)` | No float rounding errors |
| History | Status history + soft-delete | Meets data-integrity requirement |

The full relational schema is in [`schema.sql`](./schema.sql).
