# PRODUCT REQUIREMENTS DOCUMENT (PRD)
## Restaurant Ordering and Delivery Management System

**Version:** 1.1 — adds Notifications, Reviews, Cancellation/Payment-failure rules, Delivery-fee logic, and Milestone phasing; Redis/Celery now required.
**Project Type:** Web Application
**Backend:** Python + Django
**Frontend:** HTML, CSS, JavaScript
**Database:** PostgreSQL

---

## 1. Project Overview

The Restaurant Ordering and Delivery Management System is a web-based platform designed to digitize restaurant operations by allowing customers to order food online, make payments, track their orders and monitor dispatch riders in real time.

The system will also provide restaurant administrators and staff with tools to manage orders, food menus, delivery operations, customer records, promotional campaigns, notifications, customer reviews and business reporting.

## 2. Project Objectives

- Allow customers to conveniently order food online.
- Provide real-time order status updates.
- Enable customers to track dispatch riders on a map.
- Maintain records of pending, completed and cancelled orders.
- Simplify restaurant menu and food availability management.
- Provide promotional tools for seasonal campaigns and special offers.
- Improve delivery coordination and restaurant operations.
- Capture customer feedback (food & service) to improve quality.
- Notify customers and staff of key order events reliably.

## 3. User Roles

| User | Responsibilities |
|---|---|
| Customer | Browse food, place orders, make payments, track deliveries, receive notifications and leave reviews. |
| Administrator | Manage users, orders, menus, promotions, delivery fees, notifications, reviews and system settings. |
| Restaurant Staff | Receive orders, update preparation status, manage food availability and monitor notifications. |
| Dispatch Rider | View assigned deliveries, update delivery status, share live location and receive assignment notifications. |

---

## 4. Functional Requirements

### 4.1 Customer Management
- Customer registration and login.
- Manage personal profiles.
- Save and manage delivery addresses (with map pin/lat-lng).
- View previous orders.
- Receive order notifications.
- Manage notification preferences (in-app, email, SMS).

### 4.2 Food and Menu Management
- Display available food items with pictures, descriptions and prices.
- Organize meals into categories.
- Allow administrators to add, edit and remove food items.
- Update food prices and availability.
- Display special meals and daily offers.
- Display aggregate customer ratings per food item (where reviews exist).

### 4.3 Online Ordering
- Customers can browse meals and add items to a shopping cart.
- Customers can specify quantities and delivery addresses.
- Customers can review orders before checkout.
- Support online and cash-on-delivery payment options.
- Generate a unique order reference for every order.
- Allow order cancellation according to the cancellation rules in §4.11.
- Compute and display the delivery fee at checkout using the rules in §4.12.

### 4.4 Order Management and Tracking

Every order must have a status:

- Pending
- Confirmed
- Preparing
- Ready for Pickup
- Out for Delivery
- Delivered
- Cancelled

The restaurant dashboard must allow authorized staff to update order statuses.

Customers must be able to monitor their order progress.

The system must maintain historical records of all orders, including completed and cancelled orders.

Every status transition must be written to an immutable status-history record (actor, timestamp, optional note).

### 4.5 Dispatch Rider Management
- Administrators can register and manage dispatch riders.
- Assign orders to available riders.
- Riders can view their assigned deliveries.
- Riders can update delivery statuses.
- Riders can share their GPS location.
- Customers can view the assigned rider's live location on a map.
- Riders receive assignment and cancellation notifications.

### 4.6 Live Location Tracking

The system should integrate Google Maps or OpenStreetMap to provide:

- Rider location display.
- Delivery route visualization.
- Customer delivery destination.
- Estimated delivery time where supported.

Redis and Django Channels/WebSockets are required to support real-time location and order updates.

Location sharing should only operate during active deliveries, subject to rider consent, and location history must be pruned after delivery completion.

### 4.7 Promotions and Campaign Management

Administrators should be able to:
- Create promotional campaigns.
- Upload promotional banners and images.
- Set campaign start and end dates.
- Create discounts and special offers (percentage or fixed amount).
- Create promo codes with usage limits, minimum spend and validity windows.
- Activate or deactivate promotions.

