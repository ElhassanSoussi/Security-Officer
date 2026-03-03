#!/usr/bin/env python3
"""Create 100%-off Stripe promotion codes for safe live-mode testing."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.core.config import get_settings
import stripe

s = get_settings()
stripe.api_key = s.STRIPE_SECRET_KEY

if not stripe.api_key or not stripe.api_key.startswith("sk_live_"):
    print("ERROR: No live Stripe key found")
    sys.exit(1)

PLANS = ['starter', 'growth', 'elite']
EXPIRES = int(time.time()) + 86400  # 24 hours

print("")
print("Creating 100%-off promo codes (LIVE mode, single-use, 24h expiry)")
print("=" * 60)

for plan in PLANS:
    coupon_id = f"TEST_{plan.upper()}_{int(time.time())}"
    promo_code = f"FREE{plan.upper()}"
    try:
        coupon = stripe.Coupon.create(
            id=coupon_id,
            percent_off=100,
            duration="once",
            max_redemptions=1,
            redeem_by=EXPIRES,
            name=f"[TEST] {plan.title()} Plan - 100% Off",
        )
        promo = stripe.PromotionCode.create(
            coupon=coupon.id,
            code=promo_code,
            max_redemptions=1,
        )
        print(f"  OK  {plan.upper():12s}  promo code: {promo.code}")
        time.sleep(1)
    except stripe.error.StripeError as e:
        print(f"  ERR {plan.upper():12s}  {e}")

print("")
print("HOW TO TEST (you pay $0.00):")
print("  1. Go to nyccompliancearchitect.com/plans")
print("  2. Click Upgrade on any plan")
print("  3. On Stripe Checkout, click 'Add promotion code'")
print("  4. Enter: FREESTARTER, FREEGROWTH, or FREEELITE")
print("  5. Total becomes $0.00 -- enter your real card")
print("  6. Click Subscribe -- webhook fires, DB updates")
print("")
print("CLEANUP after testing:")
print("  - Cancel subscriptions in Stripe Dashboard -> Subscriptions")
print("  - Delete coupons in Stripe Dashboard -> Products -> Coupons")
print("")
