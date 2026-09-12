import streamlit as st
import pandas as pd
import plotly.express as px
from database import create_connection
from utils.auth import (
    is_logged_in,
    get_business_id,
    get_business_name
)

st.set_page_config(
    page_title="BizPilot Analytics",
    page_icon="📊",
    layout="wide"
)

# ==============================
# LOGIN CHECK
# ==============================

if not is_logged_in():
    st.warning("🔐 Please login first to access Analytics.")
    st.stop()

business_id = get_business_id()
business_name = get_business_name()

# ==============================
# HEADER
# ==============================

st.title("📊 Business Analytics")
st.write(f"Analytics for {business_name}")
st.caption("Understand your business performance with data.")
st.divider()

# ==============================
# DATE FILTER
# ==============================

st.subheader("📅 Select Date Range")

col1, col2 = st.columns(2)

with col1:
    start_date = st.date_input(
        "Start Date"
    )

with col2:
    end_date = st.date_input(
        "End Date"
    )

if start_date > end_date:
    st.error("❌ Start Date cannot be after End Date.")
    st.stop()

# ==============================
# DATABASE CONNECTION
# ==============================

connection = create_connection()

if not connection:
    st.error("❌ Database connection failed.")
    st.stop()

# ==============================
# SALES DATA
# ==============================

cursor = connection.cursor(dictionary=True)

cursor.execute(
    """
    SELECT
        s.sale_id,
        s.sale_date,
        s.total_amount,
        s.payment_status,
        c.customer_name
    FROM sales s
    LEFT JOIN customers c
        ON s.customer_id = c.customer_id
    WHERE s.business_id = %s
    AND s.sale_date BETWEEN %s AND %s
    ORDER BY s.sale_date
    """,
    (
        business_id,
        start_date,
        end_date
    )
)

sales_data = cursor.fetchall()

# ==============================
# EXPENSE DATA
# ==============================

cursor.execute(
    """
    SELECT
        expense_id,
        expense_category,
        amount,
        expense_date,
        description
    FROM expenses
    WHERE business_id = %s
    AND expense_date BETWEEN %s AND %s
    ORDER BY expense_date
    """,
    (
        business_id,
        start_date,
        end_date
    )
)

expense_data = cursor.fetchall()

# ==============================
# PRODUCT SALES DATA
# ==============================

cursor.execute(
    """
    SELECT
        p.product_name,
        SUM(si.quantity) AS total_quantity,
        SUM(si.subtotal) AS total_revenue
    FROM sale_items si
    JOIN products p
        ON si.product_id = p.product_id
    JOIN sales s
        ON si.sale_id = s.sale_id
    WHERE s.business_id = %s
    AND s.sale_date BETWEEN %s AND %s
    GROUP BY p.product_id, p.product_name
    ORDER BY total_quantity DESC
    """,
    (
        business_id,
        start_date,
        end_date
    )
)

product_sales = cursor.fetchall()

# ==============================
# PRODUCT COST
# ==============================

cursor.execute(
    """
    SELECT
        COALESCE(
            SUM(si.quantity * p.purchase_price),
            0
        ) AS product_cost
    FROM sale_items si
    JOIN products p
        ON si.product_id = p.product_id
    JOIN sales s
        ON si.sale_id = s.sale_id
    WHERE s.business_id = %s
    AND s.sale_date BETWEEN %s AND %s
    """,
    (
        business_id,
        start_date,
        end_date
    )
)

product_cost = cursor.fetchone()["product_cost"]

cursor.close()
connection.close()

# ==============================
# DATA CALCULATIONS
# ==============================

sales_df = pd.DataFrame(sales_data)
expenses_df = pd.DataFrame(expense_data)
product_df = pd.DataFrame(product_sales)

if sales_df.empty:
    total_revenue = 0
    total_orders = 0
else:
    total_revenue = float(
        sales_df["total_amount"].sum()
    )
    total_orders = len(sales_df)

if expenses_df.empty:
    total_expenses = 0
else:
    total_expenses = float(
        expenses_df["amount"].sum()
    )
    product_cost = float(product_cost or 0)

gross_profit = (
    total_revenue - product_cost
)

net_profit = (
    gross_profit - total_expenses
)

if total_revenue > 0:
    profit_margin = (
        net_profit / total_revenue
    ) * 100
else:
    profit_margin = 0

# ==============================
# KPI CARDS
# ==============================

st.subheader("💰 Financial Performance")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "💰 Revenue",
        f"₹{total_revenue:,.2f}"
    )