Examples include:
- Eid promotions.
- Christmas promotions.
- Valentine's Day offers.
- Weekend discounts.
- Special food packages.

Active promotions should be displayed on the customer website, and promotional announcements may be broadcast through the notification system.

### 4.8 Reports and Records

The administrator should have access to:
- Total orders.
- Pending orders.
- Completed orders.
- Cancelled orders.
- Total sales and revenue.
- Popular food items.
- Delivery records.
- Customer records.
- Customer review averages (food & service).

Records should be filterable by date and order status.

### 4.9 Notifications (NEW)

The system must notify the right users at the right time across the order lifecycle.

**Supported channels**
- In-app notifications (notification center + unread badge).
- Email (transactional).
- SMS (optional, enabled per restaurant configuration).
- Real-time push via WebSockets for active order/rider updates.

**Trigger events**
- Account registration / password reset.
- Order placed (customer + staff).
- Order confirmed, preparing, ready for pickup, out for delivery, delivered (customer).
- Order cancelled (customer, staff, rider as applicable).
- Payment success, payment failure, refund issued.
- Rider assigned / reassigned / delivery cancelled (rider + customer).
- New promotion or campaign broadcast (opt-in customers).
- Review request after delivery.

**Rules**
- Notifications must be created through background tasks (Celery) so page requests are never blocked.
- Failed delivery must be retried with exponential backoff; permanent failures are logged and do not block order processing.
- Users can opt out of email/SMS but must always receive in-app status notifications.
- Staff/rider dashboards show an unread count; admins can broadcast promotional notifications to opted-in customers.
- All notifications store channel, status, timestamp and related order.

### 4.10 Customer Reviews (NEW)

After an order is delivered, customers can rate and comment on their experience.

**Rating scale** (applies to each dimension):
- Very Bad
- Bad
- Okay
- Good
- Excellent

**Review fields**
- Overall rating.
- Food rating.
- Service rating.
- Optional comment: whether the food and service were good or not.
- Timestamps; visibility flag for moderation.

**Rules**
- Only the customer who placed a `DELIVERED` order may review it.
- One review per order.
- Cancelled or undelivered orders cannot be reviewed.
- Reviews may be edited within 7 days of submission.
- Admins can hide reviews that violate content policy (soft-hide, never hard delete).
- Aggregate food ratings are shown on menu items; service/overall averages appear in admin reports.
- Review requests are sent automatically after delivery via the notification system.

### 4.11 Cancellation Rules (NEW)

**Customer-initiated cancellation**
- Allowed while the order is `PENDING` or `CONFIRMED` (i.e., before `PREPARING`).
- Once the order is `PREPARING` or later, cancellation requires staff/admin approval and may be declined.
- A `DELIVERED` order can never be cancelled (it may be refunded only under a separate dispute process).
- Every cancellation records the actor, reason and timestamp in order status history.

**Cancellation outcomes by payment method**
| Order state | Card (paid) | Cash on delivery |
|---|---|---|
| Pending / Confirmed | Automatic full refund via Paystack | No charge; order closed |
| Preparing or later | Refund at restaurant discretion (full/partial or store credit) | No charge; order closed; possible no-show fee at admin discretion |
| Out for delivery | Admin-only; refund decided case-by-case | Admin-only; no charge |
| Delivered | Not cancellable | Not cancellable |

**System/staff-initiated cancellation**
- Staff/admin may cancel an order with a mandatory reason.
- Rider may mark a delivery `FAILED` (e.g., customer unreachable); admin then decides whether to cancel or reschedule.
- Cancellation triggers customer notification and, if paid, initiates/queues the refund.

### 4.12 Delivery Fee Logic (NEW)

Delivery fees are configured by the administrator and computed **server-side at checkout**. The computed fee is snapshotted onto the order so later configuration changes never alter historical orders.

**Supported modes**
1. **Flat rate** — a single fixed fee for every delivery (e.g., ₦1,000).
2. **Distance-based** — fee derived from the road/Haversine distance between the restaurant origin and the customer's delivery address.

