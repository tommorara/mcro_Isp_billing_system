# Universal Billing (ISP Hotspot Billing System)

Django 5–based hotspot and ISP billing platform for vouchers, M-Pesa payments, MikroTik/RouterOS sync, Twilio SMS, and customer self-service. Built for small and mid-sized ISPs in Kenya and similar markets.

## Core Capabilities
- Customer accounts, subscriptions, invoices, and payments (M-Pesa STK, bank, cash)
- Voucher generation and redemption for hotspot/PPPoE/Static/VPN packages
- MikroTik RouterOS sync (hotspot, PPPoE, VPN) plus FreeRADIUS export tasks
- SMS/email notifications via pluggable providers (Twilio, Africa's Talking)
- Admin dashboards with sales reports; customer portal with plans, invoices, tickets
- Celery task queue for router/RADIUS sync and voucher notifications

## Tech Stack
- Django 5.1, Django REST Framework, Jazzmin admin skin
- Celery + Redis (broker/result backend)
- SQLite by default; PostgreSQL recommended for production (see docs/postgres.md)
- Optional: RouterOS API, MySQL client (FreeRADIUS), Twilio SDK, Safaricom M-Pesa

## Project Layout
- universal_billing/: Django project settings, URLs, Celery setup
- companies/: ISP/company profile and country/currency settings
- customers/: customers, packages, subscriptions, vouchers, support tickets, tasks
- payments/: payment model, M-Pesa STK push, payment selection flow
- plugins/: pluggable payment/SMS providers (Twilio SMS, M-Pesa plugin shell)
- templates/ & static/: shared frontend assets; customers/ and payments/ templates
- docs/postgres.md: PostgreSQL + pgAdmin quick guide

## Prerequisites
- Python 3.10+
- Redis (for Celery)
- SQLite works for local; PostgreSQL 15+ recommended in production
- RouterOS API access and/or FreeRADIUS MySQL (optional, for network sync)

## Quick Start (Development)
1) Clone and create a virtualenv
```bash
git clone <repo-url> universal-billing
cd universal-billing
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2) Create `.env`
```bash
SECRET_KEY=replace-me
DEBUG=True
# ALLOWED_HOSTS=localhost,127.0.0.1
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Email (optional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=your-email@gmail.com

# SMS (Twilio example)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+2547XXXXXXX

# M-Pesa sandbox/live
MPESA_CONSUMER_KEY=...
MPESA_CONSUMER_SECRET=...
MPESA_SHORTCODE=174379
MPESA_PASSKEY=...
MPESA_CALLBACK_URL=https://your-domain/mpesa/callback
```

3) Run migrations and create an admin user
```bash
python manage.py migrate
python manage.py createsuperuser
```

4) Start services
```bash
python manage.py runserver
# In another terminal (Redis running):
celery -A universal_billing worker -l info
```

## Optional/Extra Dependencies
Install when you need the corresponding feature:
```bash
pip install routeros-api mysqlclient twilio
```
- RouterOS sync (MikroTik): `routeros-api`
- FreeRADIUS MySQL export: `mysqlclient` and a `radius` database
- Twilio SMS: `twilio`

## Environment Keys Reference
| Key | Purpose |
| --- | --- |
| SECRET_KEY | Django secret key |
| DEBUG | Toggle debug mode (True/False) |
| CELERY_BROKER_URL / CELERY_RESULT_BACKEND | Redis (or other) URLs for Celery |
| MPESA_CONSUMER_KEY / MPESA_CONSUMER_SECRET | Safaricom API credentials |
| MPESA_SHORTCODE / MPESA_PASSKEY / MPESA_CALLBACK_URL | STK push config |
| TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_PHONE_NUMBER | SMS sending |
| AFRICASTALKING_USERNAME / AFRICASTALKING_API_KEY | Alternate SMS provider |
| EMAIL_* / DEFAULT_FROM_EMAIL | Outbound email settings |
| ALLOWED_HOSTS | Comma-separated hosts for production |

## Running Tasks
- Router/RADIUS sync and expiry: Celery tasks in `customers/tasks.py`
- Voucher SMS dispatch: `send_voucher_sms` task uses Twilio credentials
- To schedule periodic jobs, add Celery Beat or an external scheduler

## Payments & SMS Plugins
- Payment plugin shell: `plugins/mpesa.py` calls `payments.mpesa.initiate_stk_push`
- SMS plugins are loaded via `PluginConfig` records; Twilio implementation lives in `plugins/sms/twilio_plugin.py`

## API Surface
- REST endpoints under `/api/` via DRF router: customers, packages, subscriptions, vouchers
- Hotspot endpoints: `/api/hotspot/plans/`, `/api/hotspot/pay/`
- Customer portal: `/customer/login/`, `/customer/dashboard/`, invoices, tickets, renewals, voucher redemption
- Admin: `/admin/` (Jazzmin skinned)

## Database
- Default is SQLite (`db.sqlite3`). For PostgreSQL, update `DATABASES` in `universal_billing/settings.py` (see `docs/postgres.md` for OS-specific setup).

## Tests
Basic app tests are scaffolded; run:
```bash
python manage.py test
```

## Contributing
Issues and PRs are welcome. Please include steps to reproduce bugs, and add/adjust tests where possible.

## License
No license file is present yet. Add one (e.g., MIT) before distributing or deploying to customers.
