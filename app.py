import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- 輔助函式：時間計算 ---
def parse_time(t_str):
    """將字串 (例如 '15:30') 轉為時間物件，若空白則回傳 None"""
    if pd.isna(t_str) or str(t_str).strip() == "":
        return None
    try:
        t_str = str(t_str).strip()
        # 處理 Excel 有時會出現的秒數 (e.g., 15:30:00)
        if len(t_str) > 5:
            t_str = t_str[:5]
        return datetime.strptime(t_str, "%H:%M")
    except:
        return None

def calc_diff_minutes(start_t, end_t):
    """計算兩個時間的差距(分鐘)，自動處理跨日 (例如 23:00 到 00:30)"""
    if not start_t or not end_t:
        return 0
    
    # 建立假日期以便計算
    dummy_date = datetime(2000, 1, 1)
    dt_start = dummy_date.replace(hour=start_t.hour, minute=start_t.minute)
    dt_end = dummy_date.replace(hour=end_t.hour, minute=end_t.minute)
    
    if dt_end < dt_start:
        dt_end += timedelta(days=1) # 跨日加一天
        
    diff = dt_end - dt_start
    return diff.total_seconds() / 60

# --- 班別設定資料庫 ---
# 格式: [ (上班1, 下班1), (上班2, 下班2) ]
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
        "D": [("10:30", "15:00"), ("17:00", "00:00")], # 修正 23:60 為 00:00
        "E": [("11:00", "15:00"), ("17:30", "00:30")],
        "F": [("10:30", "15:00"), ("17:00", "22:30")],
        "G": [("11:00", "15:30"), ("17:30", "23:30")],
    }
}

# --- 頁面設定 ---
st.set_page_config(page_title="箱舟燒肉 - 智慧薪資表", layout="wide")
st.title("🥩 箱舟燒肉 - 員工出勤試算 (Excel 貼上版)")

# --- 側邊欄：設定 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    
    # 選擇部門 (影響班別選單)
    dept = st.radio("選擇部門", ["內場", "外場"])
    
    st.divider()
    base_wage = st.number_input("時薪 (NTD)", value=190)
    ot_rate = st.number_input("加班費率", value=1.34)
    late_fee = st.number_input("遲到扣款 (元/分)", value=5)
    full_attend_bonus = st.number_input("全勤獎金", value=2000)

    st.info(f"目前顯示【{dept}】的班別規則")

# --- 初始化表格數據 ---
if 'df_data' not in st.session_state:
    # 預設生成 31 天空資料
    # 為了方便 Excel 貼上，欄位設為單純的 String
    rows = []
    for i in range(1, 32):
        rows.append([i, "", "", "", "", "", ""]) 
    st.session_state.df_data = pd.DataFrame(
        rows, 
        columns=["日期", "班別", "時段1上班", "時段1下班", "時段2上班", "時段2下班", "補休時數"]
    )

# --- 主畫面 ---

st.markdown("### 1️⃣ 輸入出勤紀錄")
st.caption("💡 提示：您可以直接從 Excel 複製「班別」與「打卡時間」區域，直接點選下方表格貼上 (Ctrl+V)。")

column_config = {
    "日期": st.column_config.NumberColumn(disabled=True, width="small"),
    "班別": st.column_config.TextColumn(help="填入 A, B, C...", width="small"),
    "時段1上班": st.column_config.TextColumn(help="輸入 15:30"),
    "時段1下班": st.column_config.TextColumn(help="輸入 23:30"),
    "時段2上班": st.column_config.TextColumn(help="雙頭班才填"),
    "時段2下班": st.column_config.TextColumn(help="雙頭班才填"),
    "補休時數": st.column_config.NumberColumn(format="%.1f")
}

edited_df = st.data_editor(
    st.session_state.df_data,
    column_config=column_config,
    num_rows="dynamic",
    height=500,
    hide_index=True
)

# --- 計算核心邏輯 ---
st.divider()
st.markdown("### 2️⃣ 計算結果")

