# Uganda Dating 🇺🇬 ❤️

A mobile-friendly Flask dating app MVP for Uganda with discovery, likes, matches, chat, profiles, premium products and MTN Mobile Money payment verification.

## MTN MoMo payment flow

The app uses the Uganda Dating merchant number configured as `MTN_MOMO_NUMBER` (default: `65616659`). A customer:

1. Chooses a paid feature.
2. Sees the MTN MoMo merchant number and exact UGX amount.
3. Pays using MTN Mobile Money.
4. Enters the payer phone number and MTN transaction ID.
5. An admin checks the payment and clicks **Verify**.
6. The purchased entitlement is activated automatically.

This MVP uses **manual transaction verification**. It does not claim to have a direct MTN API connection. For automatic confirmation, connect an authorized MTN MoMo API/aggregator account and replace the verification step with server-to-server payment status checks.

## Admin

Set these Render environment variables before production:

- `ADMIN_EMAIL` — your admin email
- `ADMIN_PASSWORD` — a strong private admin password
- `MTN_MOMO_NUMBER` — your confirmed MTN merchant/collection number
- `SECRET_KEY` — Render can generate this automatically
- `DATABASE_URL` — your production PostgreSQL connection string

Admin login: `/admin/login`

**Security:** do not publish the admin password or MTN credentials in source code. Change the default admin password immediately when deploying.

## Premium products

- Premium — UGX 10,000/month
- See who liked you — UGX 2,000/week
- Unlimited Likes — UGX 3,000/week
- Profile Boost — UGX 2,000 / 24 hours
- Super Like — UGX 500 each
- Featured Profile — UGX 5,000/week

## Run locally

```bash
pip install -r requirements.txt
export SECRET_KEY='replace-this'
export ADMIN_EMAIL='admin@yourdomain.com'
export ADMIN_PASSWORD='replace-with-a-strong-password'
export MTN_MOMO_NUMBER='65616659'
python app.py
```

## Production

Render configuration is included in `render.yaml`. Use PostgreSQL for production rather than relying on the local SQLite database.
