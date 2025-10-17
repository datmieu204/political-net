// Neo4j Cypher Script - Knowledge Graph Import
// Generated at: 2025-10-17T11:50:00.394496
// Clear existing data (optional)
// MATCH (n) DETACH DELETE n;

// Create constraints
CREATE CONSTRAINT politician_id IF NOT EXISTS FOR (p:Politician) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT position_id IF NOT EXISTS FOR (p:Position) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT location_id IF NOT EXISTS FOR (l:Location) REQUIRE l.id IS UNIQUE;
CREATE CONSTRAINT award_id IF NOT EXISTS FOR (a:Award) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT military_id IF NOT EXISTS FOR (m:MilitaryCareer) REQUIRE m.id IS UNIQUE;

// Create Politician nodes
MERGE (p:Politician {id: "Bùi Thiện Ngộ", type: "Politician", name: "Bùi Thiện Ngộ", full_name: "Bùi Thiện Ngộ", birth_date: "", death_date: "", party: "Đảng Cộng sản Việt Nam", ethnicity: "Kinh", religion: "không", nationality: "", image: "Bùi_Thiện_Ngộ.jpg", military_rank: "15px Thượng tướng"});
MERGE (p:Politician {id: "Cù Thị Hậu", type: "Politician", name: "Cù Thị Hậu", full_name: "Cù Thị Hậu", birth_date: "", death_date: "", party: "Đảng Cộng sản Việt Nam", ethnicity: "Kinh", religion: "Không", nationality: "", image: "", military_rank: ""});
MERGE (p:Politician {id: "Hoàng Bích Sơn", type: "Politician", name: "Hoàng Bích Sơn", full_name: "Hoàng Bích Sơn", birth_date: "20 tháng 1, 1924", death_date: "", party: "", ethnicity: "", religion: "", nationality: "", image: "Hoang_Bich_son.jpg", military_rank: ""});
MERGE (p:Politician {id: "Cao Đăng Chiếm", type: "Politician", name: "Cao Đăng Chiếm", full_name: "Cao Đăng Chiếm", birth_date: "1 tháng 12 năm 1921", death_date: "", party: "Đảng Cộng sản Việt Nam", ethnicity: "", religion: "", nationality: "", image: "CaoDangChiem.jpg", military_rank: "15px Thượng tướng"});
MERGE (p:Politician {id: "Hoàng Cầm (tướng)", type: "Politician", name: "Hoàng CầmNăm Thạch", full_name: "Hoàng Cầm (tướng)", birth_date: "30 tháng 4 năm 1920", death_date: "", party: "", ethnicity: "", religion: "", nationality: "22px Việt Nam", image: "Tướng Hoàng Cầm.jpg", military_rank: ""});
MERGE (p:Politician {id: "Hồng Hà (nhà báo)", type: "Politician", name: "Hồng Hà", full_name: "Hồng Hà (nhà báo)", birth_date: "", death_date: "", party: "Đảng Cộng sản Việt Nam", ethnicity: "", religion: "", nationality: "", image: "HongHa.jpg", military_rank: ""});
MERGE (p:Politician {id: "Bùi Danh Lưu", type: "Politician", name: "Bùi Danh Lưu", full_name: "Bùi Danh Lưu", birth_date: "", death_date: "", party: "", ethnicity: "Kinh", religion: "", nationality: "", image: "Bùi Danh Lưu.jpg", military_rank: ""});
MERGE (p:Politician {id: "Hoàng Quy", type: "Politician", name: "Hoàng Quy", full_name: "Hoàng Quy", birth_date: "28 tháng 3 năm 1927", death_date: "2009", party: "Đảng Cộng sản Việt Nam", ethnicity: "", religion: "", nationality: "", image: "Ông Hoàng Quy.jpg", military_rank: ""});
MERGE (p:Politician {id: "Hoàng Trường Minh", type: "Politician", name: "Hoàng Trường Minh", full_name: "Hoàng Trường Minh", birth_date: "", death_date: "", party: "Đảng Cộng sản Việt Nam", ethnicity: "Tày", religion: "", nationality: "", image: "Hoàng Trường Minh.jpg", military_rank: ""});
MERGE (p:Politician {id: "Hoàng Minh Thắng", type: "Politician", name: "Hoàng Minh Thắng", full_name: "Hoàng Minh Thắng", birth_date: "", death_date: "", party: "", ethnicity: "", religion: "", nationality: "", image: "Hoàng Minh Thắng.jpg", military_rank: ""});

