# CareBridge India — NRI Parent Care & Concierge Platform

A cloud-ready Streamlit web application for Non-Resident Indians (NRIs) to manage healthcare, daily errands, emergency support, itemized PDF invoicing, and property concierge services for their aging parents in India.

## About

CareBridge India provides a transparent, real-time caregiving and concierge platform connecting NRIs abroad with verified local Care Managers (*Sahayaks*) in India. Families can subscribe to monthly care plans or book on-demand assistance for hospital visits, banking paperwork, bill payments, and home check-ins with live GPS verification, receipt proofs, and automated PDF visit/invoice reports.

Built and maintained by [T A Srinivas (@SRINIVASTA)](https://github.com), this repository hosts a multi-role Streamlit web gateway, a multi-currency (USD/INR/GBP/EUR) billing and prepaid expense wallet, a digital medical and document vault, an automated ReportLab PDF invoice/report generator, and a live Care Manager field reporting portal.

## Modules in this repo

| Module | Description |
| :--- | :--- |
| `main.py` | Main Streamlit entry point managing session state, role-based access routing (NRI, Care Manager, Admin), communication preferences, and multi-currency switching. |
| `01_plans_and_pricing.py` | Displays public monthly subscription tiers (Essential, Complete Medical + Errands, Couple Care) and pay-as-you-go service rate cards. |
| `02_nri_dashboard.py` | Enables NRIs to schedule tasks, manage their prepaid INR expense wallet, trigger 24/7 SOS alerts, and download or send itemized PDF invoices. |
| `03_health_vault.py` | Stores prescriptions, diagnostic lab reports, insurance policies, chronological vitals logs (BP, blood sugar, pulse, SpO2), and exports PDF health summaries. |
| `04_care_manager.py` | Mobile-responsive field portal for local Care Managers in India to log GPS check-ins, record parent vitals, upload receipts, and auto-dispatch PDF reports. |
| `05_admin_ops.py` | Operations panel for verifying ground staff KYC/police clearance, settling out-of-pocket actuals, and auditing/re-sending GST PDF invoices. |

### Architecture & Workflow

```mermaid
flowchart TD
    subgraph Client_Interface_Layer["NRI Client Layer - Global Web Access"]
        A["main.py<br>Streamlit Multi-Role Gateway"] e1@-->|"Step 1 - Select Plan or Task"| B["01_plans_and_pricing.py<br>USD / INR Subscriptions & Rates"]
        A e2@-->|"Step 2 - Book Care, Invoice or SOS"| C["02_nri_dashboard.py<br>Task Scheduler, Wallet & PDF Invoices"]
    end

    subgraph Ground_Operations_Layer["India Ground Operations Layer"]
        C e3@-->|"Assigned Task + Alert"| D{"Task Category?"}
        D e4@-->|"Medical / Hospital Escort"| E["04_care_manager.py<br>Vitals Logger & Receipt Upload"]
        D e5@-->|"Banking / Property / Errand"| E
        E e6@-->|"GPS Check-in + Bill Receipts"| F["05_admin_ops.py<br>Verification & Actuals Settlement"]
    end

    subgraph Storage_and_Compliance_Layer["Database, PDF Engine & Communications Layer"]
        F e7@-->|"Verified Visit & Invoice"| G["database.py & storage.py<br>Zero-Setup SQLite3 + Local/S3 Vault"]
        G e8@-->|"Vitals & Medical Records"| H["03_health_vault.py<br>Live Family Feed & Health PDF Export"]
        G e9@-->|"PDF Invoice & Visit Summary"| I["pdf_generator.py & notifications.py<br>ReportLab PDF + Email / WhatsApp / SMS"]
    end

    e1@{ animate: true }
    e2@{ animate: true }
    e3@{ animate: true }
    e4@{ animate: true }
    e5@{ animate: true }
    e6@{ animate: true }
    e7@{ animate: true }
    e8@{ animate: true }
    e9@{ animate: true }
```
```mermaid
flowchart LR
    subgraph Onboarding["Account Creation & Provisioning"]
        SA["SYSTEM_ADMIN<br>(Pre-seeded Master Role)"] e1@-->|"Creates & Deletes Staff"| EMP["Employees<br>(ADMIN & CARE_MANAGER)"]
        CUST_REG["Public Sign-Up Tab"] e2@-->|"Self-Registration"| NRI["NRI Family Customer<br>(Role Locked to NRI)"]
    end

    subgraph Gateway["Shared Login & RBAC Routing"]
        EMP e3@--> LOGIN["main.py / login_ui.py<br>Shared Sign-In Portal"]
        NRI e4@--> LOGIN
        SA e5@--> LOGIN
        LOGIN e6@-->|"SYSTEM_ADMIN"| P_SYS["All Portals + Add/Delete Staff + Audit Logs"]
        LOGIN e7@-->|"ADMIN"| P_ADM["Admin Ops + Dispatch + KYC + Billing"]
        LOGIN e8@-->|"CARE_MANAGER"| P_CM["Care Manager Field Portal + Health Vault"]
        LOGIN e9@-->|"NRI"| P_NRI["NRI Dashboard + Health Vault + Pricing"]
    end

    e1@{ animate: true }
    e2@{ animate: true }
    e3@{ animate: true }
    e4@{ animate: true }
    e5@{ animate: true }
    e6@{ animate: true }
    e7@{ animate: true }
    e8@{ animate: true }
    e9@{ animate: true }
```

## Demo & Role Access Credentials

This platform demonstrates a four-tier Role-Based Access Control (RBAC) onboarding and login architecture:
* System Admin (SYSTEM_ADMIN): Automatically seeded on startup with master rights to create/delete employee logins and view IST audit logs.
* Operations Admin & Care Manager (ADMIN / CARE_MANAGER): Provisioned exclusively by the System Admin inside Admin Operations Console -> Manage Employees & History.
* NRI Family Customer (NRI): Self-registered via the public Create Customer Account (Sign Up) tab.

| Role | Name | Email (Login ID) | Password | Creation Method |
| :--- | :--- | :--- | :--- | :--- |
| SYSTEM_ADMIN | Master System Admin | sysadmin@carebridge.in | SysAdmin@123 | Pre-seeded on startup |
| ADMIN | Priya Nair | priya.admin@carebridge.in | AdminOps@123 | Created by System Admin |
| CARE_MANAGER | Suresh Naidu | suresh.naidu@carebridge.in | Sahayak@123 | Created by System Admin |
| NRI | Karthik Reddy | karthik.reddy@example.com | Client@123 | Public Customer Sign Up |

Note: On Streamlit Community Cloud, restarting or redeploying the container resets ephemeral SQLite storage (carebridge.db) back to the default SYSTEM_ADMIN account.

### Key Capabilities

* **Unified Medical & Concierge Care:** Combines routine health monitoring, doctor appointment escorting, and 24/7 emergency hospital support with everyday errands like pension paperwork, utility bills, and property checks.
* **Itemized PDF Invoices & Visit Reports:** Generates GST-compliant PDF tax invoices and post-visit vitals summary PDFs via ReportLab, with 1-click browser downloads and multi-channel delivery (Email attachments, WhatsApp, and SMS).
* **Transparent Prepaid Expense Wallet:** Separates service charges from 100% actual out-of-pocket costs (medicines, lab bills, cab fares), backed by mandatory photo receipt uploads before wallet deduction.
* **Zero-Setup SQLite3 & Cloud Deployment:** Runs out-of-the-box with built-in SQLite3 persistence and supports instant deployment from GitHub to Streamlit Community Cloud.

## Service Pricing Reference

### Monthly Subscriptions

| Plan Tier | Monthly Charge (INR) | Monthly Charge (USD) | Included Coverage |
| :--- | :--- | :--- | :--- |
| **Essential Errands & Check-Ins** | ₹3,500 – ₹6,000 | $45 – $75 | 2 planned home visits/month, bill payments, banking help, grocery coordination, and photo updates. |
| **Complete Medical + Errands** | ₹7,500 – ₹12,500 | $90 – $150 | 4 weekly visits, BP/sugar checks, doctor appointment escorting, medicine refills, and 24/7 SOS. |
| **Comprehensive / Couple Care** | ₹14,000 – ₹22,000 | $170 – $265 | Weekly visits covering **both parents**, hospital escorting, lab coordination, and property checks. |

### Pay-As-You-Go On-Demand Rates

* **Doctor / Hospital Visit Escort (up to 4 hrs):** ₹1,000 – ₹2,500 ($12 – $30)
* **Routine Home Wellbeing & Vitals Check:** ₹600 – ₹1,200 ($8 – $15)
* **Bank, Government, or Pension Life Certificate:** ₹1,000 – ₹2,000 ($12 – $25)
* **Airport Pickup / Drop Assistance:** ₹1,500 – ₹3,500 ($18 – $42) *(excluding actual cab/toll)*
* **Property / Locked Flat Inspection:** ₹1,500 – ₹3,000 ($18 – $36)

## Repository Structure

```text
carebridge-nri-platform/
├── .github/
│   └── workflows/
│       └── ci-cd.yml                 # Automated linting, unit tests, and security checks on push
├── .streamlit/
│   ├── config.toml                   # Custom medical-teal theme, fonts, and 25 MB upload limit
│   └── secrets.toml.example          # Template for Stripe, Razorpay, Twilio, SMTP, and S3 keys
├── app/
│   ├── main.py                       # Main entry point, session initialization, and role-based router
│   ├── assets/
│   │   ├── logo.png                  # Brand logo and favicons
│   │   └── styles.css                # Custom CSS overrides for cards, badges, and responsive UI
│   ├── auth/
│   │   ├── session_manager.py        # Role-based access control (NRI, Care Manager, Admin)
│   │   └── login_ui.py               # Role demo access and communication channel preferences
│   ├── pages/
│   │   ├── 01_plans_and_pricing.py   # Public USD/INR subscription plans and on-demand rate cards
│   │   ├── 02_nri_dashboard.py       # Service booking, prepaid wallet, SOS trigger, & PDF invoices
│   │   ├── 03_health_vault.py        # Medical reports, vitals trends, & PDF health report export
│   │   ├── 04_care_manager.py        # Ground staff GPS check-in, receipt upload, & auto-dispatch PDFs
│   │   └── 05_admin_ops.py           # Staff verification (KYC/Police ID), audit, & invoice ledger
│   ├── services/
│   │   ├── database.py               # Zero-setup SQLite3 CRUD operations for parents, tasks, & invoices
│   │   ├── storage.py                # Local Vault / AWS S3 handling for receipts, lab PDFs, & invoices
│   │   ├── payments.py               # Stripe (International USD/GBP/EUR) and Razorpay (INR) integration
│   │   ├── pdf_generator.py          # ReportLab engine for itemized PDF invoices & visit/vitals reports
│   │   └── notifications.py          # Email (PDF attachment), WhatsApp, and SMS multi-channel dispatch
│   ├── models/
│   │   └── schemas.py                # Pydantic data validation models for requests, vitals, & invoices
│   └── utils/
│       ├── currency.py               # Multi-currency conversion and 18% service-only GST math
│       └── validators.py             # Indian/international phone, Aadhaar mask, & file type checks
├── tests/
│   ├── test_billing.py               # Unit tests for currency math, GST invoices, & PDF generation
│   └── test_permissions.py           # Validation tests for phone numbers, Aadhaar masking, & uploads
├── .gitignore                        # Excludes *.db, local_vault/, secrets.toml, and __pycache__
├── Dockerfile                        # Container setup for scalable deployment (AWS ECS / GCP Cloud Run)
├── pyproject.toml                    # Code formatting (Ruff) and Pytest configuration
├── requirements.txt                  # Pinned production Python dependencies
└── README.md                         # Setup guide, pricing reference, and architecture diagram
```

## Cloud & Local Setup

### Local Development Setup

```bash
# Clone the repository
git clone https://github.com/carebridge-nri-platform.git
cd carebridge-nri-platform

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy secrets template and add your keys (optional — SQLite3 works out-of-the-box)
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# Launch the application
streamlit run app/main.py
```

Open your browser and navigate to `http://localhost:8501`.


## License

This repository is licensed under the [MIT License](LICENSE) — Copyright (c) 2026 [T A Srinivas](https://github.com).

## Disclaimer

> **Important Notice:** This platform facilitates non-clinical care coordination, errand management, and home health monitoring. In the event of a critical medical emergency, local Care Managers coordinate immediate transport to the family's designated hospital, while all clinical diagnoses and treatments remain solely under the supervision of licensed medical practitioners.

