# Báo cáo Day 09 — Vũ Thị Nhung, 2A202603156

## 1. Kết luận trước

Pipeline kết luận **Hold** (mã thoát `10`). Đầu vào có **224 ảnh** (`data/raw/`), ở bước 1 (`intake`) máy loại **22/224 ảnh** bị lỗi nặng cấp ảnh (2 ảnh hỏng, 3 ảnh quá nhỏ, 8 ảnh trùng byte, 4 ảnh trùng gần đúng, 5 ảnh rò rỉ từ tập test) và giữ lại **202/224 ảnh**. Cuối pipeline xuất bản nháp **202 ảnh** (tổng cộng 748 box: 101 `car`, 574 `person`, 41 `truck`, 32 `bus`) ra `submission/export/clean_v1/`.

**Lý do chính:** Sau khi máy tự sửa hết lỗi cú pháp (35 thay đổi trong `03_fixes.csv`) và người duyệt hết ngân sách **80/125 ảnh** trong hàng đợi (đã gán xong toàn bộ 6/6 ảnh thiếu file nhãn `MISSING_LABEL_FILE`), bộ dữ liệu **không còn lỗi bắt buộc nào (`0 lỗi error`)**, nhưng vẫn còn **38/202 ảnh (18.81%)** có cảnh báo chưa được người duyệt, vượt ngưỡng `warn_ratio_hold = 10.0%`.

## 2. Lỗi và phân việc

Số liệu lấy từ `submission/reports/02_error_list_v1.txt` (trước khi sửa tự động):

