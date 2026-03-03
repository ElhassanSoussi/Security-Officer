#!/usr/bin/env python3
"""
scripts/setup_stripe_products.py — Create Stripe Products & Prices
===================================================================
Reads STRIPE_SECRET_KEY from backend/.env and creates the three plan
Products (Starter, Growth, Elite) with monthly recurring Prices.

Prints the Price IDs so you can paste them into your .env / Render env vars.

Usage:
    cd /path/to/Security-Officer
    python3 scripts/setup_stripe_products.py

Requires: pip install stripe
"""

import os
import sys

# Resolve backend/.env
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
ENV_FILE = os.path.join(REPO_ROOT, "backend", ".env")


def load_env(path: str) -> dict:
    """Minimal .env loader (no dependencies)."""
    env = {}
    if not os.path.exists(path):
        return env
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    return env


def main():
    env = load_env(ENV_FILE)
    api_key = env.get("STRIPE_SECRET_KEY") or os.getenv("STRIPE_SECRET_KEY", "")

    if not api_key:
        print("❌ STRIPE_SECRET_KEY not found in backend/.env or environment.")
        sys.exit(1)

    try:
        import stripe
    except ImportError:
        print("❌ 'stripe' package not installed. Run: pip install stripe")
        sys.exit(1)

    stripe.api_key = api_key
    mode = "LIVE" if api_key.startswith("sk_live_") else "TEST"
    print(f"🔑 Using Stripe API key ({mode} mode)")
    print()

    PLANS = [
        {
            "name": "Starter",
            "env_key": "STRIPE_PRICE_STARTER",
            "price_cents": 14900,
            "description": "For single-project teams. 10 questionnaires, 500 MB vault, 10 exports/mo.",
        },
        {
            "name": "Growth",
            "env_key": "STRIPE_PRICE_GROWTH",
            "price_cents": 49900,
            "description": "For teams handling multiple bids. 25 questionnaires, 2 GB vault, 25 exports/mo.",
        },
        {
            "name": "Elite",
            "env_key": "STRIPE_PRICE_ELITE",
            "price_cents": 149900,
            "description": "For heavy compliance volume. 100 questionnaires, 10 GB vault, 100 exports/mo.",
        },
    ]

    print("Creating Stripe Products and Prices...")
    print("=" * 60)

    results = []
    for plan in PLANS:
        # Check if product already exists
        existing = stripe.Product.search(query=f"name:'{plan['name']}'", limit=1)
        if existing.data:
            product = existing.data[0]
            print(f"  ✅ Product '{plan['name']}' already exists: {product.id}")
        else:
            product = stripe.Product.create(
                name=plan["name"],
                description=plan["description"],
                metadata={"app": "nyc-compliance-architect"},
            )
            print(f"  ✅ Created product '{plan['name']}': {product.id}")

        # Check if a monthly price already exists for this product
        prices = stripe.Price.list(product=product.id, active=True, limit=10)
        matching_price = None
        for p in prices.data:
            if (
                p.unit_amount == plan["price_cents"]
                and p.recurring
                and p.recurring.interval == "month"
            ):
                matching_price = p
                break

        if matching_price:
            price = matching_price
            print(f"  ✅ Price already exists: {price.id} (${plan['price_cents'] / 100}/mo)")
        else:
            price = stripe.Price.create(
                product=product.id,
                unit_amount=plan["price_cents"],
                currency="usd",
                recurring={"interval": "month"},
            )
            print(f"  ✅ Created price: {price.id} (${plan['price_cents'] / 100}/mo)")

        results.append({"env_key": plan["env_key"], "price_id": price.id, "name": plan["name"]})
        print()

    print("=" * 60)
    print()
    print("📋 Add these to your backend/.env and Render environment:")
    print()
    for r in results:
        print(f"  {r['env_key']}={r['price_id']}")
    print()

    # Also show plan name aliases (FREE=Starter, PRO=Growth, ENTERPRISE=Elite)
    plan_alias_map = {"STRIPE_PRICE_STARTER": "STRIPE_PRICE_FREE", "STRIPE_PRICE_GROWTH": "STRIPE_PRICE_PRO", "STRIPE_PRICE_ELITE": "STRIPE_PRICE_ENTERPRISE"}
    print("📋 Plan name aliases (same Price IDs):")
    print()
    for r in results:
        alias = plan_alias_map.get(r["env_key"])
        if alias:
            print(f"  {alias}={r['price_id']}")
    print()

    # Offer to auto-update backend/.env
    answer = input("Auto-update backend/.env with these values? [y/N] ").strip().lower()
    if answer == "y":
        _update_env_file(ENV_FILE, results, plan_alias_map)
        print("✅ backend/.env updated!")
    else:
        print("Skipped. Copy the values above manually.")


def _update_env_file(path: str, results: list, plan_alias_map: dict):
    """Update or append Price IDs in the .env file."""
    lines = []
    if os.path.exists(path):
        with open(path) as f:
            lines = f.readlines()

    # Build key→value map
    updates = {}
    for r in results:
        updates[r["env_key"]] = r["price_id"]
        alias = plan_alias_map.get(r["env_key"])
        if alias:
            updates[alias] = r["price_id"]

    updated_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    # Append any keys not already in file
    for key, val in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}\n")

    with open(path, "w") as f:
        f.writelines(new_lines)


if __name__ == "__main__":
    main()
