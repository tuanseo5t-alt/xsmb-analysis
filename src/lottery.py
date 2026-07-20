__author__ = 'Khiem Doan'
__github__ = 'https://github.com/khiemdoan'
__email__ = 'doankhiem.crazy@gmail.com'

from copy import copy
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup, Tag
from cloudscraper import CloudScraper
from lunardate import LunarDate

from dtos import Result, ResultList


def is_tet(selected_date: date) -> bool:
    """XSMB không quay trong dịp Tết Nguyên Đán.

    Nghỉ từ 29, 30 tháng Chạp (âm lịch) đến mùng 1, 2, 3 tháng Giêng (âm lịch).
    Tổng cộng 5 ngày nghỉ mỗi năm.
    """
    lunar = LunarDate.from_solar_date(selected_date.year, selected_date.month, selected_date.day)
    return (lunar.month == 12 and lunar.day in (29, 30)) or (lunar.month == 1 and lunar.day in (1, 2, 3))


# XSMB tạm dừng để phòng chống COVID-19 từ 01/4/2020 đến 22/4/2020,
# nghỉ theo công văn 39/BTT-XSMB của Hội đồng XSKT miền Bắc.
_COVID_SUSPENSION_RANGES: tuple[tuple[date, date], ...] = (
    (date(2020, 4, 1), date(2020, 4, 22)),
)


def is_covid_suspension(selected_date: date) -> bool:
    """Trả True nếu ngày đó rơi vào đợt XSMB tạm dừng vì COVID-19."""
    return any(start <= selected_date <= end for start, end in _COVID_SUSPENSION_RANGES)


def is_no_draw_day(selected_date: date) -> bool:
    """Ngày XSMB không tổ chức quay số (Tết hoặc dịp đặc biệt)."""
    return is_tet(selected_date) or is_covid_suspension(selected_date)


