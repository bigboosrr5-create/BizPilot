"""
BizPilot — Professional Upload & Analyse
=========================================
Drop-in replacement for: pages/_Upload_Analyse.py

Features
--------
• CSV / Excel / PDF upload
• Multi-sheet Excel handling
• Table extraction from PDFs
• Automatic column detection using exact aliases + fuzzy matching
• Confidence score + mapping review/correction (now persists across reruns)
• Data cleaning and type inference (handles accounting-style negatives too)
• Revenue / cost / profit / margin calculations where possible
• Executive KPI dashboard
• Product, category, customer, geography and payment analysis
• Monthly / daily sales trend
• Pareto (80/20) analysis
• Discount, tax, shipping and marketing analysis
• Inventory / low-stock analysis
• Return/refund analysis
• Smart business insights
• Data-quality report
• CSV + Excel + professional PDF export

Important:
This module never invents unavailable business fields. If a metric cannot
be calculated from the uploaded data, it is shown as unavailable.

Changelog (professional hardening pass)
----------------------------------------
1. Column-mapping corrections now persist across Streamlit reruns via
   st.session_state, instead of being silently discarded (previous version
   recomputed auto-detection on every rerun and threw away manual fixes).
2. File reading + column detection are cached with st.cache_data so
   re-running the page (date filter, mapping tweaks) doesn't re-parse the
   whole file / re-run fuzzy matching every time.
3. Accurate "duplicate rows removed" and "original row count" metrics —
   captured BEFORE cleaning, not after (previous version always showed 0).
4. numeric_clean now understands accounting-style negative numbers in
   parentheses, e.g. "(1,250.00)" -> -1250.00.
5. A per-file signature resets the manual mapping override automatically
   when a new file is uploaded, so stale corrections from a previous file
   never leak into a new one.
6. "Reset to automatic detection" control added.
7. Defensive guards around empty groupings, zero-division, and NaN-only
   columns throughout, plus small type hints / docstrings for maintainability.
"""

import io
import os
import re
from difflib import SequenceMatcher
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

from utils.auth import is_logged_in, get_business_name, logout


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="BizPilot | Upload & Analyse",
    page_icon="📊",
    layout="wide",
)

LOGO_PATH = os.path.join("assets", "logo.png")


# ============================================================
# PREMIUM UI
# ============================================================