| Mã lỗi | Số ảnh / dòng (kèm mẫu số) | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `CORRUPT_IMAGE` | 2 / 224 ảnh (`img_0010`, `img_0136`) | Máy (`intake` / `remove_image`) | File ảnh hỏng không mở được khi gọi `im.load()`, máy bắt chính xác và loại ngay từ đầu. |
| `BAD_SIZE` | 3 / 224 ảnh (`img_0107`, `img_0113`, `img_0122`) | Máy (`intake` / `remove_image`) | Cạnh ngắn của ảnh `< 250px` (180px và 226px), không đạt chuẩn độ phân giải của dự án. |
| `DUP_IMAGE_EXACT` | 8 / 224 ảnh | Máy (`intake` / `remove_image`) | Trùng mã băm `md5` từng byte với ảnh đã có trước đó, máy giữ ảnh đầu và xoá bản trùng. |
| `DUP_IMAGE_NEAR` | 4 / 224 ảnh (`img_0076`, `img_0143`, `img_0186`, `img_0223`) | Máy (`intake` / `remove_image`) | Trùng gần đúng (`phash_dist <= 10`) do thu nhỏ hoặc chỉnh sáng nhẹ, máy tự loại ảnh sau. |
| `LEAK_TEST` | 5 / 224 ảnh (`img_0049`, `img_0101`, `img_0167`, `img_0174`, `img_0221`) | Máy (`intake` / `remove_image`) | Trùng với ảnh trong `data/test/images`, bắt buộc xoá để tránh rò rỉ tập test làm lệch kết quả đo. |
| `BAD_CLASS_NAME` | 2 lỗi / 4 lớp trong `data.yaml` (`Person`, `Bus`) | Máy (`autofix`: `rename_classes`) | Sai chữ hoa/thường trong `data.yaml`, máy ghi lại đúng danh sách `[car, person, truck, bus]`. |
| `BAD_FORMAT` | 3 dòng / 3 ảnh trên 202 ảnh (`img_0014`, `img_0022`, `img_0179`) | Máy (`autofix`: `drop_line`) | Dòng nhãn bị thiếu cột (4 cột) hoặc chứa `nan`, không đọc được toạ độ nên máy xoá dòng. |
| `BAD_CLASS_ID` | 6 dòng / 6 ảnh trên 202 ảnh (id `-1`, `4`, `7`, `93`) | Máy (`autofix`: `drop_line`) | ID lớp nằm ngoài `0..3`, máy xoá dòng hỏng và cộng điểm ưu tiên để người kiểm tra lại ảnh đó. |
| `BOX_ZERO` | 4 dòng / 4 ảnh trên 202 ảnh (`w = 0` hoặc `h = 0`) | Máy (`autofix`: `drop_line`) | Box có chiều rộng hoặc chiều cao bằng 0, không có diện tích nên máy xoá dòng. |
| `DUP_BOX` | 7 dòng / 7 ảnh trên 202 ảnh (`IoU > 0.90` cùng lớp) | Máy (`autofix`: `drop_line`) | Hai box cùng lớp chồng khít lên nhau (`IoU` từ 0.927 đến 0.995), máy xoá dòng lặp phía sau. |
| `BOX_OUT_OF_IMAGE` | 8 dòng / 8 ảnh trên 202 ảnh (tràn `0.023`–`0.060`) | Máy (`autofix`: `clip_box`) | Mép box tràn nhẹ ra ngoài biên `[0, 1]`, máy cắt phần tràn về biên `[0, 1]` và giữ nguyên lớp. |
| `MISSING_LABEL_FILE` | 6 / 202 ảnh (`img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`) | Máy ghi `needs_label` -> Người gán | Máy không thể tự đoán nhãn và không được tạo file `.txt` rỗng (rỗng nghĩa là ảnh nền), nên phải đẩy lên đầu hàng đợi cho người gán. |
| `BOX_HUGE` | 3 dòng / 3 ảnh trên 202 ảnh (`w * h > 0.95`) | Người (`review_queue`) | Box chiếm gần hết ảnh, cần người xem là vật thể lớn thật (như xe buýt chụp gần) hay khung vẽ lỗi. |
| `BOX_TINY` | 6 dòng / 6 ảnh trên 202 ảnh ở v1 (7 dòng ở v2 sau khi clip) | Người (`review_queue`) | Cạnh ngắn `< 12px`, cần người xem vật ở xa có cần giữ lại theo guideline hay xoá. |
| `CLASS_RARE` | 4 mã lớp lạ ở v1 (`-1`, `4`, `7`, `93` có `< 5` box; sang v2 còn 0) | Máy (tự hết sau khi xoá `BAD_CLASS_ID`) | Cảnh báo thống kê cấp `<dataset>` do đếm cả các token lớp sai trước khi `autofix` xoá dòng. |
| `EMPTY_LABEL` | 12 / 202 ảnh ở v1 (15 / 202 ảnh ở v2 sau khi xoá dòng lỗi) | Người (`review_queue`) | File nhãn rỗng, cần người nhìn ảnh để phân biệt ảnh nền thật hay ảnh bị thiếu nhãn. |
| `POSSIBLE_FALSE_POS` | 25 dòng / 21 ảnh trên 202 ảnh (24 dòng ở v2) | Người (`review_queue`) | Box nhãn không khớp dự đoán nào của model `yolo26l` (`conf >= 0.10`), nghi gán nhầm nền hoặc vật ngoài 4 lớp. |
| `POSSIBLE_LOOSE_BOX` | 28 dòng / 26 ảnh trên 202 ảnh | Người (`review_queue`) | Nhãn cùng lớp với model nhưng `0.30 <= IoU < 0.50`, nghi vẽ box bị lỏng hoặc lệch. |
| `POSSIBLE_MISSING` | 53 dòng / 45 ảnh trên 202 ảnh | Người (`review_queue`) | Model `yolo26l` thấy vật (`conf >= 0.60`, diện tích `>= 600 px²`) nhưng nhãn không có box, cần người xem và vẽ thêm. |
| `POSSIBLE_WRONG_CLASS` | 18 dòng / 18 ảnh trên 202 ảnh | Người (`review_queue`) | Box khớp vị trí (`IoU >= 0.50`) nhưng khác lớp giữa nhãn và model, cần người quyết định lớp đúng. |

