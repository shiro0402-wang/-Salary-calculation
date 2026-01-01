import streamlit as st
import pandas as pd
import math
from datetime import datetime, timedelta

# --- 1. 核心邏輯：智慧時間處理 ---
def smart_parse_time(t_input):
    """
    智慧判讀時間格式：
    1. 支援標準 "15:30"
    2. 支援 4碼 "1530" -> "15:30"
    3. 支援 3碼 "930"  -> "09:30"
    4. 支援 Excel 秒數 "15:30:00" -> "15:30"
    """
    if pd.isna(t_input) or str(t_input).strip() == "":
        return None, ""
    
    raw = str(t_input).strip()
    
    # 處理 Excel 可能帶有的秒數
    if ":" in raw and len(raw) > 5:
        raw = raw[:5]
        
    # 處理純數字格式 (如 1530, 930)
    if raw.isdigit():
        if len(raw) == 4:   # 1530
            raw = f"{raw[:2]}:{raw[2:]}"
        elif len(raw) == 3: # 930
            raw = f"0{raw[:1]}:{raw[1:]}"
            
    # 嘗試轉換為時間物件
    try:
        t_obj = datetime.strptime(raw, "%H:%M")
        return t_obj, raw # 回傳 (時間物件, 格式化後的字串)
    except:
        return None, raw # 格式錯誤，回傳原字串

def calc_minutes(start_t, end_t):
    """計算分鐘數，處理跨日"""
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
st.title("🥩 箱舟燒肉 - 智慧薪資結算")

# --- 4. 側邊欄設定 ---
with st.sidebar:
    st.header("⚙️ 設定參數")
    
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
    dept = st.radio("部門", ["內場", "外場"], horizontal=True)
    shift_options = list(SHIFTS_DB[dept].keys())
    selected_shift_code = st.selectbox(f"選擇{dept}班別", shift_options)
    
    current_rule_times = SHIFTS_DB[dept][selected_shift_code]
    st.caption(f"標準時間: {current_rule_times}")
    
    st.divider()
    ot_rate = st.number_input("加班費率", value=1.34)
    late_fee = st.number_input("遲到扣款(每分)", value=5)
    full_attend_bonus = st.number_input("全勤獎金", value=2000)

# --- 5. 初始化表格 ---
# 為了讓結果回填，我們需要在 session_state 中維護 dataframe
if 'df_data' not in st.session_state:
    # 建立 31 天的表格，預留結果欄位
    rows = []
    for i in range(1, 32):
        # 日期, In1, Out1, In2, Out2, 當日工時(顯), 當日加班(顯), 補休(輸), 遲到(隱), 原始加班(隱)
        rows.append([i, "", "", "", "", None, None, 0.0]) 
    
    st.session_state.df_data = pd.DataFrame(
        rows, 
        columns=["日期", "時段1上班", "時段1下班", "時段2上班", "時段2下班", 
                 "當日工時", "加班(0.5)", "補休時數"]
    )

st.info(f"💡 操作提示：直接從 Excel 複製時間貼上即可。支援輸入 **1530** 自動轉為 **15:30**。")

# --- 6. 表格編輯區 ---
# 使用 column_config 來優化輸入體驗
# 關鍵：時間欄位設為 TextColumn 以容許 4碼輸入與整批貼上
edited_df = st.data_editor(
    st.session_state.df_data,
    column_config={
        "日期": st.column_config.NumberColumn(disabled=True, width="small"),
        "時段1上班": st.column_config.TextColumn(width="small", help="可輸入 1530"),
        "時段1下班": st.column_config.TextColumn(width="small", help="可輸入 2330"),
        "時段2上班": st.column_config.TextColumn(width="small"),
        "時段2下班": st.column_config.TextColumn(width="small"),
        "當日工時": st.column_config.NumberColumn(format="%.1f hr", disabled=True), # 唯讀結果
        "加班(0.5)": st.column_config.NumberColumn(format="%.1f hr", disabled=True), # 唯讀結果
        "補休時數": st.column_config.NumberColumn(format="%.1f")
    },
    num_rows="dynamic",
    height=500,
    hide_index=True
)

# --- 7. 計算與格式化邏輯 ---
st.divider()

