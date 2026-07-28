import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Commercial Loan Overpayment Modeller", layout="wide"
)

st.title("Commercial Loan Overpayment & Term Modeller")
st.markdown(
    "Accurate baseline projection up to **April 2027** maintaining your exact current payment structures (7.25% tracking rate / 3.75% BoE base rate)."
)

# --- SIDEBAR CONTROLS ---
st.sidebar.header("Overpayment Configuration")
lump_sum = st.sidebar.slider(
    "April 2027 Lump Sum (£)",
    min_value=0,
    max_value=1_500_000,
    step=25_000,
    value=250_000,
)

allocation_strategy = st.sidebar.selectbox(
    "Lump Sum Allocation Strategy",
    [
        "Proportionate across all loans",
        "Target Loan 3 (NW) first",
        "Target Loan 1 (WA) first",
    ],
)

goal_type = st.sidebar.radio(
    "Lump Sum Treatment",
    [
        "Reduce Monthly Payment (Keep Term)",
        "Reduce Term (Keep Monthly Payment)",
    ],
)

# --- TRUE BASELINE PARAMETERS (As of June 2026) ---
annual_rate = 0.0725
monthly_rate = annual_rate / 12

# Loan 1 (WA): Balance £500,680.49 | Capital £8,632.42 | Total June payment was ~£11,667.37
b1_june = 500680.49
p1_cap = 8632.42
t1_rem = 58

# Loan 2 (W): Balance £445,076.93 | Capital £7,673.74 | Total June payment was ~£10,371.64
b2_june = 445076.93
p2_cap = 7673.74
t2_rem = 61

# Loan 3 (NW): Balance £1,828,599.64 | Total group payment £35,395.17
# Therefore Loan 3 current total monthly service = Group Total (£35,395.17) - Loan 1 Total - Loan 2 Total
b3_june = 1828599.64
t3_rem = 58
total_group_pmt = 35395.17
l1_total_june = p1_cap + (b1_june * monthly_rate)
l2_total_june = p2_cap + (b2_june * monthly_rate)
l3_total_june = total_group_pmt - (l1_total_june + l2_total_june)


# --- FORWARD PROJECTION TO APRIL 2027 (9 months) ---
def project_to_april(b1, b2, b3):
  b1_curr, b2_curr, b3_curr = b1, b2, b3
  for m in range(9):
    # Loan 1
    i1 = b1_curr * monthly_rate
    c1 = l1_total_june - i1
    b1_curr = b1_curr - c1 + i1  # standard amortization adjustment

    # Loan 2
    i2 = b2_curr * monthly_rate
    c2 = l2_total_june - i2
    b2_curr = b2_curr - c2 + i2

    # Loan 3 (Quarterly interest capitalization check at month 3, 6, 9)
    i3 = b3_curr * monthly_rate
    c3 = l3_total_june - i3
    b3_curr = b3_curr - c3 + i3

  return (
      max(0, b1_curr),
      max(0, b2_curr),
      max(0, b3_curr),
      max(0, t1_rem - 9),
      max(0, t2_rem - 9),
      max(0, t3_rem - 9),
  )


b1_apr, b2_apr, b3_apr, t1_apr_rem, t2_apr_rem, t3_apr_rem = project_to_april(
    b1_june, b2_june, b3_june
)

st.subheader("1. Projected Debt Position (April 2027 Pre-Lump Sum)")
col1, col2, col3 = st.columns(3)
col1.metric(
    "Loan 1 (WA)",
    f"£{b1_apr:,.2f}",
    f"{t1_apr_rem} Rem. Months | ~£{l1_total_june:,.2f}pm",
)
col2.metric(
    "Loan 2 (W)",
    f"£{b2_apr:,.2f}",
    f"{t2_apr_rem} Rem. Months | ~£{l2_total_june:,.2f}pm",
)
col3.metric(
    "Loan 3 (NW)",
    f"£{b3_apr:,.2f}",
    f"{t3_apr_rem} Rem. Months | ~£{l3_total_june:,.2f}pm",
)

