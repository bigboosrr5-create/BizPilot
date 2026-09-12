import streamlit as st
import pandas as pd
import numpy as np
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
    page_title="Inventory Intelligence - BizPilot",
    page_icon="📦",
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

st.title("📦 Inventory Intelligence")
st.caption(
    "Analyse stock levels, product movement and reorder requirements."
)

st.divider()

# ==================================================
# DATABASE CONNECTION
# ==================================================

connection = create_connection()

if not connection:
    st.error("❌ Database connection failed.")
    st.stop()

cursor = connection.cursor(dictionary=True)

# ==================================================
# PRODUCTS
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
    ORDER BY product_name
    """,
    (business_id,)
)

products_data = cursor.fetchall()

# ==================================================
# SALES - LAST 30 DAYS
# ==================================================

cursor.execute(
    """
    SELECT
        si.product_id,
        SUM(si.quantity) AS total_sold
    FROM sale_items si
    JOIN sales s
        ON si.sale_id = s.sale_id
    WHERE s.business_id = %s
      AND s.sale_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    GROUP BY si.product_id
    """,
    (business_id,)
)

sales_data = cursor.fetchall()

cursor.close()
connection.close()

# ==================================================
# DATAFRAMES
# ==================================================

products_df = pd.DataFrame(products_data)
sales_df = pd.DataFrame(sales_data)

# ==================================================
# NO PRODUCTS
# ==================================================

if products_df.empty:
    st.info(
        "📦 No products found. Please add products "
        "from the Products page first."
    )
    st.stop()

# ==================================================
# CLEAN PRODUCT DATA
# ==================================================

for column in [
    "purchase_price",
    "selling_price",
    "stock",
    "minimum_stock"
]:
    products_df[column] = pd.to_numeric(
        products_df[column],
        errors="coerce"
    ).fillna(0)

products_df["product_id"] = (
    pd.to_numeric(
        products_df["product_id"],
        errors="coerce"
    )
    .fillna(0)
    .astype(int)
)

# ==================================================
# CLEAN SALES DATA
# ==================================================

if sales_df.empty:

    sales_df = pd.DataFrame(
        columns=[
            "product_id",
            "total_sold"
        ]
    )

else:

    sales_df["product_id"] = (
        pd.to_numeric(
            sales_df["product_id"],
            errors="coerce"
        )
        .fillna(0)
        .astype(int)
    )

    sales_df["total_sold"] = pd.to_numeric(
        sales_df["total_sold"],
        errors="coerce"
    ).fillna(0)
    # ==================================================
# MERGE DATA
# ==================================================

inventory_df = products_df.merge(
    sales_df,
    on="product_id",
    how="left"
)

inventory_df["total_sold"] = (
    inventory_df["total_sold"]
    .fillna(0)
)

# ==================================================
# INVENTORY VALUE
# ==================================================

inventory_df["inventory_value"] = (
    inventory_df["stock"]
    * inventory_df["purchase_price"]
)

# ==================================================
# SALES VALUE
# ==================================================

inventory_df["sales_value"] = (
    inventory_df["total_sold"]
    * inventory_df["selling_price"]
)

# ==================================================
# AVERAGE DAILY SALES
# ==================================================

inventory_df["average_daily_sales"] = (
    inventory_df["total_sold"] / 30
)

# ==================================================
# ESTIMATED DAYS LEFT
# ==================================================

inventory_df["days_left"] = np.where(
    inventory_df["average_daily_sales"] > 0,
    inventory_df["stock"]
    / inventory_df["average_daily_sales"],
    np.inf
)

# ==================================================
# STOCK STATUS
# ==================================================

def get_stock_status(row):

    stock = float(row["stock"])
    minimum_stock = float(row["minimum_stock"])
    days_left = row["days_left"]

    if stock <= 0:
        return "🔴 Out of Stock"

    if stock <= minimum_stock:
        return "🔴 Critical"

    if days_left != np.inf and days_left <= 7:
        return "🟠 Attention"

    if days_left != np.inf and days_left <= 15:
        return "🟡 Monitor"

    return "🟢 Healthy"


inventory_df["status"] = inventory_df.apply(
    get_stock_status,
    axis=1
)

# ==================================================
# RECOMMENDED REORDER
# ==================================================

inventory_df["recommended_reorder"] = np.where(
    inventory_df["average_daily_sales"] > 0,
    np.ceil(
        inventory_df["average_daily_sales"] * 30
        - inventory_df["stock"]
    ),
    0
)

inventory_df["recommended_reorder"] = (
    inventory_df["recommended_reorder"]
    .clip(lower=0)
    .astype(int)
)

# ==================================================
# KPI CALCULATIONS
# ==================================================

total_products = int(
    len(inventory_df)
)

total_stock_units = int(
    inventory_df["stock"].sum()
)

total_inventory_value = float(
    inventory_df["inventory_value"].sum()
)

low_stock_count = int(
    (
        inventory_df["stock"]
        <= inventory_df["minimum_stock"]
    ).sum()
)

out_of_stock_count = int(
    (
        inventory_df["stock"]
        <= 0
    ).sum()
)

total_sold_30_days = int(
    inventory_df["total_sold"].sum()
)

# ==================================================
# KPI DISPLAY
# ==================================================

st.subheader("📊 Inventory Overview")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "📦 Total Products",
    total_products
)

col2.metric(
    "🔢 Stock Units",
    f"{total_stock_units:,}"
)

col3.metric(
    "💰 Inventory Value",
    f"₹{total_inventory_value:,.2f}"
)

col4.metric(
    "🚨 Low Stock",
    low_stock_count
)

st.divider()

col1, col2 = st.columns(2)

col1.metric(
    "🔴 Out of Stock",
    out_of_stock_count
)

col2.metric(
    "📈 Units Sold - 30 Days",
    f"{total_sold_30_days:,}"
)

# ==================================================
# INVENTORY STATUS
# ==================================================

st.divider()

st.subheader("🚦 Inventory Status")

status_summary = (
    inventory_df["status"]
    .value_counts()
    .reset_index()
)

status_summary.columns = [
    "Status",
    "Products"
]

st.dataframe(
    status_summary,
    use_container_width=True,
    hide_index=True
)

# ==================================================
# COMPLETE INVENTORY
# ==================================================
st.divider()

st.subheader("📋 Complete Inventory")

display_df = inventory_df[
    [
        "product_name",
        "category",
        "purchase_price",
        "selling_price",
        "stock",
        "minimum_stock",
        "total_sold",
        "days_left",
        "recommended_reorder",
        "status"
    ]
].copy()

# IMPORTANT:
# display_df is created BEFORE using display_df.columns

display_df.columns = [
    "Product",
    "Category",
    "Purchase Price",
    "Selling Price",
    "Current Stock",
    "Minimum Stock",
    "Sold (30 Days)",
    "Estimated Days Left",
    "Recommended Reorder",
    "Status"
]

display_df["Purchase Price"] = (
    pd.to_numeric(
        display_df["Purchase Price"],
        errors="coerce"
    )
    .fillna(0)
    .round(2)
)

display_df["Selling Price"] = (
    pd.to_numeric(
        display_df["Selling Price"],
        errors="coerce"
    )
    .fillna(0)
    .round(2)
)

display_df["Current Stock"] = (
    pd.to_numeric(
        display_df["Current Stock"],
        errors="coerce"
    )
    .fillna(0)
    .astype(int)
)

display_df["Minimum Stock"] = (
    pd.to_numeric(
        display_df["Minimum Stock"],
        errors="coerce"
    )
    .fillna(0)
    .astype(int)
)

display_df["Sold (30 Days)"] = (
    pd.to_numeric(
        display_df["Sold (30 Days)"],
        errors="coerce"
    )
    .fillna(0)
    .astype(int)
)

display_df["Estimated Days Left"] = (
    pd.to_numeric(
        display_df["Estimated Days Left"],
        errors="coerce"
    )
    .replace(np.inf, np.nan)
    .round(1)
)

display_df["Recommended Reorder"] = (
    pd.to_numeric(
        display_df["Recommended Reorder"],
        errors="coerce"
    )
    .fillna(0)
    .astype(int)
)

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)

# ==================================================
# CRITICAL STOCK
# ==================================================

st.divider()

st.subheader("🔴 Critical Stock")

critical_df = inventory_df[
    inventory_df["status"].isin(
        [
            "🔴 Out of Stock",
            "🔴 Critical"
        ]
    )
].copy()

if critical_df.empty:

    st.success(
        "✅ No critical stock products found."
    )

else:

    critical_display = critical_df[
        [
            "product_name",
            "category",
            "stock",
            "minimum_stock",
            "total_sold",
            "recommended_reorder",
            "status"
        ]
    ].copy()

    critical_display.columns = [
        "Product",
        "Category",
        "Current Stock",
        "Minimum Stock",
        "Sold (30 Days)",
        "Recommended Reorder",
        "Status"
    ]

    st.warning(
        f"⚠️ {len(critical_display)} product(s) "
        "need immediate inventory attention."
    )

    st.dataframe(
        critical_display,
        use_container_width=True,
        hide_index=True
    )

# ==================================================
# FAST MOVING PRODUCTS
# ==================================================

st.divider()

st.subheader("🔥 Fast-Moving Products")

fast_moving = (
    inventory_df[
        inventory_df["total_sold"] > 0
    ]
    .sort_values(
        "total_sold",
        ascending=False
    )
    .head(10)
)

if fast_moving.empty:

    st.info(
        "ℹ️ No product movement recorded "
        "in the last 30 days."
    )

else:

    fast_display = fast_moving[
        [
            "product_name",
            "category",
            "total_sold",
            "stock",
            "days_left"
        ]
    ].copy()

    fast_display.columns = [
        "Product",
        "Category",
        "Sold (30 Days)",
        "Current Stock",
        "Estimated Days Left"
    ]

    fast_display["Estimated Days Left"] = (
        pd.to_numeric(
            fast_display["Estimated Days Left"],
            errors="coerce"
        )
        .replace(np.inf, np.nan)
        .round(1)
    )

    st.dataframe(
        fast_display,
        use_container_width=True,
        hide_index=True
    )
    # ==================================================
# SLOW MOVING PRODUCTS
# ==================================================

st.divider()

st.subheader("🐢 Slow-Moving Products")

slow_moving = (
    inventory_df[
        inventory_df["total_sold"] > 0
    ]
    .sort_values(
        "total_sold",
        ascending=True
    )
    .head(10)
)

if slow_moving.empty:

    st.info(
        "ℹ️ Not enough sales data to identify "
        "slow-moving products."
    )

else:

    slow_display = slow_moving[
        [
            "product_name",
            "category",
            "total_sold",
            "stock"
        ]
    ].copy()

    slow_display.columns = [
        "Product",
        "Category",
        "Sold (30 Days)",
        "Current Stock"
    ]

    st.dataframe(
        slow_display,
        use_container_width=True,
        hide_index=True
    )

# ==================================================
# UNSOLD PRODUCTS
# ==================================================

st.divider()

st.subheader("⚠️ Unsold Products")

unsold_df = inventory_df[
    inventory_df["total_sold"] <= 0
].copy()

if unsold_df.empty:

    st.success(
        "✅ All products have recorded sales "
        "in the last 30 days."
    )

else:

    unsold_display = unsold_df[
        [
            "product_name",
            "category",
            "stock",
            "inventory_value"
        ]
    ].copy()

    unsold_display.columns = [
        "Product",
        "Category",
        "Current Stock",
        "Inventory Value"
    ]

    unsold_display["Inventory Value"] = (
        pd.to_numeric(
            unsold_display["Inventory Value"],
            errors="coerce"
        )
        .fillna(0)
        .round(2)
    )

    st.warning(
        f"⚠️ {len(unsold_display)} product(s) "
        "had no sales in the last 30 days."
    )

    st.dataframe(
        unsold_display,
        use_container_width=True,
        hide_index=True
    )

# ==================================================
# REORDER RECOMMENDATIONS
# ==================================================

st.divider()

st.subheader("🔄 Reorder Recommendations")

reorder_df = (
    inventory_df[
        inventory_df["recommended_reorder"] > 0
    ]
    .sort_values(
        "recommended_reorder",
        ascending=False
    )
)

if reorder_df.empty:

    st.success(
        "✅ No immediate reorder recommendations."
    )

else:

    reorder_display = reorder_df[
        [
            "product_name",
            "category",
            "stock",
            "average_daily_sales",
            "days_left",
            "recommended_reorder"
        ]
    ].copy()

    reorder_display.columns = [
        "Product",
        "Category",
        "Current Stock",
        "Avg Daily Sales",
        "Estimated Days Left",
        "Recommended Reorder"
    ]

    reorder_display["Avg Daily Sales"] = (
        pd.to_numeric(
            reorder_display["Avg Daily Sales"],
            errors="coerce"
        )
        .fillna(0)
        .round(2)
    )

    reorder_display["Estimated Days Left"] = (
        pd.to_numeric(
            reorder_display["Estimated Days Left"],
            errors="coerce"
        )
        .replace(np.inf, np.nan)
        .round(1)
    )

    reorder_display["Recommended Reorder"] = (
        pd.to_numeric(
            reorder_display["Recommended Reorder"],
            errors="coerce"
        )
        .fillna(0)
        .astype(int)
    )

    st.dataframe(
        reorder_display,
        use_container_width=True,
        hide_index=True
    )

# ==================================================
# SMART RECOMMENDATIONS
# ==================================================

st.divider()

st.subheader("🧠 Smart Inventory Recommendations")

recommendations = []

if out_of_stock_count > 0:

    recommendations.append(
        f"🔴 {out_of_stock_count} product(s) are "
        "currently out of stock. Consider restocking "
        "them immediately."
    )

if low_stock_count > 0:
    recommendations.append(
        f"📦 {low_stock_count} product(s) are at or "
        "below their minimum stock level."
    )

if not fast_moving.empty:

    top_product = str(
        fast_moving.iloc[0]["product_name"]
    )

    top_quantity = int(
        fast_moving.iloc[0]["total_sold"]
    )

    recommendations.append(
        f"🔥 {top_product} is your fastest-moving "
        f"product with {top_quantity} units sold "
        "during the last 30 days."
    )

if not unsold_df.empty:

    recommendations.append(
        f"⚠️ {len(unsold_df)} product(s) had no sales "
        "during the last 30 days. Review whether these "
        "products need promotion or better placement."
    )

if total_inventory_value > 0:

    recommendations.append(
        f"💰 Your current inventory is worth approximately "
        f"₹{total_inventory_value:,.2f} at purchase cost."
    )

if not recommendations:

    recommendations.append(
        "✅ Inventory is currently in a healthy condition."
    )

for recommendation in recommendations:
    st.info(recommendation)

# ==================================================
# INVENTORY SUMMARY
# ==================================================

st.divider()

st.subheader("📋 Inventory Summary")

col1, col2 = st.columns(2)

with col1:

    st.write(
        "Business:",
        business_name
    )

    st.write(
        "Total Products:",
        total_products
    )

    st.write(
        "Total Stock Units:",
        f"{total_stock_units:,}"
    )

with col2:

    st.write(
        "Inventory Value:",
        f"₹{total_inventory_value:,.2f}"
    )

    st.write(
        "Low Stock Products:",
        low_stock_count
    )

    st.write(
        "Out of Stock Products:",
        out_of_stock_count
    )

# ==================================================
# FOOTER
# ==================================================

st.divider()

st.caption(
    "📦 Inventory Intelligence analyses stock and "
    "last-30-day product movement to provide "
    "inventory recommendations. Actual reorder "
    "requirements may vary based on business conditions."
)