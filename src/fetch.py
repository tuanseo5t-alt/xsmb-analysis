__author__ = 'Khiem Doan'
__github__ = 'https://github.com/khiemdoan'
__email__ = 'doankhiem.crazy@gmail.com'

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from lottery import Lottery, is_tet, is_covid_suspension, is_no_draw_day

from datetime import date
START_DATE = date(2020, 1, 1)  # None = bắt đầu từ dữ liệu hiện có; hoặc truyền date(...) để build lại từ đầu
END_DATE = None                 # None = đến hôm nay; truyền date(...) để giới hạn ngày kết thúc


if __name__ == '__main__':
    lottery = Lottery()
    lottery.load()

    tz = ZoneInfo('Asia/Ho_Chi_Minh')
    now = datetime.now(tz)
    last_date = now.date()
    if now.time() < time(18, 35):
        last_date -= timedelta(days=1)

    if START_DATE is not None:
        begin_date = START_DATE
    elif not lottery.get_raw_data().empty:
        begin_date = lottery.get_last_date()
    else:
        # Không có dữ liệu cũ -> build lại từ đầu (minhngoc lưu từ ~2000)
        from datetime import date as _date
        begin_date = _date(2000, 1, 1)
        # Xóa dữ liệu cũ để build lại hoàn toàn
        lottery._data.clear()

    end_date = END_DATE if END_DATE is not None else last_date
    delta = (end_date - begin_date).days + 1
    for i in range(1, delta):
        selected_date = begin_date + timedelta(days=i)
        if is_tet(selected_date):
            print(f'Skip (Tết): {selected_date}')
            continue
        if is_covid_suspension(selected_date):
            print(f'Skip (COVID): {selected_date}')
            continue
        print(f'Fetching: {selected_date}')
        lottery.fetch(selected_date)

    lottery.generate_dataframes()
    lottery.dump()