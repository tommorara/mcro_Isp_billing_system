# Changelog

## \[Unreleased\]

### Added

- **Support Ticket System**:
  - Added `SupportTicket` model with statuses (`OPEN`, `IN_PROGRESS`, `CLOSED`), file attachments, and threaded replies.
  - Implemented customer-facing views (`customer_tickets`, `customer_ticket_detail`) for creating, viewing, and replying to tickets.
  - Updated admin interface to manage tickets with bulk status updates and SMS notifications.
  - Added templates (`tickets.html`, `ticket_detail.html`) for ticket management.

### Changed

- **Company Model**:

  - Updated `Company` model to include `HOTSPOT_LOGIN_METHODS` (`TRANSACTION`, `PHONE`, `VOUCHER`), `email`, `phone`, and `address`.
  - Retained `country` and `currency` fields, ensuring compatibility with `get_country_code`.
  - Updated `companies/admin.py` to reflect new fields.

- **Customer Models and Views**:

  - Renamed `SupportMessage` to `SupportTicket` with enhanced functionality.
  - Updated `customers/views.py` to replace `customer_support` with `customer_tickets` and `customer_ticket_detail`.
  - Integrated `hotspot_login_method` into SMS notifications and hotspot payment flows.
  - Updated `universal_billing/urls.py` to include new ticket URLs.

### Fixed

- Ensured file uploads work with `MEDIA_ROOT` and `MEDIA_URL` configuration.
- Corrected phone number formatting using `Company.get_country_code`.

### Notes

- Run `python manage.py makemigrations` and `python manage.py migrate` to apply model changes.
- Configure `MEDIA_ROOT` and `MEDIA_URL` in `settings.py` for ticket attachments.