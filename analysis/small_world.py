# analysis/small_world.py

import networkx as nx
import numpy as np
import json
from tqdm import tqdm
import random

with open('data/processed/graph/knowledge_graph_enriched.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

G = nx.Graph()
if isinstance(data, dict) and 'edges' in data:
    for edge_type, edge_list in data['edges'].items():
        for e in edge_list:
            if e.get('from') and e.get('to'):
                G.add_edge(str(e['from']), str(e['to']))

N, M = G.number_of_nodes(), G.number_of_edges()
avg_k = 2*M/N if N>0 else 0

C_obs = nx.average_clustering(G)

LCC = G.subgraph(max(nx.connected_components(G), key=len)).copy()
n_lcc = LCC.number_of_nodes()

if n_lcc <= 5000:
    all_sp = dict(nx.all_pairs_shortest_path_length(LCC))
    all_dist = [dist for s in all_sp for t, dist in all_sp[s].items() if s != t]
    L_obs = np.mean(all_dist)
    L_min = min(all_dist)
    L_max = max(all_dist)
    diameter = L_max
    exact = True
else:
    samples = random.sample(list(LCC.nodes()), min(1000, n_lcc))
    dists_list = []
    min_dists = []
    max_dists = []
    for s in tqdm(samples, desc="L_obs"):
        d = nx.single_source_shortest_path_length(LCC, s)
        dists = [dist for t, dist in d.items() if t != s]
        dists_list.extend(dists)
        min_dists.append(min(dists))
        max_dists.append(max(dists))
    L_obs = np.mean(dists_list)
    L_min = min(min_dists)
    L_max = max(max_dists)
    diameter = L_max
    exact = False

K = 300
C_rand, L_rand = [], []

for _ in tqdm(range(K), desc="Degree-preserving null"):
    G_rw = G.copy()
    try:
        nx.double_edge_swap(G_rw, nswap=3*M, max_tries=10*M)
    except:
        pass
    
    C_rand.append(nx.average_clustering(G_rw))
    
    lcc_rw = G_rw.subgraph(max(nx.connected_components(G_rw), key=len))
    nodes = list(lcc_rw.nodes())
    samples = random.sample(nodes, min(500, len(nodes)))
    dists = []
    for s in samples:
        d = nx.single_source_shortest_path_length(lcc_rw, s)
        dists.extend([dist for t, dist in d.items() if t != s])
    L_rand.append(np.mean(dists))

C_mean, C_std = np.mean(C_rand), np.std(C_rand)
L_mean, L_std = np.mean(L_rand), np.std(L_rand)
C_lo, C_hi = np.percentile(C_rand, [2.5, 97.5])
L_lo, L_hi = np.percentile(L_rand, [2.5, 97.5])

sigma = (C_obs / C_mean) / (L_obs / L_mean)

p_C = sum(1 for x in C_rand if x >= C_obs) / K
p_L = sum(1 for x in L_rand if abs(x - L_obs) >= abs(L_obs - L_mean)) / K

if sigma > 1:
    status = "SMALL-WORLD"
else:
    status = "KHÔNG PHẢI SMALL-WORLD"

with open('analysis/results/small_world_results.txt', 'w', encoding='utf-8') as f:  
    f.write("NETWORK STATISTICS\n")
    f.write(f"Number of nodes (N) = {N}\n")
    f.write(f"Number of edges (M) = {M}\n")
    f.write(f"Average level (k) = {avg_k:.4f}\n")
    f.write(f"LCC = {n_lcc} ({n_lcc/N*100:.1f}%)\n\n")
    
    f.write("OBSERVED METRICS\n")
    f.write(f"C_obs = {C_obs:.6f}\n")
    f.write(f"L_obs = {L_obs:.4f} ({'exact' if exact else 'sampled'})\n")
    f.write(f"L_min = {L_min}\n")
    f.write(f"L_max = {L_max}\n")
    f.write(f"Diameter = {diameter}\n\n")
    
    f.write(f"NULL MODEL (Degree-preserving, K={K})\n")
    f.write(f"C_rand = {C_mean:.6f} ± {C_std:.6f} [{C_lo:.6f}, {C_hi:.6f}]\n")
    f.write(f"L_rand = {L_mean:.4f} ± {L_std:.4f} [{L_lo:.4f}, {L_hi:.4f}]\n\n")
    
    f.write("STATISTICAL TESTS\n")
    f.write(f"p(C) = {p_C:.4f} {'(sig.)' if p_C < 0.05 else '(n.s.)'}\n")
    f.write(f"p(L) = {p_L:.4f} {'(sig.)' if p_L < 0.05 else '(n.s.)'}\n\n")
    
    f.write("RESULT\n")
    f.write(f"C_obs/C_rand = {C_obs/C_mean:.2f}x\n")
    f.write(f"L_obs/L_rand = {L_obs/L_mean:.2f}x\n\n")
    f.write(f"sigma = {sigma:.4f} => {status}\n")