// Create Position nodes
MERGE (p:Position {id: "Bộ trưởng Bộ Nội vụ (Nay là Bộ Công an)", type: "Position", name: "Bộ trưởng Bộ Nội vụ (Nay là Bộ Công an)"});
MERGE (p:Position {id: "Ủy viên Bộ Chính trị", type: "Position", name: "Ủy viên Bộ Chính trị"});
MERGE (p:Position {id: "40pxChủ tịch Hội Người cao tuổi Việt Nam", type: "Position", name: "40pxChủ tịch Hội Người cao tuổi Việt Nam"});
MERGE (p:Position {id: "Phó Chủ tịch Hội Người cao tuổi Việt Nam", type: "Position", name: "Phó Chủ tịch Hội Người cao tuổi Việt Nam"});
MERGE (p:Position {id: "Chủ tịch Tổng Công đoàn Việt Nam", type: "Position", name: "Chủ tịch Tổng Công đoàn Việt Nam"});
MERGE (p:Position {id: "Phó Chủ tịch thường trực Tổng Công đoàn Việt Nam", type: "Position", name: "Phó Chủ tịch thường trực Tổng Công đoàn Việt Nam"});
MERGE (p:Position {id: "Ủy viên Trung ương Đảng khóa VI, VII, VIII, IX", type: "Position", name: "Ủy viên Trung ương Đảng khóa VI, VII, VIII, IX"});
MERGE (p:Position {id: "Trưởng ban Ban Đối ngoại Trung ương Đảng Cộng sản Việt Nam", type: "Position", name: "Trưởng ban Ban Đối ngoại Trung ương Đảng Cộng sản Việt Nam"});
MERGE (p:Position {id: "Ủy viên Ủy ban Thường vụ Quốc hội, Chủ nhiệm Ủy ban Đối ngoại Quốc hội", type: "Position", name: "Ủy viên Ủy ban Thường vụ Quốc hội, Chủ nhiệm Ủy ban Đối ngoại Quốc hội"});
MERGE (p:Position {id: "Thứ trưởng Thường trực Bộ Công an", type: "Position", name: "Thứ trưởng Thường trực Bộ Công an"});
MERGE (p:Position {id: "Tổng Thanh tra Quân đội", type: "Position", name: "Tổng Thanh tra Quân đội"});
MERGE (p:Position {id: "Tư lệnh Quân khu 4", type: "Position", name: "Tư lệnh Quân khu 4"});
MERGE (p:Position {id: "Phó Chủ tịch Ủy ban Quân quản Sài Gòn - Gia Định", type: "Position", name: "Phó Chủ tịch Ủy ban Quân quản Sài Gòn - Gia Định"});
MERGE (p:Position {id: "Tư lệnh Quân đoàn 4", type: "Position", name: "Tư lệnh Quân đoàn 4"});
MERGE (p:Position {id: "Phó Tư lệnh, Tham mưu trưởng Quân Giải phóng miền Nam Việt Nam", type: "Position", name: "Phó Tư lệnh, Tham mưu trưởng Quân Giải phóng miền Nam Việt Nam"});
MERGE (p:Position {id: "Sư đoàn trưởng Sư đoàn 9", type: "Position", name: "Sư đoàn trưởng Sư đoàn 9"});
MERGE (p:Position {id: "Sư đoàn trưởng Sư đoàn 312", type: "Position", name: "Sư đoàn trưởng Sư đoàn 312"});
MERGE (p:Position {id: "Trưởng ban Đối ngoại Trung ương", type: "Position", name: "Trưởng ban Đối ngoại Trung ương"});
MERGE (p:Position {id: "Chánh Văn phòng Trung ương Đảng", type: "Position", name: "Chánh Văn phòng Trung ương Đảng"});
MERGE (p:Position {id: "Tổng biên tập Báo Nhân dân", type: "Position", name: "Tổng biên tập Báo Nhân dân"});
MERGE (p:Position {id: "Bộ trưởng Bộ Giao thông Vận tải", type: "Position", name: "Bộ trưởng Bộ Giao thông Vận tải"});
MERGE (p:Position {id: "Bộ trưởng Bộ Tài chính", type: "Position", name: "Bộ trưởng Bộ Tài chính"});
MERGE (p:Position {id: "Phó Chủ nhiệm thứ nhất Ủy ban Kế hoạch Nhà nước", type: "Position", name: "Phó Chủ nhiệm thứ nhất Ủy ban Kế hoạch Nhà nước"});
MERGE (p:Position {id: "Bí thư Tỉnh ủy Vĩnh Phú", type: "Position", name: "Bí thư Tỉnh ủy Vĩnh Phú"});
MERGE (p:Position {id: "Bí thư Tỉnh ủy Lào Cai", type: "Position", name: "Bí thư Tỉnh ủy Lào Cai"});
MERGE (p:Position {id: "Phó Chủ tịch Quốc hội Việt Nam", type: "Position", name: "Phó Chủ tịch Quốc hội Việt Nam"});
MERGE (p:Position {id: "Trưởng ban Dân tộc Trung ương", type: "Position", name: "Trưởng ban Dân tộc Trung ương"});
MERGE (p:Position {id: "Chủ tịch Hội đồng Dân tộc của Quốc hội", type: "Position", name: "Chủ tịch Hội đồng Dân tộc của Quốc hội"});
MERGE (p:Position {id: "Chủ tịch Hội đồng Trung ương lâm thời các doanh nghiệp ngoài quốc doanh", type: "Position", name: "Chủ tịch Hội đồng Trung ương lâm thời các doanh nghiệp ngoài quốc doanh"});
MERGE (p:Position {id: "Đại biểu Quốc hội Việt Namkhóa VII, VIII, IX", type: "Position", name: "Đại biểu Quốc hội Việt Namkhóa VII, VIII, IX"});
MERGE (p:Position {id: "Bộ trưởng Bộ Thương nghiệp", type: "Position", name: "Bộ trưởng Bộ Thương nghiệp"});
MERGE (p:Position {id: "Bộ trưởng Bộ Nội thương", type: "Position", name: "Bộ trưởng Bộ Nội thương"});
MERGE (p:Position {id: "Bí thư Tỉnh ủy Quảng Nam – Đà Nẵng", type: "Position", name: "Bí thư Tỉnh ủy Quảng Nam – Đà Nẵng"});
MERGE (p:Position {id: "Phó Bí thư Tỉnh ủy Quảng Nam – Đà Nẵng", type: "Position", name: "Phó Bí thư Tỉnh ủy Quảng Nam – Đà Nẵng"});
MERGE (p:Position {id: "Bí thư Tỉnh ủy Quảng Nam", type: "Position", name: "Bí thư Tỉnh ủy Quảng Nam"});
MERGE (p:Position {id: "Phó Bí thư Tỉnh ủy Quảng Nam", type: "Position", name: "Phó Bí thư Tỉnh ủy Quảng Nam"});

