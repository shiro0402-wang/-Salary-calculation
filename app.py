import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- 1. 時間處理工具 ---
def parse_time(t_str):
    """將字串 (例如 '15:30') 轉為時間物件，若空白則回傳 None"""
    if pd.isna(t_str) or str(t_str).strip() == "":
        return None
    try:
        t_str = str(t_str).strip()
        if len(t_str) > 5: t_str = t_str[:5] # 去除秒數
        return datetime.strptime(t_str, "%H:%M")
    except:
        return None

def calc_minutes(start_t, end_t):
    """計算分鐘數，自動處理跨日"""
    if not start_t or not end_t: return 0
    dummy = datetime(2000, 1, 1)
    d_start = dummy.replace(hour=start_t.hour, minute=start_t.minute)
    d_end = dummy.replace(hour=end_t.hour, minute=end_t.minute)
    if d_end < d_start: d_end += timedelta(days=1) # 跨日
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
st.title("🥩 箱舟燒肉 - 薪資計算 (班別鎖定版)")

# --- 4. 側邊欄：全域設定 ---
with st.sidebar:
    st.header("1️⃣ 班別與費率設定")
    
    # 部門與班別選擇
    dept = st.radio("部門", ["內場", "外場"], horizontal=True)
    
    # 動態取得該部門的班別列表
    shift_options = list(SHIFTS_DB[dept].keys())
    selected_shift_code = st.selectbox(f"選擇{dept}班別", shift_options)
    
    # 顯示該班別時間資訊
    current_rule_times = SHIFTS_DB[dept][selected_shift_code]
    st.info(f"📅 **目前設定：{dept} - {selected_shift_code} 班**")
    for idx, (s, e) in enumerate(current_rule_times):
        st.write(f"時段 {idx+1}: `{s}` ~ `{e}`")
    
    st.divider()
    
    # 薪資參數
    st.header("2️⃣ 薪資參數")
    base_wage = st.number_input("時薪", value=190)
    ot_rate = st.number_input("加班費率", value=1.34)
    late_fee = st.number_input("遲到扣款(每分)", value=5)
    full_attend_bonus = st.number_input("全勤獎金", value=2000)

# --- 5. 資料輸入表格 ---
if 'df_data' not in st.session_state:
    # 建立 31 天的空表格 (移除班別欄位)
    rows = [[i, "", "", "", "", ""] for i in range(1, 32)]
    st.session_state.df_data = pd.DataFrame(
        rows, 
        columns=["日期", "時段1上班", "時段1下班", "時段2上班", "時段2下班", "補休時數"]
    )

st.markdown("### 📝 出勤輸入區")
st.caption(f"⚠️ 注意：下方所有填寫的時間，都會依照左側選定的 **【{dept} {selected_shift_code}班】** 規則來計算遲到與加班。")

# 表格設定
edited_df = st.data_editor(
    st.session_state.df_data,
    column_config={
        "日期": st.column_config.NumberColumn(disabled=True, width="small"),
        "時段1上班": st.column_config.TextColumn(help="輸入 15:30"),
        "時段1下班": st.column_config.TextColumn(help="輸入 23:30"),
        "時段2上班": st.column_config.TextColumn(help="雙頭班才填"),
        "時段2下班": st.column_config.TextColumn(help="雙頭班才填"),
        "補休時數": st.column_config.NumberColumn(format="%.1f")
    },
    num_rows="dynamic",
    height=450,
    hide_index=True
)

# --- 6. 計算邏輯 ---
st.divider()

if st.button("🚀 開始計算", type="primary"):
    
    total_work = 0
    total_ot = 0
    total_late = 0
    
    # 讀取當前設定的班別規則 (例如內場A: 15:00~23:00)
    rules = current_rule_times 
    
    for index, row in edited_df.iterrows():
        # 抓取使用者輸入的時間
        u_times = [
            (parse_time(row["時段1上班"]), parse_time(row["時段1下班"])),
            (parse_time(row["時段2上班"]), parse_time(row["時段2下班"]))
        ]
        
        # 只要有填上班時間，就開始計算
        if u_times[0][0] or u_times[1][0]:
            
            # 比對每一個時段 (雙頭班會跑兩次迴圈)
            for i in range(len(rules)):
                if i >= len(u_times): break # 避免索引錯誤
                
                std_in_str, std_out_str = rules[i]
                act_in, act_out = u_times[i]
                
                # 如果使用者沒填這個時段，跳過
                if not act_in or not act_out:
                    continue
                
                # A. 實作時數
                work_mins = calc_minutes(act_in, act_out)
                total_work += (work_mins / 60)
                
                # B. 遲到計算
                # 標準上班時間物件化
                dummy = datetime(2000, 1, 1)
                std_in = datetime.strptime(std_in_str, "%H:%M")
                t_std_in = dummy.replace(hour=std_in.hour, minute=std_in.minute)
                t_act_in = dummy.replace(hour=act_in.hour, minute=act_in.minute)
                
                if t_act_in > t_std_in:
                    diff = (t_act_in - t_std_in).total_seconds() / 60
                    # 緩衝期? 這裡採嚴格制，大於0就分別算
                    total_late += diff
                    
                # C. 加班計算 (邏輯：實際下班 - 標準下班)
                std_out = datetime.strptime(std_out_str, "%H:%M")
                t_std_out = dummy.replace(hour=std_out.hour, minute=std_out.minute)
                t_act_out = dummy.replace(hour=act_out.hour, minute=act_out.minute)
                
                # 處理跨日比較 (例如 標準23:00, 實際00:30)
                # 若標準本身跨日 (17:00~00:00) -> std_out < std_in
                is_std_cross = std_out.hour < std_in.hour
                if is_std_cross: t_std_out += timedelta(days=1)
                
                # 若實際跨日 (17:00~00:30) -> act_out < act_in (或者單純看是不是隔天凌晨)
                # 簡單判定：如果標準是晚上，實際是早上，那實際就要加一天
                if t_std_out.hour >= 12 and t_act_out.hour < 12:
                    t_act_out += timedelta(days=1)
                elif is_std_cross and t_act_out.hour < 12:
                    # 標準已經跨日了，實際也是跨日，大家都加了一天，可以直接比
                     t_act_out += timedelta(days=1)

                ot_mins = (t_act_out - t_std_out).total_seconds() / 60
                if ot_mins > 0:
                    total_ot += (ot_mins / 60)

    # --- 7. 結果結算 ---
    regular_hours = total_work - total_ot
    # 避免負數 (如果使用者填的時間比標準短，可能會沒加班但總工時少)
    if regular_hours < 0: regular_hours = 0 
    
    pay_regular = regular_hours * base_wage
    pay_ot = total_ot * base_wage * ot_rate
    deduct = total_late * late_fee
    bonus = full_attend_bonus if total_late == 0 else 0
    final = pay_regular + pay_ot + bonus - deduct
    
    # 顯示區塊
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info(f"📊 **總工時: {total_work:.1f} hr**")
        st.write(f"正常: {regular_hours:.1f} hr")
        st.write(f"加班: {total_ot:.1f} hr")
    with c2:
        if total_late > 0:
            st.error(f"⚠️ **遲到: {int(total_late)} 分**")
            st.write(f"扣款: -{int(deduct)}")
        else:
            st.success("✅ 無遲到")
    with c3:
        st.markdown(f"### 💰 實領: ${int(final):,}")
        st.caption(f"含全勤 {bonus}, 加班費 {int(pay_ot)}")