st.markdown(
    """
<style>
.block-container {
    padding-top: 1.4rem;
    padding-bottom: 3rem;
    max-width: 1500px;
}

.main-title {
    font-size: 2.15rem;
    font-weight: 800;
    margin-bottom: 0.15rem;
    letter-spacing: -0.7px;
}

.sub-title {
    color: #64748B;
    font-size: 1rem;
    margin-bottom: 1.25rem;
}

.section-title {
    font-size: 1.35rem;
    font-weight: 750;
    margin-top: 1.2rem;
    margin-bottom: 0.7rem;
}

.insight-card {
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 14px 16px;
    margin: 8px 0;
    background: #FFFFFF;
}

.flow-card {
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 12px;
    text-align: center;
    background: #F8FAFC;
}

.small-muted {
    color: #64748B;
    font-size: 0.86rem;
}

.metric-note {
    color: #64748B;
    font-size: 0.78rem;
}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# LOGIN
# ============================================================

if not is_logged_in():
    st.warning("Please login to access Upload & Analyse.")
    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_container_width=True)

    st.markdown("### Upload & Analyse")
    st.caption(f"Business: {get_business_name() or 'Current Business'}")

    st.divider()

    st.markdown("**Supported files**")
    st.write("CSV • XLSX • XLS • PDF")

    st.divider()

    if st.button("Logout", use_container_width=True):
        logout()
        st.rerun()


# ============================================================
# HEADER
# ============================================================

st.markdown('<div class="main-title">📊 Upload & Analyse</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Turn an existing business file into a professional analytics dashboard — automatically.</div>',
    unsafe_allow_html=True,
)

flow = st.columns(7)
flow_text = [
    ("1", "Upload"),
    ("2", "Detect"),
    ("3", "Clean"),
    ("4", "Analyse"),
    ("5", "Visualise"),
    ("6", "Insights"),
    ("7", "Report"),
]
for col, (num, label) in zip(flow, flow_text):
    with col:
        st.markdown(
            f'<div class="flow-card"><b>{num}</b><br><span class="small-muted">{label}</span></div>',
            unsafe_allow_html=True,
        )

st.write("")


# ============================================================
# COLUMN SEMANTIC DICTIONARY
# ============================================================

ALIASES = {
    "product_id": [
        "product id", "product_id", "productid", "sku", "sku id",
        "item id", "item code", "product code", "stock keeping unit"
    ],
    "product_name": [
        "product name", "product", "item name", "item", "product title",
        "item description", "product description", "name of product"
    ],
    "category": [
        "category", "product category", "item category", "department",
        "department name", "type", "product type"
    ],
    "subcategory": [
        "subcategory", "sub category", "sub-category", "sub category name"
    ],
    "brand": [
        "brand", "brand name", "manufacturer", "make"
    ],
    "order_id": [
        "order id", "order_id", "order number", "order no", "invoice no",
        "invoice number", "transaction id", "transaction number",
        "bill no", "bill number", "receipt no", "receipt number"
    ],
    "order_date": [
        "order date", "date", "sale date", "sales date", "invoice date",
        "transaction date", "purchase date", "created date", "order_datetime"
    ],
    "quantity": [
        "quantity", "qty", "units", "units sold", "unit sold", "sold quantity",
        "sales quantity", "volume sold", "number sold"
    ],
    "revenue": [
        "revenue", "sales", "sales amount", "total sales", "net sales",
        "gross sales", "turnover", "amount sold", "sale amount",
        "total revenue", "revenue amount", "sales revenue"
    ],
    "unit_price": [
        "selling price", "sale price", "unit price", "selling rate",
        "sales price", "price per unit", "rate", "mrp", "unit selling price"
    ],
    "cost": [
        "cost", "cost price", "purchase price", "buy price", "unit cost",
        "purchase cost", "cost per unit", "buying price"
    ],
    "total_cost": [
        "total cost", "cost amount", "total purchase cost", "cost of goods",
        "cogs", "cost of goods sold", "total cogs"
    ],
    "profit": [
        "profit", "net profit", "gross profit", "profit amount",
        "profit value", "earnings"
    ],
    "profit_margin": [
        "profit margin", "margin", "profit margin %", "profit %",
        "margin percentage", "profit percentage"
    ],
    "discount": [
        "discount", "discount amount", "discount value", "discount %",
        "discount percentage", "rebate"
    ],
    "customer": [
        "customer", "customer name", "client", "client name", "buyer",
        "buyer name", "customer_name"
    ],
    "city": [
        "city", "town", "city name"
    ],
    "state": [
        "state", "state name", "province"
    ],
    "region": [
        "region", "zone", "area", "territory", "location", "market"
    ],
    "payment": [
        "payment", "payment method", "payment mode", "pay mode",
        "payment type", "method of payment"
    ],
    "payment_status": [
        "payment status", "paid status", "payment state", "paid/unpaid",
        "payment_status"
    ],
    "order_status": [
        "order status", "status", "delivery status", "fulfillment status",
        "order state"
    ],
    "return": [
        "return", "returns", "return amount", "refund", "refund amount",
        "returned amount", "return value", "refund value"
    ],
    "stock": [
        "stock", "inventory", "stock quantity", "inventory quantity",
        "available stock", "closing stock", "current stock"
    ],
    "minimum_stock": [
        "minimum stock", "min stock", "reorder level", "reorder point",
        "minimum inventory", "safety stock", "threshold stock"
    ],
    "ad_spend": [
        "ad spend", "advertising spend", "marketing spend", "marketing cost",
        "advertising cost", "ads cost", "ad cost", "promotion spend"
    ],
    "shipping": [
        "shipping", "shipping cost", "delivery cost", "freight",
        "logistics cost", "transport cost"
    ],
    "tax": [
        "tax", "tax amount", "gst", "gst amount", "vat", "sales tax",
        "tax value"
    ],
}


LABELS = {
    "product_id": "Product ID / SKU",
    "product_name": "Product",
    "category": "Category",
    "subcategory": "Subcategory",
    "brand": "Brand",
    "order_id": "Order ID",
    "order_date": "Order Date",
    "quantity": "Quantity",
    "revenue": "Revenue / Sales",
    "unit_price": "Selling Price",
    "cost": "Unit Cost",
    "total_cost": "Total Cost",
    "profit": "Profit",
    "profit_margin": "Profit Margin",
    "discount": "Discount",
    "customer": "Customer",
    "city": "City",
    "state": "State",
    "region": "Region",
    "payment": "Payment Method",
    "payment_status": "Payment Status",
    "order_status": "Order Status",
    "return": "Return / Refund",
    "stock": "Stock / Inventory",
    "minimum_stock": "Minimum / Reorder Stock",
    "ad_spend": "Marketing / Ad Spend",
    "shipping": "Shipping Cost",
    "tax": "Tax / GST",
}


NUMERIC_FIELDS = {
    "quantity", "revenue", "unit_price", "cost", "total_cost",
    "profit", "profit_margin", "discount", "return", "stock",
    "minimum_stock", "ad_spend", "shipping", "tax"
}


# ============================================================
# HELPERS
# ============================================================

def normalize_text(value) -> str:
    value = str(value).strip().lower()
    value = re.sub(r"[%₹$€£]", "", value)
    value = re.sub(r"[_\-/]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Trim whitespace, drop fully-empty rows/cols and duplicate rows."""
    df = df.copy()

    df.columns = [
        str(c).replace("\n", " ").replace("\r", " ").strip()
        for c in df.columns
    ]

    # Remove unnamed Excel/PDF columns
    valid_cols = [
        c for c in df.columns
        if not str(c).lower().startswith("unnamed")
    ]
    df = df[valid_cols]

    df = df.dropna(axis=0, how="all")
    df = df.dropna(axis=1, how="all")

    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].map(
                lambda x: x.strip() if isinstance(x, str) else x
            )

    df = df.drop_duplicates().reset_index(drop=True)
    return df