if st.button("🚀 開始計算薪資與考勤"):
    
    total_work_hours = 0
    total_ot_hours = 0
    total_late_mins = 0
    total_comp_hours = 0 # 補休
    
    log_details = [] # 用來存詳細計算過程
    
    current_rules = SHIFTS_DB[dept]
    
    for index, row in edited_df.iterrows():
        shift_code = str(row["班別"]).strip().upper()
        date_num = row["日期"]
        comp_h = float(row["補休時數"]) if row["補休時數"] else 0
        total_comp_hours += comp_h
        
        # 如果沒填班別，跳過
        if not shift_code or shift_code not in current_rules:
            continue
            
        # 取得該班別的標準時間 (List of tuples)
        rule_times = current_rules[shift_code]
        # 轉換使用者輸入的時間
        user_times = [
            (parse_time(row["時段1上班"]), parse_time(row["時段1下班"])),
            (parse_time(row["時段2上班"]), parse_time(row["時段2下班"]))
        ]
        
        day_late = 0
        day_work = 0
        day_ot = 0
        
        # 比對每個時段 (內場A班只有一個時段，C班有兩個)
        for i in range(len(rule_times)):
            # 標準時間
            std_in_str, std_out_str = rule_times[i]
            std_in = datetime.strptime(std_in_str, "%H:%M")
            std_out = datetime.strptime(std_out_str, "%H:%M")
            
            # 使用者打卡時間 (如果使用者沒填第二段，就跳過)
            act_in, act_out = user_times[i]
            
            if act_in and act_out:
                # 1. 計算工時 (實際上班 - 實際下班)
                work_mins = calc_diff_minutes(act_in, act_out)
                day_work += (work_mins / 60)
                
                # 2. 計算遲到 (實際上班 > 標準上班)
                # 這裡要小心跨日問題，但上班通常不會跨日跨太遠，簡單比對即可
                # 為了精準，我們把標準時間的日期設為跟 act_in 一樣 (或是 dummy)
                dummy = datetime(2000, 1, 1)
                t_std_in = dummy.replace(hour=std_in.hour, minute=std_in.minute)
                t_act_in = dummy.replace(hour=act_in.hour, minute=act_in.minute)
                
                if t_act_in > t_std_in:
                    diff = (t_act_in - t_std_in).total_seconds() / 60
                    day_late += diff
                
                # 3. 計算加班 (實際下班 > 標準下班)
                # 處理跨日：如果標準是 00:00，實際是 00:30
                # 邏輯：計算 (實際下班 - 標準下班) 的分鐘數
                
                # 特殊處理：如果標準下班是 00:00 (視為隔天)
                t_std_out = dummy.replace(hour=std_out.hour, minute=std_out.minute)
                t_act_out = dummy.replace(hour=act_out.hour, minute=act_out.minute)
                
                # 判斷是否跨日 (例如標準 23:00, 實際 00:30 -> 實際比較小，所以實際要+1天)
                if std_out.hour >= 12 and act_out.hour < 12:
                     t_act_out += timedelta(days=1)
                
                # 判斷標準本身是否跨日 (例如標準是 17:00 ~ 00:00)
                if std_out.hour < std_in.hour:
                    t_std_out += timedelta(days=1)
                    if act_out.hour < 12: # 實際也是隔天
                        # 已經在上面處理過 t_act_out 嗎？
                        # 如果 t_std_out 已經加一天了，t_act_out 也要確保邏輯正確
                        # 簡單法：算出差距，如果是正的就算加班
                         pass
                    else:
                        # 標準跨日(到隔天0點)，但實際還在當天(例如23:50)，這樣沒加班
                        pass
                
                # 計算差距
                ot_mins = (t_act_out - t_std_out).total_seconds() / 60
                if ot_mins > 0:
                    day_ot += (ot_mins / 60)

        total_work_hours += day_work
        total_ot_hours += day_ot
        total_late_mins += day_late
    
    # --- 薪資計算 ---
    # 正常工時扣除加班時數 (假設 total_work_hours 包含了加班時間，需還原成正常工時計薪，或依您規則)
    # 這裡假設：正常工時費 = (總工時 - 加班工時) * 時薪
    # 加班費 = 加班工時 * 時薪 * 倍率
    
    regular_hours = total_work_hours - total_ot_hours
    salary_regular = regular_hours * base_wage
    salary_ot = total_ot_hours * base_wage * ot_rate
    deduction = total_late_mins * late_fee
    bonus = full_attend_bonus if total_late_mins == 0 else 0
    
    final_pay = salary_regular + salary_ot + bonus - deduction
    
    # --- 顯示報告 ---
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### ⏱️ 時數統計")
        st.write(f"總工時: **{total_work_hours:.1f}** 小時")
        st.write(f"加班: **{total_ot_hours:.1f}** 小時")
        st.write(f"補休累積: **{total_comp_hours:.1f}** 小時")
        
    with col2:
        st.markdown("#### ⚠️ 異常考勤")
        if total_late_mins > 0:
            st.error(f"遲到: {int(total_late_mins)} 分鐘")
            st.write(f"扣款: -${int(deduction)}")
        else:
            st.success("無遲到紀錄")
            
    with col3:
        st.markdown("#### 💰 薪資預估")
        st.write(f"本薪: ${int(salary_regular):,}")
        st.write(f"加班費: ${int(salary_ot):,}")
        st.write(f"全勤: ${bonus} " + ("✅" if bonus>0 else "❌"))
        st.markdown(f"### 實領: ${int(final_pay):,}")

    # 除錯用：顯示判讀結果 (可選)
    # st.write("系統判讀明細:", log_details)