// Create Location nodes
MERGE (l:Location {id: "Sài Gòn, Nam kỳ, Liên bang Đông Dương", type: "Location", name: "Sài Gòn, Nam kỳ, Liên bang Đông Dương"});
MERGE (l:Location {id: "Thành phố Hồ Chí Minh, Việt Nam", type: "Location", name: "Thành phố Hồ Chí Minh, Việt Nam"});
MERGE (l:Location {id: "Phú Thọ, Việt Nam Dân chủ Cộng hòa", type: "Location", name: "Phú Thọ, Việt Nam Dân chủ Cộng hòa"});
MERGE (l:Location {id: "Quảng Nam", type: "Location", name: "Quảng Nam"});
MERGE (l:Location {id: "Hà Nội", type: "Location", name: "Hà Nội"});
MERGE (l:Location {id: "Mỹ Tho, Liên bang Đông Dương", type: "Location", name: "Mỹ Tho, Liên bang Đông Dương"});
MERGE (l:Location {id: "Sơn Công, Ứng Hòa, tỉnh Hà Đông, Liên bang Đông Dương", type: "Location", name: "Sơn Công, Ứng Hòa, tỉnh Hà Đông, Liên bang Đông Dương"});
MERGE (l:Location {id: "thành phố Nam Định, tỉnh Nam Định, Liên bang Đông Dương", type: "Location", name: "thành phố Nam Định, tỉnh Nam Định, Liên bang Đông Dương"});
MERGE (l:Location {id: "Hà Nội, Việt Nam", type: "Location", name: "Hà Nội, Việt Nam"});
MERGE (l:Location {id: "Đào Xá, Thanh Thủy, Phú Thọ, Bắc Kỳ, Liên bang Đông Dương", type: "Location", name: "Đào Xá, Thanh Thủy, Phú Thọ, Bắc Kỳ, Liên bang Đông Dương"});
MERGE (l:Location {id: "Bệnh viện Hữu Nghị, Hà Nội, Việt Nam", type: "Location", name: "Bệnh viện Hữu Nghị, Hà Nội, Việt Nam"});
MERGE (l:Location {id: "tỉnh Hưng Yên, Liên bang Đông Dương", type: "Location", name: "tỉnh Hưng Yên, Liên bang Đông Dương"});
MERGE (l:Location {id: "Bắc Kạn, Bắc Kỳ, Liên bang Đông Dương", type: "Location", name: "Bắc Kạn, Bắc Kỳ, Liên bang Đông Dương"});
MERGE (l:Location {id: "Thăng Bình, Quảng Nam, Liên bang Đông Dương", type: "Location", name: "Thăng Bình, Quảng Nam, Liên bang Đông Dương"});
MERGE (l:Location {id: "Đà Nẵng, Việt Nam", type: "Location", name: "Đà Nẵng, Việt Nam"});