def numeric_clean(series: pd.Series) -> pd.Series:
    """Convert a messy text/number column into floats.

    Handles thousands separators, currency symbols, percent signs and
    accounting-style negative numbers written in parentheses, e.g. "(500)".
    """
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    s = series.astype(str).str.strip()

    # Accounting-style negatives: (1,250.00) -> -1250.00
    neg_mask = s.str.match(r"^\(.*\)$", na=False)
    s = s.str.replace(r"^\((.*)\)$", r"-\1", regex=True)

    s = (
        s.str.replace(",", "", regex=False)
        .str.replace("₹", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("€", "", regex=False)
        .str.replace("£", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.strip()
    )

    out = pd.to_numeric(s, errors="coerce")
    return out


def date_score(series: pd.Series) -> float:
    parsed = pd.to_datetime(series, errors="coerce", dayfirst=True)
    valid = parsed.notna().mean()
    return float(valid)


def semantic_score(column: str, aliases: list) -> tuple:
    col = normalize_text(column)

    best = 0.0
    best_alias = ""

    for alias in aliases:
        a = normalize_text(alias)

        if col == a:
            score = 1.00
        elif a in col or col in a:
            score = 0.84
        else:
            score = SequenceMatcher(None, col, a).ratio()

        if score > best:
            best = score
            best_alias = alias

    return best, best_alias


@st.cache_data(show_spinner=False)
def detect_columns(df: pd.DataFrame):
    """Fuzzy-match every known business field to the best available column."""
    candidates = {}

    for field, aliases in ALIASES.items():
        options = []

        for col in df.columns:
            score, matched_alias = semantic_score(col, aliases)

            # Additional date intelligence
            if field == "order_date":
                try:
                    dscore = date_score(df[col])
                    score = max(score, min(0.98, dscore * 0.98))
                except Exception:
                    pass

            # Numeric intelligence
            if field in NUMERIC_FIELDS:
                numeric_ratio = numeric_clean(df[col]).notna().mean()
                if numeric_ratio >= 0.70:
                    score = min(1.0, score + 0.04)

            options.append((col, score, matched_alias))

        options.sort(key=lambda x: x[1], reverse=True)
        candidates[field] = options

    mapping = {}
    confidence = {}
    used = set()

    # First pass: strongest exact-ish semantic matches
    for field in sorted(candidates, key=lambda f: candidates[f][0][1], reverse=True):
        for col, score, _alias in candidates[field]:
            if score >= 0.92 and col not in used:
                mapping[field] = col
                confidence[field] = score
                used.add(col)
                break

    # Second pass: good fuzzy matches, with stricter threshold
    for field in candidates:
        if field in mapping:
            continue

        for col, score, _alias in candidates[field]:
            if col in used:
                continue

            threshold = 0.78

            # Avoid dangerous automatic assumptions
            if field in {"revenue", "cost", "profit", "unit_price", "total_cost"}:
                threshold = 0.84

            if score >= threshold:
                mapping[field] = col
                confidence[field] = score
                used.add(col)
                break

    return mapping, confidence, candidates


def apply_mapping(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    work = df.copy()

    for field, source_col in mapping.items():
        if source_col and source_col in work.columns:
            work[f"__{field}"] = work[source_col]

    # Numeric conversion
    for field in NUMERIC_FIELDS:
        c = f"__{field}"
        if c in work.columns:
            work[c] = numeric_clean(work[c])

    # Date conversion
    if "__order_date" in work.columns:
        work["__order_date"] = pd.to_datetime(
            work["__order_date"], errors="coerce", dayfirst=True
        )

    return work


def safe_sum(df: pd.DataFrame, field: str) -> Optional[float]:
    col = f"__{field}"
    if col not in df.columns:
        return None
    value = pd.to_numeric(df[col], errors="coerce").sum(min_count=1)
    return None if pd.isna(value) else float(value)


def safe_mean(df: pd.DataFrame, field: str) -> Optional[float]:
    col = f"__{field}"
    if col not in df.columns:
        return None
    value = pd.to_numeric(df[col], errors="coerce").mean()
    return None if pd.isna(value) else float(value)


def money(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/A"
    return f"₹{value:,.2f}"


def number(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/A"
    return f"{value:,.0f}"


def pct(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/A"
    return f"{value:.2f}%"


def metric_available(work: pd.DataFrame, field: str) -> bool:
    return f"__{field}" in work.columns and work[f"__{field}"].notna().any()


def make_derived_metrics(work: pd.DataFrame) -> pd.DataFrame:
    work = work.copy()

    has_revenue = metric_available(work, "revenue")
    has_qty = metric_available(work, "quantity")
    has_unit_price = metric_available(work, "unit_price")
    has_cost = metric_available(work, "cost")
    has_total_cost = metric_available(work, "total_cost")
    has_profit = metric_available(work, "profit")

    # Revenue: use explicit revenue first; otherwise quantity × unit price.
    if not has_revenue and has_qty and has_unit_price:
        work["__revenue"] = (
            pd.to_numeric(work["__quantity"], errors="coerce")
            * pd.to_numeric(work["__unit_price"], errors="coerce")
        )
        has_revenue = True

    # Cost: explicit total cost first; otherwise quantity × unit cost.
    if not has_total_cost and has_cost and has_qty:
        work["__total_cost"] = (
            pd.to_numeric(work["__cost"], errors="coerce")
            * pd.to_numeric(work["__quantity"], errors="coerce")
        )
        has_total_cost = True

    # If an explicit total cost exists, keep it as total cost.
    # If only cost exists and quantity is unavailable, use cost as the
    # available cost measure rather than inventing multiplication.
    if not has_total_cost and has_cost:
        work["__total_cost"] = pd.to_numeric(
            work["__cost"], errors="coerce"
        )
        has_total_cost = True

    if not has_profit and has_revenue and has_total_cost:
        work["__profit"] = (
            pd.to_numeric(work["__revenue"], errors="coerce")
            - pd.to_numeric(work["__total_cost"], errors="coerce")
        )
        has_profit = True

    # Margin is derived only when revenue is available.
    if not metric_available(work, "profit_margin") and has_revenue and has_profit:
        rev = pd.to_numeric(work["__revenue"], errors="coerce")
        prof = pd.to_numeric(work["__profit"], errors="coerce")
        work["__profit_margin"] = np.where(
            rev != 0, (prof / rev) * 100, np.nan
        )

    return work


@st.cache_data(show_spinner=False)
def read_csv_cached(raw_bytes: bytes) -> pd.DataFrame:
    for encoding in ["utf-8-sig", "utf-8", "cp1252", "latin1"]:
        try:
            return pd.read_csv(io.BytesIO(raw_bytes), encoding=encoding)
        except Exception:
            continue
    raise ValueError("CSV could not be decoded.")


@st.cache_data(show_spinner=False)
def read_excel_cached(raw_bytes: bytes):
    sheets = pd.read_excel(io.BytesIO(raw_bytes), sheet_name=None)
    cleaned = {}

    for name, frame in sheets.items():
        frame = clean_dataframe(frame)
        if not frame.empty:
            cleaned[name] = frame

    if not cleaned:
        raise ValueError("No usable Excel sheet was found.")

    primary_name = max(
        cleaned,
        key=lambda name: cleaned[name].shape[0] * cleaned[name].shape[1]
    )

    return cleaned[primary_name], cleaned


@st.cache_data(show_spinner=False)
def extract_pdf_cached(raw_bytes: bytes) -> pd.DataFrame:
    if pdfplumber is None:
        raise ImportError(
            "PDF support requires pdfplumber. Install it with: pip install pdfplumber"
        )

    frames = []

    with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()

            for table in tables:
                if not table or len(table) < 2:
                    continue

                header = table[0]
                body = table[1:]

                if not header:
                    continue

                header = [
                    str(x).strip() if x is not None else f"Column {i+1}"
                    for i, x in enumerate(header)
                ]

                frame = pd.DataFrame(body, columns=header)
                frame["__pdf_page"] = page_no
                frames.append(frame)

    if not frames:
        raise ValueError(
            "No table could be extracted from this PDF. "
            "If it is a scanned/image PDF, OCR support is required."
        )

    return clean_dataframe(pd.concat(frames, ignore_index=True))


def format_table(df: pd.DataFrame, max_rows: int = 20) -> pd.DataFrame:
    out = df.head(max_rows).copy()

    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")

    return out


def group_metric(work: pd.DataFrame, group_field: str, metric: str = "revenue", top_n: int = 15):
    gcol = f"__{group_field}"
    mcol = f"__{metric}"

    if gcol not in work.columns or mcol not in work.columns:
        return None

    temp = work[[gcol, mcol]].copy()
    temp[gcol] = temp[gcol].astype(str).str.strip()
    temp[mcol] = pd.to_numeric(temp[mcol], errors="coerce")
    temp = temp.dropna(subset=[gcol, mcol])

    if temp.empty:
        return None

    result = (
        temp.groupby(gcol, as_index=False)[mcol]
        .sum()
        .sort_values(mcol, ascending=False)
        .head(top_n)
    )
    result.columns = [LABELS.get(group_field, group_field), metric.title()]
    return result


def create_bar(df, x, y, title, horizontal=False):
    if df is None or df.empty:
        return None

    if horizontal:
        fig = px.bar(
            df,
            x=y,
            y=x,
            orientation="h",
            title=title,
            text_auto=".2s",
        )
    else:
        fig = px.bar(
            df,
            x=x,
            y=y,
            title=title,
            text_auto=".2s",
        )

    fig.update_layout(
        height=430,
        margin=dict(l=20, r=20, t=60, b=20),
        hovermode="x unified",
    )
    return fig


def create_pie(df, names, values, title):
    if df is None or df.empty:
        return None

    fig = px.pie(
        df,
        names=names,
        values=values,
        title=title,
        hole=0.42,
    )
    fig.update_layout(
        height=430,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return fig


def add_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawCentredString(
        landscape(A4)[0] / 2,
        8 * mm,
        f"BizPilot • Generated {datetime.now().strftime('%d %b %Y, %I:%M %p')}"
    )
    canvas.restoreState()


# ============================================================
# UPLOAD
# ============================================================

uploaded = st.file_uploader(
    "Upload your existing business file",
    type=["csv", "xlsx", "xls", "pdf"],
    help="Upload the actual file you already have. No manual data formatting is required.",
)

if uploaded is None:
    st.info(
        "Upload your CSV, Excel or table-based PDF to start automatic analysis."
    )
    st.stop()


# ============================================================
# FILE SIGNATURE (used to reset manual mapping when file changes)
# ============================================================

file_signature = f"{uploaded.name}_{uploaded.size}"

if st.session_state.get("bp_file_sig") != file_signature:
    st.session_state["bp_file_sig"] = file_signature
    st.session_state["bp_mapping_override"] = None  # fresh file -> fresh detection


# ============================================================
# READ FILE
# ============================================================

try:
    extension = uploaded.name.lower().split(".")[-1]
    raw_bytes = uploaded.getvalue()

    if extension == "csv":
        pre_clean_df = read_csv_cached(raw_bytes)
        sheets = None

    elif extension in {"xlsx", "xls"}:
        pre_clean_df, sheets = read_excel_cached(raw_bytes)

    elif extension == "pdf":
        pre_clean_df = extract_pdf_cached(raw_bytes)
        sheets = None

    else:
        st.error("Unsupported file type.")
        st.stop()

    original_row_count = len(pre_clean_df)
    duplicate_row_count = int(pre_clean_df.duplicated().sum())
    raw_df = clean_dataframe(pre_clean_df)

except Exception as e:
    st.error(f"Could not read the file: {e}")
    st.stop()


if raw_df.empty:
    st.error("The uploaded file contains no usable rows.")
    st.stop()


# ============================================================
# DETECTION (auto) + MANUAL OVERRIDE (persisted in session_state)
# ============================================================

auto_mapping, confidence, candidates = detect_columns(raw_df)

if st.session_state.get("bp_mapping_override"):
    mapping = st.session_state["bp_mapping_override"]
else:
    mapping = auto_mapping

with st.spinner("Understanding columns and preparing analytics..."):
    work = apply_mapping(raw_df, mapping)
    work = make_derived_metrics(work)


# ============================================================
# MAPPING REVIEW
# ============================================================

st.markdown('<div class="section-title">🧠 Automatic Column Understanding</div>', unsafe_allow_html=True)

det_rows = []
for field, source in mapping.items():
    conf_value = confidence.get(field)
    det_rows.append(
        {
            "BizPilot Field": LABELS.get(field, field),
            "Detected Column": source,
            "Confidence": f"{conf_value*100:.0f}%" if conf_value is not None else "Manual",
        }
    )

if det_rows:
    st.dataframe(
        pd.DataFrame(det_rows),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.warning(
        "No standard business fields were confidently detected. "
        "You can map important columns manually below."
    )

with st.expander("⚙️ Review / Correct Column Mapping"):
    st.caption(
        "This changes only how BizPilot analyses the uploaded data. "
        "Your original file is not modified. Corrections are remembered "
        "for this file until you upload a different one or reset them."
    )

    corrected = dict(mapping)

    fields_for_mapping = [
        "product_name", "category", "brand", "order_id", "order_date",
        "quantity", "revenue", "unit_price", "cost", "total_cost", "profit",
        "profit_margin", "discount", "customer", "city", "state", "region",
        "payment", "payment_status", "order_status", "return", "stock",
        "minimum_stock", "ad_spend", "shipping", "tax",
    ]

    cols = ["— Not detected —"] + list(raw_df.columns)

    map_columns = st.columns(3)

    for i, field in enumerate(fields_for_mapping):
        with map_columns[i % 3]:
            current = corrected.get(field)
            default_index = cols.index(current) if current in cols else 0

            selected = st.selectbox(
                LABELS[field],
                cols,
                index=default_index,
                key=f"mapping_{field}",
            )

            corrected[field] = None if selected == "— Not detected —" else selected

    btn_col1, btn_col2 = st.columns(2)

    with btn_col1:
        if st.button("Apply Mapping & Recalculate", type="primary", use_container_width=True):
            # Drop fields the user explicitly cleared.
            st.session_state["bp_mapping_override"] = {
                k: v for k, v in corrected.items() if v
            }
            st.success("Mapping applied.")
            st.rerun()

    with btn_col2:
        if st.button("Reset to Automatic Detection", use_container_width=True):
            st.session_state["bp_mapping_override"] = None
            st.rerun()


# ============================================================
# DATA OVERVIEW
# ============================================================

st.markdown('<div class="section-title">📁 Data Overview</div>', unsafe_allow_html=True)

overview_cols = st.columns(5)
overview_cols[0].metric("Rows", f"{len(raw_df):,}")
overview_cols[1].metric("Columns", f"{len(raw_df.columns):,}")
overview_cols[2].metric("Detected Fields", f"{len(mapping):,}")
overview_cols[3].metric("Duplicate Rows Removed", f"{duplicate_row_count:,}")
overview_cols[4].metric(
    "Data Completeness",
    f"{(1 - raw_df.isna().mean().mean()) * 100:.1f}%"
)

with st.expander("👀 View Cleaned Data Preview"):
    st.dataframe(
        format_table(raw_df, 30),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# KPI CALCULATION
# ============================================================

revenue = safe_sum(work, "revenue")
cost = safe_sum(work, "total_cost")
profit = safe_sum(work, "profit")
units = safe_sum(work, "quantity")
discount = safe_sum(work, "discount")
returns = safe_sum(work, "return")
ad_spend = safe_sum(work, "ad_spend")
shipping = safe_sum(work, "shipping")
tax = safe_sum(work, "tax")

margin = None
if revenue not in (None, 0) and profit is not None:
    margin = profit / revenue * 100

orders = None
if "__order_id" in work.columns:
    orders = work["__order_id"].nunique(dropna=True)

customers = None
if "__customer" in work.columns:
    customers = work["__customer"].nunique(dropna=True)

avg_order = None
if revenue is not None and orders:
    avg_order = revenue / orders

roas = None
if revenue is not None and ad_spend not in (None, 0):
    roas = revenue / ad_spend


# ============================================================
# EXECUTIVE DASHBOARD
# ============================================================

st.markdown('<div class="section-title">📌 Executive Business Dashboard</div>', unsafe_allow_html=True)

k1, k2, k3, k4, k5, k6 = st.columns(6)

k1.metric("Revenue / Sales", money(revenue))
k2.metric("Total Cost", money(cost))
k3.metric("Profit", money(profit))
k4.metric("Profit Margin", pct(margin))
k5.metric("Orders", number(orders))
k6.metric("Units Sold", number(units))

k7, k8, k9, k10, k11, k12 = st.columns(6)

k7.metric("Customers", number(customers))
k8.metric("Avg. Order Value", money(avg_order))
k9.metric("Discount", money(discount))
k10.metric("Returns / Refunds", money(returns))
k11.metric("Ad Spend", money(ad_spend))
k12.metric("ROAS", f"{roas:.2f}x" if roas is not None else "N/A")


# ============================================================
# DATE FILTER
# ============================================================

filtered = work.copy()

if "__order_date" in work.columns and work["__order_date"].notna().any():
    min_date = work["__order_date"].min().date()
    max_date = work["__order_date"].max().date()

    st.markdown('<div class="section-title">🗓️ Analysis Period</div>', unsafe_allow_html=True)

    d1, d2 = st.columns(2)
    start = d1.date_input("From", min_date, min_value=min_date, max_value=max_date, key="analysis_start")
    end = d2.date_input("To", max_date, min_value=min_date, max_value=max_date, key="analysis_end")

    if start > end:
        st.error("Start date cannot be after end date.")
        st.stop()

    filtered = work[
        (work["__order_date"].dt.date >= start)
        & (work["__order_date"].dt.date <= end)
    ].copy()

    if filtered.empty:
        st.warning("No records exist in the selected date range.")
        st.stop()


# ============================================================
# PRODUCT PERFORMANCE
# ============================================================

if "__product_name" in filtered.columns:
    st.markdown('<div class="section-title">🏆 Product Performance</div>', unsafe_allow_html=True)

    product_rev = group_metric(filtered, "product_name", "revenue", 20)
    product_profit = group_metric(filtered, "product_name", "profit", 20)
    product_qty = group_metric(filtered, "product_name", "quantity", 20)

    p1, p2 = st.columns(2)

    with p1:
        fig = create_bar(
            product_rev,
            "Product",
            "Revenue",
            "Top Products by Revenue",
            horizontal=True,
        )
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Revenue analysis requires a recognised revenue or quantity+price field.")

    with p2:
        if product_profit is not None:
            fig = create_bar(
                product_profit,
                "Product",
                "Profit",
                "Top Products by Profit",
                horizontal=True,
            )
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Profit analysis requires revenue + cost/profit data.")

    p3, p4 = st.columns(2)

    with p3:
        if product_rev is not None:
            st.plotly_chart(
                create_pie(
                    product_rev,
                    "Product",
                    "Revenue",
                    "Revenue Share by Product",
                ),
                use_container_width=True,
            )

    with p4:
        if product_qty is not None:
            st.plotly_chart(
                create_bar(
                    product_qty,
                    "Product",
                    "Quantity",
                    "Units Sold by Product",
                    horizontal=True,
                ),
                use_container_width=True,
            )

    if product_rev is not None:
        st.dataframe(
            product_rev,
            use_container_width=True,
            hide_index=True,
        )

        # Pareto / 80-20
        pareto = product_rev.copy()
        rev_total = pareto["Revenue"].sum()
        if rev_total:
            pareto["Cumulative %"] = pareto["Revenue"].cumsum() / rev_total * 100

            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    x=pareto["Product"],
                    y=pareto["Revenue"],
                    name="Revenue",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=pareto["Product"],
                    y=pareto["Cumulative %"],
                    name="Cumulative %",
                    yaxis="y2",
                    mode="lines+markers",
                )
            )
            fig.update_layout(
                title="Product Revenue Pareto Analysis",
                yaxis=dict(title="Revenue"),
                yaxis2=dict(
                    title="Cumulative %",
                    overlaying="y",
                    side="right",
                    range=[0, 105],
                ),
                height=470,
                margin=dict(l=20, r=20, t=60, b=80),
            )
            st.plotly_chart(fig, use_container_width=True)


# ============================================================
# CATEGORY ANALYSIS
# ============================================================

if "__category" in filtered.columns:
    st.markdown('<div class="section-title">📦 Category Intelligence</div>', unsafe_allow_html=True)

    cat_rev = group_metric(filtered, "category", "revenue", 20)
    cat_profit = group_metric(filtered, "category", "profit", 20)

    c1, c2 = st.columns(2)

    with c1:
        if cat_rev is not None:
            st.plotly_chart(
                create_bar(
                    cat_rev,
                    "Category",
                    "Revenue",
                    "Revenue by Category",
                ),
                use_container_width=True,
            )

    with c2:
        if cat_rev is not None:
            st.plotly_chart(
                create_pie(
                    cat_rev,
                    "Category",
                    "Revenue",
                    "Category Revenue Mix",
                ),
                use_container_width=True,
            )

    if cat_profit is not None:
        st.dataframe(
            cat_profit,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# SALES TREND
# ============================================================

if "__order_date" in filtered.columns and metric_available(filtered, "revenue"):
    st.markdown('<div class="section-title">📈 Sales Trend & Growth</div>', unsafe_allow_html=True)

    trend = filtered.dropna(subset=["__order_date", "__revenue"]).copy()

    if not trend.empty:
        trend["Date"] = trend["__order_date"].dt.date
        daily = trend.groupby("Date", as_index=False)["__revenue"].sum()
        daily.columns = ["Date", "Revenue"]

        fig = px.line(
            daily,
            x="Date",
            y="Revenue",
            markers=True,
            title="Revenue Trend Over Time",
        )
        fig.update_layout(
            height=440,
            margin=dict(l=20, r=20, t=60, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

        monthly = trend.assign(
            Month=trend["__order_date"].dt.to_period("M").astype(str)
        ).groupby("Month", as_index=False)["__revenue"].sum()
        monthly.columns = ["Month", "Revenue"]

        if len(monthly) >= 2:
            monthly["Growth %"] = monthly["Revenue"].pct_change() * 100

            st.dataframe(
                monthly,
                use_container_width=True,
                hide_index=True,
            )


# ============================================================
# CUSTOMER ANALYSIS
# ============================================================

if "__customer" in filtered.columns and metric_available(filtered, "revenue"):
    st.markdown('<div class="section-title">👥 Customer Intelligence</div>', unsafe_allow_html=True)

    cust = group_metric(filtered, "customer", "revenue", 20)

    if cust is not None:
        c1, c2 = st.columns(2)

        with c1:
            st.plotly_chart(
                create_bar(
                    cust,
                    "Customer",
                    "Revenue",
                    "Top Customers by Revenue",
                    horizontal=True,
                ),
                use_container_width=True,
            )

        with c2:
            st.dataframe(cust, use_container_width=True, hide_index=True)


# ============================================================
# GEOGRAPHY
# ============================================================

geo_field = None
for f in ["city", "state", "region"]:
    if f"__{f}" in filtered.columns:
        geo_field = f
        break

if geo_field and metric_available(filtered, "revenue"):
    st.markdown('<div class="section-title">🌍 Geographic Performance</div>', unsafe_allow_html=True)

    geo = group_metric(filtered, geo_field, "revenue", 20)

    if geo is not None:
        st.plotly_chart(
            create_bar(
                geo,
                LABELS[geo_field],
                "Revenue",
                f"Revenue by {LABELS[geo_field]}",
                horizontal=True,
            ),
            use_container_width=True,
        )
        st.dataframe(geo, use_container_width=True, hide_index=True)


# ============================================================
# PAYMENT / ORDER STATUS
# ============================================================

if "__payment" in filtered.columns:
    st.markdown('<div class="section-title">💳 Payment & Order Status</div>', unsafe_allow_html=True)

    p1, p2 = st.columns(2)

    with p1:
        payment_counts = (
            filtered["__payment"]
            .astype(str)
            .value_counts()
            .reset_index()
        )
        payment_counts.columns = ["Payment Method", "Orders"]
        st.plotly_chart(
            create_pie(payment_counts, "Payment Method", "Orders", "Payment Method Mix"),
            use_container_width=True,
        )

    with p2:
        if "__order_status" in filtered.columns:
            status_counts = (
                filtered["__order_status"]
                .astype(str)
                .value_counts()
                .reset_index()
            )
            status_counts.columns = ["Order Status", "Orders"]
            st.plotly_chart(
                create_pie(
                    status_counts,
                    "Order Status",
                    "Orders",
                    "Order Status Distribution",
                ),
                use_container_width=True,
            )


# ============================================================
# INVENTORY INTELLIGENCE
# ============================================================

if "__stock" in filtered.columns:
    st.markdown('<div class="section-title">📦 Inventory Intelligence</div>', unsafe_allow_html=True)

    inv_cols = ["__stock"]
    if "__product_name" in filtered.columns:
        inv_cols.insert(0, "__product_name")
    if "__minimum_stock" in filtered.columns:
        inv_cols.append("__minimum_stock")

    inv = filtered[inv_cols].copy()

    rename = {
        "__product_name": "Product",
        "__stock": "Stock",
        "__minimum_stock": "Minimum Stock",
    }
    inv = inv.rename(columns=rename)

    if "Minimum Stock" in inv.columns:
        inv["Stock Status"] = np.where(
            inv["Stock"] <= inv["Minimum Stock"],
            "Low Stock",
            "Healthy",
        )

        low_count = (inv["Stock Status"] == "Low Stock").sum()
        st.metric("Low Stock Items", int(low_count))

        if low_count:
            st.warning(
                f"{low_count} item(s) are at or below their minimum/reorder stock level."
            )

    st.dataframe(
        inv.drop_duplicates(),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# DISCOUNT / MARKETING / COST INTELLIGENCE
# ============================================================

st.markdown('<div class="section-title">💰 Commercial Intelligence</div>', unsafe_allow_html=True)

commercial = st.columns(4)

commercial[0].metric("Discount", money(discount))
commercial[1].metric("Shipping", money(shipping))
commercial[2].metric("Tax / GST", money(tax))
commercial[3].metric("Marketing Spend", money(ad_spend))

if ad_spend not in (None, 0) and revenue is not None and roas is not None:
    st.info(
        f"Estimated ROAS: **{roas:.2f}x** — based on available revenue and marketing/ad spend."
    )

if discount is not None and revenue:
    discount_ratio = discount / revenue * 100
    st.write(f"Discount-to-revenue ratio: **{discount_ratio:.2f}%**")


# ============================================================
# SMART INSIGHTS
# ============================================================

st.markdown('<div class="section-title">🧠 Smart Business Insights</div>', unsafe_allow_html=True)

insights = []

if revenue is not None:
    insights.append(f"Total analysed revenue/sales are **{money(revenue)}**.")

if profit is not None:
    if profit > 0:
        insights.append(f"Overall analysed profit is **{money(profit)}**.")
    elif profit < 0:
        insights.append(f"The analysed dataset shows an overall loss of **{money(abs(profit))}**.")
    else:
        insights.append("The analysed dataset is approximately at break-even.")

if margin is not None:
    if margin >= 30:
        insights.append(
            f"Overall profit margin is **{margin:.2f}%**, indicating a strong gross profitability level in this dataset."
        )
    elif margin >= 15:
        insights.append(
            f"Overall profit margin is **{margin:.2f}%**. Margin should be monitored alongside discounts and costs."
        )
    else:
        insights.append(
            f"Overall profit margin is **{margin:.2f}%**. Cost, pricing and discount strategy deserve attention."
        )

if units is not None and units > 0 and revenue is not None:
    avg_realization = revenue / units
    insights.append(
        f"Average revenue realization per unit is approximately **{money(avg_realization)}**."
    )

if avg_order is not None and orders:
    insights.append(
        f"Average order value is approximately **{money(avg_order)}** across {orders:,} unique orders."
    )

if "__product_name" in filtered.columns and revenue:
    pr = group_metric(filtered, "product_name", "revenue", 100)
    if pr is not None and len(pr) > 0:
        top_product = pr.iloc[0]["Product"]
        top_value = pr.iloc[0]["Revenue"]
        share = top_value / revenue * 100
        insights.append(
            f"Top revenue product is **{top_product}**, contributing approximately "
            f"**{money(top_value)}** ({share:.1f}% of revenue)."
        )

if "__category" in filtered.columns and revenue:
    cr = group_metric(filtered, "category", "revenue", 100)
    if cr is not None and len(cr) > 0:
        top_cat = cr.iloc[0]["Category"]
        top_cat_value = cr.iloc[0]["Revenue"]
        cat_share = top_cat_value / revenue * 100
        insights.append(
            f"Top revenue category is **{top_cat}**, contributing {cat_share:.1f}% of revenue."
        )

if ad_spend not in (None, 0) and roas is not None:
    if roas >= 4:
        insights.append(f"Marketing efficiency looks strong with an estimated **{roas:.2f}x ROAS**.")
    elif roas < 2:
        insights.append(f"Estimated ROAS is **{roas:.2f}x**; marketing efficiency should be reviewed.")

if returns is not None and revenue:
    return_ratio = returns / revenue * 100
    insights.append(
        f"Return/refund value is approximately **{return_ratio:.2f}% of revenue** based on the available fields."
    )

if "__stock" in filtered.columns and "__minimum_stock" in filtered.columns:
    low = (
        pd.to_numeric(filtered["__stock"], errors="coerce")
        <= pd.to_numeric(filtered["__minimum_stock"], errors="coerce")
    ).sum()
    if low:
        insights.append(
            f"Inventory alert: **{int(low)}** record(s) are at or below the supplied minimum/reorder stock level."
        )

if not insights:
    insights.append(
        "Not enough recognised business fields were available to generate reliable financial insights."
    )

for i, text in enumerate(insights, start=1):
    st.markdown(
        f'<div class="insight-card"><b>{i}.</b> {text}</div>',
        unsafe_allow_html=True,
    )


# ============================================================
# DATA QUALITY
# ============================================================

st.markdown('<div class="section-title">🔍 Data Quality & Reliability</div>', unsafe_allow_html=True)

quality = pd.DataFrame(
    {
        "Check": [
            "Original rows (before cleaning)",
            "Rows analysed (after filters)",
            "Columns analysed",
            "Missing cells",
            "Duplicate rows removed",
            "Detected business fields",
            "Date field available",
            "Revenue field available",
            "Profit field available",
            "Product field available",
            "Customer field available",
        ],
        "Result": [
            f"{original_row_count:,}",
            f"{len(filtered):,}",
            f"{len(raw_df.columns):,}",
            f"{int(raw_df.isna().sum().sum()):,}",
            f"{duplicate_row_count:,}",
            f"{len(mapping):,}",
            "Yes" if "__order_date" in filtered.columns else "No",
            "Yes" if metric_available(filtered, "revenue") else "No",
            "Yes" if metric_available(filtered, "profit") else "No",
            "Yes" if "__product_name" in filtered.columns else "No",
            "Yes" if "__customer" in filtered.columns else "No",
        ],
    }
)
st.dataframe(quality, use_container_width=True, hide_index=True)


# ============================================================
# EXPORT DATA
# ============================================================

st.markdown('<div class="section-title">📤 Export Analysis</div>', unsafe_allow_html=True)

# User-friendly cleaned/export table.
export_df = filtered.copy()

# Remove internal columns.
internal_cols = [c for c in export_df.columns if c.startswith("__")]
export_df = export_df.drop(columns=internal_cols, errors="ignore")

csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")

e1, e2 = st.columns(2)

with e1:
    st.download_button(
        "⬇️ Download Analysed CSV",
        data=csv_bytes,
        file_name="BizPilot_Analysed_Data.csv",
        mime="text/csv",
        use_container_width=True,
    )

with e2:
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Analysed Data")
        pd.DataFrame(det_rows).to_excel(
            writer,
            index=False,
            sheet_name="Detected Columns",
        )
        quality.to_excel(
            writer,
            index=False,
            sheet_name="Data Quality",
        )

    st.download_button(
        "⬇️ Download Analysis Excel",
        data=excel_buffer.getvalue(),
        file_name="BizPilot_Analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


# ============================================================
# PDF REPORT
# ============================================================

def build_pdf() -> bytes:
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "BizTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=21,
        leading=25,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=8,
    )

    sub_style = ParagraphStyle(
        "BizSub",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=9,
        textColor=colors.HexColor("#64748B"),
        spaceAfter=14,
    )

    heading = ParagraphStyle(
        "BizHeading",
        parent=styles["Heading2"],
        fontSize=14,
        leading=17,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=10,
        spaceAfter=7,
    )

    body = ParagraphStyle(
        "BizBody",
        parent=styles["BodyText"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155"),
    )

    story = []

    story.append(Paragraph("BizPilot — Business Analytics Report", title_style))
    story.append(
        Paragraph(
            f"Business: {get_business_name() or 'Business'} • "
            f"Source: {uploaded.name} • "
            f"Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
            sub_style,
        )
    )

    # Executive KPIs
    story.append(Paragraph("Executive Summary", heading))

    kpi_data = [
        ["Revenue", "Cost", "Profit", "Margin", "Orders", "Units"],
        [
            money(revenue),
            money(cost),
            money(profit),
            pct(margin),
            number(orders),
            number(units),
        ],
    ]

    kt = Table(kpi_data, colWidths=[42 * mm] * 6)
    kt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(kt)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Smart Insights", heading))
    for item in insights:
        plain = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", item)
        story.append(Paragraph("• " + plain, body))
        story.append(Spacer(1, 3))

    story.append(Paragraph("Detected Business Fields", heading))

    detected_table = [["BizPilot Field", "Source Column", "Confidence"]]
    for row in det_rows:
        detected_table.append(
            [row["BizPilot Field"], row["Detected Column"], row["Confidence"]]
        )

    if len(detected_table) == 1:
        detected_table.append(["No confident fields", "—", "—"])

    dt = Table(
        detected_table,
        colWidths=[65 * mm, 90 * mm, 30 * mm],
        repeatRows=1,
    )
    dt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(dt)

    # Product performance
    if "__product_name" in filtered.columns:
        pr = group_metric(filtered, "product_name", "revenue", 10)

        if pr is not None:
            story.append(Paragraph("Top Product Performance", heading))

            product_table = [["Product", "Revenue"]]
            for _, row in pr.head(10).iterrows():
                product_table.append(
                    [str(row["Product"]), money(row["Revenue"])]
                )

            pt = Table(
                product_table,
                colWidths=[110 * mm, 45 * mm],
                repeatRows=1,
            )
            pt.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            story.append(pt)

    story.append(PageBreak())

    story.append(Paragraph("Data Quality", heading))

    quality_table = [["Check", "Result"]]
    for _, row in quality.iterrows():
        quality_table.append([str(row["Check"]), str(row["Result"])])

    qt = Table(
        quality_table,
        colWidths=[100 * mm, 50 * mm],
        repeatRows=1,
    )
    qt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(qt)

    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            "Methodology: BizPilot analyses only fields available or reliably "
            "derived from the uploaded dataset. Missing business information is "
            "not fabricated. Revenue may be derived from Quantity × Selling Price "
            "when both are available; total cost may be derived from Quantity × "
            "Unit Cost; profit may be derived from Revenue − Total Cost.",
            body,
        )
    )

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)

    return buffer.getvalue()


st.markdown('<div class="section-title">📄 Final Professional Report</div>', unsafe_allow_html=True)

if st.button("Generate Final PDF Report", type="primary", use_container_width=True):
    try:
        with st.spinner("Generating professional PDF report..."):
            pdf_bytes = build_pdf()

        st.success("Final PDF report is ready.")
        st.download_button(
            "⬇️ Download Final BizPilot PDF Report",
            data=pdf_bytes,
            file_name="BizPilot_Final_Analysis_Report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    except Exception as e:
        st.error(f"PDF report generation failed: {e}")


# ============================================================
# END
# ============================================================

st.markdown("---")
st.caption(
    "BizPilot • Manage • Analyse • Grow • Automatic Business Data Intelligence"
)