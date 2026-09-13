import streamlit as st
import pandas as pd
from datetime import date, timedelta
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)

from database import create_connection
from utils.auth import (
    is_logged_in,
    get_business_id,
    get_business_name,
    logout
)


# =========================================================
# LOGIN CHECK
# =========================================================

if not is_logged_in():
    st.warning("🔐 Please login first.")
    st.stop()


business_id = get_business_id()
business_name = get_business_name()


# =========================================================
# PAGE HEADER
# =========================================================

st.title("📊 Reports")
st.caption(f"Business: {business_name}")

st.sidebar.success(f"🏪 {business_name}")

if st.sidebar.button("🚪 Logout"):
    logout()
    st.rerun()


# =========================================================
# DATE FILTER
# =========================================================

st.subheader("📅 Report Period")

col1, col2 = st.columns(2)

with col1:
    start_date = st.date_input(
        "Start Date",
        value=date.today() - timedelta(days=30)
    )

with col2:
    end_date = st.date_input(
        "End Date",
        value=date.today()
    )


if start_date > end_date:
    st.error("❌ Start Date cannot be after End Date.")
    st.stop()


# =========================================================
# DATABASE CONNECTION
# =========================================================

connection = create_connection()

if connection is None:
    st.error("❌ Database connection failed.")
    st.stop()


# =========================================================
# LOAD SALES
# =========================================================

sales_query = """
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
ORDER BY s.sale_date DESC
"""

sales_df = pd.read_sql(
    sales_query,
    connection,
    params=(int(business_id), start_date, end_date)
)


# =========================================================
# LOAD SALE ITEMS
# =========================================================

items_query = """
SELECT
    si.sale_id,
    si.product_id,
    p.product_name,
    p.category,
    p.purchase_price,
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
"""

items_df = pd.read_sql(
    items_query,
    connection,
    params=(int(business_id), start_date, end_date)
)


# =========================================================
# LOAD EXPENSES
# =========================================================

expense_query = """
SELECT
    expense_id,
    expense_category,
    amount,
    expense_date,
    description
FROM expenses
WHERE business_id = %s
AND expense_date BETWEEN %s AND %s
ORDER BY expense_date DESC
"""

expenses_df = pd.read_sql(
    expense_query,
    connection,
    params=(int(business_id), start_date, end_date)
)


# =========================================================
# LOAD INVENTORY
# =========================================================

inventory_query = """
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
"""

inventory_df = pd.read_sql(
    inventory_query,
    connection,
    params=(int(business_id),)
)


connection.close()


# =========================================================
# CALCULATIONS
# =========================================================
revenue = float(sales_df["total_amount"].sum()) if not sales_df.empty else 0

orders = len(sales_df)

expenses = float(expenses_df["amount"].sum()) if not expenses_df.empty else 0


if not items_df.empty:
    items_df["product_cost"] = (
        items_df["quantity"] *
        items_df["purchase_price"]
    )

    product_cost = float(items_df["product_cost"].sum())

else:
    product_cost = 0


gross_profit = revenue - product_cost

net_profit = gross_profit - expenses

profit_margin = (
    (net_profit / revenue) * 100
    if revenue > 0
    else 0
)


# =========================================================
# MAIN KPI
# =========================================================

st.subheader("📈 Business Summary")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("💰 Revenue", f"₹{revenue:,.2f}")

with c2:
    st.metric("🛒 Orders", orders)

with c3:
    st.metric("💸 Expenses", f"₹{expenses:,.2f}")

with c4:
    st.metric("📈 Net Profit", f"₹{net_profit:,.2f}")


st.divider()


# =========================================================
# PROFIT ANALYSIS
# =========================================================

st.subheader("💹 Profit Analysis")

p1, p2, p3, p4 = st.columns(4)

with p1:
    st.metric(
        "Revenue",
        f"₹{revenue:,.2f}"
    )

with p2:
    st.metric(
        "Product Cost",
        f"₹{product_cost:,.2f}"
    )

with p3:
    st.metric(
        "Gross Profit",
        f"₹{gross_profit:,.2f}"
    )

with p4:
    st.metric(
        "Profit Margin",
        f"{profit_margin:.2f}%"
    )


# =========================================================
# SALES REPORT
# =========================================================

st.divider()

st.subheader("🛒 Sales Report")

if sales_df.empty:

    st.info("No sales found for the selected period.")

