(meo) (political-net) PS E:\political-net> python -m algorithm.shortest_path.test_algo_networkx
Loading graph from data\processed\graph\knowledge_graph.json ...
Loaded 5100 nodes, 11664 edges.

Finding shortest path from pol248258 to pol1463408 (networkx)...

Path length (number of edges): 6
[0] pol248258 (Politician) - Võ Văn Thưởng
   └──[SUCCEEDED]──>
[1] pol459014 (Politician) - Nguyễn Xuân Phúc
   └──[PRECEDED]──>
[2] pol436788 (Politician) - Phạm Minh Chính
   └──[PRECEDED]──>
[3] pol3282315 (Politician) - Nguyễn Văn Đọc
   └──[PRECEDED]──>
[4] pol15134650 (Politician) - Nguyễn Xuân Ký
   └──[PRECEDED]──>
[5] pol13653301 (Politician) - Vũ Đại Thắng
   └──[SUCCEEDED]──>
[6] pol1463408 (Politician) - Hoàng Đăng Quang