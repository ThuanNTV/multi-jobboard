import os
import json
import logging
from pathlib import Path
from datetime import datetime

from typing import List, Dict, Union, Optional, Any

from jobhub_crawler.utils.helpers import _find_folder, _find_latest_file, _find_project_root

project_root = _find_project_root(Path(__file__))
crawler_folder = _find_folder('crawler', search_dir=project_root)
output_folder = _find_folder('output', search_dir=crawler_folder)
last_file_output = _find_latest_file(search_dir=output_folder, suffix='.json')


def _check_valid_input(data_check: Any) -> bool:
    """Kiểm tra đầu vào có phải list và không rỗng không."""
    return isinstance(data_check, list) and bool(data_check)

def _open_and_read_file(file_path: str, key_level1: str, key_level2: str) -> Union[List[Dict[str, str]], Dict]:
    """
    Đọc file JSON và trích xuất dữ liệu theo key_level1 và key_level2.

    Args:
        file_path (str): Đường dẫn tới file JSON.
        key_level1 (str): Tên key cấp 1 ('jobs' hoặc 'metadata').
        key_level2 (str): Tên key cấp 2 cần trích xuất trong 'jobs' (ví dụ 'url').

    Returns:
        Nếu key_level1 == 'jobs': List các dict {'title': ..., 'url': ...}
        Nếu key_level1 == 'metadata': Dict metadata đầy đủ.
        Nếu lỗi hoặc không tìm thấy: trả về rỗng ([] hoặc {}).
    """
    if not isinstance(file_path, str) or not os.path.isfile(file_path):
        print(f"❌ File không tồn tại hoặc tên file không hợp lệ: {file_path}")
        return [] if key_level1 == 'jobs' else {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)

        if not isinstance(json_data, dict):
            print("❌ File JSON không chứa đối tượng cấp cao nhất dạng dict.")
            return [] if key_level1 == 'jobs' else {}

        if key_level1 == 'jobs':
            if key_level1 not in json_data:
                print(f"❌ Key '{key_level1}' không tồn tại trong file JSON.")
                return []
            extracted_values = []
            for entry in json_data[key_level1]:
                if isinstance(entry, dict) and key_level2 in entry:
                    extracted_values.append({
                        'title': entry.get('title', ''),
                        'url': entry[key_level2]
                    })
                else:
                    print(f"⚠️ Một phần tử không có key '{key_level2}' hoặc không phải dict: {entry}")
            return extracted_values

        elif key_level1 == 'metadata':
            if key_level1 not in json_data:
                print(f"❌ Key '{key_level1}' không tồn tại trong file JSON.")
                return {}
            return json_data[key_level1]

        else:
            print(f"❌ Key cấp 1 '{key_level1}' chưa được hỗ trợ.")
            return [] if key_level1 == 'jobs' else {}

    except json.JSONDecodeError as e:
        print(f"❌ Lỗi giải mã JSON: {e}")
        return [] if key_level1 == 'jobs' else {}
    except Exception as e:
        print(f"❌ Lỗi không xác định khi đọc file: {e}")
        return [] if key_level1 == 'jobs' else {}


def _find_diff_text_in_array(data: List[str], data_check: List[str]) -> List[str]:
    """Trả về các URL khác biệt giữa hai danh sách."""
    set_data = set(data)
    set_data_check = set(data_check)

    only_in_data = set_data - set_data_check
    only_in_data_check = set_data_check - set_data

    return list(only_in_data.union(only_in_data_check))

def _find_diff_dict(data: List[Dict], data_check: List[Dict]) -> List[Dict]:
    """
    Trả về các dict trong data_check có URL chưa tồn tại trong data.
    """
    # Tập hợp các URL đã tồn tại trong data
    existing_urls = {item["url"] for item in data if "url" in item}

    # Trả về các dict trong data_check có URL chưa từng xuất hiện trong data
    result = [
        item for item in data_check
        if "url" in item and item["url"] not in existing_urls
    ]

    return result

