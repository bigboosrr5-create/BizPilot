# BizPilot

## Smart Business Management & Analytics Platform

Manage • Analyse • Grow

BizPilot is a web-based business management and analytics platform designed for small businesses.

It helps business owners manage products, customers, sales, expenses and inventory while providing useful analytics, reports and smart business insights.

---

## 🚀 Key Features

- 🔐 Secure Business Login
- 📊 Business Dashboard
- 📦 Product & Inventory Management
- 👥 Customer Management
- 💰 Sales Management
- 💸 Expense Management
- 📈 Business Analytics
- 🤖 Smart Business Insights
- 🔮 Sales Forecasting
- 📦 Inventory Intelligence
- 📄 Business Reports
- 🧾 Invoice Generation
- 📥 PDF & CSV Downloads
- 🗄️ MySQL Database Integration

---

## 🎯 Target Users

BizPilot is designed mainly for small and growing businesses such as:

- Stationery Shops
- Book Shops
- Clothing Shops
- Mobile & Accessories Shops
- Gift Shops
- Small Retail Businesses
- Small Service Businesses

---

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend & Business Logic |
| Streamlit | Web Application Interface |
| MySQL | Database Management |
| Pandas | Data Analysis |
| NumPy | Numerical Processing |
| Plotly | Interactive Charts |
| ReportLab | PDF Reports & Invoices |
| bcrypt | Password Security |
| python-dotenv | Environment Configuration |

---

## 📊 Main Modules

### 1. Dashboard

Provides an overview of business performance including:

- Today's Sales
- Monthly Sales
- Expenses
- Estimated Profit
- Pending Payments
- Sales Trends
- Low Stock Alerts

### 2. Products

Allows businesses to:

- Add products
- View products
- Manage selling and purchase prices
- Track stock
- Set minimum stock levels

### 3. Customers

Allows businesses to maintain:

- Customer name
- Phone number
- Email
- Address

### 4. Sales

Sales management includes:

- Customer selection
- Product selection
- Quantity
- Selling price
- Payment status
- Automatic stock reduction

### 5. Expenses

Businesses can record:

- Expense category
- Amount
- Date
- Description

### 6. Analytics

Provides business performance analysis such as:

- Revenue
- Expenses
- Profit
- Profit Margin
- Sales Growth
- Top Products
- Expense Categories

### 7. Smart Insights

BizPilot analyzes business data and provides useful insights such as:

- Sales growth or decline
- Best-selling products
- Low-stock products
- Major expense categories
- Business performance observations

### 8. Forecasting

Uses historical sales data to estimate future sales trends.

### 9. Inventory Intelligence

Helps identify:

- Low-stock products
- Stock status
- Inventory value
- Products requiring attention

### 10. Reports

Generates business reports with:

- Sales summary
- Expense summary
- Profit analysis
- Inventory information
- CSV export
- PDF report

### 11. Invoices

Allows users to generate professional PDF invoices from recorded sales.

---

## 🗄️ Database

BizPilot uses MySQL as its database.

Main tables include:

- businesses
- customers
- products
- sales
- sale_items
- expenses

The application uses business_id to keep business data separated.

---

## 🔐 Security

BizPilot uses:

- Password hashing with bcrypt
- Environment variables for database credentials
- Business-based data filtering
- Session-based login protection

Database credentials are stored in .env and should not be uploaded to GitHub.

---

## 📈 Business Analysis Layer

BizPilot is not only a software application but also demonstrates Business Analysis concepts.

### Business Requirements

The system should help small businesses manage their daily operations and understand their business performance.

### Key Business Problems

Small businesses may face challenges such as:

- Manual record keeping
- Difficulty tracking inventory
- Limited sales visibility
- Expense management problems
- Lack of business analytics
- Difficulty identifying trends

### Proposed Solution
BizPilot combines business management with analytics to provide a centralized platform for operational and decision-making support.

---

## 📊 Key Performance Indicators

BizPilot can track important KPIs such as:

- Total Revenue
- Total Expenses
- Gross Profit
- Net Profit
- Profit Margin
- Sales Growth
- Number of Orders
- Pending Payments
- Low Stock Products
- Top-Selling Products

---

## 🔄 Business Flow

`text
Business Login
      ↓
Dashboard
      ↓
Manage Products & Customers
      ↓
Record Sales & Expenses
      ↓
Update Inventory
      ↓
Analyze Business Data
      ↓
Generate Insights
      ↓
Forecast Future Trends
      ↓
Generate Reports & Invoices