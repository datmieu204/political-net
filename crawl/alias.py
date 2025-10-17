# ./crawl/alias.py

"""
Alias mapping for infobox keys in Vietnamese to English.
"""

COMPREHENSIVE_MAPPING = {
    # Basic Info
    "tên": "name",
    "name": "name",
    "tiền tố": "honorific_prefix",
    "honorific_prefix": "honorific_prefix",
    "hậu tố": "honorific_suffix",
    "honorific_suffix": "honorific_suffix",
    
    # Image
    "hình": "image",
    "image": "image",
    "cỡ hình": "imagesize",
    "imagesize": "imagesize",
    "miêu tả": "caption",
    "caption": "caption",
    "alt": "alt",
    
    # Office/Position
    "chức vụ": "office",
    "office": "office",
    "nhiệm kỳ": "term",
    "term": "term",
    "bắt đầu": "term_start",
    "term_start": "term_start",
    "kết thúc": "term_end",
    "term_end": "term_end",
    
    # Predecessor/Successor
    "tiền nhiệm": "predecessor",
    "predecessor": "predecessor",
    "trước": "predecessor",
    "kế nhiệm": "successor",
    "successor": "successor",
    "sau": "successor",
    
    # Leader/Deputy
    "trưởng chức vụ": "leader_title",
    "trưởng viên chức": "leader_name",
    "leader_title": "leader_title",
    "leader_name": "leader_name",
    "phó chức vụ": "deputy_title",
    "phó viên chức": "deputy_name",
    "phó": "deputy",
    "deputy": "deputy",
    "deputy_title": "deputy_title",
    "deputy_name": "deputy_name",
    
    # Geographic
    "địa hạt": "constituency",
    "constituency": "constituency",
    "quê quán": "hometown",
    "hometown": "hometown",
    "nơi_ở": "residence",
    "nơi ở": "residence",
    
    # Birth/Death
    "ngày sinh": "birth_date",
    "birth_date": "birth_date",
    "nơi sinh": "birth_place",
    "birth_place": "birth_place",
    "ngày mất": "death_date",
    "death_date": "death_date",
    "nơi mất": "death_place",
    "death_place": "death_place",
    "nơi an táng": "resting_place",
    "resting_place": "resting_place",
    
    # Personal
    "quốc tịch": "nationality",
    "nationality": "nationality",
    "dân tộc": "ethnicity",
    "ethnicity": "ethnicity",
    "tôn giáo": "religion",
    "đạo": "religion",
    "religion": "religion",
    "nghề nghiệp": "occupation",
    "occupation": "occupation",
    
    # Political
    "đảng": "party",
    "party": "party",
    "ngày vào đảng": "party_entry_date",
    "party_entry_date": "party_entry_date",
    
    # Family
    "vợ": "spouse",
    "chồng": "spouse",
    "spouse": "spouse",
    "con": "children",
    "children": "children",
    "cha": "father",
    "father": "father",
    "mẹ": "mother",
    "mother": "mother",
    "họ hàng": "relatives",
    "relatives": "relatives",
    
    # Education
    "học vấn": "education_level",
    "giáo dục": "education",
    "giáo_dục": "education",
    "education": "education",
    "học trường": "alma_mater",
    "alma_mater": "alma_mater",
    
    # Awards
    "giải thưởng": "awards",
    "khen thưởng": "awards",
    "awards": "awards",
    
    # Military
    "cấp bậc": "military_rank",
    "military_rank": "military_rank",
    "rank": "military_rank",
    "thuộc": "branch",
    "branch": "branch",
    "năm phục vụ": "years_of_service",
    "years_of_service": "years_of_service",
    "đơn vị": "unit",
    "unit": "unit",
    "chỉ huy": "commands",
    "commands": "commands",
    "tham chiến": "battles",
    "battles": "battles",
    
    # Other
    "chữ ký": "signature",
    "signature": "signature",
    "ghi chú": "footnotes",
    "footnotes": "footnotes",
    "website": "website",
    "nickname": "nickname",
    "biệt danh": "nickname",
    
    # Template specific
    "embed": "embed",
    "module": "module",
    "cont": "cont",
    "titlestyle": "titlestyle",

    # others
    "khác": "other",
    "other": "other",
    "thêm": "other",
}