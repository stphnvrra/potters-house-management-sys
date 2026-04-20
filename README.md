# The Potter's House Management System

An all-in-one Management and Enterprise Resource Planning (ERP) web application developed in Django for **The Potter's House**. This system is designed to streamline operations across various departments, from inventory management to human resources, ensuring seamless business flow and robust tracking mechanisms.

## System Features

### 1. Inventory & Purchasing
- **Inventory Tracking:** Real-time tracking of item levels, costs, and availability. Includes detailed categorizations (SKU, color, model, shape, size, material, dimensions).
- **Purchase Orders:** Manage purchase order requests and finalized purchase orders with integrated delivery receipts.
- **Supplier Management:** Track and maintain records of various suppliers.

### 2. Product and Job Orders (Operations)
- **Product Management:** Manage pricing details (SRP, MP, LP), combos, and manufacturing materials.
- **Client & Job Orders:** Comprehensive job order workflow, allowing staff to track job status, partial/complete releases, discounting, and payments.
- **Production Areas & Product Flow:** Monitor the workflow of products across various production stations to measure labor output.
- **Labor Tracking:** Granular recording of labor outputs (e.g., printing, pressing, assembling, boxing) and individual piece rates per employee.

### 3. Human Resources and Payroll
- **Employee Management:** Complete employment records, including basic profiles, education, contracts, skills, and histories.
- **Payroll System:** Auto-generates payrolls considering salary rates, total labor output from operations, and deductions (e.g., cash advances, absences, incident reports).

### 4. Financials & Expenses (Accounting)
- **Expense Summaries & Management:** Tracks and logs cash flows from various fund sources (Cash, Bank). Includes expense classifications and delivery voucher support.
- **Client Payments:** Maintains complete and searchable records of Accounts Receivable / Official Receipts linked directly to specific clients and Job Orders.

### 5. Access Control & Logs
- **Custom Authorization:** Extended role-based access control linking Users to Employee records and Dashboard Access scopes.
- **Activity Logging:** Widespread audit trails documenting `create`, `update`, `delete`, and `archive` operations across models to enforce accountability.

## Tech Stack
- **Backend**: Python, Django
- **Database**: MySQL
- **Frontend Engine**: Django Templates with UI interactions