// Create Award nodes
MERGE (a:Award {id: "Huy hiệu 50 năm tuổi Đảng", type: "Award", name: "Huy hiệu 50 năm tuổi Đảng"});

// Create MilitaryCareer nodes
MERGE (m:MilitaryCareer {id: "Công an nhân dân Việt Nam", type: "MilitaryCareer", name: "Công an nhân dân Việt Nam"});
MERGE (m:MilitaryCareer {id: "22px Quân đội nhân dân Việt Nam", type: "MilitaryCareer", name: "22px Quân đội nhân dân Việt Nam"});

// Create SERVED_AS relationships
MATCH (p:Politician {id: "Bùi Thiện Ngộ"}), (pos:Position {id: "Bộ trưởng Bộ Nội vụ (Nay là Bộ Công an)"}) MERGE (p)-[:SERVED_AS {term_start: "9 tháng 8 năm 1991", term_end: "6 tháng 11 năm 1996"}]->(pos);
MATCH (p:Politician {id: "Bùi Thiện Ngộ"}), (pos:Position {id: "Ủy viên Bộ Chính trị"}) MERGE (p)-[:SERVED_AS {term_start: "1991", term_end: "1996"}]->(pos);
MATCH (p:Politician {id: "Cù Thị Hậu"}), (pos:Position {id: "40pxChủ tịch Hội Người cao tuổi Việt Nam"}) MERGE (p)-[:SERVED_AS {term_start: "11 tháng 11 năm 2011", term_end: "9 tháng 11 năm 2016"}]->(pos);
MATCH (p:Politician {id: "Cù Thị Hậu"}), (pos:Position {id: "Phó Chủ tịch Hội Người cao tuổi Việt Nam"}) MERGE (p)-[:SERVED_AS {term_start: "30 tháng 12 năm 2006", term_end: "11 tháng 11 năm 2011"}]->(pos);
MATCH (p:Politician {id: "Cù Thị Hậu"}), (pos:Position {id: "Chủ tịch Tổng Công đoàn Việt Nam"}) MERGE (p)-[:SERVED_AS {term_start: "3 tháng 11 năm 1998", term_end: "30 tháng 12 năm 2006"}]->(pos);
MATCH (p:Politician {id: "Cù Thị Hậu"}), (pos:Position {id: "Phó Chủ tịch thường trực Tổng Công đoàn Việt Nam"}) MERGE (p)-[:SERVED_AS {term_start: "17 tháng 10 năm 1988", term_end: "6 tháng 11 năm 1998"}]->(pos);
MATCH (p:Politician {id: "Cù Thị Hậu"}), (pos:Position {id: "Ủy viên Trung ương Đảng khóa VI, VII, VIII, IX"}) MERGE (p)-[:SERVED_AS {term_start: "18 tháng 12 năm 1986", term_end: "25 tháng 4 năm 2006"}]->(pos);
MATCH (p:Politician {id: "Hoàng Bích Sơn"}), (pos:Position {id: "Trưởng ban Ban Đối ngoại Trung ương Đảng Cộng sản Việt Nam"}) MERGE (p)-[:SERVED_AS {term_start: "", term_end: ""}]->(pos);
MATCH (p:Politician {id: "Hoàng Bích Sơn"}), (pos:Position {id: "Ủy viên Ủy ban Thường vụ Quốc hội, Chủ nhiệm Ủy ban Đối ngoại Quốc hội"}) MERGE (p)-[:SERVED_AS {term_start: "1992", term_end: "1997"}]->(pos);
MATCH (p:Politician {id: "Cao Đăng Chiếm"}), (pos:Position {id: "Thứ trưởng Thường trực Bộ Công an"}) MERGE (p)-[:SERVED_AS {term_start: "", term_end: ""}]->(pos);
MATCH (p:Politician {id: "Hoàng Cầm (tướng)"}), (pos:Position {id: "Tổng Thanh tra Quân đội"}) MERGE (p)-[:SERVED_AS {term_start: "1987", term_end: "1992"}]->(pos);
MATCH (p:Politician {id: "Hoàng Cầm (tướng)"}), (pos:Position {id: "Tư lệnh Quân khu 4"}) MERGE (p)-[:SERVED_AS {term_start: "1981", term_end: "1986"}]->(pos);
MATCH (p:Politician {id: "Hoàng Cầm (tướng)"}), (pos:Position {id: "Phó Chủ tịch Ủy ban Quân quản Sài Gòn - Gia Định"}) MERGE (p)-[:SERVED_AS {term_start: "3 tháng 5 năm 1975", term_end: "20 tháng 1 năm 1976"}]->(pos);
MATCH (p:Politician {id: "Hoàng Cầm (tướng)"}), (pos:Position {id: "Tư lệnh Quân đoàn 4"}) MERGE (p)-[:SERVED_AS {term_start: "1974", term_end: "1981"}]->(pos);
MATCH (p:Politician {id: "Hoàng Cầm (tướng)"}), (pos:Position {id: "Phó Tư lệnh, Tham mưu trưởng Quân Giải phóng miền Nam Việt Nam"}) MERGE (p)-[:SERVED_AS {term_start: "1970", term_end: "1974"}]->(pos);
MATCH (p:Politician {id: "Hoàng Cầm (tướng)"}), (pos:Position {id: "Sư đoàn trưởng Sư đoàn 9"}) MERGE (p)-[:SERVED_AS {term_start: "1964", term_end: "1970"}]->(pos);
MATCH (p:Politician {id: "Hoàng Cầm (tướng)"}), (pos:Position {id: "Sư đoàn trưởng Sư đoàn 312"}) MERGE (p)-[:SERVED_AS {term_start: "1955", term_end: "1964"}]->(pos);
MATCH (p:Politician {id: "Hồng Hà (nhà báo)"}), (pos:Position {id: "Trưởng ban Đối ngoại Trung ương"}) MERGE (p)-[:SERVED_AS {term_start: "tháng 6 năm 1991", term_end: "tháng 6 năm 1996"}]->(pos);
MATCH (p:Politician {id: "Hồng Hà (nhà báo)"}), (pos:Position {id: "Chánh Văn phòng Trung ương Đảng"}) MERGE (p)-[:SERVED_AS {term_start: "tháng 3 năm 1987", term_end: "1991"}]->(pos);
MATCH (p:Politician {id: "Hồng Hà (nhà báo)"}), (pos:Position {id: "Tổng biên tập Báo Nhân dân"}) MERGE (p)-[:SERVED_AS {term_start: "1982", term_end: "1987"}]->(pos);
MATCH (p:Politician {id: "Bùi Danh Lưu"}), (pos:Position {id: "Bộ trưởng Bộ Giao thông Vận tải"}) MERGE (p)-[:SERVED_AS {term_start: "21 tháng 6 năm 1986", term_end: "6 tháng 11 năm 1996"}]->(pos);
MATCH (p:Politician {id: "Hoàng Quy"}), (pos:Position {id: "Bộ trưởng Bộ Tài chính"}) MERGE (p)-[:SERVED_AS {term_start: "16 tháng 2 năm 1987", term_end: "1 tháng 2 năm 1992"}]->(pos);
MATCH (p:Politician {id: "Hoàng Quy"}), (pos:Position {id: "Phó Chủ nhiệm thứ nhất Ủy ban Kế hoạch Nhà nước"}) MERGE (p)-[:SERVED_AS {term_start: "29 tháng 10 năm 1983", term_end: "16 tháng 2 năm 1987"}]->(pos);
MATCH (p:Politician {id: "Hoàng Quy"}), (pos:Position {id: "Bí thư Tỉnh ủy Vĩnh Phú"}) MERGE (p)-[:SERVED_AS {term_start: "Tháng 10, 1977", term_end: "Tháng 10, 1983"}]->(pos);
MATCH (p:Politician {id: "Hoàng Quy"}), (pos:Position {id: "Bí thư Tỉnh ủy Lào Cai"}) MERGE (p)-[:SERVED_AS {term_start: "Đầu 1949", term_end: "1954"}]->(pos);
MATCH (p:Politician {id: "Hoàng Quy"}), (pos:Position {id: "Bí thư Tỉnh ủy Lào Cai"}) MERGE (p)-[:SERVED_AS {term_start: "Cuối 1947", term_end: "Tháng 4, 1948"}]->(pos);
MATCH (p:Politician {id: "Hoàng Trường Minh"}), (pos:Position {id: "Phó Chủ tịch Quốc hội Việt Nam"}) MERGE (p)-[:SERVED_AS {term_start: "19 tháng 4 năm 1987", term_end: "12 tháng 10 năm 1989"}]->(pos);
MATCH (p:Politician {id: "Hoàng Trường Minh"}), (pos:Position {id: "Trưởng ban Dân tộc Trung ương"}) MERGE (p)-[:SERVED_AS {term_start: "1 tháng 2 năm 1982", term_end: "1 tháng 8 năm 1989"}]->(pos);
MATCH (p:Politician {id: "Hoàng Trường Minh"}), (pos:Position {id: "Chủ tịch Hội đồng Dân tộc của Quốc hội"}) MERGE (p)-[:SERVED_AS {term_start: "26 tháng 4 năm 1981", term_end: "19 tháng 4 năm 1987"}]->(pos);
MATCH (p:Politician {id: "Hoàng Minh Thắng"}), (pos:Position {id: "Chủ tịch Hội đồng Trung ương lâm thời các doanh nghiệp ngoài quốc doanh"}) MERGE (p)-[:SERVED_AS {term_start: "1991", term_end: "1998"}]->(pos);
MATCH (p:Politician {id: "Hoàng Minh Thắng"}), (pos:Position {id: "Đại biểu Quốc hội Việt Namkhóa VII, VIII, IX"}) MERGE (p)-[:SERVED_AS {term_start: "1981", term_end: "1997"}]->(pos);
MATCH (p:Politician {id: "Hoàng Minh Thắng"}), (pos:Position {id: "Bộ trưởng Bộ Thương nghiệp"}) MERGE (p)-[:SERVED_AS {term_start: "1990", term_end: "1991"}]->(pos);
MATCH (p:Politician {id: "Hoàng Minh Thắng"}), (pos:Position {id: "Bộ trưởng Bộ Nội thương"}) MERGE (p)-[:SERVED_AS {term_start: "1986", term_end: "1990"}]->(pos);
MATCH (p:Politician {id: "Hoàng Minh Thắng"}), (pos:Position {id: "Bí thư Tỉnh ủy Quảng Nam – Đà Nẵng"}) MERGE (p)-[:SERVED_AS {term_start: "1982", term_end: "1986"}]->(pos);
MATCH (p:Politician {id: "Hoàng Minh Thắng"}), (pos:Position {id: "Phó Bí thư Tỉnh ủy Quảng Nam – Đà Nẵng"}) MERGE (p)-[:SERVED_AS {term_start: "1975", term_end: "1982"}]->(pos);
MATCH (p:Politician {id: "Hoàng Minh Thắng"}), (pos:Position {id: "Bí thư Tỉnh ủy Quảng Nam"}) MERGE (p)-[:SERVED_AS {term_start: "1970", term_end: "1975"}]->(pos);
MATCH (p:Politician {id: "Hoàng Minh Thắng"}), (pos:Position {id: "Phó Bí thư Tỉnh ủy Quảng Nam"}) MERGE (p)-[:SERVED_AS {term_start: "1967", term_end: "1969"}]->(pos);