class Lottery:
    BASE_URL = 'https://www.minhngoc.net.vn/ket-qua-xo-so/mien-bac/{date:%d-%m-%Y}.html'

    HEADERS = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.minhngoc.net.vn/',
    }

    def __init__(self) -> None:
        self._http = CloudScraper()

        self._data: dict[date, Result] = {}

        self._raw_data: pd.DataFrame = pd.DataFrame()
        self._2_digits_data: pd.DataFrame = pd.DataFrame()
        self._sparse_data: pd.DataFrame = pd.DataFrame()

        self._begin_date = date.today()
        self._last_date = date.today()

    def load(self) -> None:
        try:
            with open('data/xsmb.json', 'r', encoding='utf-8') as f:
                data = ResultList.model_validate_json(f.read())
            for d in data.root:
                self._data[d.date] = d
            self.generate_dataframes()
        except FileNotFoundError:
            pass

    def dump(self) -> None:
        from pathlib import Path

        out_dir = Path(__file__).resolve().parent.parent / 'data'
        out_dir.mkdir(parents=True, exist_ok=True)

        def _dump(df: pd.DataFrame, file_name: str) -> None:
            df.to_csv(out_dir / f'{file_name}.csv', index=False)
            df.to_json(out_dir / f'{file_name}.json', orient='records', date_format='iso', indent=2)
            df.to_parquet(out_dir / f'{file_name}.parquet', index=False)

        _dump(self._raw_data, 'xsmb')
        _dump(self._2_digits_data, 'xsmb-2-digits')
        _dump(self._sparse_data, 'xsmb-sparse')

    def fetch(self, selected_date: date) -> None:
        if selected_date in self._data:
            return

        # XSMB không quay trong dịp Tết Nguyên Đán hoặc các đợt tạm dừng
        # (vd COVID-19 tháng 4/2020), bỏ qua.
        if is_no_draw_day(selected_date):
            return

        soup = self._fetch_soup(selected_date)
        if soup is None:
            return

        target = selected_date.strftime('%d/%m/%Y')
        # Mỗi box_kqxs trên trang là 1 ngày. Tìm box có td.ngay chứa ngày cần lấy.
        for box in soup.find_all('div', class_='box_kqxs'):
            tbl = box.find('table', class_='bkqtinhmienbac')
            if tbl is None:
                continue
            header_row = tbl.find('tr')
            if header_row is None:
                continue
            ngay_cell = header_row.find('td', class_='ngay')
            if ngay_cell is None:
                continue
            tngay_span = ngay_cell.find('span', class_='tngay')
            ngay_text = self._clean_text(tngay_span) if tngay_span else self._clean_text(ngay_cell)
            if target not in ngay_text:
                continue
            result = self._parse_box(box, selected_date, ngay_text)
            if result is not None:
                self._data[result.date] = result
            return

    def _fetch_soup(self, selected_date: date) -> Optional[BeautifulSoup]:
        """Tải trang tương ứng với `selected_date`. Mỗi ngày dùng URL riêng."""
        url = self.BASE_URL.format(date=selected_date)
        try:
            resp = self._http.get(url, headers=self.HEADERS, timeout=30)
        except Exception:
            return None
        if resp.status_code != 200:
            return None
        return BeautifulSoup(resp.text, 'lxml')

    def _parse_box(self, box: Tag, selected_date: date, ngay_text: str) -> Optional[Result]:
        tbl = box.find('table', class_='bkqtinhmienbac')
        if tbl is None:
            return None

        # Cấu trúc URL mới: thông tin nằm trong tr[0] của table.bkqtinhmienbac
        # td.thu = tên thứ, td.ngay > span.tngay = "Ngày: dd/mm/yyyy",
        #   > div.phathanh > div.loaive_content = ký hiệu trúng
        header_row = tbl.find('tr')
        thu_cell = header_row.find('td', class_='thu') if header_row else None
        ngay_cell = header_row.find('td', class_='ngay') if header_row else None

        thu = self._clean_text(thu_cell) if thu_cell else ''

        if ngay_cell is not None:
            tngay_span = ngay_cell.find('span', class_='tngay')
            ngay_text = self._clean_text(tngay_span) if tngay_span else ngay_text
            ky_hieu_el = ngay_cell.find('div', class_='loaive_content')
            ky_hieu = self._clean_text(ky_hieu_el) if ky_hieu_el else ''
        else:
            ky_hieu = ''

        title_a = box.find('div', class_='title')
        tinh = self._clean_text(title_a.find('a')) if title_a and title_a.find('a') else ''

        numbers = self._extract_prizes(tbl)
        if numbers is None:
            return None

        return Result(
            date=selected_date,
            thu=thu,
            tinh=tinh,
            ngay_text=ngay_text,
            ky_hieu=ky_hieu,
            special=numbers['db'][0],
            prize1=numbers['g1'][0],
            prize2_1=numbers['g2'][0], prize2_2=numbers['g2'][1],
            prize3_1=numbers['g3'][0], prize3_2=numbers['g3'][1], prize3_3=numbers['g3'][2],
            prize3_4=numbers['g3'][3], prize3_5=numbers['g3'][4], prize3_6=numbers['g3'][5],
            prize4_1=numbers['g4'][0], prize4_2=numbers['g4'][1], prize4_3=numbers['g4'][2], prize4_4=numbers['g4'][3],
            prize5_1=numbers['g5'][0], prize5_2=numbers['g5'][1], prize5_3=numbers['g5'][2],
            prize5_4=numbers['g5'][3], prize5_5=numbers['g5'][4], prize5_6=numbers['g5'][5],
            prize6_1=numbers['g6'][0], prize6_2=numbers['g6'][1], prize6_3=numbers['g6'][2],
            prize7_1=numbers['g7'][0], prize7_2=numbers['g7'][1], prize7_3=numbers['g7'][2], prize7_4=numbers['g7'][3],
        )

    @staticmethod
    def _clean_text(el: Optional[Tag]) -> str:
        if el is None:
            return ''
        return el.get_text(' ', strip=True)

    @staticmethod
    def _parse_prize_cell(td: Tag, expected_length: int) -> list[str]:
        """Tách các ô giải thành token số nguyên dạng chuỗi.

        Trả về `None` nếu số lượng token không khớp `expected_count` hoặc
        có token nào không đúng `expected_length` ký tự (zero-padded).
        Trả về chuỗi rỗng nếu ô rỗng.
        """
        raw = td.get_text(' ', strip=True)
        tokens = [t for t in raw.split() if t.isdigit()]
        if len(tokens) == 0:
            return []
        for t in tokens:
            if len(t) != expected_length:
                raise ValueError(
                    f'Prize token "{t}" has length {len(t)}, expected {expected_length}'
                )
        return tokens

    def _extract_prizes(self, tbl: Tag) -> Optional[dict[str, list[str]]]:
        # Định dạng: (key, class_name, expected_count, expected_token_length)
        spec = (
            ('db', 'giaidb', 1, 5),
            ('g1', 'giai1', 1, 5),
            ('g2', 'giai2', 2, 5),
            ('g3', 'giai3', 6, 5),
            ('g4', 'giai4', 4, 4),
            ('g5', 'giai5', 6, 4),
            ('g6', 'giai6', 3, 3),
            ('g7', 'giai7', 4, 2),
        )
        result: dict[str, list[str]] = {}
        for key, cls, count, length in spec:
            td = tbl.find('td', class_=cls)
            if td is None:
                return None
            nums = self._parse_prize_cell(td, length)
            if len(nums) != count:
                return None
            result[key] = nums
        return result

    def generate_dataframes(self) -> None:
        if not self._data:
            return
        self._raw_data = pd.DataFrame([d.model_dump() for d in self._data.values()])
        self._raw_data['date'] = pd.to_datetime(self._raw_data['date'])

        # Mỗi cột giải có độ dài cố định (5/5/5/5/4/4/3/2). Khi tách 2 số cuối,
        # ta lấy đúng 2 ký tự cuối của chuỗi zero-padded.
        numeric_cols = [c for c in self._raw_data.columns if c not in ('date', 'thu', 'tinh', 'ngay_text', 'ky_hieu')]

        self._2_digits_data = copy(self._raw_data)
        # Lấy 2 ký tự cuối của mỗi chuỗi số rồi ép kiểu int (lúc này an toàn).
        self._2_digits_data[numeric_cols] = self._2_digits_data[numeric_cols].apply(
            lambda x: x.str[-2:].astype(int)
        )

        self._sparse_data = pd.concat(
            [
                self._2_digits_data.iloc[:, 0:1],
                pd.DataFrame(np.zeros((self._2_digits_data.shape[0], 100), dtype=int)),
            ],
            axis=1,
        )
        self._sparse_data.iloc[:, 1:] = self._sparse_data.iloc[:, 1:].astype('int64')
        for i in range(self._2_digits_data.shape[0]):
            counts = self._2_digits_data[numeric_cols].iloc[i].value_counts()
            for k, v in counts.items():
                self._sparse_data.iloc[i, k + 1] = int(v)

        begin_date = self._raw_data['date'].min()
        self._begin_date = begin_date.to_pydatetime().date()
        last_date = self._raw_data['date'].max()
        self._last_date = last_date.to_pydatetime().date()

    def get_raw_data(self) -> pd.DataFrame:
        return self._raw_data

    def get_2_digits_data(self) -> pd.DataFrame:
        return self._2_digits_data

    def get_sparse_data(self) -> pd.DataFrame:
        return self._sparse_data

    def get_last_date(self) -> date:
        return self._last_date