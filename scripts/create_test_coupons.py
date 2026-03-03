#!/usr/bin/env python3
"""
Create 100%-off Stripe coupons for safe live-mode testing.
Each coupon is single-use and expires in 24 hours.

Usage:
    # Set your LIVE secret key
    export STRIPE_SECRET_KEY="sk_live_..."
    python scripts/create_test_coupons.py

This will print 3 coupon codes — one for each plan.
Apply the coupon at Stripe Checkout to pay $0.
After testing, delete the coupons from Stripe Dashboard.
"""

import os
import sys
import time

try:
    import stripe
except ImportError:
    print("ERROR: stripe package not installed. Run: pip install stripe")
    sys.exit(1)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
if not stripe.api_key or not stripe.api_key.startswith("sk_live_"):
    print("ERROR: Set STRIPE_SECRET_KEY to your sk_live_... key")
    print("  export STRIPE_SECRET_KEY='sk_live_...'")
    sys.exit(1)

PLANS = ["starter", "growth", "elite"]
EXPIRES = int(time.time()) + 86400  # 24 hours from now

print("")
print("═══════════════════════════════════════════════════════════")
print("  Creating 100%-off test coupons (live mode, single-use)")
print("═══════════════════════════════════════════════════════════")
print("")

coupons = []
for plan in PLANS:
    coupon_id = f"TEST_{plan.upper()}_{int(time.time())}"
    try:
        coupon = stripe.Coupon.create(
            id=coupon_id,
            percent_off=100,
            duration="once",            # Only first invoice is free
            max_redemptions=1,          # Single use
            redeem_by=EXPIRES,          # Expires in 24h
            name=f"[TEST] {plan.title()} Plan - 100% Off",
        )
        coupons.append((plan, coupon.id))
        print(f"  ✓ {plan.upper():12s} → coupon: {coupon.id}")
    except stripe.error.StripeError as e:
        print(f"  ✗ {plan.upper():12s} → ERROR: {e}")

if coupons:
    print("")
    print("═══════════════════════════════════════════════════════════")
    print("  HOW TO USE:")
    print("═══════════════════════════════════════════════════════════")
    print("")
    print("  1. Go to nyccompliancearchitect.com → Plans → click Upgrade")
    print("  2. On the Stripe Checkout page, click 'Add promotion code'")
    print("  3. Paste the coupon code for that plan")
    print("  4. Enter your real card — you'll be charged $0.00")
    print("  5. Complete checkout → verify webhook fires")
    print("")
    print("  After testing, clean up:")
    print("  • Cancel subscriptions in Stripe Dashboard → Subscriptions")
    print("  • Delete coupons in Stripe Dashboard → Products → Coupons")
    print("")

    # Now enable promotion codes on checkout sessions
    print("═══════════════════════════════════════════════════════════")
    print("  ⚠️  IMPORTANT: Enable promotion codes in checkout")
    print("═══════════════════════════════════════════════════════════")
    print("")
    print("  Your checkout code needs allow_promotion_codes=True.")
    print("  I'll patch this in the backend now.")
    print("")
