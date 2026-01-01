import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- 1. 時間處理工具 ---
def parse_time(t_str):
    if pd.isna(t_str) or str(t_str).strip() == "": return None
    try:
        t_str = str(t_str).strip()
        if len(t_str) > 5: t_str = t_str[:5]
        return datetime.strptime(t_str, "%H:%M")
    except: return None

def calc_minutes(start_t, end_t):
    if not start_t or not end_t: return 0
    dummy = datetime(2000, 1, 1)
    d_start = dummy.replace(hour=start_t.hour, minute=start_t.minute)
    d_end = dummy.replace(hour=end_t.hour, minute=end_t.minute)
    if d_end < d_start: d_end += timedelta(days=1)
    return (d_end - d_start).total_seconds() / 60

# --- 2. 班別資料庫 ---
SHIFTS_DB = {
    "內場": {
        "A": [("15:00", "23:00")],
        "B": [("15:00", "00:00")],
        "C": [("10:30", "14:30"), ("17:30", "21:30")],
        "D": [("10:30", "14:30"), ("17:30", "23:00")],
        "E": [("10:30", "14:30"), ("17:30", "00:00")],
    },
    "外場": {
        "A": [("15:30", "23:30")],
        "B": [("15:30", "00:30")],
        "C": [("10:00", "14:00"), ("17:00", "22:00")],
        "D": [("10:30", "15:00"), ("17:00", "00:00")], 
        "E": [("11:00", "15:00"), ("17:30", "00:30")],
        "F": [("10:30", "15:00"), ("17:00", "22:30")],
        "G": [("11:00", "15:30"), ("17:30", "23:30")],
    }
}

# --- 3. 頁面設定 ---
st.set_page_config(page_title="箱舟燒肉薪資表", layout="wide")
st.title("🥩 箱舟燒肉 - 薪資計算系統")

# --- 4. 側邊欄設定 ---
with st.sidebar:
    st.header("1️⃣ 員工類型與薪資")
    
    emp_type = st.radio("計薪模式", ["月薪正職", "時薪 PT"], horizontal=True)
    
    base_wage = 0      
    monthly_pay = 0    
    ot_base_rate = 0   
    
    if emp_type == "月薪正職":
        monthly_pay = st.number_input("底薪 (NTD)", value=32000, step=1000)
        default_ot_base = int(monthly_pay / 240)
        ot_base_rate = st.number_input("加班費計算時薪 (底薪/240)", value=default_ot_base)
    else:
        base_wage = st.number_input("PT 時薪 (NTD)", value=190, step=5)
        ot_base_rate = base_wage 
        
    st.divider()
    
    st.header("2️⃣ 班別規則")
    dept = st.radio("部門", ["內場", "外場"], horizontal=True)
    shift_options = list(SHIFTS_DB[dept].keys())
    selected_shift_code = st.selectbox(f"選擇{dept}班別", shift_options)
    
    current_rule_times = SHIFTS_DB[dept][selected_shift_code]
    st.caption(f"上班時間: {current_rule_times}")
    
    st.divider()
    st.header("3️⃣ 通用參數")
    ot_rate = st.number_input("加班費率", value=1.34)
    late_fee = st.number_input("遲到扣款(每分)", value=5)
    full_attend_bonus = st.number_input("全勤獎金", value=2000)

# --- 5. 表格輸入 ---
if 'df_data' not in st.session_state:
    rows = [[i, "", "", "", "", ""] for i in range(1, 32)]
    st.session_state.df_data = pd.DataFrame(
        rows, columns=["日期", "時段1上班", "時段1下班", "時段2上班", "時段2下班", "補休時數"]
    )

st.info(f"當前模式：**{emp_type}** | 班別：**{dept}-{selected_shift_code}**")

edited_df = st.data_editor(
    st.session_state.df_data,
    column_config={
        "日期": st.column_config.NumberColumn(disabled=True, width="small"),
        "時段1上班": st.column_config.TextColumn(help="貼上時間"),
        "時段1下班": st.column_config.TextColumn(help="貼上時間"),
        "補休時數": st.column_config.NumberColumn(format="%.1f")
    },
    num_rows="dynamic",
    height=400,
    hide_index=True
)

# --- 6. 計算與結果展示 ---
st.divider()

