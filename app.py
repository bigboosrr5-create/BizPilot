import os
import streamlit as st
import pandas as pd
import plotly.express as px
from database import create_connection
from utils.auth import (
    is_logged_in,
    get_business_id,
    get_business_name,
    get_owner_name,
    logout
)

# =========================================================
# PAGE CONFIG
# =========================================================

LOGO_PATH = os.path.join("assets", "logo.png")

st.set_page_config(
    page_title="BizPilot | Business Management",
    page_icon=LOGO_PATH if os.path.exists("C:\\Users\\bhara\\OneDrive\\Documents\\Desktop\\BizPilot\\assets\\logo.png") else "📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# PREMIUM UI
# =========================================================

st.markdown("""
<style>

.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1400px;
}

h1 {
    font-weight: 800 !important;
    letter-spacing: -0.6px;
}

h2 {
    font-weight: 750 !important;
}

h3 {
    font-weight: 650 !important;
}

section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(128,128,128,0.15);
}

section[data-testid="stSidebar"] h1 {
    font-size: 25px !important;
}

.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    min-height: 42px;
}

.stDownloadButton > button {
    border-radius: 8px;
    font-weight: 600;
    min-height: 42px;
}

.stTextInput input,
.stNumberInput input,
.stDateInput input,
.stTextArea textarea {
    border-radius: 8px;
}

div[data-baseweb="select"] > div {
    border-radius: 8px;
}

div[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
}

div[data-testid="stMetric"] {
    padding: 15px;
    border-radius: 10px;
    border: 1px solid rgba(128,128,128,0.15);
    background: rgba(128,128,128,0.03);
}

.bizpilot-hero {
    padding: 35px;
    border-radius: 18px;
    border: 1px solid rgba(128,128,128,0.15);
    margin-bottom: 25px;
}

.bizpilot-card {
    padding: 22px;
    border-radius: 14px;
    border: 1px solid rgba(128,128,128,0.15);
    background: rgba(128,128,128,0.025);
    min-height: 150px;
}

.bizpilot-footer {
    text-align: center;
    padding: 30px 0 10px 0;
    opacity: 0.65;
    font-size: 14px;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# LOGIN CHECK
# =========================================================

if not is_logged_in():

    # ---------------- SIDEBAR ----------------

    with st.sidebar:

        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, use_container_width=True)
        else:
            st.markdown("# BizPilot")

        st.markdown("---")
        st.markdown("### Welcome to BizPilot")
        st.caption("Manage • Analyse • Grow")

    # ---------------- HOME PAGE ----------------

    st.markdown('<div class="bizpilot-hero">', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 2])

    with col1:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=220)

    with col2:
        st.title("BizPilot")
        st.subheader("Manage • Analyse • Grow")

        st.write(
            "A smart business management and analytics platform "
            "designed to help small businesses manage sales, "
            "inventory, expenses and business performance."
        )

        st.info(
            "Please use the Login page from the sidebar to access your business dashboard."
        )

    st.markdown("</div>", unsafe_allow_html=True)

    # ---------------- FEATURES ----------------

    st.markdown("## 🚀 Powerful Business Management")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("""
        <div class="bizpilot-card">
        <h3>📊 Dashboard</h3>
        <p>Get a clear overview of sales, expenses, profit and inventory.</p>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
        <div class="bizpilot-card">
        <h3>📦 Inventory</h3>
        <p>Track products, stock levels and identify low-stock items.</p>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown("""
        <div class="bizpilot-card">
        <h3>📈 Analytics</h3>
        <p>Understand business performance using meaningful analytics.</p>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

    c4, c5, c6 = st.columns(3)

    with c4:
        st.markdown("""
        <div class="bizpilot-card">
        <h3>💰 Sales</h3>
        <p>Record sales and automatically keep business data organised.</p>
        </div>
        """, unsafe_allow_html=True)

    with c5:
        st.markdown("""
        <div class="bizpilot-card">
        <h3>💡 Smart Insights</h3>
        <p>Get useful business insights from your sales and expense data.</p>
        </div>
        """, unsafe_allow_html=True)

    with c6:
        st.markdown("""
        <div class="bizpilot-card">
        <h3>📄 Reports & Invoices</h3>
        <p>Generate professional reports and downloadable invoices.</p>
        </div>
        """, unsafe_allow_html=True)

    # ---------------- BUSINESS FLOW ----------------

    st.markdown("---")
    st.markdown("## 🔄 How BizPilot Works")

    flow1, flow2, flow3, flow4 = st.columns(4)

    with flow1:
        st.markdown("### 1️⃣ Record")
        st.caption("Add sales, products, customers and expenses.")

    with flow2:
        st.markdown("### 2️⃣ Store")
        st.caption("Business information is securely stored in MySQL.")

    with flow3:
        st.markdown("### 3️⃣ Analyse")
        st.caption("BizPilot converts data into useful analytics.")

    with flow4:
        st.markdown("### 4️⃣ Grow")
        st.caption("Use insights to make better business decisions.")

    # ---------------- TECHNOLOGY ----------------

    st.markdown("---")
    st.markdown("## 🛠️ Technology Stack")

    tech1, tech2, tech3, tech4, tech5 = st.columns(5)

    tech1.metric("Backend", "Python")
    tech2.metric("Database", "MySQL")
    tech3.metric("Interface", "Streamlit")
    tech4.metric("Analytics", "Pandas")
    tech5.metric("Charts", "Plotly")

    # ---------------- FOOTER ----------------

    st.markdown("""
    <div class="bizpilot-footer">
        <b>BizPilot</b> — Manage • Analyse • Grow<br>
        Smart Business Management & Analytics Platform
    </div>
    """, unsafe_allow_html=True)

    st.stop()


# =========================================================
# LOGGED-IN DASHBOARD
# =========================================================

business_id = get_business_id()
business_name = get_business_name()
owner_name = get_owner_name()

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_container_width=True)
    else:
        st.markdown("# BizPilot")

    st.markdown("---")

    st.markdown("### 🏢 Business")
    st.write(business_name)

    if owner_name:
        st.caption(f"Owner: {owner_name}")

    st.markdown("---")

    if st.button("🚪 Logout", use_container_width=True):
        logout()
        st.rerun()


# =========================================================
# DATABASE
# =========================================================

connection = create_connection()

if connection is None:
    st.error("❌ Database connection failed.")
    st.stop()


# =========================================================
# DATA
# =========================================================

try:
    sales_df = pd.read_sql(
        """
        SELECT sale_date, total_amount, payment_status
        FROM sales
        WHERE business_id = %s
        ORDER BY sale_date
        """,
        connection,
        params=(business_id,)
    )
    expense_df = pd.read_sql(
        """
        SELECT expense_date, amount, expense_category
        FROM expenses
        WHERE business_id = %s
        ORDER BY expense_date
        """,
        connection,
        params=(business_id,)
    )

    products_df = pd.read_sql(
        """
        SELECT product_name, category, stock, minimum_stock,
               purchase_price, selling_price
        FROM products
        WHERE business_id = %s
        ORDER BY product_name
        """,
        connection,
        params=(business_id,)
    )

    # =========================================================
    # CALCULATIONS
    # =========================================================

    total_sales = (
        sales_df["total_amount"].sum()
        if not sales_df.empty else 0
    )

    total_expenses = (
        expense_df["amount"].sum()
        if not expense_df.empty else 0
    )

    total_products = len(products_df)

    low_stock_count = (
        len(products_df[
            products_df["stock"] <= products_df["minimum_stock"]
        ])
        if not products_df.empty else 0
    )

    estimated_profit = total_sales - total_expenses

    # =========================================================
    # HEADER
    # =========================================================

    st.title("BizPilot Dashboard")

    st.write(
        f"Welcome back, {owner_name or business_name} 👋"
    )

    st.caption(
        "Manage your business, analyse performance and make smarter decisions."
    )

    # =========================================================
    # KPI
    # =========================================================

    k1, k2, k3, k4, k5 = st.columns(5)

    k1.metric(
        "💰 Total Sales",
        f"₹{total_sales:,.2f}"
    )

    k2.metric(
        "💸 Expenses",
        f"₹{total_expenses:,.2f}"
    )

    k3.metric(
        "📈 Estimated Profit",
        f"₹{estimated_profit:,.2f}"
    )

    k4.metric(
        "📦 Products",
        total_products
    )

    k5.metric(
        "⚠️ Low Stock",
        low_stock_count
    )

    # =========================================================
    # SALES CHART
    # =========================================================

    st.markdown("---")
    st.markdown("## 📈 Sales Overview")

    if not sales_df.empty:

        sales_df["sale_date"] = pd.to_datetime(
            sales_df["sale_date"]
        )

        daily_sales = (
            sales_df
            .groupby("sale_date", as_index=False)["total_amount"]
            .sum()
        )

        fig = px.line(
            daily_sales,
            x="sale_date",
            y="total_amount",
            markers=True,
            title="Sales Trend"
        )

        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Sales (₹)",
            hovermode="x unified"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    else:
        st.info("No sales data available yet.")

    # =========================================================
    # TWO COLUMN SECTION
    # =========================================================

    left, right = st.columns(2)

    # =========================================================
    # INVENTORY
    # =========================================================

    with left:

        st.markdown("## 📦 Inventory Overview")

        if not products_df.empty:

            inventory_display = products_df[
                [
                    "product_name",
                    "category",
                    "stock",
                    "minimum_stock"
                ]
            ].copy()

            inventory_display.columns = [
                "Product",
                "Category",
                "Stock",
                "Min Stock"
            ]

            st.dataframe(
                inventory_display,
                use_container_width=True,
                hide_index=True
            )

        else:
            st.info("No products available.")

    # =========================================================
    # EXPENSE ANALYSIS
    # =========================================================

    with right:

        st.markdown("## 💸 Expense Analysis")

        if not expense_df.empty:

            category_expense = (
                expense_df
                .groupby("expense_category", as_index=False)["amount"]
                .sum()
            )

            fig_expense = px.pie(
                category_expense,
                names="expense_category",
                values="amount",
                title="Expenses by Category"
            )
            st.plotly_chart(
                fig_expense,
                use_container_width=True
            )

        else:
            st.info("No expense data available yet.")

    # =========================================================
    # LOW STOCK ALERT
    # =========================================================

    st.markdown("---")
    st.markdown("## ⚠️ Low Stock Alerts")

    if not products_df.empty:

        low_stock_df = products_df[
            products_df["stock"] <= products_df["minimum_stock"]
        ].copy()

        if not low_stock_df.empty:

            for _, row in low_stock_df.iterrows():

                st.warning(
                    f"{row['product_name']} — "
                    f"Current stock: {int(row['stock'])} | "
                    f"Minimum required: {int(row['minimum_stock'])}"
                )

        else:
            st.success("✅ All products have sufficient stock.")

    else:
        st.info("No inventory data available.")

    # =========================================================
    # SMART INSIGHTS
    # =========================================================

    st.markdown("---")
    st.markdown("## 💡 Smart Business Insights")

    if total_sales > 0:

        if estimated_profit > 0:
            st.success(
                f"Your current estimated profit is "
                f"₹{estimated_profit:,.2f}."
            )
        else:
            st.warning(
                "Your current expenses are higher than your recorded sales."
            )

    if low_stock_count > 0:

        st.info(
            f"{low_stock_count} product(s) have reached or fallen below "
            "their minimum stock level."
        )

    if total_sales == 0:

        st.info(
            "Start recording sales to unlock more business insights."
        )

    # =========================================================
    # FOOTER
    # =========================================================

    st.markdown("""
    <div class="bizpilot-footer">
        <b>BizPilot</b> — Manage • Analyse • Grow<br>
        Smart Business Management & Analytics Platform
    </div>
    """, unsafe_allow_html=True)

finally:
    # =========================================================
    # CLOSE DATABASE
    # =========================================================
    connection.close()