def _find_diff_dict_2(data: List[Dict], data_check: List[Dict]) -> List[Dict]:
    """Trả về các dict có URL khác biệt giữa hai danh sách."""
    # Lọc và ánh xạ url -> dict
    data_urls = {item["url"]: item for item in data if "url" in item}
    check_urls = {item["url"]: item for item in data_check if "url" in item}

    # Tập hợp các url chỉ xuất hiện ở một trong hai danh sách
    diff_urls = set(data_urls) ^ set(check_urls)  # symmetric_difference

    # Thu thập dict tương ứng với url khác biệt
    result = [data_urls.get(url) or check_urls.get(url) for url in diff_urls]

    return result


def _get_data_in_file(
        file_path: Optional[str] = None,
        key_level1: str = "jobs",
        key_level2: str = "url"
) -> Optional[List[str]]:
    """
    Đọc và trích xuất danh sách URL từ file JSON.

    Args:
        file_path (Optional[str]): File cần đọc. Nếu không truyền, mặc định dùng `last_file_output`.
        key_level1 (str): Key cấp 1.
        key_level2 (str): Key cấp 2.

    Returns:
        Optional[List[str]]: Danh sách URL nếu thành công, None nếu lỗi.
    """
    target_file = file_path or last_file_output

    if not target_file:
        print("❌ Không tìm thấy file JSON phù hợp.")
        return None

    data = _open_and_read_file(file_path=target_file, key_level1=key_level1, key_level2=key_level2)

    if len(data) > 1:
        if not _check_valid_input(data):
            print("❌ Dữ liệu đọc được không hợp lệ.")
            return None

    return data

def _merge_two_records(record2: Dict[str, Any], filename: Optional[str] = None) -> Optional[str]:
    try:
        input_path = Path(last_file_output)
        if not input_path.exists():
            logging.warning(f"[⚠️] File gốc không tồn tại: {input_path}")
            return None

        with open(input_path, "r", encoding="utf-8") as file:
            record1 = json.load(file)

    except Exception as e:
        logging.error(f"[❌] Lỗi khi đọc file đầu vào {last_file_output}: {e}")
        return None

    try:
        # Gộp job và loại trùng theo URL
        job_map = {
            job.get("url"): job
            for job in record1.get("jobs", []) + record2.get("jobs", [])
            if job.get("url")
        }
        jobs = list(job_map.values())

        # Tổng hợp source
        sources = {}
        for job in jobs:
            src = job.get("source")
            if src:
                sources[src] = sources.get(src, 0) + 1

        # Metadata
        meta1 = record1.get("metadata", {})
        meta2 = record2.get("metadata", {})
        created_at = max(
            meta1.get("created_at", "1970-01-01"),
            meta2.get("created_at", "1970-01-01"),
            key=lambda x: datetime.fromisoformat(x)
        )
        execution_time = meta1.get("execution_time", 0.0) + meta2.get("execution_time", 0.0)

        # Output record
        output = {
            "metadata": {
                "total_jobs": len(jobs),
                "created_at": created_at,
                "execution_time": execution_time,
                "sources": sources
            },
            "jobs": jobs
        }

        # Tạo tên file nếu chưa có
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"jobs_{timestamp}.json"

        filepath = os.path.join(output_folder, filename)
        output_path = Path(filepath)

        # Ghi file mới
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())

        # Sau khi đã merge và ghi file thành công, mới xoá bản cũ
        try:
            input_path.unlink()
            logging.info(f"[🗑️] Đã xoá file gốc: {input_path}")
        except Exception as del_err:
            logging.warning(f"[⚠️] Không thể xoá file gốc: {input_path} - {del_err}")

        logging.info(f"[✅] Gộp file thành công: {output_path}")
        return str(output_path)

    except Exception as e:
        logging.error(f"[❌] Lỗi khi merge records: {e}")
        return None


# if __name__ == '__main__':
#     data = get_data_in_file()
#     if data:
#         print(f"✅ Trích xuất được {len(data)} URL:")
#         for url in data:
#             print("   •", url)
#
#     print(find_diff_urls(data, data_check))