if st.button("🚀 格式化時間並計算薪資", type="primary"):
    
    total_work = 0
    total_ot_final = 0 # 經過 0.5 進位處理後的總加班
    total_late = 0
    
    # 暫存列表用來更新 DataFrame
    updated_data = []
    
    for index, row in edited_df.iterrows():
        # 1. 取得原始輸入
        raw_t1_in = row["時段1上班"]
        raw_t1_out = row["時段1下班"]
        raw_t2_in = row["時段2上班"]
        raw_t2_out = row["時段2下班"]
        
        # 2. 智慧格式化 (將 1530 轉為 15:30, 並取得時間物件)
        t1_in_obj, t1_in_str = smart_parse_time(raw_t1_in)
        t1_out_obj, t1_out_str = smart_parse_time(raw_t1_out)
        t2_in_obj, t2_in_str = smart_parse_time(raw_t2_in)
        t2_out_obj, t2_out_str = smart_parse_time(raw_t2_out)
        
        u_times = [(t1_in_obj, t1_out_obj), (t2_in_obj, t2_out_obj)]
        
        # 單日統計
        day_work_mins = 0
        day_ot_mins = 0
        day_late_mins = 0
        has_data = False
        
        # 3. 考勤計算
        if t1_in_obj or t2_in_obj:
            has_data = True
            for i in range(len(current_rule_times)):
                if i >= len(u_times): break
                
                std_in_str, std_out_str = current_rule_times[i]
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
                
                # 加班 (原始分鐘數)
                t_std_out = dummy.replace(hour=int(std_out_str[:2]), minute=int(std_out_str[3:]))
                t_act_out = dummy.replace(hour=act_out.hour, minute=act_out.minute)
                
                # 跨日判定
                if int(std_out_str[:2]) < int(std_in_str[:2]): t_std_out += timedelta(days=1)
                if t_std_out.hour >= 12 and t_act_out.hour < 12: t_act_out += timedelta(days=1)
                elif t_std_out.day > t_act_out.day and t_act_out.hour < 12: t_act_out += timedelta(days=1)
                
                diff_ot = (t_act_out - t_std_out).total_seconds() / 60
                if diff_ot > 0: day_ot_mins += diff_ot

        # 4. 加班 0.5 單位計算邏輯
        # 規則：每滿 30 分鐘算 0.5 小時 (floor(分 / 30) * 0.5)
        # 例如：29分 -> 0, 30分 -> 0.5, 59分 -> 0.5, 60分 -> 1.0
        day_ot_units = math.floor(day_ot_mins / 30) * 0.5
        
        # 累加總數
        total_work += (day_work_mins / 60)
        total_ot_final += day_ot_units
        total_late += day_late_mins
        
        # 5. 更新 Row 資料 (回填格式化後的時間字串 + 計算結果)
        new_row = [
            row["日期"],
            t1_in_str,   # 回填 15:30
            t1_out_str,  # 回填 23:30
            t2_in_str,
            t2_out_str,
            round(day_work_mins / 60, 1) if has_data else None,  # 當日工時
            day_ot_units if has_data else None,                  # 當日加班(0.5)
            row["補休時數"]
        ]
        updated_data.append(new_row)

    # 更新 session_state 並強制刷新頁面以顯示結果
    st.session_state.df_data = pd.DataFrame(
        updated_data, 
        columns=["日期", "時段1上班", "時段1下班", "時段2上班", "時段2下班", 
                 "當日工時", "加班(0.5)", "補休時數"]
    )
    
    # 薪資結算
    deduct = total_late * late_fee
    bonus = full_attend_bonus if total_late == 0 else 0
    pay_ot = total_ot_final * ot_base_rate * ot_rate
    
    if emp_type == "月薪正職":
        final_salary = monthly_pay + pay_ot + bonus - deduct
        base_display = f"${monthly_pay:,} (底薪)"
    else:
        # PT: 正常工時薪資 (扣除加班時數，避免重複算) + 加班費
        # 注意：這裡的 total_work 包含了加班時間
        # 如果 PT 的時薪已經包含在打卡時間內，通常算法是:
        # (總時數 - 加班時數) * 時薪 + 加班費
        # 但這裡的加班時數經過 0.5 取整，為了精確，我們用 (總工時 - 總加班時數)
        regular_hours = total_work - total_ot_final 
        if regular_hours < 0: regular_hours = 0
        
        pay_regular = regular_hours * base_wage
        final_salary = pay_regular + pay_ot + bonus - deduct
        base_display = f"${int(pay_regular):,} (工時薪資)"

    # 顯示總結報告
    st.success("✅ 計算完成！時間格式已自動修正，計算結果已回填至表格。")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"### 🗓️ 月總工時: {total_work:.1f} hr")
        st.write(f"📈 總加班(0.5進位): {total_ot_final:.1f} hr")
        if total_late > 0: st.error(f"⚠️ 總遲到: {int(total_late)} 分")
        else: st.write("✅ 本月全勤")
        
    with c2:
        st.write(f"基本: {base_display}")
        st.write(f"加班費: +${int(pay_ot):,}")
        st.write(f"遲到扣款: -${int(deduct):,}")
        st.write(f"全勤獎金: +${bonus:,}")
        
    with c3:
        st.metric(label="💰 實領薪資", value=f"${int(final_salary):,}")

    # 這一行非常重要，讓表格重新渲染顯示新數據
    st.rerun()
