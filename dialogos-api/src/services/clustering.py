# src/services/clustering.py
import numpy as np
from sklearn.cluster import DBSCAN
from src.services.topic_generation import generate_topic_for_cluster  # Updated import

def perform_clustering(embeddings, min_cluster_size=2):
    """
    Perform clustering on embeddings.
    Args:
        embeddings: List or array of embeddings
        min_cluster_size: Minimum number of points to form a cluster
    Returns:
        List of cluster labels
    """
    try:
        embeddings_array = np.array(embeddings)
        clustering = DBSCAN(eps=0.5, min_samples=min_cluster_size, metric='cosine').fit(embeddings_array)
        return clustering.labels_
    except Exception as e:
        print(f"Error in clustering: {str(e)}")
        return [-1] * len(embeddings)

def generate_cluster_metadata(clusters, titles, distance_matrix):
    """
    Generate metadata for clusters, including topics.
    Args:
        clusters: List of cluster labels
        titles: List of titles corresponding to embeddings
        distance_matrix: Precomputed distance matrix
    Returns:
        Dict mapping cluster IDs to metadata (e.g., topics)
    """
    try:
        cluster_dict = {}
        for cluster_id in set(clusters):
            if cluster_id == -1:  # Noise points
                continue
            indices = [i for i, label in enumerate(clusters) if label == cluster_id]
            cluster_titles = [titles[i] for i in indices]
            if cluster_titles:
                topic = generate_topic_for_cluster(cluster_titles)
                cluster_dict[cluster_id] = {"topic": topic, "size": len(indices)}
            else:
                cluster_dict[cluster_id] = {"topic": "Miscellaneous", "size": 0}
        return cluster_dict
    except Exception as e:
        print(f"Error generating cluster metadata: {str(e)}")
        return {}