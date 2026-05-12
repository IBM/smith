from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances
import numpy as np

commands = []
with open("commands_cluster", 'r') as f:
    for command in f:
        commands.append(command.strip())

model = SentenceTransformer("all-MiniLM-L6-v2")
embeddings = model.encode(commands)
clustering = DBSCAN(eps=0.1, min_samples=2, metric='cosine')
labels = clustering.fit_predict(embeddings)
for command, label in zip(commands, labels):
    print(f"[Cluster {label}] {command}")


