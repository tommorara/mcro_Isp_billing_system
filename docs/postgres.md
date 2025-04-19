# PostgreSQL 17 and pgAdmin 4 Guide

## Windows
- **Install PostgreSQL 17**:
  - Download from [postgresql.org](https://www.postgresql.org/download/windows/) or [enterprisedb.com](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads).
  - Run installer, set password: `simplepass`.
  - Include pgAdmin 4 v9.2 (bundled).
- **Start pgAdmin 4**:
  - Access at `http://localhost:5050`.
  - Set master password.
- **Create Database**:
  - In pgAdmin, right-click `Databases` > `Create` > `Database`.
  - Name: `billing`.
- **Create User**:
  - Right-click `Login/Group Roles` > `Create` > `Login/Group Role`.
  - Name: `billing_user`, Password: `simplepass`.
  - Privileges: Enable `Can login?`, `Create databases?`.
- **Grant Privileges**:
  - Expand `Databases` > `billing` > `Query Tool`.
  - Run: `GRANT ALL PRIVILEGES ON DATABASE billing TO billing_user;`.
- **Backup**:
  - Right-click schema (e.g., `isp1`) > `Backup` > Save as `isp1.sql`.
- **Troubleshoot**:
  - Start service: `net start postgresql-x64-17`.
  - Check `pg_hba.conf` (`C:\Program Files\PostgreSQL\17\data`):


## Ubuntu 24.04 VPS
- **Install PostgreSQL 17**:
```bash
sudo apt update
sudo apt install postgresql-17 postgresql-contrib-17

## Install pgAdmin 4 v9.2
curl -fsS https://www.pgadmin.org/static/packages_pgadmin_org.pub | sudo gpg --dearmor -o /usr/share/keyrings/packages-pgadmin-org.gpg
sudo sh -c 'echo "deb [signed-by=/usr/share/keyrings/packages-pgadmin-org.gpg] https://ftp.postgresql.org/pub/pgadmin/pgadmin4/apt/noble pgadmin4 main" > /etc/apt/sources.list.d/pgadmin4.list'
sudo apt update
sudo apt install pgadmin4-web
sudo /usr/pgadmin4/bin/setup-web.sh

sudo service postgresql start
sudo service apache2 start  # For pgAdmin web

## Create Database/User
sudo -u postgres psql
CREATE DATABASE billing;
CREATE USER billing_user WITH PASSWORD 'simplepass';
GRANT ALL PRIVILEGES ON DATABASE billing TO billing_user;
\q

## Backup
pg_dump -h localhost -U billing_user isp1 > isp1.sql

## List schema
psql -U billing_user -d billing -c "SELECT schema_name FROM information_schema.schemata;"


## Common Tasks
View schemas: In pgAdmin, expand Databases > billing > Schemas.
Query data: SELECT * FROM companies_company; in Query Tool.
Create index: CREATE INDEX idx_company_name ON companies_company (name);.
Check version: SELECT version(); in Query Tool.


# Simple PostgreSQL Guide (Windows)
- Install: Download PostgreSQL 15 from https://www.enterprisedb.com/downloads/postgres-postgresql-downloads
- Start pgAdmin 4: Included with installer, access at http://localhost:5050
- Create database: In pgAdmin, right-click Databases > Create > Name: billing
- Create user: In pgAdmin, right-click Login/Group Roles > Create > Name: billing_user, Password: simplepass
- Grant privileges: In pgAdmin, run SQL: GRANT ALL PRIVILEGES ON DATABASE billing TO billing_user;
- Backup: In pgAdmin, right-click Schema (e.g., isp1) > Backup > Save as isp1.sql


# Simple PostgreSQL Guide
- Start PostgreSQL: `sudo service postgresql start`
- Access psql: `psql -U billing_user -d billing`
- List schemas: `SELECT schema_name FROM information_schema.schemata;`
- Create tenant schema: Run `python manage.py create_tenant`
- Backup schema: `pg_dump -h localhost -U billing_user isp1 > isp1.sql`

🚀 Getting Started
Overview
Develop the companies app on Windows to set up multi-tenancy with django-tenants for 10–50 ISP tenants. This provides schema-based isolation and subdomains (e.g., isp1.localhost), optimized for simple local development and deployment to an Ubuntu 24.04 VPS.
Prerequisites

Windows: 10/11, 1–4GB RAM
Ubuntu VPS: 24.04, 1GB RAM
Python 3.10+
PostgreSQL 15

Windows Development

Install Python:

Download Python 3.11 from python.org.
Check “Add Python to PATH” during installation.
Verify: python --version


Install PostgreSQL:

Download PostgreSQL 15 from postgresql.org.
Set password: simplepass for postgres user.
Open pgAdmin 4 and run:CREATE DATABASE billing;
CREATE USER billing_user WITH PASSWORD 'simplepass';
GRANT ALL PRIVILEGES ON DATABASE billing TO billing_user;




Set Up Project:

Create virtual environment:cd universal_billing
python -m virtualenv venv
.\venv\Scripts\activate


Install dependencies:pip install -r requirements.txt




Configure .env:
DATABASE_URL=postgres://billing_user:simplepass@localhost:5432/billing
SECRET_KEY=your-secret-key
DEBUG=True


Run Migrations:
python manage.py migrate


Create Test Tenant:
python manage.py create_tenant --subdomain=isp1 --name="ISP One" --email=admin@isp1.com


Configure DNS:

Edit C:\Windows\System32\drivers\etc\hosts (run Notepad as Administrator):127.0.0.1 isp1.localhost




Start Server:
python manage.py runserver


Visit http://isp1.localhost:8000.


Run Tests:
pytest companies/tests/models/test_company.py



Ubuntu 24.04 VPS Deployment

Install Dependencies:
sudo apt update
sudo apt install python3 python3-pip postgresql postgresql-contrib


Configure PostgreSQL:
sudo service postgresql start
sudo -u postgres psql -c "CREATE DATABASE billing;"
sudo -u postgres psql -c "CREATE USER billing_user WITH PASSWORD 'simplepass';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE billing TO billing_user;"


Copy Project:
scp -r universal_billing/ user@vps-ip:/home/user/


Set Up on VPS:
ssh user@vps-ip
cd universal_billing
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000



Next Steps

Develop customers for ISP clients.
Implement isp for hotspot authentication.
Add billing_core for billing plans.

Notes

Use pgAdmin 4 on Windows for PostgreSQL management.
Keep requirements.txt minimal: django, django-tenants, psycopg2-binary.
Review docs/postgres.md for PostgreSQL basics.
Test on Windows, deploy to VPS with identical codebase.