**Distance-based formula (default)**
```
fee = base_fee + max(0, ceil(distance_km - base_distance_km)) × per_km_fee
```
- `distance_km` = distance from restaurant origin to delivery destination.
- Fee is rounded to the nearest whole currency unit.
- If distance exceeds `max_delivery_radius_km`, the order is rejected as out of range.

**Configuration settings**
| Setting | Meaning | Example |
|---|---|---|
| `DELIVERY_FEE_MODE` | `FLAT` or `DISTANCE` | `DISTANCE` |
| `FLAT_DELIVERY_FEE` | Fee used in flat mode | ₦1,000 |
| `BASE_DELIVERY_FEE` | Starting fee in distance mode | ₦500 |
| `BASE_DISTANCE_KM` | Distance covered by the base fee | 3 km |
| `PER_KM_FEE` | Fee per additional km | ₦150 |
| `MAX_DELIVERY_RADIUS_KM` | Maximum deliverable distance | 15 km |
| `FREE_DELIVERY_THRESHOLD` | Optional cart subtotal for free delivery | ₦20,000 |

**Rules**
- If `DELIVERY_FEE_MODE = DISTANCE` but coordinates are unavailable, fall back to `FLAT_DELIVERY_FEE` and flag the order for manual review.
- Free delivery applies when the subtotal meets `FREE_DELIVERY_THRESHOLD` (if set) or a valid free-delivery promo is applied.
- Delivery fee is shown in the cart summary, at checkout, on the order confirmation and in admin reports.
- Delivery fee is excluded from discount calculations unless a promo explicitly targets it.
- Admin can override the fee for a specific order with a logged reason.

### 4.13 Payment Failure Rules (NEW)

**Online (Paystack)**
- If Paystack initialization fails, the order stays `PENDING`, no payment record is marked successful, and the customer is shown a retry option.
- Payment is confirmed **only** after server-side verification (`/transaction/verify`) or a valid, signature-checked webhook — never from client redirect params alone.
- On verification failure, amount/currency mismatch or an invalid signature:
  - Mark the `Payment` as `FAILED`.
  - Keep the order `PENDING` (do not confirm it).
  - Log the raw provider response and flag for admin review on amount mismatch.
- Failed payments may be retried; each attempt creates a new payment reference tied to the order.
- If payment is not completed within **15 minutes**, a Celery task automatically cancels the order and releases any reserved stock.
- Webhooks are idempotent: duplicate events for a reference are ignored (safe to replay).
- Successful payments followed by cancellation are refunded per §4.11; refund status is tracked on the payment record.

**Cash on delivery**
- Order is confirmed without an online payment; the `Payment` remains `PENDING` with method `CASH`.
- If the rider cannot collect payment or the customer refuses delivery, the delivery is marked `FAILED`, the payment is marked `FAILED`, and the order is reported to admin.
- Collected cash is marked `SUCCESS` on delivery and included in revenue reports.

**General**
- Payment failures never delete order items; the order remains visible in history with its failure reason.
- Every payment state change is timestamped and auditable.

---

## 5. Non-Functional Requirements

- **Security:** Secure authentication and role-based access control.
- **Performance:** Pages and order operations should respond efficiently; long-running work (notifications, ETA, exports) runs in Celery.
- **Responsiveness:** The website must work on desktops, tablets and mobile devices.
- **Reliability:** Orders and payment records must be stored consistently; Redis-backed task queues must be monitored and retried.
- **Scalability:** The architecture should support future expansion.
- **Data Integrity:** Historical order and payment records must be preserved; status history and reviews are immutable/soft-deleted.
- **Usability:** Interfaces should be simple and easy to navigate.
- **Availability:** Real-time features degrade to polling if WebSockets drop; critical order flows must not depend on optional channels.

## 6. Technology Stack

