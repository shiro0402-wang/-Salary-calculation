import streamlit as st
import pandas as pd
import math
from datetime import datetime, timedelta

# --- 1. 核心邏輯：智慧時間處理 ---
def smart_parse_time(t_input):
    if pd.isna(t_input) or str(t_input).strip() == "": return None, ""
    raw = str(t_input).strip()
    if ":" in raw and len(raw) > 5: raw = raw[:5]
    if raw.isdigit():
        if len(raw) == 4: raw = f"{raw[:2]}:{raw[2:]}"
        elif len(raw) == 3: raw = f"0{raw[:1]}:{raw[1:]}"
    try:
        t_obj = datetime.strptime(raw, "%H:%M")
        return t_obj, raw
    except: return None, raw

def calc_minutes(start_t, end_t):
    if not start_t or not end_t: return 0
    dummy = datetime(2000, 1, 1)
    d_start = dummy.replace(hour=start_t.hour, minute=start_t.minute)
    d_end = dummy.replace(hour=end_t.hour, minute=end_t.minute)
    if d_end < d_start: d_end += timedelta(days=1)
    return (d_end - d_start).total_seconds() / 60

# --- 2. 班別資料庫 (完整版) ---
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
st.title("🥩 箱舟燒肉 - 薪資計算 (每日班別版)")

# --- 4. 側邊欄：全域設定 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    
    # 這裡的部門選擇變成「預設值」，會自動填入表格
    default_dept = st.radio("預設部門 (填表用)", ["內場", "外場"], help="表格預設會帶入這個部門，若當天支援別部門可於表格內修改")
    
    st.divider()
    emp_type = st.radio("計薪模式", ["月薪正職", "時薪 PT"], horizontal=True)
    
    base_wage = 0      
    monthly_pay = 0    
    ot_base_rate = 0   
    
    if emp_type == "月薪正職":
        monthly_pay = st.number_input("底薪", value=32000, step=1000)
        default_ot_base = int(monthly_pay / 240)
        ot_base_rate = st.number_input("加班費計算時薪", value=default_ot_base)
    else:
        base_wage = st.number_input("PT 時薪", value=190, step=5)
        ot_base_rate = base_wage 
        
    st.divider()
    ot_rate = st.number_input("加班費率", value=1.34)
    late_fee = st.number_input("遲到扣款(每分)", value=5)
    full_attend_bonus = st.number_input("全勤獎金", value=2000)
    
    # 顯示規則參考用
    st.markdown("---")
    st.caption("📖 班別規則速查:")
    view_dept = st.selectbox("查看部門規則", ["內場", "外場"])
    st.json(SHIFTS_DB[view_dept], expanded=False)

# --- 5. 初始化表格 ---
if 'df_data' not in st.session_state:
    rows = []
    for i in range(1, 32):
        # 預設部門帶入側邊欄的設定
        # 欄位順序: 日期, 班別, In1, Out1, In2, Out2, 部門, 補休, 工時(顯), 加班(顯)
        rows.append([i, "", "", "", "", "", default_dept, 0.0, None, None]) 
    
    st.session_state.df_data = pd.DataFrame(
        rows, 
        columns=["日期", "班別", "時段1上班", "時段1下班", "時段2上班", "時段2下班", 
                 "部門", "補休時數", "當日工時", "加班(0.5)"]
    )

st.markdown("### 📝 出勤資料輸入")
st.info("💡 **操作技巧**：您可以直接從 Excel 複製 `班別` 與 `時間` 區域，貼在下表的「班別」欄位。若當天支援不同部門，請在後方「部門」欄位修改。")

# --- 6. 表格編輯區 ---
edited_df = st.data_editor(
    st.session_state.df_data,
    column_config={
        "日期": st.column_config.NumberColumn(disabled=True, width="small"),
        
        # 班別放在前面，方便貼上
        "班別": st.column_config.TextColumn(width="small", help="填入 A, B, C..."),
        
        "時段1上班": st.column_config.TextColumn(width="small", help="可輸入 1530"),
        "時段1下班": st.column_config.TextColumn(width="small", help="可輸入 2330"),
        "時段2上班": st.column_config.TextColumn(width="small"),
        "時段2下班": st.column_config.TextColumn(width="small"),
        
        # 部門放在中間/後面，避免影響 Excel 貼上順序
        "部門": st.column_config.SelectboxColumn(
            options=["內場", "外場"],
            width="small",
            required=True,
            help="該日所屬部門規則"
        ),
        
        "當日工時": st.column_config.NumberColumn(format="%.1f hr", disabled=True), 
        "加班(0.5)": st.column_config.NumberColumn(format="%.1f hr", disabled=True),
        "補休時數": st.column_config.NumberColumn(format="%.1f")
    },
    num_rows="dynamic",
    height=500,
    hide_index=True
)

# --- 7. 計算與格式化邏輯 ---
st.divider()

