__author__ = 'Khiem Doan'
__github__ = 'https://github.com/khiemdoan'
__email__ = 'doankhiem.crazy@gmail.com'

from datetime import date

from pydantic import BaseModel, RootModel


class Result(BaseModel):
    date: date

    thu: str
    tinh: str
    ngay_text: str
    ky_hieu: str

    # Lưu dưới dạng chuỗi zero-padded để giữ nguyên số 0 ở đầu
    # (vd giải nhất "07533" không bị thành 7533 khi lưu file).
    special: str     # 5 số

    prize1: str      # 5 số

    prize2_1: str    # 5 số
    prize2_2: str

    prize3_1: str    # 5 số
    prize3_2: str
    prize3_3: str
    prize3_4: str
    prize3_5: str
    prize3_6: str

    prize4_1: str    # 4 số
    prize4_2: str
    prize4_3: str
    prize4_4: str

    prize5_1: str    # 4 số
    prize5_2: str
    prize5_3: str
    prize5_4: str
    prize5_5: str
    prize5_6: str

    prize6_1: str    # 3 số
    prize6_2: str
    prize6_3: str

    prize7_1: str    # 2 số
    prize7_2: str
    prize7_3: str
    prize7_4: str


class ResultList(RootModel):
    root: list[Result]