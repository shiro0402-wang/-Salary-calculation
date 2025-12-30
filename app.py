import streamlit as st
import pandas as pd

# --- 頁面設定 ---
st.set_page_config(page_title="箱舟燒肉 - 薪資計算", layout="wide")
st.title("🥩 箱舟燒肉 - 薪資計算系統")

# --- 側邊欄設定 ---
with st.sidebar:
    st.header("⚙️ 設定")
    base_wage = st.number_input("時薪", value=190)
    ot_rate = st.number_input("加班費率", value=1.34)
    late_fee = st.number_input("遲到扣款(每分)", value=5)
    full_attend = st.number_input("全勤獎金", value=2000)

# --- 資料結構 ---
# 建立一個 31 天的空表格
data = []
for i in range(1, 32):
    # 預設格式: 日期, 班別, 上班, 下班, 正常工時, 加班時數, 補休, 遲到
    data.append([i, "A", None, None, 0.0, 0.0, 0.0, 0])

df = pd.DataFrame(data, columns=["日期", "班別", "上班", "下班", "正常工時", "加班", "補休", "遲到"])

# --- 表格輸入區 ---
st.info("👇 請直接修改表格內容：")
edited_df = st.data_editor(
    df,
    column_config={
        "上班": st.column_config.TimeColumn(format="HH:mm"),
        "下班": st.column_config.TimeColumn(format="HH:mm"),
        "正常工時": st.column_config.NumberColumn(format="%.1f"),
        "加班": st.column_config.NumberColumn(format="%.1f"),
        "補休": st.column_config.NumberColumn(format="%.1f"),
        "遲到": st.column_config.NumberColumn(format="%d 分"),
    },
    height=500
)

# --- 自動計算 ---
total_hours = edited_df["正常工時"].sum()
total_ot = edited_df["加班"].sum()
total_late = edited_df["遲到"].sum()

salary = (total_hours * base_wage) + (total_ot * base_wage * ot_rate)
penalty = total_late * late_fee
bonus = full_attend if total_late == 0 else 0
final_pay = salary + bonus - penalty

# --- 顯示結果 ---
st.divider()
col1, col2 = st.columns(2)
with col1:
    st.markdown("### 📊 統計")
    st.write(f"正常工時: {total_hours} hr")
    st.write(f"加班時數: {total_ot} hr")
    st.write(f"遲到總計: {total_late} min")

with col2:
    st.markdown("### 💰 薪資試算")
    st.write(f"基本+加班: ${int(salary):,}")
    st.write(f"全勤獎金: ${bonus} " + ("✅" if bonus > 0 else "❌"))
    st.write(f"遲到扣款: -${int(penalty)}")
    st.markdown(f"## 實領: ${int(final_pay):,}")
