# Dev 5 assumptions (promotions, reviews, reports, QA)

Status: PROPOSAL. Dev 5 is building on this unless someone objects. Reply on the PR.

## Taken from docs/schema.sql (no assumption)
- Roles: CUSTOMER, STAFF, RIDER, ADMIN
- Order status: PENDING, CONFIRMED, PREPARING, READY_FOR_PICKUP, OUT_FOR_DELIVERY, DELIVERED, CANCELLED
- Payment status: PENDING, SUCCESS, FAILED, REFUNDED
- Delivery status: ASSIGNED, IN_TRANSIT, DELIVERED, FAILED, CANCELLED
- Discount type: PERCENTAGE, FIXED
- Review rating: VERY_BAD, BAD, OKAY, GOOD, EXCELLENT (one review per order)
- Revenue = sum of orders_order.total where status = DELIVERED (as in vw_daily_sales)

## Needs a team decision
1. Country and currency: schema defaults to Nigeria / NGN. Dev 5 proposes Ghana / GHS.
   Must be settled before the first migrations.
2. Schema additions Dev 5 proposes (all optional, nothing else changes):
   - promotions_promocode.per_user_limit (INT NULL, default 1)
   - promotions_promocode.max_discount_amount (NUMERIC(12,2) NULL)
   - promotions_promocode.applies_to_delivery_fee (BOOLEAN, default FALSE)
     PRD: delivery fees are excluded from discounts unless a promo targets them.
   - new table promotions_promoredemption (promo, user, order_id UNIQUE, discount_amount, redeemed_at)
     for idempotent redemption and per-customer limits
   - reviews_review.hidden_reason, hidden_by_id, hidden_at (moderation audit trail)

## Checkout contract with Dev 3
- Dev 3 calls apps.promotions.services.validate_promo(code, subtotal, user, delivery_fee)
  -> PromoResult(valid, discount, reason, message, promo). Read-only.
- After payment status becomes SUCCESS (server-verified), Dev 3 calls
  record_redemption(code=, user=, order_id=, discount_amount=). Idempotent per order.
- Dev 3 stores discount_total on the order. Dev 5 reports read the stored snapshot.

## Questions
- Dev 1: role mechanism (User.role field vs Django groups), when the User model merges, menu_fooditem fields.
- Dev 3: valid status transitions, services for listing/updating/cancelling/refunding orders.
- Dev 4: delivery event names/payloads, how to register Celery tasks (promotion scheduling, report exports).
- Dev 2: who builds the review form and the promo banner display.
- Lead: API_DOCUMENTATION.md location, PR reviewer for Dev 5, coverage target, first integration demo date.