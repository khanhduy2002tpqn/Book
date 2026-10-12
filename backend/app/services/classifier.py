import re
from typing import Tuple, Optional


def detect_grade_and_subject(filename: str) -> Tuple[str, str]:
    """
    Tự động nhận diện Khối lớp và Môn học từ tên file sách giáo khoa tiếng Việt.
    Ví dụ:
        SGK_-_Toán_11_-_Tập_1_-_Chương_trình_mới.pdf -> ('Lớp 11', 'Toán')
        SGK_-_Văn_9_-_Chương_trình_mới_-_Tập_1.pdf -> ('Lớp 9', 'Ngữ văn')
        Tieng_Anh_10_Global_Success.pdf -> ('Lớp 10', 'Tiếng Anh')
        Hoa_Hoc_12.pdf -> ('Lớp 12', 'Hóa học')
    """
    clean_name = filename.replace("_", " ").replace("-", " ")

    # 1. Nhận diện Khối lớp (Lớp 1 -> Lớp 12)
    grade = None
    grade_match = re.search(r'(?:lớp|lop|khối|khoi|grade|k)\s*(\d{1,2})', clean_name, re.IGNORECASE)
    if grade_match:
        val = int(grade_match.group(1))
        if 1 <= val <= 12:
            grade = f"Lớp {val}"

    if not grade:
        for num in range(12, 0, -1):
            if re.search(rf'(?<!\d){num}(?!\d)', clean_name):
                grade = f"Lớp {num}"
                break

    if not grade:
        if re.search(r'\b(đại học|dai hoc|university)\b', clean_name, re.IGNORECASE):
            grade = "Đại học"
        else:
            grade = "Chung"

    # 2. Nhận diện Môn học
    subject = None
    subjects_map = {
        "Toán": [r'\btoán\b', r'\btoan\b', r'\bmath\b', r'\bđại số\b', r'\bhình học\b', r'\bgiải tích\b'],
        "Ngữ văn": [r'\bngữ văn\b', r'\bngu van\b', r'\bvăn\b', r'\bvan\b', r'\btiếng việt\b', r'\btieng viet\b', r'\bvăn học\b'],
        "Tiếng Anh": [r'\btiếng anh\b', r'\btieng anh\b', r'\benglish\b', r'\banh văn\b', r'\bglobal success\b', r'\bfriends\b'],
        "Vật lí": [r'\bvật lí\b', r'\bvật lý\b', r'\bvat li\b', r'\bvat ly\b', r'\blí\b', r'\bly\b', r'\bphysics\b'],
        "Hóa học": [r'\bhóa học\b', r'\bhoa hoc\b', r'\bhóa\b', r'\bhoa\b', r'\bchemistry\b'],
        "Sinh học": [r'\bsinh học\b', r'\bsinh hoc\b', r'\bsinh\b', r'\bbiology\b'],
        "Lịch sử": [r'\blịch sử\b', r'\blich su\b', r'\bsử\b', r'\bsu\b', r'\bhistory\b'],
        "Địa lí": [r'\bđịa lí\b', r'\bđịa lý\b', r'\bdia li\b', r'\bdia ly\b', r'\bđịa\b', r'\bgeography\b'],
        "Tin học": [r'\btin học\b', r'\btin hoc\b', r'\btin\b', r'\binformatics\b', r'\bcomputer\b'],
        "GDCD": [r'\bgdcd\b', r'\bgiáo dục công dân\b', r'\bgiao duc cong dan\b', r'\bkinh tế và pháp luật\b'],
        "Công nghệ": [r'\bcông nghệ\b', r'\bcong nghe\b'],
        "Khoa học tự nhiên": [r'\bkhtn\b', r'\bkhoa học tự nhiên\b', r'\bkhoa hoc tu nhien\b'],
        "Lịch sử & Địa lí": [r'\blịch sử và địa lí\b', r'\blich su va dia ly\b']
    }

    for subj_name, patterns in subjects_map.items():
        if any(re.search(p, clean_name, re.IGNORECASE) for p in patterns):
            subject = subj_name
            break

    if not subject:
        subject = "Khác"

    return grade, subject
