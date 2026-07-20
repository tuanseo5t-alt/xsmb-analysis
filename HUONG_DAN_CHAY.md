# Hướng dẫn chạy thử Vietnam Lottery (XSMB) Analysis

Dự án này lấy kết quả xổ số miền Bắc từ `minhngoc.net.vn`, lưu ra 3 định dạng (CSV/JSON/Parquet) và sinh phân tích thống kê (heatmap, top 10, distribution...).

> Lưu ý quan trọng: `minhngoc.net.vn` chỉ giữ cache **7 ngày gần nhất** cho mỗi URL. Mỗi lần chạy chỉ lấy được dữ liệu của những ngày còn nằm trong cache. Để có lịch sử đầy đủ, cần chạy script **đều đặn mỗi ngày** để tích lũy dữ liệu vào thư mục `data/`.

---

## 1. Yêu cầu môi trường

- Python **3.14**
- Hệ điều hành: Windows / Linux / macOS

Tất cả package cần thiết đã liệt kê trong `pyproject.toml`:

```
tzdata, pydantic, pydantic-settings, cloudscraper, tenacity,
beautifulsoup4, lxml, lunardate,
numpy, pandas, pyarrow, matplotlib, seaborn, jinja2
```

---

## 2. Cài đặt

### 2.1. Tạo môi trường ảo và cài package

**Windows (PowerShell):**

```powershell
cd c:\xamppp\htdocs\API\XSMB\vietnam-lottery-xsmb-analysis-main
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
```

**Linux / macOS:**

```bash
cd vietnam-lottery-xsmb-analysis-main
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

Nếu dùng `uv`:

```bash
uv sync
```

---

## 3. Chạy thử nhanh

### 3.1. Lấy dữ liệu (chỉ chạy 1 ngày cụ thể)

Mở `src/fetch.py`, ở đầu file đặt `START_DATE` để buộc chạy lại từ ngày đó:

```python
from datetime import date
START_DATE = date(2024, 2, 13)  # ngày này phải còn nằm trong cache 7 ngày của minhngoc
```

Rồi chạy:

```bash
cd src
python fetch.py
```

Script sẽ:

1. Fetch từng ngày bắt đầu từ `START_DATE` đến **ngày mới nhất có kết quả** (mặc định là hôm qua nếu chưa tới 18:35; sau 18:35 là hôm nay).
2. Bỏ qua Tết Nguyên Đán (5 ngày: 29, 30 tháng Chạp + 1, 2, 3 tháng Giêng âm lịch).
3. Cache theo URL (mỗi URL có thể chứa tới 7 ngày, tái sử dụng nếu trùng).
4. Ghi ra `data/xsmb.csv`, `data/xsmb.json`, `data/xsmb.parquet` (+ 2 bộ `xsmb-2-digits.*` và `xsmb-sparse.*`).

### 3.2. Lấy nhiều ngày liên tiếp

```python
START_DATE = date(2025, 7, 10)   # chạy từ ngày này
```

Sau đó chạy `python fetch.py` — script sẽ tự đi qua từng ngày cho đến hôm nay.

### 3.3. Chạy incremental (chỉ fetch ngày mới)

Để mặc định `START_DATE = None`. Script sẽ tự lấy `get_last_date()` từ `data/xsmb.json` nếu có, hoặc bắt đầu từ `2000-01-01` nếu chưa có data.

### 3.4. Chạy phân tích và render README

```bash
cd src
python analyze.py
```

Script sẽ sinh:

- 4 ảnh trong `images/`: `special_delta.jpg`, `special_delta_top_10.jpg`, `heatmap.jpg`, `top-10.jpg`, `distribution.jpg`, `delta.jpg`, `delta_top_10.jpg`
- File `README.md` ở thư mục gốc (render từ `src/templates/README.j2`).

---

## 4. Test nhanh parser (không cần network)

Tạo file `test_parser.py` ở thư mục gốc:

```python
import sys
sys.path.insert(0, r'src')

