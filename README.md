# Political-Net

> Hệ thống xây dựng Knowledge Graph cho các chính trị gia Việt Nam từ dữ liệu Wikipedia

## 📋 Mục lục

- [Giới thiệu](#giới-thiệu)
- [Tính năng](#tính-năng)
- [Cấu trúc dự án](#cấu-trúc-dự-án)
- [Cài đặt](#cài-đặt)
- [Sử dụng](#sử-dụng)
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Dữ liệu](#dữ-liệu)
- [Đóng góp](#đóng-góp)

## 🎯 Giới thiệu

**Political-Net** là một hệ thống tự động thu thập, xử lý và xây dựng Knowledge Graph về các chính trị gia Việt Nam. Dự án sử dụng dữ liệu từ Wikipedia tiếng Việt để tạo ra một cơ sở tri thức có cấu trúc về các chính trị gia, bao gồm thông tin về:

- Tiểu sử và thông tin cá nhân
- Vị trí chính trị đã đảm nhiệm
- Quan hệ với các chính trị gia khác (tiền nhiệm, kế nhiệm)
- Học vấn và bằng cấp
- Quá trình công tác quân sự
- Các giải thưởng và danh hiệu
- Mối quan hệ địa lý (nơi sinh, nơi mất)

## ✨ Tính năng

### 1. Thu thập dữ liệu (Crawling)

- ✅ Crawl danh sách chính trị gia từ các khóa Quốc hội
- ✅ Trích xuất thông tin từ infobox Wikipedia
- ✅ Xử lý và chuẩn hóa dữ liệu thô
- ✅ Hỗ trợ crawl song song với async logging

### 2. Xử lý và chuẩn hóa dữ liệu (Preprocessing)

- ✅ Chuẩn hóa ngày tháng năm sinh
- ✅ Chuẩn hóa thông tin giải thưởng
- ✅ Chuẩn hóa thông tin học vấn
- ✅ Chuẩn hóa tên tỉnh/thành phố
- ✅ Chuẩn hóa thông tin chiến dịch quân sự
- ✅ Làm sạch và chuẩn hóa dữ liệu chính đảng

### 3. Xây dựng Knowledge Graph

- ✅ Xây dựng các node: Politician, Position, Location, Award, MilitaryCareer, etc.
- ✅ Xây dựng các edge: SERVED_AS, SUCCEEDED, PRECEDED, BORN_AT, etc.
- ✅ Tự động phát hiện và xử lý mối quan hệ
- ✅ Xuất dữ liệu sang định dạng JSON và Cypher (Neo4j)

### 4. Phân tích và thuật toán

- ✅ Xây dựng graph từ dữ liệu đã chuẩn hóa
- ✅ Phát hiện mối quan hệ giữa các chính trị gia
- ✅ Trích xuất thông tin từ wikilink

## 📁 Cấu trúc dự án

```
political-net/
│
├── algorithm/              # Các thuật toán xử lý graph
│   ├── __init__.py
│   └── graph_builder.py   # Xây dựng graph từ dữ liệu
│
├── crawl/                 # Module thu thập dữ liệu
│   ├── __init__.py
│   ├── alias.py          # Xử lý alias cho tên chính trị gia
│   ├── crawl_names.py    # Crawl danh sách tên
│   └── crawl_politicians.py  # Crawl thông tin chi tiết
│
├── data/                  # Thư mục chứa dữ liệu
│   ├── database/         # Database JSON
│   │   └── politicians_db.json
│   ├── mess/             # Dữ liệu mẫu và seed
│   │   ├── data_sample.json
│   │   ├── knowledge_graph_sample.json
│   │   └── seed_politicians.txt
│   ├── processed/        # Dữ liệu đã xử lý
│   │   ├── politicians_names.txt
│   │   ├── graph/        # Knowledge graph
│   │   │   ├── knowledge_graph.json
│   │   │   └── neo4j_import.cypher
│   │   └── infobox/      # Dữ liệu infobox đã chuẩn hóa
│   │       ├── politicians_data.json
│   │       ├── politicians_data_cleaned.json
│   │       ├── politicians_data_normalized.json
│   │       └── politicians_data_*_normalized.json
│   └── raw/              # Dữ liệu thô
│       └── viwiki-latest-pages-articles.xml
│
├── graph/                 # Module xây dựng knowledge graph
│   ├── build_edges_.py   # Xây dựng các cạnh
│   ├── build_kgs.py      # Xây dựng knowledge graph chính
│   └── graph.py          # Các hàm tiện ích cho graph
│
├── logs/                  # Thư mục chứa log files
│   ├── algorithm/
│   ├── crawl/
│   ├── graph/
│   └── preprocessing/
│
├── preprocessing/         # Module tiền xử lý dữ liệu
│   ├── awards_normalizer.py      # Chuẩn hóa giải thưởng
│   ├── battles_normalizer.py     # Chuẩn hóa chiến dịch
│   ├── birth_date_normalizer.py  # Chuẩn hóa ngày sinh
│   ├── clean_infobox.py          # Làm sạch infobox
│   ├── education_normalizer.py   # Chuẩn hóa học vấn
│   ├── party_normalizer.py       # Chuẩn hóa đảng phái
│   └── province_normalizer.py    # Chuẩn hóa địa danh
│
├── utils/                 # Các tiện ích dùng chung
│   ├── __init__.py
│   ├── config.py         # Cấu hình hệ thống
│   ├── external.py       # Dữ liệu ngoài và constants
│   └── queue_based_async_logger.py  # Async logger
│
├── main.py               # Entry point chính
├── pyproject.toml        # Cấu hình project và dependencies
├── requirements.txt      # Dependencies list
├── uv.lock              # Lock file cho uv package manager
└── README.md            # Tài liệu này
```

## 🚀 Cài đặt

### Yêu cầu hệ thống

- Python >= 3.11
- uv package manager (khuyến nghị) hoặc pip

### Bước 1: Cài đặt uv

**Cách 1: Sử dụng pip**

```bash
pip install uv
```

**Cách 2: Cài đặt từ script (khuyến nghị)**

Windows (PowerShell):

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Chi tiết: [UV Installation Guide](https://docs.astral.sh/uv/getting-started/installation/)

### Bước 2: Clone repository

```bash
git clone https://github.com/datmieu204/political-net.git
cd political-net
```

### Bước 3: Cài đặt dependencies

```bash
# Đồng bộ dependencies từ uv.lock
uv sync
```

### Bước 4: Kích hoạt môi trường ảo

**Windows:**

```powershell
.venv\Scripts\activate
```

**macOS/Linux:**

```bash
source .venv/bin/activate
```

## 💻 Sử dụng

### 1. Crawl danh sách chính trị gia

```bash
python main.py
```

Script này sẽ crawl danh sách chính trị gia từ các khóa Quốc hội (từ khóa I đến XIII).

### 2. Crawl thông tin chi tiết

```python
from crawl.crawl_politicians import crawl_politicians_data

# Crawl thông tin từ file danh sách
crawl_politicians_data(
    input_file="data/processed/politicians_names.txt",
    output_file="data/processed/infobox/politicians_data.json"
)
```

### 3. Xử lý và chuẩn hóa dữ liệu

```python
# Làm sạch dữ liệu
from preprocessing.clean_infobox import clean_all_infoboxes
clean_all_infoboxes()

# Chuẩn hóa ngày sinh
from preprocessing.birth_date_normalizer import normalize_birth_dates
normalize_birth_dates()

# Chuẩn hóa giải thưởng
from preprocessing.awards_normalizer import normalize_awards
normalize_awards()

# Chuẩn hóa học vấn
from preprocessing.education_normalizer import normalize_education
normalize_education()

# Chuẩn hóa địa danh
from preprocessing.province_normalizer import normalize_provinces
normalize_provinces()
```

### 4. Xây dựng Knowledge Graph

```python
from graph.build_kgs import KnowledgeGraphBuilder

# Khởi tạo builder
kg_builder = KnowledgeGraphBuilder()

# Build graph từ dữ liệu đã chuẩn hóa
kg_builder.build_from_file("data/processed/infobox/politicians_data_normalized.json")

# Xuất kết quả
kg_builder.export_to_json("data/processed/graph/knowledge_graph.json")
kg_builder.export_to_neo4j("data/processed/graph/neo4j_import.cypher")
```

### 5. Import vào Neo4j (Optional)

Nếu muốn visualize và query knowledge graph bằng Neo4j:

```bash
# Khởi động Neo4j
# Sau đó import file Cypher
cypher-shell < data/processed/graph/neo4j_import.cypher
```

## 🏗️ Kiến trúc hệ thống

### Pipeline xử lý dữ liệu

```
Wikipedia Pages
      ↓
[1. Crawling Module]
      ↓
Raw Data (JSON)
      ↓
[2. Preprocessing Module]
      ↓
Normalized Data
      ↓
[3. Graph Builder]
      ↓
Knowledge Graph
      ↓
[4. Export (JSON/Neo4j)]
      ↓
Final Output
```

### Các thành phần chính

1. **Crawling Module**: Thu thập dữ liệu từ Wikipedia
2. **Preprocessing Module**: Chuẩn hóa và làm sạch dữ liệu
3. **Algorithm Module**: Phân tích và trích xuất mối quan hệ
4. **Graph Module**: Xây dựng knowledge graph
5. **Utils**: Logging, configuration, external data

## 📊 Dữ liệu

### Schema của Knowledge Graph

#### Nodes

- **Politician**: Chính trị gia
- **Position**: Vị trí/chức vụ
- **Location**: Địa điểm (tỉnh/thành phố)
- **Award**: Giải thưởng/danh hiệu
- **MilitaryCareer**: Quân ngạch
- **MilitaryRank**: Cấp bậc quân đội
- **Campaigns**: Chiến dịch quân sự
- **AlmaMater**: Trường học
- **AcademicTitle**: Học vị/học hàm

#### Edges

- **SERVED_AS**: Đảm nhiệm vị trí
- **SUCCEEDED**: Kế nhiệm
- **PRECEDED**: Tiền nhiệm
- **BORN_AT**: Sinh tại
- **DIED_AT**: Mất tại
- **AWARDED**: Được trao tặng
- **SERVED_IN**: Phục vụ trong
- **HAS_RANK**: Có cấp bậc
- **FOUGHT_IN**: Tham gia chiến dịch
- **ALUMNUS_OF**: Tốt nghiệp từ
- **HAS_ACADEMIC_TITLE**: Có học vị

### Dependencies chính

```toml
beautifulsoup4 >= 4.14.2    # Web scraping
lxml >= 6.0.2               # XML parsing
requests >= 2.32.5          # HTTP requests
mwparserfromhell >= 0.7.2   # MediaWiki parsing
wikitextparser >= 0.56.4    # Wikitext parsing
networkx >= 3.5             # Graph algorithms
pandas >= 2.3.3             # Data manipulation
neo4j >= 6.0.2              # Graph database
matplotlib >= 3.10.6        # Visualization
jupyter >= 1.1.1            # Interactive notebooks
```

## 🤝 Đóng góp

Mọi đóng góp đều được hoan nghênh! Vui lòng:

1. Fork repository
2. Tạo branch mới (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Tạo Pull Request

## 📝 License

Dự án này được phân phối dưới MIT License.

## 👥 Tác giả

- **datmieu204** - [GitHub](https://github.com/datmieu204)
- **HungIsWorking** - [GitHub](https://github.com/HungIsWorking)
- **chocoyeni** - [GitHub](https://github.com/chocoyeni)

## 📧 Liên hệ

Nếu có bất kỳ câu hỏi hoặc góp ý nào, vui lòng tạo issue trên GitHub.

---

**Note**: Dự án này chỉ nhằm mục đích nghiên cứu và học tập. Dữ liệu được thu thập từ Wikipedia tuân theo [Creative Commons Attribution-ShareAlike License](https://creativecommons.org/licenses/by-sa/3.0/).