// Create SUCCEEDED relationships
MATCH (p1:Politician {id: "Bùi Thiện Ngộ"}), (p2:Politician {id: "Mai Chí Thọ"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Bùi Thiện Ngộ"}), (p2:Politician {id: "Mai Chí Thọ"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Cù Thị Hậu"}), (p2:Politician {id: "Nguyễn Tấn Trịnh"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Cù Thị Hậu"}), (p2:Politician {id: "Nguyễn Văn Tư"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Bích Sơn"}), (p2:Politician {id: "Vũ Quang (định hướng)"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Bích Sơn"}), (p2:Politician {id: "Nguyễn Thị Bình"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Cầm (tướng)"}), (p2:Politician {id: "Lê Quang Hòa"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Cầm (tướng)"}), (p2:Politician {id: "Hoàng Minh Thi"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Cầm (tướng)"}), (p2:Politician {id: "Nguyễn Minh Châu (thượng tướng)"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Cầm (tướng)"}), (p2:Politician {id: "Lê Trọng Tấn"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hồng Hà (nhà báo)"}), (p2:Politician {id: "Hoàng Bích Sơn"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hồng Hà (nhà báo)"}), (p2:Politician {id: "Nguyễn Khánh (Phó Thủ tướng)"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hồng Hà (nhà báo)"}), (p2:Politician {id: "Hoàng Tùng"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Bùi Danh Lưu"}), (p2:Politician {id: "Đồng Sĩ Nguyên"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Quy"}), (p2:Politician {id: "Vũ Tuân"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Quy"}), (p2:Politician {id: "Kim Ngọc"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Quy"}), (p2:Politician {id: "Vũ Nhất"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Quy"}), (p2:Politician {id: "Lê Thanh (chính khách)"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Trường Minh"}), (p2:Politician {id: "Xuân Thủy"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Trường Minh"}), (p2:Politician {id: "Hoàng Văn Kiểu"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Trường Minh"}), (p2:Politician {id: "Chu Văn Tấn"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Minh Thắng"}), (p2:Politician {id: "Hoàng Đức Nghi"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Minh Thắng"}), (p2:Politician {id: "Lê Đức Thịnh"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Minh Thắng"}), (p2:Politician {id: "Hồ Nghinh"}) MERGE (p1)-[:SUCCEEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Minh Thắng"}), (p2:Politician {id: "Trần Thận"}) MERGE (p1)-[:SUCCEEDED]->(p2);

