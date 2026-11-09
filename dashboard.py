"""Founder dashboard. Run locally:  streamlit run dashboard.py

Reads ONLY the aggregate views (see src/queries.py). Plain-English titles, one takeaway
sentence under every chart, because the reader is a founder, not an analyst.
"""
import os

import plotly.express as px
import streamlit as st

# On Streamlit Community Cloud secrets live in st.secrets; locally they come from .env
if "DATABASE_URL" not in os.environ:
    try:
        os.environ["DATABASE_URL"] = st.secrets["DATABASE_URL"]
    except Exception:
        pass

from src import queries  # noqa: E402  (imported after the secret is available)

st.set_page_config(page_title="Founder dashboard", page_icon="🏗️", layout="wide")

MODULE_LABELS = {"bills": "Bills (AP)", "invoices": "Invoices (AR)", "lien_waivers": "Lien waivers",
                 "contracts": "Contracts", "change_orders": "Change orders"}


@st.cache_data(ttl=300, show_spinner="Loading from Postgres...")
def load():
    return {
        "active": queries.weekly_active_companies(),
        "modules": queries.documents_per_module(),
        "pay_weekly": queries.weekly_days_to_pay(),
        "bills": queries.bill_summary().iloc[0],
        "quality": queries.data_quality(),
    }


st.title("🏗️ How is the product being used?")
st.caption("Synthetic data for a construction-software proof of concept. "
           "The most recent week is still in progress, so its numbers are partial.")

try:
    d = load()
except Exception as exc:  # show a friendly message instead of a stack trace
    st.error("Could not load data. Check DATABASE_URL and that the pipeline has been run.")
    st.caption(type(exc).__name__)
    st.stop()

active, modules, pay_weekly, bills = d["active"], d["modules"], d["pay_weekly"], d["bills"]
modules["label"] = modules["module"].map(MODULE_LABELS).fillna(modules["module"])

# ---------- headline numbers ----------
complete = active.iloc[:-1] if len(active) > 2 else active  # drop the in-progress week
k1, k2, k3, k4 = st.columns(4)
k1.metric("Active companies (last full week)", int(complete.iloc[-1]["active_companies"]))
k2.metric("Documents processed", f"{int(modules['documents'].sum()):,}")
k3.metric("Avg days, bill received → paid", f"{float(bills['avg_days_to_pay']):.1f}")
k4.metric("Bills still unpaid", f"{int(bills['open_bills']):,}")
st.divider()

# ---------- 1. weekly active companies ----------
st.subheader("1. How many companies use the product each week?")
fig = px.line(active, x="week_start", y="active_companies", markers=True,
              labels={"week_start": "Week starting", "active_companies": "Active companies"})
fig.update_yaxes(rangemode="tozero")
st.plotly_chart(fig, width="stretch")
first, last = complete.iloc[0], complete.iloc[-1]
change = (last["active_companies"] - first["active_companies"]) / first["active_companies"] * 100
st.markdown(f"**Takeaway:** weekly active companies went from **{int(first['active_companies'])}** "
            f"(week of {first['week_start']:%b %d}) to **{int(last['active_companies'])}** "
            f"(week of {last['week_start']:%b %d}), {'up' if change >= 0 else 'down'} {abs(change):.0f}%. "
            "A company counts as active if it did anything in the product that week.")

# ---------- 2. documents per module ----------
st.subheader("2. Which parts of the product get used most?")
fig = px.bar(modules.sort_values("documents"), x="documents", y="label", orientation="h",
             labels={"documents": "Documents processed", "label": ""}, text="documents")
st.plotly_chart(fig, width="stretch")
top = modules.iloc[0]
share = top["documents"] / modules["documents"].sum() * 100
st.markdown(f"**Takeaway:** **{top['label']}** is the busiest module with **{int(top['documents']):,}** "
            f"documents ({share:.0f}% of all activity). The least used is "
            f"**{modules.iloc[-1]['label']}**, which is where to look for adoption gaps.")

# ---------- 3. time to pay ----------
st.subheader("3. How long does it take to pay a bill?")
fig = px.line(pay_weekly, x="week_start", y="avg_days_to_pay", markers=True,
              hover_data=["bills_paid"],
              labels={"week_start": "Week the bill was paid", "avg_days_to_pay": "Average days",
                      "bills_paid": "Bills paid"})
fig.update_yaxes(rangemode="tozero")
st.plotly_chart(fig, width="stretch")
st.markdown(f"**Takeaway:** across **{int(bills['paid_bills']):,}** paid bills the average is "
            f"**{float(bills['avg_days_to_pay']):.1f} days** from received to paid, and "
            f"**{int(bills['open_bills']):,}** bills are still open (not counted in the average). "
            "The first weeks look faster only because bills that take longer had not been paid yet.")

with st.expander("Data quality checks"):
    st.dataframe(d["quality"], hide_index=True, width="stretch")