**Giải thích hàng đợi `05_review_queue.csv` và kết quả duyệt 80 ảnh:**
* `review_queue.py` xếp hạng ảnh theo tổng điểm: mỗi cảnh báo cộng `weight * (1 + conf)` (`WRONG_CLASS: 3`, `MISSING: 2`, `FALSE_POS: 2`, `LOOSE_BOX: 1.5`, `EMPTY_LABEL: 1`), cộng thêm điểm nếu ảnh vừa bị máy sửa (`FIXED_DROP_LINE: +2`, `FIXED_CLIP_BOX: +1`) và cộng `NEEDS_LABEL: +10` cho ảnh thiếu file nhãn. Vì vậy `img_0020` xếp đầu bảng (`priority = 11.524` do có cả `FIXED_DROP_LINE`, `POSSIBLE_MISSING` và `POSSIBLE_WRONG_CLASS` với `conf = 0.95`), tiếp theo ở vị trí 2 đến 7 là toàn bộ **6 ảnh `NEEDS_LABEL` (`priority = 10.0`)** để người duyệt luôn gán nhãn cho ảnh thiếu file trước tiên.
* Với ngân sách **80/125 ảnh**, so sánh `04_error_list_v2.txt` và `07_error_list_v3.txt` cho thấy người duyệt đã xử lý xong **6/6 ảnh `MISSING_LABEL_FILE` (100%)**, đồng thời giải quyết được phần lớn các lỗi ngữ nghĩa nặng: `POSSIBLE_WRONG_CLASS` giảm từ **18 xuống 3 dòng** (sửa được 15/18 = 83.3%), `POSSIBLE_MISSING` giảm từ **53 xuống 13 dòng** (sửa được 40/53 = 75.5%), `EMPTY_LABEL` giảm từ **15 xuống 4 ảnh** (sửa được 11/15 = 73.3%), `POSSIBLE_LOOSE_BOX` giảm từ **28 xuống 20 dòng** và `POSSIBLE_FALSE_POS` giảm từ **24 xuống 21 dòng**. Tổng số cảnh báo giảm từ **145 dòng (trên 119 ảnh)** xuống còn **71 dòng (trên 38 ảnh chưa duyệt)**.

## 3. Calibration (2 ngưỡng)

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước -> sau) | Lý do (đánh đổi) |
|---|---:|---:|---|---|
| `duplicates.phash_dist` | 2 | **10** | `DUP_IMAGE_NEAR`: `1.00 / 0.50` (F1 `0.67`) -> **`1.00 / 0.67`** (F1 `0.80`) | Đây là lỗi `ERROR` làm máy tự động xoá ảnh ở bước `intake`, nên phải ưu tiên giữ `Precision = 1.00` để không xoá nhầm ảnh sạch. Tăng từ `2` lên `10` giúp bắt thêm các ảnh gần trùng trên cả `calib` (Recall tăng từ `0.50` lên `0.67`) lẫn `raw` (bắt thêm cặp trùng thật `img_0223` – `img_0077` ở `dist=6`, `img_0186` – `img_0061` ở `dist=10` và ảnh rò rỉ `img_0101` trùng `test/test_039.jpg`) mà chưa phát sinh báo động giả. |
| `second_opinion.conf` | 0.25 | **0.60** | • `MISSING`: `0.50 / 1.00` -> **`0.57 / 1.00`** (F1 `0.73`)<br>• `WRONG_CLASS`: `0.56 / 0.83` -> **`0.62 / 0.83`** (F1 `0.71`)<br>• `LOOSE_BOX`: `0.29 / 0.40` -> `0.20 / 0.20` | Ở mức `0.25`, model báo động giả quá nhiều (`FP = 8` ở `MISSING`, `FP = 4` ở `WRONG_CLASS`) làm tốn ngân sách duyệt 80 ảnh. Chọn `0.60` giúp tăng Precision lên `0.57` và `0.62` trong khi vẫn giữ nguyên Recall cao nhất cho 2 lỗi quan trọng nhất (`MISSING` giữ `R = 1.00`, `WRONG_CLASS` giữ `R = 0.83`). Không tăng lên `0.70` hay `0.80` vì lúc đó Recall của `POSSIBLE_MISSING` bị tụt xuống `0.88` và `0.75` (bỏ sót nhiều vật thể thiếu nhãn để đổi lấy hàng đợi ngắn giả tạo). |

