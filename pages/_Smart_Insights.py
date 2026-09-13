import streamlit as st
import pandas as pd
from database import create_connection
from utils.auth import (
    is_logged_in,
    get_business_id,
    get_business_name
)

# ==================================================
# PAGE CONFIG
# ==================================================

st.set_page_config(
    page_title="Smart Insights - BizPilot",
    page_icon="💡",
    layout="wide"
)

# ==================================================
# LOGIN CHECK
# ==================================================

if not is_logged_in():
    st.warning("🔐 Please login first.")
    st.stop()

business_id = int(get_business_id())
business_name = get_business_name()

# ==================================================
# SIDEBAR
# ==================================================

with st.sidebar:
    st.markdown("### 🏪 Business")
    st.write(business_name)

    st.divider()

    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ==================================================
# HEADER
# ==================================================

st.title("💡 Smart Business Insights")
st.caption(
    "Smart recommendations based on your business data."
)

st.divider()

# ==================================================
# DATE FILTER
# ==================================================

st.subheader("📅 Analysis Period")

col1, col2 = st.columns(2)

start_date = col1.date_input(
    "Start Date",
    value=pd.Timestamp.today().replace(day=1).date()
)

end_date = col2.date_input(
    "End Date",
    value=pd.Timestamp.today().date()
)

if start_date > end_date:
    st.error("❌ Start Date cannot be greater than End Date.")
    st.stop()

# ==================================================
# DATABASE CONNECTION
# ==================================================

connection = create_connection()

if not connection:
    st.error("❌ Database connection failed.")
    st.stop()

cursor = connection.cursor(dictionary=True)

# ==================================================
# SALES DATA
# ==================================================

cursor.execute(
    """
    SELECT
        sale_id,
        sale_date,
        total_amount,
        payment_status
    FROM sales
    WHERE business_id = %s
      AND sale_date BETWEEN %s AND %s
    ORDER BY sale_date
    """,
    (
        business_id,
        start_date,
        end_date
    )
)

sales_data = cursor.fetchall()

# ==================================================
# SALE ITEMS
# ==================================================

cursor.execute(
    """
    SELECT
        si.product_id,
        p.product_name,
        si.quantity,
        si.selling_price,
        si.subtotal
    FROM sale_items si
    JOIN sales s
        ON si.sale_id = s.sale_id
    JOIN products p
        ON si.product_id = p.product_id
    WHERE s.business_id = %s
      AND s.sale_date BETWEEN %s AND %s
    """,
    (
        business_id,
        start_date,
        end_date
    )
)

sale_items_data = cursor.fetchall()

# ==================================================
# EXPENSE DATA
# ==================================================

cursor.execute(
    """
    SELECT
        expense_category,
        amount,
        expense_date,
        description
    FROM expenses
    WHERE business_id = %s
      AND expense_date BETWEEN %s AND %s
    """,
    (
        business_id,
        start_date,
        end_date
    )
)

expense_data = cursor.fetchall()

# ==================================================
# PRODUCT DATA
# ==================================================

cursor.execute(
    """
    SELECT
        product_id,
        product_name,
        category,
        purchase_price,
        selling_price,
        stock,
        minimum_stock
    FROM products
    WHERE business_id = %s
    """,
    (business_id,)
)

product_data = cursor.fetchall()

cursor.close()
connection.close()

# ==================================================
# DATAFRAMES
# ==================================================
sales_df = pd.DataFrame(sales_data)
items_df = pd.DataFrame(sale_items_data)
expenses_df = pd.DataFrame(expense_data)
products_df = pd.DataFrame(product_data)

# ==================================================
# SALES CALCULATION
# ==================================================

if sales_df.empty:
    revenue = 0.0
    total_orders = 0
else:

    sales_df["total_amount"] = pd.to_numeric(
        sales_df["total_amount"],
        errors="coerce"
    ).fillna(0)

    revenue = float(
        sales_df["total_amount"].sum()
    )

    total_orders = int(
        sales_df["sale_id"].nunique()
    )

# ==================================================
# PRODUCT COST CALCULATION
# ==================================================

