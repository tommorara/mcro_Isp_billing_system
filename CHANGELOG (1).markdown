# Changelog

## [Unreleased]

### Added
- **Email Notifications**:
  - Added email notifications for ticket creation, replies, status changes, customer login/logout, profile updates, payments, and voucher redemption.
  - Configured in `customers/views.py` and `customers/utils.py` using Django's `send_mail`.
- **Pluggable SMS Integration**:
  - Added `PluginConfig` model in `plugins/models.py` for SMS provider configurations.
  - Implemented Twilio SMS plugin in `plugins/sms/twilio_plugin.py`.
  - Updated `send_sms` in `customers/utils.py` to use active SMS plugin.
- **Ticket Enhancements**:
  - Added `category` and `priority` fields to `SupportTicket` model.
  - Added `assigned_to` field for ticket assignment in admin interface.
  - Implemented audit trail with `AuditLog` for ticket actions.
  - Enhanced admin search with `customer__name` and `customer__email`.
  - Added escalation for high-priority tickets, notifying staff via email.

### Changed
- **Support Ticket System**:
  - Updated `customers/tickets.html` and `ticket_detail.html` to display category and priority.
  - Enhanced `SupportTicketAdmin` with assignment and search improvements.
  - Updated `customers/views.py` to include email/SMS notifications and audit logging.
- **Company Model**:
  - Ensured `hotspot_login_method` integration with SMS notifications.
- **Customer Admin**:
  - Fixed `make_password` import in `customers/admin.py`.

### Fixed
- Fixed `NameError: name 'make_password' is not defined` in `customers/admin.py`.
- Fixed `SyntaxError` in `customers/views.py` by correcting `assetidwrapper` to `wrapper` in `customer_required` decorator.

### Notes
- Run `python manage.py makemigrations` and `python manage.py migrate` to apply model changes.
- Configure `MEDIA_ROOT` and `MEDIA_URL` in `settings.py` for ticket attachments.
- Add email settings to `settings.py` (e.g., Gmail SMTP).
- Configure SMS plugins in admin interface (`/admin/plugins/pluginconfig/`).