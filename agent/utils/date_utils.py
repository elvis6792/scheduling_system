import datetime

def resolve_colloquial_date(d_str: str) -> str:
    today = datetime.date.today()
    weekdays = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
    
    for k, v in weekdays.items():
        if f"週{k}" in d_str or f"禮拜{k}" in d_str or f"拜{k}" in d_str:
            days_ahead = v - today.weekday()
            target_date = today + datetime.timedelta(days=days_ahead)
            return target_date.strftime("%Y-%m-%d")
            
    return d_str