**Điểm đánh lừa của Calibration và bằng chứng trên dữ liệu:**
Trên bảng sweep của tập `data/calib` (39 ảnh), ngưỡng `duplicates.phash_dist = 16` cho kết quả đẹp nhất với `Precision = 1.00, Recall = 0.83, F1 = 0.91` (không có báo động giả nào trên 39 ảnh). Nhưng vì `calib` chỉ có 39 ảnh nên số cặp ảnh đem so sánh rất ít. Khi thử áp `phash_dist = 16` lên tập `data/raw` (224 ảnh tự so với nhau và so với 140 ảnh `test`/`gold_val`), số ảnh bị quy là trùng và rò rỉ nhảy từ **17 ảnh (ở mức 10) lên 26 ảnh (+9 ảnh bị xoá nhầm)**:
* `LEAK_TEST` tăng vọt từ 5 lên 11 ảnh (6 ảnh bình thường gồm `img_0013`, `img_0017`, `img_0021`, `img_0033`, `img_0038`, `img_0115` bị báo nhầm là trùng tập test).
* `DUP_IMAGE_NEAR` tăng từ 4 lên 7 ảnh: khi mở xem trực tiếp các cặp bị bắt ở `dist = 16`, đó là những ảnh hoàn toàn khác nhau, ví dụ `img_0011.jpg` (cầu thủ đánh tennis trên sân xanh) bị báo trùng với `img_0008.jpg` (hai người trượt tuyết trên núi tuyết), hay `img_0084` bị báo trùng với `img_0074`.
* Trong khi đó ở `phash_dist = 10`, mở xem cặp `img_0186.jpg` – `img_0061.jpg` (`dist = 10`, cùng cảnh cô gái ngồi ghế công viên) và `img_0223.jpg` – `img_0077.jpg` (`dist = 6`, cùng cảnh xe buýt trước tháp đồng hồ nhưng khác độ sáng) thì đều là ảnh trùng thật. Do đó chọn `phash_dist = 10` là hợp lý nhất.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

**(a) Chứng minh cửa chặn (`gate`) chặn đúng khi còn lỗi bắt buộc:**
Khi chạy lệnh tắt ngân sách người duyệt (`--budget 0`):
```bash
python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb
```
Ở bước `autofix`, 6 ảnh không có file nhãn (`MISSING_LABEL_FILE`: `img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`) chỉ được ghi log `needs_label` chứ máy không tự tạo file `.txt`. Vì `--budget 0` nên không có người gán nhãn cho 6 ảnh này. Đến bước 4 vòng 3, `gate.decide` thấy còn `n_errors = 6` lỗi bắt buộc nên kết luận **Rework** (`"còn 6 lỗi bắt buộc chưa được xử lý (cảnh báo chưa duyệt: 112/202 ảnh)"`), trả về **mã thoát `20`**, in thông báo `KHÔNG xuất: còn lỗi bắt buộc (Rework)` và thư mục `work/exp_nb/clean_v1/` hoàn toàn không được tạo ra (`exported: null` trong `work/rep_nb/08_summary.json`).

**(b) Ba lỗi tự nhìn thấy trên `work/viz/*.png` và các điểm mù của pipeline:**
* **Ba lỗi quan sát bằng mắt thường khi mở ảnh `work/viz/` ở Bước 1:**
  1. `work/viz/img_0020.png`: Khung số 3 vẽ người phụ nữ áo xanh ghi nhãn `3:93` (sai ID lớp -> máy bắt được bằng `BAD_CLASS_ID`), còn chiếc xe buýt màu cam *"Metro Local"* lại gán là `1:truck` thay vì `bus` (lỗi ngữ nghĩa -> cần `second_opinion` báo `POSSIBLE_WRONG_CLASS` để người sửa).
  2. `work/viz/img_0001.png` và `img_0005.png`: Ở `img_0001.png`, người mặc quân phục đứng bên phải bị bỏ sót không có box (`POSSIBLE_MISSING`); ở `img_0005.png`, chiếc trụ màu xanh trắng trên vỉa hè trái bị vẽ nhầm box `3:person` (`POSSIBLE_FALSE_POS`).
  3. `work/viz/img_0015.png`: Khung `3:person` của người đánh bóng chày chỉ bao nửa người trên và cắt lẹm vào lưng trọng tài áo xanh đứng trước, đồng thời thiếu box riêng cho trọng tài.