if st.button("🚀 計算薪資與工時", type="primary"):
    total_work = 0
    total_ot = 0
    total_late = 0
    
    # 用來儲存每一天的計算結果，最後做成表格
    daily_details = []
    
    for index, row in edited_df.iterrows():
        u_times = [
            (parse_time(row["時段1上班"]), parse_time(row["時段1下班"])),
            (parse_time(row["時段2上班"]), parse_time(row["時段2下班"]))
        ]
        
        # 單日統計變數
        day_work_mins = 0
        day_ot_mins = 0
        day_late_mins = 0
        has_record = False
        
        if u_times[0][0] or u_times[1][0]: # 有上班才算
            has_record = True
            for i in range(len(current_rule_times)):
                if i >= len(u_times): break
                std_in_str, std_out_str = current_rule_times[i]
                act_in, act_out = u_times[i]
                
                if not act_in or not act_out: continue
                
                # A. 工時計算
                w_mins = calc_minutes(act_in, act_out)
                day_work_mins += w_mins
                
                # B. 遲到計算
                dummy = datetime(2000, 1, 1)
                t_std_in = dummy.replace(hour=int(std_in_str[:2]), minute=int(std_in_str[3:]))
                t_act_in = dummy.replace(hour=act_in.hour, minute=act_in.minute)
                if t_act_in > t_std_in:
                    day_late_mins += (t_act_in - t_std_in).total_seconds() / 60
                
                # C. 加班計算
                t_std_out = dummy.replace(hour=int(std_out_str[:2]), minute=int(std_out_str[3:]))
                t_act_out = dummy.replace(hour=act_out.hour, minute=act_out.minute)
                
                # 跨日邏輯
                if int(std_out_str[:2]) < int(std_in_str[:2]): t_std_out += timedelta(days=1)
                if t_std_out.hour >= 12 and t_act_out.hour < 12: t_act_out += timedelta(days=1)
                elif t_std_out.day > t_act_out.day and t_act_out.hour < 12: t_act_out += timedelta(days=1)
                
                diff_ot = (t_act_out - t_std_out).total_seconds() / 60
                if diff_ot > 0: day_ot_mins += diff_ot

        # 累加到總月數
        total_work += (day_work_mins / 60)
        total_ot += (day_ot_mins / 60)
        total_late += day_late_mins
        
        # 紀錄這一天的詳細數據 (只紀錄有上班的日子，或顯示空白)
        if has_record:
            daily_details.append({
                "日期": row["日期"],
                "當日工時": round(day_work_mins / 60, 1), # 這裡就是您要的「當日上班時數」
                "遲到分鐘": int(day_late_mins),
                "加班時數": round(day_ot_mins / 60, 1)
            })

    # === 薪資計算 ===
    deduct = total_late * late_fee
    bonus = full_attend_bonus if total_late == 0 else 0
    pay_ot = total_ot * ot_base_rate * ot_rate
    
    if emp_type == "月薪正職":
        final_salary = monthly_pay + pay_ot + bonus - deduct
        display_base = f"${monthly_pay:,} (底薪)"
    else:
        regular_hours = total_work - total_ot
        if regular_hours < 0: regular_hours = 0
        pay_regular = regular_hours * base_wage
        final_salary = pay_regular + pay_ot + bonus - deduct
        display_base = f"${int(pay_regular):,} (工時薪資)"

    # === 結果顯示 (上層總結) ===
    c1, c2, c3 = st.columns(3)
    with c1:
        # 這裡顯示「一個月上班總時數」
        st.markdown(f"### 🗓️ 月總工時: {total_work:.1f} hr")
        st.write(f"📈 總加班: {total_ot:.1f} hr")
        if total_late > 0: st.error(f"⚠️ 總遲到: {int(total_late)} 分")
        else: st.success("✅ 本月全勤")
        
    with c2:
        st.markdown("#### 薪資明細")
        st.write(f"基本: {display_base}")
        st.write(f"加班費: +${int(pay_ot):,}")
        st.write(f"遲到扣款: -${int(deduct):,}")
        st.write(f"全勤獎金: +${bonus:,}")
        
    with c3:
        st.metric(label="💰 實領薪資", value=f"${int(final_salary):,}")
    
    # === 結果顯示 (下層詳細表格) ===
    st.divider()
    st.subheader("📋 每日工時明細表")
    if daily_details:
        result_df = pd.DataFrame(daily_details)
        # 設定欄位顯示格式，讓工時有顏色 highlight
        st.dataframe(
            result_df,
            column_config={
                "日期": st.column_config.NumberColumn(format="%d"),
                "當日工時": st.column_config.NumberColumn(format="%.1f hr"),
                "遲到分鐘": st.column_config.NumberColumn(format="%d min"),
                "加班時數": st.column_config.NumberColumn(format="%.1f hr"),
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.caption("尚未輸入任何出勤紀錄")