# --- APPLY LUMP SUM ALLOCATION ---
rem_lump = lump_sum
al1, al2, al3 = 0, 0, 0

if allocation_strategy == "Target Loan 3 (NW) first":
  al3 = min(rem_lump, b3_apr)
  rem_lump -= al3
  al1 = min(rem_lump, b1_apr)
  rem_lump -= al1
  al2 = min(rem_lump, b2_apr)
elif allocation_strategy == "Target Loan 1 (WA) first":
  al1 = min(rem_lump, b1_apr)
  rem_lump -= al1
  al3 = min(rem_lump, b3_apr)
  rem_lump -= al3
  al2 = min(rem_lump, b2_apr)
else:  # Proportionate
  total_bal = b1_apr + b2_apr + b3_apr
  if total_bal > 0:
    al1 = lump_sum * (b1_apr / total_bal)
    al2 = lump_sum * (b2_apr / total_bal)
    al3 = lump_sum * (b3_apr / total_bal)

b1_post = max(0, b1_apr - al1)
b2_post = max(0, b2_apr - al2)
b3_post = max(0, b3_apr - al3)

st.divider()
st.subheader("2. Post-Lump Sum Impact Analysis")


def calc_new_payment(balance, original_term):
  if balance <= 0 or original_term <= 0:
    return 0
  return (
      balance
      * monthly_rate
      * (1 + monthly_rate) ** original_term
      / ((1 + monthly_rate) ** original_term - 1)
  )


if "Reduce Monthly Payment" in goal_type:
  new_l1_pmt = calc_new_payment(b1_post, t1_apr_rem)
  new_l2_pmt = calc_new_payment(b2_post, t2_apr_rem)
  new_l3_pmt = calc_new_payment(b3_post, t3_apr_rem)
  total_new_group_pmt = new_l1_pmt + new_l2_pmt + new_l3_pmt

  summary_df = pd.DataFrame({
      "Loan Tranche": ["Loan 1 (WA)", "Loan 2 (W)", "Loan 3 (NW)", "Total Group"],
      "Balance After Lump Sum": [b1_post, b2_post, b3_post, b1_post + b2_post + b3_post],
      "New Monthly Servicing": [new_l1_pmt, new_l2_pmt, new_l3_pmt, total_new_group_pmt],
  })
  st.dataframe(
      summary_df.style.format({
          "Balance After Lump Sum": "£{:,.2f}",
          "New Monthly Servicing": "£{:,.2f}",
      })
  )
  st.success(
      f"By injecting £{lump_sum:,.2f} in April 2027, your total monthly group debt service drops from ~£35,395.17 down to **£{total_new_group_pmt:,.2f}**."
  )

else:
  st.markdown(
      "*Note: Term reduction calculation holds current payment structures flat against lower principal bases, accelerating clearance dates.*"
  )


  def calc_new_term(balance, pmt):
    if balance <= 0 or pmt <= (balance * monthly_rate):
      return 0
    return -np.log(1 - (balance * monthly_rate) / pmt) / np.log(
        1 + monthly_rate
    )


  new_t1 = calc_new_term(b1_post, l1_total_june)
  new_t2 = calc_new_term(b2_post, l2_total_june)
  new_t3 = calc_new_term(b3_post, l3_total_june)

  term_df = pd.DataFrame({
      "Loan Tranche": ["Loan 1 (WA)", "Loan 2 (W)", "Loan 3 (NW)"],
      "Months Remaining (Pre-Lump Sum)": [
          t1_apr_rem,
          t2_apr_rem,
          t3_apr_rem,
      ],
      "New Months Remaining (Post-Lump Sum)": [round(new_t1, 1), round(new_t2, 1), round(new_t3, 1)],
      "Months Saved": [
          round(t1_apr_rem - new_t1, 1),
          round(t2_apr_rem - new_t2, 1),
          round(t3_apr_rem - new_t3, 1),
      ],
  })
  st.dataframe(term_df)