// Create PRECEDED relationships
MATCH (p1:Politician {id: "Bùi Thiện Ngộ"}), (p2:Politician {id: "Lê Minh Hương"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Bùi Thiện Ngộ"}), (p2:Politician {id: "Lê Minh Hương"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Cù Thị Hậu"}), (p2:Politician {id: "Phạm Thị Hải Chuyền"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Cù Thị Hậu"}), (p2:Politician {id: "Đặng Ngọc Tùng"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Bích Sơn"}), (p2:Politician {id: "Hồng Hà (nhà báo)"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Bích Sơn"}), (p2:Politician {id: "Đỗ Văn Tài"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Cầm (tướng)"}), (p2:Politician {id: "Nguyễn Kiệm"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Cầm (tướng)"}), (p2:Politician {id: "Nguyễn Quốc Thước"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Cầm (tướng)"}), (p2:Politician {id: "Nguyễn Văn Quảng"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Cầm (tướng)"}), (p2:Politician {id: "Nguyễn Minh Châu (thượng tướng)"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Cầm (tướng)"}), (p2:Politician {id: "Nguyễn Thăng Bình"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hồng Hà (nhà báo)"}), (p2:Politician {id: "Nguyễn Văn Son"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hồng Hà (nhà báo)"}), (p2:Politician {id: "Phan Diễn"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hồng Hà (nhà báo)"}), (p2:Politician {id: "Hà Đăng"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Bùi Danh Lưu"}), (p2:Politician {id: "Lê Ngọc Hoàn"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Quy"}), (p2:Politician {id: "Hồ Tế"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Quy"}), (p2:Politician {id: "Đậu Ngọc Xuân"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Quy"}), (p2:Politician {id: "Nguyễn Văn Tôn"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Quy"}), (p2:Politician {id: "Hoàng Trường Minh"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Quy"}), (p2:Politician {id: "Vũ Nhất"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Trường Minh"}), (p2:Politician {id: "Phùng Văn Tửu"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Trường Minh"}), (p2:Politician {id: "Nông Đức Mạnh"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Minh Thắng"}), (p2:Politician {id: "Hồ Nghinh"}) MERGE (p1)-[:PRECEDED]->(p2);
MATCH (p1:Politician {id: "Hoàng Minh Thắng"}), (p2:Politician {id: "Đỗ Thế Chấp"}) MERGE (p1)-[:PRECEDED]->(p2);