else:

    display_sales = sales_df.copy()

    display_sales.columns = [
        "Sale ID",
        "Sale Date",
        "Total Amount",
        "Payment Status",
        "Customer"
    ]

    st.dataframe(
        display_sales,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# PAYMENT STATUS
# =========================================================

if not sales_df.empty:

    st.subheader("💳 Payment Status")

    payment_summary = (
        sales_df
        .groupby("payment_status")["total_amount"]
        .agg(["count", "sum"])
        .reset_index()
    )

    payment_summary.columns = [
        "Payment Status",
        "Orders",
        "Amount"
    ]

    st.dataframe(
        payment_summary,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# EXPENSE REPORT
# =========================================================

st.divider()

st.subheader("💸 Expense Report")

if expenses_df.empty:

    st.info("No expenses found for the selected period.")

else:

    display_expenses = expenses_df.copy()

    display_expenses.columns = [
        "Expense ID",
        "Category",
        "Amount",
        "Date",
        "Description"
    ]

    st.dataframe(
        display_expenses,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# EXPENSE CATEGORY SUMMARY
# =========================================================

if not expenses_df.empty:

    st.subheader("📊 Expense Category Summary")

    expense_summary = (
        expenses_df
        .groupby("expense_category")["amount"]
        .sum()
        .reset_index()
        .sort_values("amount", ascending=False)
    )

    expense_summary.columns = [
        "Category",
        "Total Expense"
    ]

    st.dataframe(
        expense_summary,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# INVENTORY REPORT
# =========================================================

st.divider()

st.subheader("📦 Inventory Report")

if inventory_df.empty:

    st.info("No products found.")

else:
    inventory_df["inventory_value"] = (
        inventory_df["stock"] *
        inventory_df["purchase_price"]
    )

    inventory_df["status"] = inventory_df.apply(
        lambda row:
        "Out of Stock"
        if row["stock"] == 0
        else "Low Stock"
        if row["stock"] <= row["minimum_stock"]
        else "Healthy",
        axis=1
    )

    total_inventory_value = float(
        inventory_df["inventory_value"].sum()
    )

    low_stock_count = int(
        (inventory_df["stock"] <= inventory_df["minimum_stock"]).sum()
    )

    out_of_stock = int(
        (inventory_df["stock"] == 0).sum()
    )

    i1, i2, i3 = st.columns(3)

    with i1:
        st.metric(
            "📦 Total Products",
            len(inventory_df)
        )

    with i2:
        st.metric(
            "💰 Inventory Value",
            f"₹{total_inventory_value:,.2f}"
        )

    with i3:
        st.metric(
            "⚠️ Low Stock",
            low_stock_count
        )

    inventory_display = inventory_df[
        [
            "product_id",
            "product_name",
            "category",
            "purchase_price",
            "selling_price",
            "stock",
            "minimum_stock",
            "inventory_value",
            "status"
        ]
    ].copy()

    inventory_display.columns = [
        "Product ID",
        "Product Name",
        "Category",
        "Purchase Price",
        "Selling Price",
        "Stock",
        "Minimum Stock",
        "Inventory Value",
        "Status"
    ]

    st.dataframe(
        inventory_display,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# CSV DOWNLOAD
# =========================================================

st.divider()

st.subheader("📥 Download Reports")

d1, d2, d3 = st.columns(3)


with d1:

    if not sales_df.empty:

        sales_csv = sales_df.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            label="📥 Sales CSV",
            data=sales_csv,
            file_name="bizpilot_sales_report.csv",
            mime="text/csv"
        )


with d2:

    if not expenses_df.empty:

        expense_csv = expenses_df.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            label="📥 Expenses CSV",
            data=expense_csv,
            file_name="bizpilot_expense_report.csv",
            mime="text/csv"
        )


with d3:

    if not inventory_df.empty:

        inventory_csv = inventory_df.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            label="📥 Inventory CSV",
            data=inventory_csv,
            file_name="bizpilot_inventory_report.csv",
            mime="text/csv"
        )


# =========================================================
# PDF REPORT
# =========================================================

st.divider()

st.subheader("📄 Business PDF Report")


def create_pdf():

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()

    story = []

    # Title
    story.append(
        Paragraph(
            "BizPilot - Business Report",
            styles["Title"]
        )
    )

    story.append(Spacer(1, 10))

    story.append(
        Paragraph(
            f"<b>Business:</b> {business_name}",
            styles["Normal"]
        )
    )

    story.append(
        Paragraph(
            f"<b>Report Period:</b> "
            f"{start_date} to {end_date}",
            styles["Normal"]
        )
    )

    story.append(Spacer(1, 15))

    # Summary
    story.append(
        Paragraph(
            "Business Summary",
            styles["Heading2"]
        )
    )
    summary_data = [
        ["Metric", "Value"],
        ["Revenue", f"₹{revenue:,.2f}"],
        ["Orders", str(orders)],
        ["Product Cost", f"₹{product_cost:,.2f}"],
        ["Gross Profit", f"₹{gross_profit:,.2f}"],
        ["Expenses", f"₹{expenses:,.2f}"],
        ["Net Profit", f"₹{net_profit:,.2f}"],
        ["Profit Margin", f"{profit_margin:.2f}%"]
    ]

    summary_table = Table(
        summary_data,
        colWidths=[220, 180]
    )

    summary_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ])
    )

    story.append(summary_table)

    # Sales
    story.append(Spacer(1, 20))

    story.append(
        Paragraph(
            "Sales Report",
            styles["Heading2"]
        )
    )

    if sales_df.empty:

        story.append(
            Paragraph(
                "No sales found.",
                styles["Normal"]
            )
        )

    else:

        sales_data = [
            [
                "ID",
                "Date",
                "Customer",
                "Amount",
                "Status"
            ]
        ]

        for _, row in sales_df.iterrows():

            sales_data.append([
                str(row["sale_id"]),
                str(row["sale_date"]),
                str(row["customer_name"] or "Walk-in"),
                f"₹{float(row['total_amount']):,.2f}",
                str(row["payment_status"])
            ])

        sales_table = Table(
            sales_data,
            repeatRows=1,
            colWidths=[40, 70, 120, 80, 70]
        )

        sales_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )

        story.append(sales_table)

    # Expenses
    story.append(Spacer(1, 20))

    story.append(
        Paragraph(
            "Expense Report",
            styles["Heading2"]
        )
    )

    if expenses_df.empty:

        story.append(
            Paragraph(
                "No expenses found.",
                styles["Normal"]
            )
        )

    else:

        expense_data = [
            [
                "ID",
                "Category",
                "Amount",
                "Date"
            ]
        ]

        for _, row in expenses_df.iterrows():

            expense_data.append([
                str(row["expense_id"]),
                str(row["expense_category"]),
                f"₹{float(row['amount']):,.2f}",
                str(row["expense_date"])
            ])

        expense_table = Table(
            expense_data,
            repeatRows=1,
            colWidths=[50, 180, 100, 100]
        )

        expense_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ])
        )

        story.append(expense_table)

    # Inventory
    story.append(Spacer(1, 20))

    story.append(
        Paragraph(
            "Inventory Summary",
            styles["Heading2"]
        )
    )

    if inventory_df.empty:

        story.append(
            Paragraph(
                "No products found.",
                styles["Normal"]
            )
        )

    else:
        inventory_data = [
            [
                "Product",
                "Stock",
                "Min Stock",
                "Value",
                "Status"
            ]
        ]

        for _, row in inventory_df.iterrows():

            inventory_data.append([
                str(row["product_name"]),
                str(row["stock"]),
                str(row["minimum_stock"]),
                f"₹{float(row['inventory_value']):,.2f}",
                str(row["status"])
            ])

        inventory_table = Table(
            inventory_data,
            repeatRows=1,
            colWidths=[140, 60, 70, 100, 80]
        )

        inventory_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ])
        )

        story.append(inventory_table)

    story.append(Spacer(1, 25))

    story.append(
        Paragraph(
            "Generated by BizPilot - Manage • Analyse • Grow",
            styles["Normal"]
        )
    )

    doc.build(story)

    buffer.seek(0)

    return buffer


if st.button("📄 Generate PDF Report"):

    pdf_file = create_pdf()

    st.success("✅ PDF Report generated successfully!")

    st.download_button(
        label="⬇️ Download PDF Report",
        data=pdf_file,
        file_name="BizPilot_Business_Report.pdf",
        mime="application/pdf"
    )


# =========================================================
# FINAL
# =========================================================

st.divider()

st.success(
    "✅ Report generated using the logged-in business data."
)
