import os
import bcrypt
import streamlit as st
import pandas as pd
import plotly.express as px

from database import create_connection
from auth import (
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

    # ---------------- LOGIN PAGE ----------------

    st.markdown("""
    <style>
    .login-container {
        max-width: 520px;
        margin: 50px auto 20px auto;
        padding: 34px 38px;
        border-radius: 20px;
        border: 1px solid rgba(128,128,128,0.18);
        box-shadow: 0 12px 40px rgba(0,0,0,0.08);
    }

    .login-title {
        text-align: center;
        font-size: 34px;
        font-weight: 800;
        margin-top: 10px;
    }

    .login-subtitle {
        text-align: center;
        opacity: 0.70;
        margin-bottom: 22px;
    }

    .login-footer {
        text-align: center;
        opacity: 0.60;
        font-size: 13px;
        margin-top: 18px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="login-container">', unsafe_allow_html=True)

    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=150)

    st.markdown(
        '<div class="login-title">🔐 BizPilot</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="login-subtitle">Manage • Analyse • Grow</div>',
        unsafe_allow_html=True
    )

    st.divider()
    st.subheader("Business Login")

    with st.form("login_form", clear_on_submit=False):

        email = st.text_input(
            "📧 Email Address",
            placeholder="Enter your business email"
        )

        password = st.text_input(
            "🔑 Password",
            type="password",
            placeholder="Enter your password"
        )

        login = st.form_submit_button(
            "🚀 Login",
            use_container_width=True
        )

    if login:

        if email.strip() == "" or password.strip() == "":
            st.error("❌ Please enter Email and Password.")

        else:

            connection = create_connection()

            if connection:

                cursor = None

                try:
                    cursor = connection.cursor(dictionary=True)

                    cursor.execute("""
                        SELECT
                            business_id,
                            business_name,
                            owner_name,
                            email,
                            password_hash
                        FROM businesses
                        WHERE email = %s
                    """, (email.strip(),))

                    business = cursor.fetchone()

                except Exception as e:
                    business = None
                    st.error(f"❌ Login/database error: {e}")

                finally:
                    if cursor is not None:
                        cursor.close()
                    connection.close()

                if business:

                    stored_hash = business.get("password_hash")

                    try:
                        password_ok = bool(
                            stored_hash
                            and bcrypt.checkpw(
                                password.encode("utf-8"),
                                stored_hash.encode("utf-8")
                                if isinstance(stored_hash, str)
                                else stored_hash
                            )
                        )
                    except Exception:
                        password_ok = False

                    if password_ok:

                        st.session_state["logged_in"] = True
                        st.session_state["business_id"] = business["business_id"]
                        st.session_state["business_name"] = business["business_name"]
                        st.session_state["owner_name"] = business["owner_name"]

                        st.success(
                            f"✅ Welcome to BizPilot, "
                            f"{business['business_name']}!"
                        )

                        st.rerun()

                    else:
                        st.error("❌ Incorrect password.")

                else:
                    st.error("❌ Business account not found.")

            else:
                st.error("❌ Database connection failed.")

    st.markdown(
        '<div class="login-footer">Secure Business Management & Analytics Platform</div>',
        unsafe_allow_html=True
    )

    st.markdown("</div>", unsafe_allow_html=True)

    # Do not render the dashboard until the user is logged in.
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
