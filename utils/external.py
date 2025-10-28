

PRIORITY_TEMPLATES = [
    "viên chức", "Viên chức", "thông tin viên chức", "Thông tin viên chức",
    "infobox", "infobox viên chức", "infobox nhân vật", "infobox officeholder",
    "infobox officeholder 1", "infobox officeholder1", "thông tin nhân vật",
    "thông tin chính khách", "thông tin chức vụ", "chức vụ", "Thông tin chức vụ", "Thông tin chính khách"
]

EXCLUDE_KEYWORDS = [
    'tập tin:', 'file:', 'hình:', 'image:', 'thể loại:', 'category:',
    'wikipedia:', 'wp:', 'template:', 'mẫu:', 'đầu tiên', 'first',
    'none', 'vacant', 'không có', 'chưa có', 'mới thành lập',
    'position established', 'office established'
]

VIETNAM_KEYWORDS = [
    'việt nam', 'vietnam', 'viet nam',
    'hà nội', 'sài gòn', 'hanoi', 'saigon', 'hồ chí minh',
    'đà nẵng', 'hải phòng', 'cần thơ', 
    'bắc ninh', 'hải dương', 'nam định', 'thái bình',
    'nghệ an', 'thanh hóa', 'quảng nam', 'quảng ngãi',
    'đồng nai', 'bình dương', 'vũng tàu', 'long an',
    'tiền giang', 'bến tre', 'vĩnh long', 'an giang',
    'kiên giang', 'cà mau', 'bạc liêu', 'sóc trăng',
    '{{vie}}', '{{viet nam}}', 'cộng hòa xã hội chủ nghĩa việt nam',
    'việt nam dân chủ cộng hòa', 'việt nam cộng hòa',
    'bắc kỳ', 'trung kỳ', 'nam kỳ', 'bắc bộ', 'trung bộ', 'nam bộ',
    "An Giang", "Bà Rịa - Vũng Tàu", "Bắc Giang", "Bắc Kạn", "Bạc Liêu", "Bắc Ninh",
    "Bến Tre", "Bình Định", "Bình Dương", "Bình Phước", "Bình Thuận",
    "Cà Mau", "Cần Thơ", "Cao Bằng", "Đà Nẵng", "Đắk Lắk", "Đắk Nông",
    "Điện Biên", "Đồng Nai", "Đồng Tháp", "Gia Lai",
    "Hà Giang", "Hà Nam", "Hà Nội", "Hà Tĩnh", "Hải Dương",
    "Hải Phòng", "Hậu Giang", "TP. Hồ Chí Minh", "Hòa Bình",
    "Hưng Yên", "Khánh Hòa", "Kiên Giang", "Kon Tum", "Lai Châu",
    "Lâm Đồng", "Lạng Sơn", "Lào Cai", "Long An", "Nam Định", "Nghệ An",
    "Ninh Bình", "Ninh Thuận", "Phú Thọ", "Phú Yên", "Quảng Bình",
    "Quảng Nam", "Quảng Ngãi", "Quảng Ninh", "Quảng Trị", "Sóc Trăng",
    "Sơn La", "Tây Ninh", "Thái Bình", "Thái Nguyên", "Thanh Hóa",
    "Thừa Thiên - Huế", "Tiền Giang", "Trà Vinh", "Tuyên Quang",
    "Vĩnh Long", "Vĩnh Phúc", "Yên Bái"
]

NON_VIETNAM_KEYWORDS = [
    'thái lan', 'thailand', 'bangkok',
    'brunei', 'bandar seri begawan',
    'singapore', 'singapo',
    'malaysia', 'kuala lumpur',
    'indonesia', 'jakarta',
    'philippines', 'manila',
    'myanmar', 'burma', 'yangon',
    'cambodia', 'campuchia', 'phnom penh',
    'laos', 'lào', 'vientiane',
    'trung quốc', 'china', 'beijing', 'bắc kinh',
    'nhật bản', 'japan', 'tokyo',
    'hàn quốc', 'korea', 'seoul',
    'ấn độ', 'india', 'new delhi',
    'hoa kỳ', 'america', 'washington',
    'nga', 'russia', 'moscow',
    'pháp', 'france', 'paris',
    'anh', 'britain', 'london'
]

FIELDS_TO_CHECK = [
    'birth_place', 'nơi_sinh',
    'nationality', 'quốc_tịch',
    'death_place', 'nơi_chết',
    'residence', 'cư_trú'
]

INVALID_KEYWORDS = [
    'báo chí', 'thông tin báo chí',
    'cơ quan', 'infobox cơ quan',
    'tổ chức', 'organization',
    'company', 'công ty',
    'website', 'trang web',
    'newspaper', 'tờ báo',
    'magazine', 'tạp chí',
    'đài', 'station',
    'trường', 'school', 'university', 'đại học',
    'bệnh viện', 'hospital',
    'ngân hàng', 'bank',
    'đảng', 'party', 'political party',  
    'ban', 'committee',  
    'bộ', 'ministry',  
    'settlement', 'địa điểm',
    'building', 'tòa nhà',
    'event', 'sự kiện',
]

VALID_KEYWORDS = [
    'officeholder',
    'infobox officeholder',
    'military person',
    'infobox military person',
    'royalty',
    'infobox royalty',
    'person',
    'infobox person',
    'nhân vật',
    'thông tin nhân vật',
    'Thông tin nhân vật',
    'nhà chính trị',
    'Nhà Chính trị'
    'quân nhân',
    'Quân nhân',
    'hoàng gia',
    'president',
    'prime minister',
    'viên chức',
    'Viên chức',
    'thông tin viên chức',
    'Thông tin viên chức',
    'Thông tin chính khách',
    'chính khách',
    'Chính khách',
]