| Component | Technology |
|---|---|
| Backend | Python + Django |
| Frontend | HTML, CSS, JavaScript |
| Database | PostgreSQL |
| Real-time communication | Django Channels + WebSockets |
| Caching / Background tasks | Redis + Celery (**Required**) |
| Maps and location | Google Maps or OpenStreetMap (Leaflet) |
| Payment integration | Paystack |
| Image storage | Cloudinary or local storage during development |
| Task scheduling | Celery Beat (Required, with Celery) |

Redis and Celery are **required** components — they back WebSocket channels, caching, notification delivery, ETA recomputation, promotion scheduling and report exports.

## 7. Main System Modules

1. Authentication and User Management
2. Customer Dashboard
3. Food and Menu Management
4. Shopping Cart and Checkout
5. Order Management
6. Payment Management
7. Dispatch Rider Management
8. Live Delivery Tracking
9. Promotions and Campaigns
10. Notifications
11. Customer Reviews
12. Reports and Analytics

## 8. Milestones and Phasing

Work is organized into delivery phases so the team can plan agile sprints and ship value incrementally.

### Phase 1 — Core Ordering & Admin (MVP)
**Goal:** A customer can browse, order, pay (or choose cash) and staff/admin can manage the full order lifecycle.

- Project scaffold, settings split, PostgreSQL, custom User + roles/RBAC.
- Menu & category management (admin CRUD, availability, images).
- Cart, checkout, delivery fee engine (flat + distance), order creation with unique references.
- Order lifecycle + status history; staff dashboard for status updates.
- Customer dashboard (profile, addresses, order history).
- Paystack integration: initialize, verify, webhook; cash-on-delivery flag.
- Cancellation and payment-failure rules (§4.11, §4.13).
- Admin basics: users, orders, menus.
- Redis + Celery baseline (background worker + scheduler).

**Exit criteria:** End-to-end order from menu → checkout → payment → preparation → delivered/cancelled, with correct fees and audit history.

### Phase 2 — Real-Time Tracking & Promotions
**Goal:** Deliveries are transparent in real time and marketing campaigns drive orders.

- Rider registration/management, availability and order assignment.
- Rider dashboard: assigned deliveries, status updates, GPS sharing (consent-gated).
- Django Channels + Redis: live order status and rider location over WebSockets.
- Leaflet/OpenStreetMap customer tracking (rider marker, route, destination, ETA).
- Promotions & campaigns: banners, discounts, promo codes, scheduling, activation.
- Notification delivery for all order/rider events (in-app + email).
- Admin broadcast of promotional notifications.

**Exit criteria:** Customer watches rider progress live; active promotions display and apply correctly at checkout.

### Phase 3 — Feedback, Reporting & Hardening
**Goal:** Operate the business with insight and quality controls.

- Customer reviews (overall/food/service + comments), moderation and aggregate ratings.
- Review request notifications after delivery.
- Reports & analytics: orders, revenue, popular items, delivery records, review averages, date/status filters.
- Notification preferences, SMS channel (if enabled) and retry/backoff hardening.
- Security hardening, rate limiting, backups, monitoring, test coverage.
- Performance and scalability tuning.

**Exit criteria:** Admin can measure sales/quality, customers can review, and the system meets security/reliability targets.

### Sprint Mapping (suggested 2-week sprints)
| Sprint | Focus |
|---|---|
| 1 | Scaffold, auth, roles, menu models |
| 2 | Cart, checkout, delivery fees |
| 3 | Orders, status history, staff dashboard |
| 4 | Paystack, cancellation/payment-failure rules |
| 5 | Rider management + assignment |
| 6 | Channels, WebSockets, live map |
| 7 | Promotions & campaigns |
| 8 | Notifications (all events) |
| 9 | Reviews & moderation |
| 10 | Reports, hardening, launch prep |

## 9. Expected Outcome

The completed system should provide a centralized platform for restaurant ordering and delivery management.

Customers should be able to order food conveniently, monitor their deliveries live, receive timely notifications and review their experience, while restaurant management should have greater control over orders, food availability, delivery fees, dispatch operations, promotions, customer feedback and business records.

**Project Goal:** To improve customer convenience, delivery transparency and the overall efficiency of restaurant operations.