* **Các điểm mù mà pipeline KHÔNG bắt được (kèm bằng chứng):**
  1. **Ảnh trùng nhưng bị cắt (crop) mạnh hoặc biến đổi nhiều (`DUP_IMAGE_NEAR`):** Trong `data/calib/MANIFEST.csv` có 6 ảnh gần trùng nhưng ở `phash_dist = 10` (kể cả tăng lên `14`), check `duplicates` vẫn bỏ sót **2/6 ảnh (`FN = 2`, Recall = 0.67)** là `calib_037` (biến đổi mức 3 của `calib_015`) và `calib_038` (biến đổi mức 4 của `calib_024`) vì khi ảnh bị cắt sâu, giá trị pHash thay đổi lớn làm khoảng cách Hamming vượt quá ngưỡng an toàn.
  2. **Box lỏng vừa phải hoặc lệch khi hai vật che khuất nhau (`POSSIBLE_LOOSE_BOX`):** Trên tập `calib`, ở `conf = 0.60`, check `second_opinion` chỉ bắt được **1/5 lỗi `LOOSE_BOX` (`TP = 1, FN = 4`, Recall = 0.20)**, bỏ sót các ca như `calib_002` (dòng 3, `scale = 1.54`), `calib_006` (dòng 1, `scale = 1.48`), `calib_012` (dòng 1, `scale = 1.45`) vì IoU giữa box phình nhẹ với box của model vẫn đạt quanh ngưỡng `iou_loose = 0.50` hoặc `conf` của model thấp hơn `0.60`.
  3. **Lỗi nhầm lớp hoặc thiếu nhãn khi chính model `yolo26l` cũng nhầm hoặc vật nhỏ `< 600 px²`:** Trên `data/calib`, `POSSIBLE_WRONG_CLASS` luôn bị sót **1/6 lỗi (`FN = 1`, Recall tối đa `0.83` ở mọi mức `conf` từ `0.10` đến `0.80`)** do model checker không dự đoán ra lớp đúng tại vị trí đó; ngoài ra các vật thể thật ở xa có diện tích `< 600 px²` (`min_area_px`) đều bị bỏ qua nên nếu nhãn gốc thiếu các vật nhỏ này thì pipeline cũng không báo.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)

**Chưa chạy.** Lý do: máy cá nhân không có GPU rời nên mình tập trung hoàn thành và kiểm tra kỹ phần lõi của pipeline (`make check-core`).

## 6. Quyết định và ghi chú AI

**(a) Quyết định cuối cùng và điều kiện để đổi thành Release:**
* Quyết định cuối cùng là **Hold** — giữ bộ dữ liệu ở trạng thái bản nháp (`submission/export/clean_v1/`), chưa phát hành chính thức.
* Để chuyển từ **Hold** sang **Release**, tỉ lệ ảnh còn cảnh báo chưa duyệt phải `< 10.0%` trên tổng số 202 ảnh, tức là tối đa chỉ được còn **20 ảnh** (`20 / 202 = 9.90% < 10.0%`). Hiện tại sau khi duyệt 80 ảnh vẫn còn **38 ảnh** có cảnh báo, nên cần **tăng ngân sách người duyệt thêm tối thiểu 18–19 ảnh nữa (nâng tổng số ảnh duyệt từ 80 lên 98–99 ảnh)** để duyệt tiếp các ảnh từ dòng 81 đến dòng 99 trong `05_review_queue.csv`.

**(b) Ghi chú dùng AI:**
* **Prompt chính:** Dán docstring + unit test của từng module (`label_format.py`, `gate.py`, `autofix.py`, `second_opinion.py`) và yêu cầu viết hàm Python đọc ngưỡng từ `cfg`, trả về đúng cấu trúc `Issue` / `dict`, chỉ sửa trong thư mục làm việc `ds` (không đụng vào `data/raw`), xử lý dòng trống ở giữa file và dòng dính nhiều lỗi.
* **Cách kiểm code AI:** Tự đọc lại từng dòng code xem có lệnh xoá nhầm file hay viết cứng ngưỡng không, sau đó chạy `pytest` cho từng file test, tự chạy thử thêm ca biên (1 dòng vừa tràn ảnh vừa lặp box) và đối chiếu kết quả trên tập `data/calib` và `data/raw`.
* **Một lần AI sai:** Khi viết `label_format.py`, ban đầu AI đặt lệnh `continue` ngay sau khi bắt lỗi `BOX_OUT_OF_IMAGE` nên nếu 1 dòng vừa tràn mép ảnh vừa trùng với dòng trên (`DUP_BOX`) thì bị bỏ sót lỗi `DUP_BOX` (dẫn tới `autofix` chỉ cắt box thay vì xoá dòng lặp); mình đã xoá `continue` ở nhánh tràn mép để kiểm tra tiếp `DUP_BOX` và vượt qua `test_line_with_two_errors_is_dropped_once_and_not_clipped`.
* **CVAT (tùy chọn):** Bỏ qua.
