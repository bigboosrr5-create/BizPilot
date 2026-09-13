import streamlit as st
from database import create_connection
from auth import (
    is_logged_in,
    get_business_id,
    get_business_name,
    logout
)

st.set_page_config(
    page_title="BizPilot Dashboard",
    page_icon="📊",
    layout="wide"
)

# ==============================
# LOGIN CHECK
# ==============================

if not is_logged_in():
    st.warning("🔐 Please login first to access the dashboard.")
    st.stop()

business_id = get_business_id()
business_name = get_business_name()

# ==============================
# SIDEBAR
# ==============================

with st.sidebar:
    st.markdown("### 🏪 Business")
    st.write(business_name)

    st.divider()

    if st.button("🚪 Logout", use_container_width=True):
        logout()
        st.rerun()

# ==============================
# PAGE HEADER
# ==============================

st.title("📊 BizPilot Dashboard")
st.caption("Manage • Analyse • Grow")

st.write(f"Welcome to {business_name} 👋")

st.divider()

# ==============================
# DATABASE CONNECTION
# ==============================

connection = create_connection()

if not connection:
    st.error("❌ Database connection failed.")
    st.stop()

cursor = connection.cursor()

# ==============================
# TOTAL PRODUCTS
# ==============================

cursor.execute("""
    SELECT COUNT(*)
    FROM products
    WHERE business_id = %s
""", (business_id,))

total_products = cursor.fetchone()[0]

# ==============================
# TOTAL CUSTOMERS
# ==============================

cursor.execute("""
    SELECT COUNT(*)
    FROM customers
    WHERE business_id = %s
""", (business_id,))

total_customers = cursor.fetchone()[0]

# ==============================
# TOTAL SALES
# ==============================

cursor.execute("""
    SELECT COUNT(*)
    FROM sales
    WHERE business_id = %s
""", (business_id,))

total_sales = cursor.fetchone()[0]

# ==============================
# TOTAL REVENUE
# ==============================

cursor.execute("""
    SELECT COALESCE(SUM(total_amount), 0)
    FROM sales
    WHERE business_id = %s
""", (business_id,))

total_revenue = cursor.fetchone()[0]

# ==============================
# TOTAL EXPENSES
# ==============================

cursor.execute("""
    SELECT COALESCE(SUM(amount), 0)
    FROM expenses
    WHERE business_id = %s
""", (business_id,))

total_expenses = cursor.fetchone()[0]

# ==============================
# ESTIMATED PROFIT
# ==============================

estimated_profit = (
    float(total_revenue) - float(total_expenses)
)

cursor.close()
connection.close()

# ==============================
# BUSINESS OVERVIEW
# ==============================

st.subheader("📈 Business Overview")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "💰 Total Revenue",
        f"₹{float(total_revenue):,.2f}"
    )

with col2:
    st.metric(
        "💸 Total Expenses",
        f"₹{float(total_expenses):,.2f}"
    )

with col3:
    st.metric(
        "📊 Estimated Profit",
        f"₹{estimated_profit:,.2f}"
    )

with col4:
    st.metric(
        "🧾 Total Sales",
        total_sales
    )

st.divider()

# ==============================
# BUSINESS SUMMARY
# ==============================

st.subheader("📦 Business Summary")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "📦 Total Products",
        total_products
    )

with col2:
    st.metric(
        "👥 Total Customers",
        total_customers
    )

with col3:
    st.metric(
        "🧾 Total Orders",
        total_sales
    )

st.divider()

# ==============================
# LOW STOCK ALERT
# ==============================

st.subheader("⚠️ Low Stock Alert")

connection = create_connection()

if connection:

    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            product_name,
            stock,
            minimum_stock
        FROM products
        WHERE business_id = %s
        AND stock <= minimum_stock
        ORDER BY stock ASC
    """, (business_id,))
    low_stock_products = cursor.fetchall()

    cursor.close()
    connection.close()

    if low_stock_products:

        st.warning(
            f"⚠️ {len(low_stock_products)} product(s) "
            "are running low on stock."
        )

        st.dataframe(
            low_stock_products,
            use_container_width=True
        )

    else:

        st.success(
            "✅ All products have sufficient stock."
        )

st.divider()

# ==============================
# TOP SELLING PRODUCTS
# ==============================

st.subheader("🏆 Top Selling Products")

connection = create_connection()

if connection:

    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            p.product_name,
            SUM(si.quantity) AS total_quantity
        FROM sale_items si

        JOIN products p
            ON si.product_id = p.product_id

        JOIN sales s
            ON si.sale_id = s.sale_id

        WHERE s.business_id = %s

        GROUP BY
            p.product_id,
            p.product_name

        ORDER BY total_quantity DESC

        LIMIT 5
    """, (business_id,))

    top_products = cursor.fetchall()

    cursor.close()
    connection.close()

    if top_products:

        st.dataframe(
            top_products,
            use_container_width=True
        )

    else:

        st.info(
            "ℹ️ No sales data available yet."
        )