with col2:
    st.metric(
        "📦 Product Cost",
        f"₹{product_cost:,.2f}"
    )

with col3:
    st.metric(
        "💸 Expenses",
        f"₹{total_expenses:,.2f}"
    )

with col4:
    st.metric(
        "📊 Net Profit",
        f"₹{net_profit:,.2f}"
    )

st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "🧾 Total Orders",
        total_orders
    )

with col2:
    st.metric(
        "📈 Gross Profit",
        f"₹{gross_profit:,.2f}"
    )

with col3:
    st.metric(
        "📊 Profit Margin",
        f"{profit_margin:.2f}%"
    )

st.divider()

# ==============================
# SALES TREND
# ==============================

st.subheader("📈 Sales Trend")

if not sales_df.empty:

    sales_df["sale_date"] = pd.to_datetime(
        sales_df["sale_date"]
    )

    daily_sales = (
        sales_df
        .groupby("sale_date")["total_amount"]
        .sum()
        .reset_index()
    )

    daily_sales.columns = [
        "Date",
        "Revenue"
    ]

    fig = px.line(
        daily_sales,
        x="Date",
        y="Revenue",
        markers=True,
        title="Daily Sales Revenue"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

else:

    st.info(
        "ℹ️ No sales data available for the selected period."
    )

st.divider()

# ==============================
# TOP SELLING PRODUCTS
# ==============================

st.subheader("🏆 Top Selling Products")

if not product_df.empty:

    product_df["total_quantity"] = pd.to_numeric(
        product_df["total_quantity"]
    )

    product_df["total_revenue"] = pd.to_numeric(
        product_df["total_revenue"]
    )

    top_products = product_df.head(10)

    fig = px.bar(
        top_products,
        x="product_name",
        y="total_quantity",
        title="Top Products by Quantity Sold"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    st.dataframe(
        product_df,
        use_container_width=True
    )

else:

    st.info(
        "ℹ️ No product sales data available."
    )

st.divider()

# ==============================
# EXPENSE ANALYSIS
# ==============================

st.subheader("💸 Expense Analysis")

if not expenses_df.empty:

    category_expenses = (
        expenses_df
        .groupby("expense_category")["amount"]
        .sum()
        .reset_index()
    )

    fig = px.pie(
        category_expenses,
        names="expense_category",
        values="amount",
        title="Expenses by Category"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    st.dataframe(
        category_expenses,
        use_container_width=True
    )

else:

    st.info(
        "ℹ️ No expense data available."
    )

st.divider()

# ==============================
# SALES DETAILS
# ==============================

st.subheader("🧾 Sales Details")

if not sales_df.empty:

    st.dataframe(
        sales_df,
        use_container_width=True
    )

else:

    st.info(
        "ℹ️ No sales recorded for the selected period."
    )

st.divider()

# ==============================
# LOW STOCK ALERT
# ==============================

st.subheader("⚠️ Low Stock Products")

connection = create_connection()

if connection:

    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            product_name,
            category,
            stock,
            minimum_stock
        FROM products
        WHERE business_id = %s
        AND stock <= minimum_stock
        ORDER BY stock ASC
        """,
        (business_id,)
    )

    low_stock = cursor.fetchall()

    cursor.close()
    connection.close()

    if low_stock:

        st.warning(
            f"⚠️ {len(low_stock)} product(s) "
            "need attention."
        )

        st.dataframe(
            low_stock,
            use_container_width=True
        )

    else:

        st.success(
            "✅ No low-stock products."
        )

st.divider()

# ==============================
# BUSINESS SUMMARY
# ==============================

st.subheader("💡 Business Summary")

if total_revenue == 0 and total_expenses == 0:

    st.info(
        "Start recording sales and expenses "
        "to generate business analytics."
    )

else:

    if net_profit > 0:
        st.success(
            f"✅ Your business generated "
            f"₹{net_profit:,.2f} net profit "
            "during the selected period."
        )

    elif net_profit < 0:
        st.error(
            f"⚠️ Your business recorded a loss of "
            f"₹{abs(net_profit):,.2f} "
            "during the selected period."
        )

    else:
        st.warning(
            "Your business is currently at break-even "
            "for the selected period."
        )

    if profit_margin >= 20:

        st.success(
            f"📈 Profit margin is {profit_margin:.2f}%, "
            "which is a strong result."
        )

    elif profit_margin > 0:

        st.info(
            f"📊 Profit margin is "
            f"{profit_margin:.2f}%."
        )

    else:

        st.warning(
            "⚠️ Improve sales or control costs "
            "to improve profitability."
        )