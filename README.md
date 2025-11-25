# Universal Billing - Open-Source Hotspot Billing System

**Universal Billing** is a full-featured Django-based hotspot billing platform built for Internet Service Providers (ISPs) in Kenya and other emerging markets.

It handles customer subscriptions, **M-Pesa**, vouchers, MikroTik/RADIUS sync, Twilio SMS, support tickets, and analytics - everything needed to run a modern Wi-Fi or fiber hotspot business.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Django](https://img.shields.io/badge/Django-4.2%2B-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Contributions welcome](https://img.shields.io/badge/Contributions-welcome-orange)

## Author & Maintainer
**Livingstone Kimani**  
GitHub: [@Kimsy254](https://github.com/Kimsy254)

## Features

- M-Pesa payments (sandbox + live)
- MikroTik Hotspot / PPPoE / Static / VPN sync
- RADIUS integration
- Voucher system
- Twilio SMS notifications
- Admin reports & API

**customer portal is still very basic!**  
A lot of work remains on the user-facing side:
- Modern, responsive customer dashboard (React/Vue or beautiful Django templates)
- Real-time data usage graphs
- Payment history & PDF invoices
- Profile management & password reset
- Dark mode + Swahili (Kiswahili) translations
- Mobile-first experience
- Accessibility improvements
- More tests (especially frontend)

**This repo is now public because we want the community to help build an amazing open source hotspot billing system!**  

## Features (Already Working)

| Feature                         | Status  | Notes                              |
|---------------------------------|---------|------------------------------------|
| M-Pesa                | Done    | With retry logic & callbacks       |
| MikroTik sync (API + VPN)       | Done    | Hotspot, PPPoE, Static, VPN        |
| RADIUS (MySQL)                  | Done    | radcheck / radreply                |
| Voucher generation & redemption | Done    | Bulk + single                      |
| Twilio SMS notifications       | Done    | Payments, tickets, vouchers        |
| Support ticket system           | Almost Done    | With attachments                   |
| Daily/Monthly sales reports     | Done    | Admin panel + API                  |
| Swagger API docs                | Done    | `/swagger/`                        |

## Quick Start (Development)

```bash
git clone https://github.com/livingstonekimani/universal-billing.git
cd universal-billing
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Copy example env
cp .env.example .env

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
