from datetime import datetime, timedelta

lot_number = "24306"

year, day = int("20" + lot_number[:2]), int(lot_number[2:])
date = datetime(year, 1, 1) + timedelta(day - 1)
