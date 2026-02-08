from datetime import datetime

def format_date(date):
    if isinstance(date, datetime):
        dt_obj = date
    else:
        dt_obj = datetime.fromisoformat(date)
    
    return dt_obj.strftime("%b %d, %Y")