// Create BORN_AT relationships
MATCH (p:Politician {id: "Bùi Thiện Ngộ"}), (l:Location {id: "Sài Gòn, Nam kỳ, Liên bang Đông Dương"}) MERGE (p)-[:BORN_AT]->(l);
MATCH (p:Politician {id: "Cù Thị Hậu"}), (l:Location {id: "Phú Thọ, Việt Nam Dân chủ Cộng hòa"}) MERGE (p)-[:BORN_AT]->(l);
MATCH (p:Politician {id: "Hoàng Bích Sơn"}), (l:Location {id: "Quảng Nam"}) MERGE (p)-[:BORN_AT]->(l);
MATCH (p:Politician {id: "Cao Đăng Chiếm"}), (l:Location {id: "Mỹ Tho, Liên bang Đông Dương"}) MERGE (p)-[:BORN_AT]->(l);
MATCH (p:Politician {id: "Hoàng Cầm (tướng)"}), (l:Location {id: "Sơn Công, Ứng Hòa, tỉnh Hà Đông, Liên bang Đông Dương"}) MERGE (p)-[:BORN_AT]->(l);
MATCH (p:Politician {id: "Hồng Hà (nhà báo)"}), (l:Location {id: "thành phố Nam Định, tỉnh Nam Định, Liên bang Đông Dương"}) MERGE (p)-[:BORN_AT]->(l);
MATCH (p:Politician {id: "Bùi Danh Lưu"}), (l:Location {id: "Đào Xá, Thanh Thủy, Phú Thọ, Bắc Kỳ, Liên bang Đông Dương"}) MERGE (p)-[:BORN_AT]->(l);
MATCH (p:Politician {id: "Hoàng Quy"}), (l:Location {id: "tỉnh Hưng Yên, Liên bang Đông Dương"}) MERGE (p)-[:BORN_AT]->(l);
MATCH (p:Politician {id: "Hoàng Trường Minh"}), (l:Location {id: "Bắc Kạn, Bắc Kỳ, Liên bang Đông Dương"}) MERGE (p)-[:BORN_AT]->(l);
MATCH (p:Politician {id: "Hoàng Minh Thắng"}), (l:Location {id: "Thăng Bình, Quảng Nam, Liên bang Đông Dương"}) MERGE (p)-[:BORN_AT]->(l);

