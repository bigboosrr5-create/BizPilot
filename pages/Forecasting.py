import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
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
    page_title="Forecasting - BizPilot",
    page_icon="🔮",
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

st.title("🔮 Sales Forecasting")
st.caption(
    "Use historical sales data to estimate future business revenue."
)

st.divider()

# ==================================================
# FORECAST SETTINGS
# ==================================================

st.subheader("⚙️ Forecast Settings")

col1, col2 = st.columns(2)

forecast_days = col1.selectbox(
    "Forecast Period",
    [7, 15, 30],
    index=2,
    format_func=lambda x: f"Next {x} Days"
)

history_days = col2.selectbox(
    "Historical Data",
    [7, 14, 30, 60, 90],
    index=2,
    format_func=lambda x: f"Last {x} Days"
)

# ==================================================
# DATABASE CONNECTION
# ==================================================

connection = create_connection()

if not connection:
    st.error("❌ Database connection failed.")
    st.stop()

cursor = connection.cursor(dictionary=True)

# ==================================================
# GET SALES DATA
# ==================================================

cursor.execute(
    """
    SELECT
        sale_date,
        total_amount
    FROM sales
    WHERE business_id = %s
    ORDER BY sale_date DESC
    LIMIT %s
    """,
    (
        business_id,
        int(history_days)
    )
)

sales_data = cursor.fetchall()

cursor.close()
connection.close()

# ==================================================
# DATAFRAME
# ==================================================

sales_df = pd.DataFrame(sales_data)

# ==================================================
# NO DATA HANDLING
# ==================================================

if sales_df.empty:

    st.warning(
        "⚠️ Not enough sales data available for forecasting."
    )

    st.info(
        "Please add some sales from the Sales page first."
    )

    st.stop()

# ==================================================
# CLEAN DATA
# ==================================================

sales_df["sale_date"] = pd.to_datetime(
    sales_df["sale_date"]
)

sales_df["total_amount"] = pd.to_numeric(
    sales_df["total_amount"],
    errors="coerce"
).fillna(0)

# ==================================================
# DAILY SALES
# ==================================================

daily_sales = (
    sales_df
    .groupby("sale_date", as_index=False)["total_amount"]
    .sum()
    .sort_values("sale_date")
)

# ==================================================
# FILL MISSING DATES
# ==================================================

if not daily_sales.empty:

    full_dates = pd.date_range(
        start=daily_sales["sale_date"].min(),
        end=daily_sales["sale_date"].max(),
        freq="D"
    )

    daily_sales = (
        daily_sales
        .set_index("sale_date")
        .reindex(full_dates, fill_value=0)
        .rename_axis("sale_date")
        .reset_index()
    )

# ==================================================
# BASIC CALCULATIONS
# ==================================================
historical_revenue = float(
    daily_sales["total_amount"].sum()
)

number_of_days = len(daily_sales)

if number_of_days > 0:

    average_daily_sales = (
        historical_revenue / number_of_days
    )

else:

    average_daily_sales = 0.0

average_daily_sales = float(
    average_daily_sales
)

average_sale = float(
    sales_df["total_amount"].mean()
)

total_orders = int(
    len(sales_df)
)

# ==================================================
# FORECAST CALCULATION
# ==================================================

# Use recent daily sales for a simple forecast.

recent_days = min(
    7,
    len(daily_sales)
)

recent_sales = (
    daily_sales
    .tail(recent_days)["total_amount"]
)

if not recent_sales.empty:

    forecast_daily_average = float(
        recent_sales.mean()
    )

else:

    forecast_daily_average = float(
        average_daily_sales
    )

forecast_revenue = float(
    forecast_daily_average * forecast_days
)

# ==================================================
# FORECAST DATES
# ==================================================

last_date = daily_sales["sale_date"].max()

forecast_dates = pd.date_range(
    start=last_date + pd.Timedelta(days=1),
    periods=forecast_days,
    freq="D"
)

forecast_values = np.full(
    forecast_days,
    forecast_daily_average,
    dtype=float
)

forecast_df = pd.DataFrame(
    {
        "Date": forecast_dates,
        "Forecast Sales": forecast_values
    }
)

# ==================================================
# KPI SECTION
# ==================================================

st.subheader("📊 Forecast Overview")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "💰 Historical Revenue",
    f"₹{historical_revenue:,.2f}"
)

col2.metric(
    "📅 Avg. Daily Sales",
    f"₹{average_daily_sales:,.2f}"
)

col3.metric(
    "🔮 Forecast Revenue",
    f"₹{forecast_revenue:,.2f}"
)

col4.metric(
    "🧾 Total Orders",
    total_orders
)

st.divider()

# ==================================================
# HISTORICAL SALES CHART
# ==================================================

st.subheader("📈 Historical Sales Trend")

historical_chart = daily_sales.copy()

historical_chart["Type"] = "Historical"