product_cost = 0.0

if not items_df.empty:

    items_df["product_id"] = pd.to_numeric(
        items_df["product_id"],
        errors="coerce"
    )

    items_df["quantity"] = pd.to_numeric(
        items_df["quantity"],
        errors="coerce"
    ).fillna(0)

    # ----------------------------------------------
    # Convert product IDs to normal Python int
    # ----------------------------------------------

    product_ids = [
        int(product_id)
        for product_id in items_df["product_id"].dropna().unique()
    ]

    if len(product_ids) > 0:

        connection = create_connection()

        if connection:

            cursor = connection.cursor(
                dictionary=True
            )

            placeholders = ",".join(
                ["%s"] * len(product_ids)
            )

            query = f"""
                SELECT
                    product_id,
                    purchase_price
                FROM products
                WHERE business_id = %s
                  AND product_id IN ({placeholders})
            """

            # IMPORTANT:
            # Convert everything to normal Python int
            query_params = tuple(
                [int(business_id)] +
                [int(product_id) for product_id in product_ids]
            )

            cursor.execute(
                query,
                query_params
            )

            purchase_prices = cursor.fetchall()

            cursor.close()
            connection.close()

            purchase_df = pd.DataFrame(
                purchase_prices
            )

            if not purchase_df.empty:

                purchase_df["product_id"] = (
                    purchase_df["product_id"]
                    .astype(int)
                )

                purchase_df["purchase_price"] = (
                    pd.to_numeric(
                        purchase_df["purchase_price"],
                        errors="coerce"
                    )
                    .fillna(0)
                )

                items_df = items_df.merge(
                    purchase_df,
                    on="product_id",
                    how="left"
                )

                items_df["purchase_price"] = (
                    pd.to_numeric(
                        items_df["purchase_price"],
                        errors="coerce"
                    )
                    .fillna(0)
                )

                items_df["product_cost"] = (
                    items_df["quantity"]
                    * items_df["purchase_price"]
                )

                product_cost = float(
                    items_df["product_cost"].sum()
                )

# ==================================================
# EXPENSE CALCULATION
# ==================================================

if expenses_df.empty:

    total_expenses = 0.0

else:

    expenses_df["amount"] = pd.to_numeric(
        expenses_df["amount"],
        errors="coerce"
    ).fillna(0)

    total_expenses = float(
        expenses_df["amount"].sum()
    )

# ==================================================
# PROFIT CALCULATIONS
# ==================================================

gross_profit = float(
    revenue - product_cost
)

net_profit = float(
    gross_profit - total_expenses
)

if revenue > 0:
    profit_margin = (
        net_profit / revenue
    ) * 100

else:

    profit_margin = 0.0

# ==================================================
# KPI SECTION
# ==================================================

st.subheader("📊 Business Performance")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "💰 Revenue",
    f"₹{revenue:,.2f}"
)

col2.metric(
    "📦 Product Cost",
    f"₹{product_cost:,.2f}"
)

col3.metric(
    "💸 Expenses",
    f"₹{total_expenses:,.2f}"
)

col4.metric(
    "📈 Net Profit",
    f"₹{net_profit:,.2f}"
)

st.divider()

col1, col2, col3 = st.columns(3)

col1.metric(
    "🧾 Total Orders",
    total_orders
)

col2.metric(
    "📊 Profit Margin",
    f"{profit_margin:.2f}%"
)

col3.metric(
    "💵 Gross Profit",
    f"₹{gross_profit:,.2f}"
)

st.divider()

# ==================================================
# SMART INSIGHTS
# ==================================================

st.header("🧠 Smart Insights")

insights = []

# --------------------------------------------------
# Sales Insight
# --------------------------------------------------

if revenue == 0:

    insights.append(
        "⚠️ No sales were recorded during the "
        "selected period. Consider focusing on "
        "customer engagement and promotions."
    )

else:

    insights.append(
        f"💰 Your business generated "
        f"₹{revenue:,.2f} revenue during the "
        f"selected period."
    )

