# Restaurant Project --- Five-Developer Team Structure & Git Collaboration Plan

A practical ownership, integration and workflow guide for building the
**Restaurant Ordering & Delivery Management System**.

**Technology foundation:** Django 5 · PostgreSQL 16 ·
HTML/CSS/JavaScript · Django Channels · Redis + Celery ·
Leaflet/OpenStreetMap · Paystack · Cloudinary

**Team model:** Five developers working in parallel through one shared
GitHub repository, with clear module ownership, documented interfaces,
pull requests and integration testing.

## Document Purpose

This document divides the restaurant project into five developer
responsibilities so five individuals can contribute concurrently without
duplicating work or constantly conflicting over the same files. Each
developer owns a defined area, delivers working functionality, and
integrates through agreed interfaces and GitHub pull requests.

## Table of Contents

1.  [Five-Developer Allocation](#1-five-developer-allocation)
2.  [Detailed Responsibilities and
    Ownership](#2-detailed-responsibilities-and-ownership)
3.  [Shared GitHub Repository
    Structure](#3-shared-github-repository-structure)
4.  [Git Collaboration Strategy](#4-git-collaboration-strategy)
5.  [How the Five Developers Work
    Together](#5-how-the-five-developers-work-together)
6.  [Development Phases and Team
    Participation](#6-development-phases-and-team-participation)
7.  [Rules to Prevent Developer
    Conflicts](#7-rules-to-prevent-developer-conflicts)
8.  [Definition of
    Completion](#8-definition-of-completion-for-each-developer)
9.  [Final Team Structure](#9-final-team-structure)
10. [Recommendations and Implementation
    Notes](#10-recommendations-and-implementation-notes)

------------------------------------------------------------------------

## 1. Five-Developer Allocation

The project is divided by technical ownership and deliverables---not
simply by assigning unrelated pages. The allocation follows the Django
apps and system responsibilities described in the project architecture
and PRD.

  -----------------------------------------------------------------------
  Developer               Primary ownership       Main outcome
  ----------------------- ----------------------- -----------------------
  **Developer 1**         Backend infrastructure, Django foundation,
                          authentication and      accounts, roles, shared
                          database                backend and menu data

  **Developer 2**         Customer website and    Responsive customer
                          ordering experience     website, menu browsing,
                                                  cart, checkout UI and
                                                  customer dashboard

  **Developer 3**         Orders, payments and    Order lifecycle,
                          business logic          checkout calculations,
                                                  Paystack, cash
                                                  payments, cancellation
                                                  and refunds

  **Developer 4**         Delivery, real-time     Rider operations, GPS,
                          tracking and            maps, WebSockets,
                          notifications           notifications and
                                                  delivery events

  **Developer 5**         Admin dashboard,        Management interfaces,
                          promotions, reviews and reports, campaigns,
                          quality assurance       reviews, testing and
                                                  launch readiness
  -----------------------------------------------------------------------

## 2. Detailed Responsibilities and Ownership

### Developer 1 --- Backend Infrastructure, Authentication and Database

**Primary responsibility:** Build the foundation upon which the other
developers depend.

**Owns:**

``` text
config/
apps/accounts/
apps/core/
apps/menu/
```

**Tasks:** 1. Initialize the Django project and configure PostgreSQL. 2.
Configure settings split: `base.py`, `dev.py` and `prod.py`. 3. Create
the custom User model before the first database migration. 4. Implement
customer, staff, rider and admin roles and permissions. 5. Implement
registration, login, logout, customer profiles and delivery addresses.
6. Build rider profile models and shared backend utilities. 7. Create
food categories and food item models; provide menu administration
backend. 8. Configure Cloudinary and local media storage for
development. 9. Establish shared model conventions, permissions and
backend patterns.

**Deliverables:** Django foundation; authentication and authorization;
database models and migrations; menu/category backend; shared backend
conventions.

**Boundary:** Other developers should not independently modify the
custom User model. Changes to shared settings and core foundations
should be coordinated through this developer.

### Developer 2 --- Customer Website, Menu Interface and Shopping Experience

**Primary responsibility:** Build the customer-facing experience from
visiting the website through checkout.

**Owns:**

``` text
templates/customer/
static/css/customer/
static/js/customer/
static/img/
```

**Tasks:** 1. Design the responsive restaurant homepage and navigation.
2. Build food category, listing and food detail pages. 3. Display food
images, descriptions, prices, availability and ratings. 4. Display
special meals, daily offers and promotions. 5. Build the shopping cart
interface, quantity controls and item removal. 6. Build checkout,
delivery address selection and order summaries. 7. Display delivery fees
and payment choices supplied by backend services. 8. Build customer
dashboard, profile, saved addresses and order history. 9. Build order
confirmation and payment result pages. 10. Integrate customer interfaces
with the agreed backend APIs.

**Deliverables:** Responsive customer website; food browsing; cart
interface; checkout experience; customer dashboard.

**Boundary:** Own the customer-facing frontend, not the underlying
order/payment business rules. Developer 3 owns those services.

### Developer 3 --- Order Management, Checkout and Payment Integration

**Primary responsibility:** Ensure orders, transactions and restaurant
business rules work correctly.

**Owns:**

``` text
apps/orders/
apps/payments/
```

**Tasks:** 1. Implement cart and cart-item backend models and order
creation. 2. Generate unique order references and preserve order-item
price snapshots. 3. Implement order statuses, valid transitions and
immutable status history. 4. Implement checkout calculations and
server-side totals. 5. Implement flat-rate and distance-based delivery
fee calculations, free-delivery thresholds and fee snapshots. 6.
Integrate Paystack payment initialization, server-side verification and
signature-checked webhooks. 7. Implement cash-on-delivery payments,
payment failures and payment retries. 8. Implement cancellation rules,
refund processing and refund tracking. 9. Maintain payment/order audit
records and publish order events for notification workflows.

**Deliverables:** Ordering engine; checkout and transaction processing;
Paystack integration; order management backend; cancellation and refund
handling.

**Security rule:** Confirm payment only after server-side verification
or a valid signature-checked webhook. Never trust client redirect
parameters alone.

### Developer 4 --- Delivery Management, GPS Tracking and Notifications

**Primary responsibility:** Build dispatch operations and real-time
delivery functionality.

**Owns:**

``` text
apps/delivery/
apps/notifications/
config/asgi.py
```

**Tasks:** 1. Implement rider registration, management and availability.
2. Implement delivery assignment and rider delivery dashboard. 3.
Implement assigned-delivery listings and delivery status updates. 4.
Implement rider GPS sharing with consent and privacy controls. 5.
Implement Django Channels consumers and Redis channel layers. 6.
Implement live customer order status and rider-location updates. 7.
Integrate Leaflet and OpenStreetMap for rider marker, destination and
route visualization. 8. Implement ETA updates where supported. 9.
Implement in-app and email notifications. 10. Integrate Celery
background tasks, retries and notification failure logging. 11. Prune
rider location history after delivery completion.

**Deliverables:** Rider dashboard; delivery assignment; live rider
tracking; real-time updates; notification infrastructure.

**Boundary:** Redis and Celery are required components. Coordinate with
Developer 3 because order and payment events trigger delivery and
notification workflows.

### Developer 5 --- Admin Dashboard, Promotions, Reviews, Reports and Testing

**Primary responsibility:** Give restaurant management the tools to
operate and monitor the business.

**Owns:**

``` text
apps/dashboard/
apps/promotions/
apps/reviews/
templates/admin/
templates/staff/
static/css/admin/
static/js/admin/
tests/
```

**Tasks:** 1. Build administrator and restaurant staff dashboards. 2.
Build user, order, menu and delivery management interfaces. 3. Build
delivery-fee configuration interfaces. 4. Implement promotional
campaigns, banners, discounts, promo codes and scheduling. 5. Build
customer review functionality and food/service rating displays. 6.
Implement review moderation and visibility controls. 7. Build sales,
revenue, popular-food, delivery and customer reports. 8. Implement
date/status filters and review analytics. 9. Coordinate integration
testing, role-based access testing and application workflow tests. 10.
Prepare quality reports and support deployment readiness.

**Deliverables:** Admin and staff dashboards; promotions; reviews;
reports and analytics; integration and QA reports.

**Boundary:** Consume services from other developers; do not duplicate
their backend business logic.

------------------------------------------------------------------------

## 3. Shared GitHub Repository Structure

All five developers work inside one central repository. The structure
below preserves the architecture's Django apps while making frontend and
documentation ownership clearer.

``` text
restaurant-delivery/
├── manage.py
├── requirements.txt
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── prod.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── apps/
│   ├── accounts/
│   ├── core/
│   ├── menu/
│   ├── orders/
│   ├── payments/
│   ├── delivery/
│   ├── notifications/
│   ├── promotions/
│   ├── reviews/
│   └── dashboard/
├── templates/
│   ├── customer/
│   ├── staff/
│   ├── rider/
│   └── admin/
├── static/
│   ├── css/
│   │   ├── customer/
│   │   ├── admin/
│   │   └── shared/
│   ├── js/
│   │   ├── customer/
│   │   ├── admin/
│   │   └── shared/
│   └── img/
├── tests/
└── docs/
    ├── ARCHITECTURE.md
    ├── PRD.md
    ├── schema.sql
    ├── API_DOCUMENTATION.md
    ├── GIT_WORKFLOW.md
    └── DEVELOPER_GUIDE.md
```

------------------------------------------------------------------------

## 4. Git Collaboration Strategy

**Recommended approach:** One GitHub repository, five developer-owned
branches, one integration branch and a protected production branch.

### Branch Structure

``` text
main
└── develop
    ├── feature/dev1-infrastructure
    ├── feature/dev2-customer-website
    ├── feature/dev3-orders-payments
    ├── feature/dev4-delivery-tracking
    └── feature/dev5-admin-reviews
```

  -----------------------------------------------------------------------
  Branch                              Purpose
  ----------------------------------- -----------------------------------
  `main`                              Stable, tested production code.

  `develop`                           Combined development and
                                      integration code.

  `feature/dev1-infrastructure`       Developer 1's backend foundation
                                      work.

  `feature/dev2-customer-website`     Developer 2's customer-facing work.

  `feature/dev3-orders-payments`      Developer 3's order and payment
                                      work.

  `feature/dev4-delivery-tracking`    Developer 4's delivery and
                                      real-time work.

  `feature/dev5-admin-reviews`        Developer 5's admin, reviews and QA
                                      work.
  -----------------------------------------------------------------------

Developers should create smaller task branches from their assigned
development branch when implementing individual features. Completed work
is submitted through a Pull Request into `develop`.

### Example Task-Branch Workflow

``` bash
git checkout develop
git pull origin develop

git checkout -b feature/dev2-food-menu-page

# Make and test the changes
git add .
git commit -m "feat(customer): implement food menu page"

git push origin feature/dev2-food-menu-page

# Open a Pull Request into develop on GitHub
```

### Git Rules for Everyone

1.  Nobody pushes directly to `main`.
2.  Nobody merges unreviewed code into `develop`.
3.  Every developer creates feature branches for tasks.
4.  Test each feature before submitting a Pull Request.
5.  Pull the latest `develop` changes regularly.
6.  Resolve merge conflicts carefully; do not discard another
    developer's work.
7.  Use meaningful commit messages.
8.  Never commit `.env` files, passwords, payment secrets or API keys.
9.  Coordinate database migrations and shared model changes before
    merging.
10. Require at least one other developer to review each Pull Request.

### Suggested Commit Messages

``` text
feat(accounts): implement customer registration
feat(menu): add food category management
feat(orders): implement checkout calculation
feat(payments): integrate Paystack verification
feat(delivery): implement rider GPS tracking
feat(dashboard): add revenue analytics
fix(orders): correct cancellation validation
test(payments): add webhook verification tests
```

------------------------------------------------------------------------

## 5. How the Five Developers Work Together

### Example Workflow: A Customer Places an Order

  -----------------------------------------------------------------------
  Step                    Developer               Contribution
  ----------------------- ----------------------- -----------------------
  1                       Developer 2             Builds food browsing,
                                                  cart and checkout
                                                  interface.

  2                       Developer 1             Provides
                                                  authentication,
                                                  customer accounts,
                                                  addresses and menu
                                                  data.

  3                       Developer 3             Provides cart
                                                  processing, checkout,
                                                  order creation and
                                                  payment services.

  4                       Developer 4             Receives order events
                                                  and prepares
                                                  notification and
                                                  delivery workflows.

  5                       Developer 5             Provides the
                                                  staff/admin interface
                                                  to receive and manage
                                                  the order.
  -----------------------------------------------------------------------

### Integration Agreements Required Before Implementation

The team must agree on:

-   Database model names, fields and relationships.
-   API endpoint URLs and request/response formats.
-   Authentication and permission requirements.
-   Order and payment status names and valid transitions.
-   WebSocket event names and payload structures.
-   Shared CSS, JavaScript and template conventions.

### Illustrative API Contract (Example Only)

**Endpoint:**

``` http
POST /api/orders/checkout/
```

**Request:**

``` json
{
    "address_id": 12,
    "payment_method": "CARD"
}
```

**Response:**

``` json
{
    "order_reference": "ORD-20261112-ABC123",
    "status": "PENDING",
    "total": 250.00,
    "payment_url": "..."
}
```

This is an example of an interface contract for team planning. It is not
a statement that this endpoint already exists. The responsible
developers must agree and document the actual contract before
integration.

------------------------------------------------------------------------

## 6. Development Phases and Team Participation

All five developers should participate throughout the project, with
different responsibilities in each phase.

  -----------------------------------------------------------------------
  Phase                   Participation           Expected result
  ----------------------- ----------------------- -----------------------
  **1. Foundation**       All five                Project setup, Git
                                                  workflow, database and
                                                  initial interfaces.

  **2. Core ordering**    Developers 1, 2, 3, 5;  Menu, cart, checkout,
                          Developer 4 prepares    orders and admin.
                          infrastructure          

  **3. Payments**         Developers 1, 3, 4, 5;  Paystack, cash
                          Developer 2 integrates  payments, cancellation
                          UI                      and notifications.

  **4. Delivery**         Developers 1, 3, 4, 5;  Rider assignment, GPS
                          Developer 2 integrates  and live tracking.
                          tracking UI             

  **5. Business           All five                Promotions, reviews,
  management**                                    reports and dashboards.

  **6. Final testing**    All five                Security, integration,
                                                  bug fixes and
                                                  deployment.
  -----------------------------------------------------------------------

The original PRD proposes ten two-week sprints. Retain that as the
overall planning framework unless the team formally agrees to revise it.

### Suggested Sprint Mapping

  Sprint   Focus
  -------- ---------------------------------------------------
  1        Scaffold, authentication, roles and menu models.
  2        Cart, checkout and delivery fees.
  3        Orders, status history and staff dashboard.
  4        Paystack, cancellation and payment-failure rules.
  5        Rider management and assignment.
  6        Channels, WebSockets and live map.
  7        Promotions and campaigns.
  8        Notifications and event coverage.
  9        Reviews and moderation.
  10       Reports, hardening and launch preparation.

------------------------------------------------------------------------

## 7. Rules to Prevent Developers from Interfering with One Another

  -----------------------------------------------------------------------
  Shared resource         Coordinator / owner     Team rule
  ----------------------- ----------------------- -----------------------
  Django settings         Developer 1             Request shared changes
                                                  through reviewed PRs.

  Custom User model       Developer 1             No independent changes
                                                  by other developers.

  Database schema         Developer 1 coordinates All developers follow
  conventions                                     agreed conventions.

  Orders and payments     Developer 3             Other modules integrate
                                                  through agreed
                                                  services.

  Customer frontend       Developer 2             Avoid editing customer
                                                  templates without
                                                  coordination.

  Delivery and WebSockets Developer 4             Publish event contracts
                                                  for other modules.

  Admin and reporting UI  Developer 5             Consume existing
                                                  services; avoid
                                                  duplicate business
                                                  logic.

  Global styles and       Team agreement          No unilateral changes
  shared components                               to shared components.

  Database migrations     Relevant app owner      Coordinate dependencies
                                                  and migration order.
  -----------------------------------------------------------------------

### Important Localization Decision

The supplied SQL schema contains Nigeria and NGN defaults. Since the
project is being developed in Ghana, the team should confirm the
intended operating country and currency, and decide whether these
defaults should become Ghana and GHS before finalizing the initial
migrations. Do not silently change historical or business requirements
without team approval.

------------------------------------------------------------------------

## 8. Definition of Completion for Each Developer

A developer's assignment is not complete merely because code has been
written. The work must be functional, tested, documented and integrated.

-   [ ] Working functionality demonstrated in the application.
-   [ ] Clean, organized code following agreed conventions.
-   [ ] Database migrations, where applicable.
-   [ ] Unit tests for relevant business logic.
-   [ ] API documentation, where applicable.
-   [ ] Updated README or developer documentation.
-   [ ] Successful GitHub Pull Request and review.
-   [ ] Successful integration with the other modules.
-   [ ] Demonstration to the other four developers.

------------------------------------------------------------------------

## 9. Final Team Structure

  -----------------------------------------------------------------------
  Role                    Primary ownership       Shared contribution
  ----------------------- ----------------------- -----------------------
  **Project Coordinator / Sprint planning, GitHub Keeps work aligned and
  Team Lead**             oversight and           resolves cross-module
                          integration             blockers.
                          coordination            

  **Developer 1**         Backend and database    Shared foundations,
                                                  authentication and data
                                                  contracts.

  **Developer 2**         Customer website        Customer-facing
                                                  workflow and API
                                                  integration.

  **Developer 3**         Orders and payments     Reliable order and
                                                  transaction lifecycle.

  **Developer 4**         Delivery and real-time  Rider operations,
                                                  location updates and
                                                  notifications.

  **Developer 5**         Admin and quality       Management tools,
                          assurance               reporting and
                                                  integration testing.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 10. Recommendations and Implementation Notes

1.  Divide the project by technical ownership and deliverables, not by
    random pages.
2.  Keep the Architecture document as the technical reference and the
    PRD as the functional requirements reference.
3.  Use the supplied SQL schema as the database-domain reference; review
    its country/currency defaults with the team.
4.  Create and agree on API contracts before parallel frontend/backend
    integration.
5.  Protect `main` and require Pull Requests and reviews.
6.  Coordinate shared files, settings, user model changes and
    migrations.
7.  Demonstrate working progress regularly so every team member gains
    practical experience with the full system.
8.  Keep Redis, Celery and Celery Beat in the planned implementation and
    deployment; they are required by the architecture and PRD.

### Final Recommendation

Use one shared GitHub repository with five clearly assigned module
owners. Each developer works independently on feature branches,
documents their interfaces, submits reviewed pull requests and
participates in integration testing.

The result should be one coherent restaurant ordering and delivery
platform---not five disconnected pieces of software.

------------------------------------------------------------------------

**Document basis:** This team structure is based on the supplied
Restaurant Ordering & Delivery Management System PRD and Technical
Architecture, together with the five-developer allocation prepared for
the project.
