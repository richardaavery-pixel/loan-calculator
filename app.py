import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Loan Overpayment & Tranche Modeller", layout="wide"
)

st.title("Commercial Loan Overpayment & Term Modeller")
st.markdown(
    "Modelling baseline balances up to **April 2027** (assuming a flat 7.25% rate / 3.75% BoE base rate) and calculating the impact of your lump sum overpayment."
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

# --- BASELINE PARAMETERS (As of June 2026) ---
# Rates (3.5% + 3.75% Base Rate = 7.25%)
annual_rate = 0.0725
monthly_rate = annual_rate / 12

# Loan 1: WA
b1_june = 500680.49
p1_cap = 8632.42
t1_rem = 58

# Loan 2: W
b2_june = 445076.93
p2_cap = 7673.74
t2_rem = 61

# Loan 3: NW (Est June balance based on trajectory)
b3_june = 1828599.64
t3_rem = 58
p3_cap_est = 35395.17 - (p1_cap + p2_cap)


# --- FUNCTION TO PROJECT FORWARD TO APRIL 2027 ---
def project_to_april(b1, b2, b3):
  months_to_april = 9
  for _ in range(months_to_april):
    i1 = b1 * monthly_rate
    b1 = b1 - p1_cap + i1

    i2 = b2 * monthly_rate
    b2 = b2 - p2_cap + i2

    i3 = b3 * monthly_rate
    b3 = b3 - p3_cap_est + i3

  return max(0, b1), max(0, b2), max(0, b3)


b1_apr, b2_apr, b3_apr = project_to_april(b1_june, b2_june, b3_june)

st.subheader("1. Projected Debt Position (April 2027 Pre-Lump Sum)")
col1, col2, col3 = st.columns(3)
col1.metric("Loan 1 (WA)", f"£{b1_apr:,.2f}", "50 Rem. Months")
col2.metric("Loan 2 (W)", f"£{b2_apr:,.2f}", "53 Rem. Months")
col3.metric("Loan 3 (NW)", f"£{b3_apr:,.2f}", "50 Rem. Months")

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
  new_p1_cap = calc_new_payment(b1_post, 50)
  new_p2_cap = calc_new_payment(b2_post, 53)
  new_p3_cap = calc_new_payment(b3_post, 50)

  total_new_payment = new_p1_cap + new_p2_cap + new_p3_cap

  summary_df = pd.DataFrame({
      "Loan Tranche": ["Loan 1 (WA)", "Loan 2 (W)", "Loan 3 (NW)", "Total Group"],
      "Balance After Lump Sum": [b1_post, b2_post, b3_post, b1_post + b2_post + b3_post],
      "New Estimated Monthly Servicing": [new_p1_cap, new_p2_cap, new_p3_cap, total_new_payment],
  })
  st.dataframe(
      summary_df.style.format({
          "Balance After Lump Sum": "£{:,.2f}",
          "New Estimated Monthly Servicing": "£{:,.2f}",
      })
  )
  st.success(
      f"By injecting £{lump_sum:,.2f} in April 2027, your total monthly debt servicing requirement drops immediately."
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


  new_t1 = calc_new_term(b1_post, p1_cap + (b1_apr * monthly_rate))
  new_t2 = calc_new_term(b2_post, p2_cap + (b2_apr * monthly_rate))
  new_t3 = calc_new_term(b3_post, p3_cap_est + (b3_apr * monthly_rate))

  term_df = pd.DataFrame({
      "Loan Tranche": ["Loan 1 (WA)", "Loan 2 (W)", "Loan 3 (NW)"],
      "Original Months Remaining": [50, 53, 50],
      "New Months Remaining (Post-Lump Sum)": [round(new_t1, 1), round(new_t2, 1), round(new_t3, 1)],
      "Months Saved": [
          round(50 - new_t1, 1),
          round(53 - new_t2, 1),
          round(50 - new_t3, 1),
      ],
  })
  st.dataframe(term_df)