# --------------------------------------------------
# Profit Insight
# --------------------------------------------------

if net_profit > 0:

    insights.append(
        f"✅ Your estimated net profit is "
        f"₹{net_profit:,.2f}."
    )

elif net_profit < 0:

    insights.append(
        f"⚠️ Your business is showing an "
        f"estimated loss of ₹{abs(net_profit):,.2f}."
    )

else:

    insights.append(
        "ℹ️ Your estimated net profit is currently zero."
    )

# --------------------------------------------------
# Profit Margin Insight
# --------------------------------------------------

if profit_margin >= 30:

    insights.append(
        f"🟢 Strong profit margin of "
        f"{profit_margin:.2f}%. Your business appears "
        "to be generating healthy returns."
    )

elif profit_margin >= 15:

    insights.append(
        f"🟡 Profit margin is "
        f"{profit_margin:.2f}%. There may be "
        "opportunities to improve profitability."
    )

elif revenue > 0:

    insights.append(
        f"🔴 Profit margin is only "
        f"{profit_margin:.2f}%. Review product pricing "
        "and operating expenses."
    )

# ==================================================
# BEST SELLING PRODUCT
# ==================================================

if not items_df.empty:

    product_sales = (
        items_df
        .groupby("product_name")["quantity"]
        .sum()
        .sort_values(ascending=False)
    )

    if not product_sales.empty:

        best_product = str(
            product_sales.index[0]
        )

        best_quantity = int(
            product_sales.iloc[0]
        )

        insights.append(
            f"🏆 {best_product} is your "
            f"best-selling product with "
            f"{best_quantity} units sold."
        )

# ==================================================
# HIGHEST EXPENSE CATEGORY
# ==================================================

if not expenses_df.empty:

    expense_categories = (
        expenses_df
        .groupby("expense_category")["amount"]
        .sum()
        .sort_values(ascending=False)
    )

    if not expense_categories.empty:

        highest_expense_category = str(
            expense_categories.index[0]
        )

        highest_expense_amount = float(
            expense_categories.iloc[0]
        )

        insights.append(
            f"💸 {highest_expense_category} "
            f"is your highest expense category at "
            f"₹{highest_expense_amount:,.2f}."
        )

# ==================================================
# LOW STOCK PRODUCTS
# ==================================================
low_stock_df = pd.DataFrame()

if not products_df.empty:

    products_df["stock"] = pd.to_numeric(
        products_df["stock"],
        errors="coerce"
    ).fillna(0)

    products_df["minimum_stock"] = pd.to_numeric(
        products_df["minimum_stock"],
        errors="coerce"
    ).fillna(0)

    low_stock_df = products_df[
        products_df["stock"]
        <= products_df["minimum_stock"]
    ]

    if not low_stock_df.empty:

        insights.append(
            f"📦 You have **{len(low_stock_df)} "
            "product(s)** at or below the minimum "
            "stock level."
        )

    else:

        insights.append(
            "✅ No products are currently below "
            "the minimum stock level."
        )

# ==================================================
# DISPLAY INSIGHTS
# ==================================================

for insight in insights:

    st.info(insight)

# ==================================================
# RECOMMENDATIONS
# ==================================================

st.divider()

st.header("🎯 Business Recommendations")

recommendations = []

# --------------------------------------------------
# Sales Recommendation
# --------------------------------------------------

if revenue == 0:

    recommendations.append(
        "📢 Try promotional offers or improve "
        "customer outreach to generate more sales."
    )

else:

    recommendations.append(
        "📈 Track your sales regularly and identify "
        "products that generate the most revenue."
    )

# --------------------------------------------------
# Profit Recommendation
# --------------------------------------------------

if profit_margin < 15 and revenue > 0:

    recommendations.append(
        "💡 Review product pricing and operating "
        "expenses to improve your profit margin."
    )

elif profit_margin >= 30:

    recommendations.append(
        "🚀 Your profit margin is strong. Focus on "
        "maintaining product quality and customer "
        "satisfaction."
    )

# --------------------------------------------------
# Inventory Recommendation
# --------------------------------------------------