from datetime import date
from lottery import Lottery, is_tet

l = Lottery()
l.fetch(date(2025, 7, 15))
r = l._data.get(date(2025, 7, 15))
if r:
    print(r.thu, r.tinh, r.ngay_text, r.ky_hieu)
    print('DB:', r.special, 'G1:', r.prize1)
else:
    print('Không lấy được dữ liệu')

# Test Tết
for d in [date(2024, 2, 10), date(2024, 2, 11), date(2024, 2, 12), date(2024, 2, 13)]:
    print(d, 'Tết?', is_tet(d))
```

Chạy:

```bash
python test_parser.py
```

---

## 5. Cấu trúc dữ liệu xuất ra

Mỗi record trong `xsmb.json` có các trường:

| Trường | Kiểu | Mô tả |
|---|---|---|
| `date` | ISO date | Ngày quay |
| `thu` | string | Thứ (Thứ hai, Thứ ba, ..., Chủ nhật) |
| `tinh` | string | Luôn là `KẾT QUẢ XỔ SỐ Miền Bắc` |
| `ngay_text` | string | Chuỗi gốc từ web, ví dụ `Ngày: 01/01/2020` |
| `ky_hieu` | string | Ký hiệu trúng giải ĐB, ví dụ `9AP-3AP-1AP` |
| `special` | int | Giải đặc biệt (5 số) |
| `prize1` | int | Giải nhất (5 số) |
| `prize2_1`, `prize2_2` | int | Giải nhì (5 số × 2) |
| `prize3_1` … `prize3_6` | int | Giải ba (5 số × 6) |
| `prize4_1` … `prize4_4` | int | Giải tư (4 số × 4) |
| `prize5_1` … `prize5_6` | int | Giải năm (4 số × 6) |
| `prize6_1` … `prize6_3` | int | Giải sáu (3 số × 3) |
| `prize7_1` … `prize7_4` | int | Giải bảy (2 số × 4) |

Ngoài ra còn 2 file phái sinh:

- `xsmb-2-digits.*`: các giải đã lấy `% 100` (chỉ 2 số cuối).
- `xsmb-sparse.*`: bảng đếm tần suất 2 số cuối từ `00..99` cho mỗi ngày.

---

## 6. Workflow đề xuất (chạy hàng ngày)

**GitHub Actions** (đã có sẵn ở `.github/workflows/`):

- Hàng ngày chạy `python src/fetch.py` rồi `python src/analyze.py`.
- Commit lại `data/` và `images/` để tích lũy lịch sử.
- README sẽ tự cập nhật với ngày mới nhất.

**Chạy local thủ công:**

```bash
cd src
python fetch.py && python analyze.py
```

---

## 7. Xử lý lỗi thường gặp

| Lỗi | Nguyên nhân | Cách xử lý |
|---|---|---|
| `ModuleNotFoundError: No module named 'X'` | Thiếu dependency | `pip install -e .` (hoặc `uv sync`) |
| Không lấy được data cho ngày cũ | URL chỉ chứa 7 ngày gần nhất | Chạy `fetch.py` hàng ngày để tích lũy |
| Lỗi 403 / 503 từ minhngoc | Bị Cloudflare chặn | Đảm bảo `cloudscraper` đã cài đúng phiên bản |
| `pyarrow` lỗi khi ghi parquet | Thiếu pyarrow | `pip install pyarrow` |
| Plot không hiển thị trong README | Chưa chạy `analyze.py` | `python analyze.py` để sinh ảnh trong `images/` |
| Lỗi font tiếng Việt khi plot | Thiếu font hỗ trợ Unicode | Cài `matplotlib` kèm font có dấu (DejaVu Sans mặc định đã OK) |

---

## 8. Lệnh một dòng từ A → Z

```bash
# Cài
pip install -e .

# Lấy data (đặt START_DATE ở src/fetch.py trước nếu cần)
cd src && python fetch.py

# Phân tích + sinh ảnh + render README
python analyze.py
```