historical_chart = historical_chart.rename(
    columns={
        "sale_date": "Date",
        "total_amount": "Sales"
    }
)

fig_history = px.line(
    historical_chart,
    x="Date",
    y="Sales",
    markers=True,
    title="Historical Daily Sales"
)

fig_history.update_layout(
    xaxis_title="Date",
    yaxis_title="Sales (₹)",
    hovermode="x unified"
)

st.plotly_chart(
    fig_history,
    use_container_width=True
)

# ==================================================
# FORECAST CHART
# ==================================================

st.subheader("🔮 Sales Forecast")

forecast_chart = forecast_df.copy()

forecast_chart = forecast_chart.rename(
    columns={
        "Forecast Sales": "Sales"
    }
)

fig_forecast = px.line(
    forecast_chart,
    x="Date",
    y="Sales",
    markers=True,
    title=f"Next {forecast_days} Days Forecast"
)

fig_forecast.update_layout(
    xaxis_title="Date",
    yaxis_title="Forecast Sales (₹)",
    hovermode="x unified"
)

st.plotly_chart(
    fig_forecast,
    use_container_width=True
)

# ==================================================
# COMBINED CHART
# ==================================================

st.subheader("📊 Historical + Forecast")

historical_part = daily_sales[
    ["sale_date", "total_amount"]
].copy()

historical_part = historical_part.rename(
    columns={
        "sale_date": "Date",
        "total_amount": "Sales"
    }
)

historical_part["Type"] = "Historical"

forecast_part = forecast_df[
    ["Date", "Forecast Sales"]
].copy()

forecast_part = forecast_part.rename(
    columns={
        "Forecast Sales": "Sales"
    }
)

forecast_part["Type"] = "Forecast"

combined_df = pd.concat(
    [
        historical_part,
        forecast_part
    ],
    ignore_index=True
)
fig_combined = px.line(
    combined_df,
    x="Date",
    y="Sales",
    color="Type",
    markers=True,
    title="Historical Sales and Future Forecast"
)

fig_combined.update_layout(
    xaxis_title="Date",
    yaxis_title="Sales (₹)",
    hovermode="x unified"
)

st.plotly_chart(
    fig_combined,
    use_container_width=True
)

# ==================================================
# FORECAST TABLE
# ==================================================

st.divider()

st.subheader("📋 Forecast Details")

display_forecast = forecast_df.copy()

display_forecast["Date"] = (
    display_forecast["Date"]
    .dt.strftime("%d-%m-%Y")
)

display_forecast["Forecast Sales"] = (
    display_forecast["Forecast Sales"]
    .round(2)
)

st.dataframe(
    display_forecast,
    use_container_width=True,
    hide_index=True
)

# ==================================================
# FORECAST SUMMARY
# ==================================================

st.divider()

st.subheader("💡 Forecast Summary")

summary_col1, summary_col2 = st.columns(2)

with summary_col1:

    st.write(
        "Business:",
        business_name
    )

    st.write(
        "Historical Days Analysed:",
        number_of_days
    )

    st.write(
        "Recent Average Daily Sales:",
        f"₹{forecast_daily_average:,.2f}"
    )

with summary_col2:

    st.write(
        "Forecast Period:",
        f"{forecast_days} days"
    )

    st.write(
        "Estimated Future Revenue:",
        f"₹{forecast_revenue:,.2f}"
    )

    st.write(
        "Average Sale Value:",
        f"₹{average_sale:,.2f}"
    )

# ==================================================
# SMART INTERPRETATION
# ==================================================

st.divider()

st.subheader("🧠 Forecast Interpretation")

if forecast_daily_average > average_daily_sales:

    st.success(
        "📈 Recent sales are higher than the overall "
        "historical average. If this trend continues, "
        "future revenue may remain strong."
    )

elif forecast_daily_average < average_daily_sales:

    st.warning(
        "📉 Recent sales are below the historical average. "
        "Consider analysing products, customers and "
        "expenses to understand the reason."
    )

else:

    st.info(
        "➡️ Recent sales are approximately in line with "
        "the historical average."
    )

# ==================================================
# BUSINESS RECOMMENDATIONS
# ==================================================

st.subheader("🎯 Business Recommendations")

if forecast_revenue > 0:

    st.info(
        f"💰 Based on recent sales, estimated revenue "
        f"for the next {forecast_days} days is "
        f"₹{forecast_revenue:,.2f}."
    )

if forecast_daily_average > 0:

    st.info(
        "📦 Keep sufficient inventory for products "
        "that are selling frequently."
    )

if forecast_daily_average < average_daily_sales:

    st.info(
        "📢 Consider promotional activities or "
        "customer engagement strategies to improve sales."
    )

# ==================================================
# IMPORTANT NOTE
# ==================================================

st.divider()

st.caption(
    "⚠️ Forecasting is an estimate based on historical "
    "sales patterns. Actual future sales may differ due "
    "to seasonality, customer behaviour, market conditions "
    "and other business factors."
)