if st.button("🚀 格式化時間並計算", type="primary"):
    
    total_work = 0
    total_ot_final = 0 
    total_late = 0
    updated_data = []
    
    for index, row in edited_df.iterrows():
        # 1. 讀取該行的部門與班別
        row_dept = row["部門"]
        row_shift = str(row["班別"]).strip().upper() if row["班別"] else None
        
        # 2. 智慧格式化時間
        t1_in_obj, t1_in_str = smart_parse_time(row["時段1上班"])
        t1_out_obj, t1_out_str = smart_parse_time(row["時段1下班"])
        t2_in_obj, t2_in_str = smart_parse_time(row["時段2上班"])
        t2_out_obj, t2_out_str = smart_parse_time(row["時段2下班"])
        
        u_times = [(t1_in_obj, t1_out_obj), (t2_in_obj, t2_out_obj)]
        
        day_work_mins = 0
        day_ot_mins = 0
        day_late_mins = 0
        has_data = False
        
        # 3. 尋找對應規則
        # 必須要有班別代號，且該代號存在於所選部門的規則中
        current_rules = []
        if row_dept in SHIFTS_DB and row_shift in SHIFTS_DB[row_dept]:
            current_rules = SHIFTS_DB[row_dept][row_shift]
        
        # 4. 開始計算
        if t1_in_obj or t2_in_obj:
            has_data = True
            
            # 如果找不到規則 (例如忘了填班別，或填了 Z)，有時間但沒規則 -> 只算工時，無法算遲到加班
            if not current_rules:
                # 簡易工時計算 (無規則模式)
                for act_in, act_out in u_times:
                    day_work_mins += calc_minutes(act_in, act_out)
            else:
                # 有規則模式
                for i in range(len(current_rules)):
                    if i >= len(u_times): break
                    std_in_str, std_out_str = current_rules[i]
                    act_in, act_out = u_times[i]
                    
                    if not act_in or not act_out: continue
                    
                    # 工時
                    day_work_mins += calc_minutes(act_in, act_out)
                    
                    # 遲到
                    dummy = datetime(2000, 1, 1)
                    t_std_in = dummy.replace(hour=int(std_in_str[:2]), minute=int(std_in_str[3:]))
                    t_act_in = dummy.replace(hour=act_in.hour, minute=act_in.minute)
                    if t_act_in > t_std_in:
                        day_late_mins += (t_act_in - t_std_in).total_seconds() / 60
                    
                    # 加班
                    t_std_out = dummy.replace(hour=int(std_out_str[:2]), minute=int(std_out_str[3:]))
                    t_act_out = dummy.replace(hour=act_out.hour, minute=act_out.minute)
                    
                    if int(std_out_str[:2]) < int(std_in_str[:2]): t_std_out += timedelta(days=1)
                    if t_std_out.hour >= 12 and t_act_out.hour < 12: t_act_out += timedelta(days=1)
                    elif t_std_out.day > t_act_out.day and t_act_out.hour < 12: t_act_out += timedelta(days=1)
                    
                    diff_ot = (t_act_out - t_std_out).total_seconds() / 60
                    if diff_ot > 0: day_ot_mins += diff_ot

        # 加班 0.5 單位
        day_ot_units = math.floor(day_ot_mins / 30) * 0.5
        
        total_work += (day_work_mins / 60)
        total_ot_final += day_ot_units
        total_late += day_late_mins
        
        # 回填資料
        new_row = [
            row["日期"],
            row_shift if row_shift else "", # 班別
            t1_in_str, t1_out_str, t2_in_str, t2_out_str,
            row_dept, # 部門保持原樣
            row["補休時數"],
            round(day_work_mins / 60, 1) if has_data else None,
            day_ot_units if has_data else None
        ]
        updated_data.append(new_row)

    # 更新表格
    st.session_state.df_data = pd.DataFrame(
        updated_data, 
        columns=["日期", "班別", "時段1上班", "時段1下班", "時段2上班", "時段2下班", 
                 "部門", "補休時數", "當日工時", "加班(0.5)"]
    )
    
    # 薪資結算
    deduct = total_late * late_fee
    bonus = full_attend_bonus if total_late == 0 else 0
    pay_ot = total_ot_final * ot_base_rate * ot_rate
    
    if emp_type == "月薪正職":
        final_salary = monthly_pay + pay_ot + bonus - deduct
        base_display = f"${monthly_pay:,} (底薪)"
    else:
        regular_hours = total_work - total_ot_final 
        if regular_hours < 0: regular_hours = 0
        pay_regular = regular_hours * base_wage
        final_salary = pay_regular + pay_ot + bonus - deduct
        base_display = f"${int(pay_regular):,} (工時薪資)"

    # 結果顯示
    st.success("✅ 計算完成！")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"### 🗓️ 月總工時: {total_work:.1f} hr")
        st.write(f"📈 總加班(0.5): {total_ot_final:.1f} hr")
        if total_late > 0: st.error(f"⚠️ 總遲到: {int(total_late)} 分")
        else: st.write("✅ 本月全勤")
        
    with c2:
        st.write(f"基本: {base_display}")
        st.write(f"加班費: +${int(pay_ot):,}")
        st.write(f"遲到扣款: -${int(deduct):,}")
        st.write(f"全勤獎金: +${bonus:,}")
        
    with c3:
        st.metric(label="💰 實領薪資", value=f"${int(final_salary):,}")

    st.rerun()
