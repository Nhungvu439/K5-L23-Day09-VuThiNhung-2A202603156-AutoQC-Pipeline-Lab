"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


REMOVE_IMG_CODES = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}
DROP_LINE_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
CLIP_LINE_CODES = {"BOX_OUT_OF_IMAGE"}


def fix(ds, issues, cfg):
    err_issues = [i for i in issues if i.severity == ERROR]
    fixes = []
    removed_images = set()

    # 1. Xoá ảnh + nhãn bị lỗi cấp ảnh (trùng, rò rỉ, hỏng, sai kích thước)
    for i in err_issues:
        if i.code in REMOVE_IMG_CODES or i.code.startswith("DUP_IMAGE_"):
            stem = i.image
            if stem in removed_images:
                continue
            img_p = ds.image_path(stem)
            lbl_p = ds.label_path(stem)
            if img_p is None and not lbl_p.exists():
                removed_images.add(stem)
                continue
            if img_p is not None and img_p.exists():
                img_p.unlink()
            if lbl_p.exists():
                lbl_p.unlink()
            ds._size_cache.pop(stem, None)
            removed_images.add(stem)
            fixes.append(
                {
                    "image": stem,
                    "line": "",
                    "action": "remove_image",
                    "before": i.code,
                    "after": "đã xoá ảnh + nhãn",
                }
            )

    # 2. Sửa tên lớp trong data.yaml
    if any(i.code == "BAD_CLASS_NAME" for i in err_issues):
        expected = {idx: name for idx, name in enumerate(cfg["classes"])}
        current = ds.yaml_names()
        if current != expected:
            d = (
                yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
                if ds.yaml_path.exists()
                else {}
            )
            before_names = d.get("names", current)
            d["names"] = expected
            ds.yaml_path.write_text(
                yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            fixes.append(
                {
                    "image": "data.yaml",
                    "line": "",
                    "action": "rename_classes",
                    "before": str(before_names),
                    "after": str(expected),
                }
            )

    # 3. Ghi nhận ảnh thiếu file nhãn (chuyển người gán, không tạo file rỗng)
    seen_missing = set()
    for i in err_issues:
        if i.code == "MISSING_LABEL_FILE":
            stem = i.image
            if stem in removed_images or stem in seen_missing:
                continue
            if not ds.label_path(stem).exists():
                seen_missing.add(stem)
                fixes.append(
                    {
                        "image": stem,
                        "line": "",
                        "action": "needs_label",
                        "before": "(không có file)",
                        "after": "chuyển người gán",
                    }
                )

    # 4. Gom lỗi dòng nhãn theo từng file rồi sửa 1 lần trên số dòng gốc
    by_file = defaultdict(lambda: defaultdict(set))
    for i in err_issues:
        if i.code in DROP_LINE_CODES or i.code in CLIP_LINE_CODES:
            if i.image in removed_images or i.line is None:
                continue
            by_file[i.image][i.line].add(i.code)

    for stem, line_map in by_file.items():
        lp = ds.label_path(stem)
        if not lp.exists():
            continue
        raw_lines = lp.read_text(encoding="utf-8", errors="replace").splitlines()
        new_lines = []
        changed = False

        for idx, raw_ln in enumerate(raw_lines, start=1):
            if idx not in line_map:
                new_lines.append(raw_ln)
                continue

            codes = line_map[idx]
            changed = True
            if codes & DROP_LINE_CODES:
                fixes.append(
                    {
                        "image": stem,
                        "line": idx,
                        "action": "drop_line",
                        "before": raw_ln.strip(),
                        "after": "",
                    }
                )
                continue

            # Chỉ còn BOX_OUT_OF_IMAGE -> cắt về [0, 1]
            try:
                cls_id, cx, cy, w, h = parse_yolo_line(raw_ln)
            except ValueError:
                fixes.append(
                    {
                        "image": stem,
                        "line": idx,
                        "action": "drop_line",
                        "before": raw_ln.strip(),
                        "after": "",
                    }
                )
                continue

            raw_x1, raw_y1 = cx - w / 2.0, cy - h / 2.0
            raw_x2, raw_y2 = cx + w / 2.0, cy + h / 2.0
            if raw_x1 >= 0.0 and raw_y1 >= 0.0 and raw_x2 <= 1.0 and raw_y2 <= 1.0:
                new_lines.append(raw_ln)
                continue

            x1 = max(0.0, min(1.0, raw_x1))
            y1 = max(0.0, min(1.0, raw_y1))
            x2 = max(0.0, min(1.0, raw_x2))
            y2 = max(0.0, min(1.0, raw_y2))
            nw = x2 - x1
            nh = y2 - y1

            if nw <= 0.0 or nh <= 0.0:
                fixes.append(
                    {
                        "image": stem,
                        "line": idx,
                        "action": "drop_line",
                        "before": raw_ln.strip(),
                        "after": "",
                    }
                )
            else:
                ncx = (x1 + x2) / 2.0
                ncy = (y1 + y2) / 2.0
                after_ln = f"{cls_id} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}"
                new_lines.append(after_ln)
                fixes.append(
                    {
                        "image": stem,
                        "line": idx,
                        "action": "clip_box",
                        "before": raw_ln.strip(),
                        "after": after_ln,
                    }
                )

        if changed:
            lp.write_text(
                "\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8"
            )

    return fixes