if not products_df.empty:

    low_stock_count = int(
        len(
            products_df[
                products_df["stock"]
                <= products_df["minimum_stock"]
            ]
        )
    )

    if low_stock_count > 0:

        recommendations.append(
            f"📦 Consider restocking "
            f"{low_stock_count} low-stock product(s)."
        )

# --------------------------------------------------
# Expense Recommendation
# --------------------------------------------------

if not expenses_df.empty:

    if revenue > 0 and total_expenses > revenue * 0.30:

        recommendations.append(
            "💸 Expenses are relatively high compared "
            "with revenue. Review unnecessary business costs."
        )

    else:

        recommendations.append(
            "📊 Continue monitoring expense categories "
            "to control unnecessary spending."
        )

# --------------------------------------------------
# Best Seller Recommendation
# --------------------------------------------------

if not items_df.empty:

    product_sales = (
        items_df
        .groupby("product_name")["quantity"]
        .sum()
        .sort_values(ascending=False)
    )

    if not product_sales.empty:

        best_product = str(
            product_sales.index[0]
        )

        recommendations.append(
            f"🏆 Consider maintaining sufficient stock "
            f"of {best_product}, since it is currently "
            "your best-selling product."
        )

# ==================================================
# DISPLAY RECOMMENDATIONS
# ==================================================

for recommendation in recommendations:

    st.success(recommendation)

# ==================================================
# PRODUCT PERFORMANCE
# ==================================================

st.divider()

st.header("📦 Product Performance")
if items_df.empty:

    st.info(
        "ℹ️ No product sales data available "
        "for the selected period."
    )

else:

    product_performance = (
        items_df
        .groupby("product_name")
        .agg(
            Units_Sold=("quantity", "sum"),
            Sales_Value=("subtotal", "sum")
        )
        .reset_index()
        .sort_values(
            "Units_Sold",
            ascending=False
        )
    )

    product_performance["Units_Sold"] = (
        product_performance["Units_Sold"]
        .astype(int)
    )

    product_performance["Sales_Value"] = (
        pd.to_numeric(
            product_performance["Sales_Value"],
            errors="coerce"
        )
        .fillna(0)
        .round(2)
    )

    st.dataframe(
        product_performance,
        use_container_width=True,
        hide_index=True
    )

# ==================================================
# INVENTORY ATTENTION
# ==================================================

st.divider()

st.header("🚨 Inventory Attention")

if products_df.empty:

    st.info("No products found.")

else:

    inventory_attention = products_df[
        products_df["stock"]
        <= products_df["minimum_stock"]
    ][
        [
            "product_name",
            "category",
            "stock",
            "minimum_stock"
        ]
    ].copy()

    if inventory_attention.empty:

        st.success(
            "✅ All products have sufficient stock."
        )

    else:

        st.warning(
            f"⚠️ {len(inventory_attention)} "
            "product(s) need inventory attention."
        )

        st.dataframe(
            inventory_attention,
            use_container_width=True,
            hide_index=True
        )

# ==================================================
# BUSINESS SUMMARY
# ==================================================

st.divider()

st.header("📋 Business Summary")

summary_col1, summary_col2 = st.columns(2)

with summary_col1:

    st.write(
        "Business:",
        business_name
    )

    st.write(
        "Analysis From:",
        start_date
    )

    st.write(
        "Analysis To:",
        end_date
    )

    st.write(
        "Total Orders:",
        total_orders
    )

with summary_col2:

    st.write(
        "Revenue:",
        f"₹{revenue:,.2f}"
    )

    st.write(
        "Expenses:",
        f"₹{total_expenses:,.2f}"
    )

    st.write(
        "Net Profit:",
        f"₹{net_profit:,.2f}"
    )

    st.write(
        "Profit Margin:",
        f"{profit_margin:.2f}%"
    )

# ==================================================
# FOOTER
# ==================================================

st.divider()

st.caption(
    "💡 BizPilot Smart Insights uses your business "
    "data to generate rule-based recommendations. "
    "Insights are estimates and should support, "
    "not replace, business judgment."
)