// Create DIED_AT relationships
MATCH (p:Politician {id: "Bùi Thiện Ngộ"}), (l:Location {id: "Thành phố Hồ Chí Minh, Việt Nam"}) MERGE (p)-[:DIED_AT]->(l);
MATCH (p:Politician {id: "Hoàng Bích Sơn"}), (l:Location {id: "Hà Nội"}) MERGE (p)-[:DIED_AT]->(l);
MATCH (p:Politician {id: "Cao Đăng Chiếm"}), (l:Location {id: "Thành phố Hồ Chí Minh, Việt Nam"}) MERGE (p)-[:DIED_AT]->(l);
MATCH (p:Politician {id: "Hồng Hà (nhà báo)"}), (l:Location {id: "Hà Nội, Việt Nam"}) MERGE (p)-[:DIED_AT]->(l);
MATCH (p:Politician {id: "Bùi Danh Lưu"}), (l:Location {id: "Bệnh viện Hữu Nghị, Hà Nội, Việt Nam"}) MERGE (p)-[:DIED_AT]->(l);
MATCH (p:Politician {id: "Hoàng Trường Minh"}), (l:Location {id: "Hà Nội, Việt Nam"}) MERGE (p)-[:DIED_AT]->(l);
MATCH (p:Politician {id: "Hoàng Minh Thắng"}), (l:Location {id: "Đà Nẵng, Việt Nam"}) MERGE (p)-[:DIED_AT]->(l);

// Create AWARDED relationships
MATCH (p:Politician {id: "Bùi Danh Lưu"}), (a:Award {id: "Huy hiệu 50 năm tuổi Đảng"}) MERGE (p)-[:AWARDED]->(a);

// Create SERVED_IN relationships
MATCH (p:Politician {id: "Bùi Thiện Ngộ"}), (m:MilitaryCareer {id: "Công an nhân dân Việt Nam"}) MERGE (p)-[:SERVED_IN]->(m);
MATCH (p:Politician {id: "Cao Đăng Chiếm"}), (m:MilitaryCareer {id: "Công an nhân dân Việt Nam"}) MERGE (p)-[:SERVED_IN]->(m);
MATCH (p:Politician {id: "Hoàng Cầm (tướng)"}), (m:MilitaryCareer {id: "22px Quân đội nhân dân Việt Nam"}) MERGE (p)-[:SERVED_IN]->(m);
MATCH (p:Politician {id: "Hoàng Minh Thắng"}), (m:MilitaryCareer {id: "22px Quân đội nhân dân Việt Nam"}) MERGE (p)-[:SERVED_IN]->(m);