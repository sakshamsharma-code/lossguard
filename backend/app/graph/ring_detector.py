"""
Graph/structural layer — the core differentiator (research-notes.md §5, §8).

Builds a graph where users are nodes, and edges connect users who share a
device_id, address_id, or payment_method_id. Connected components of this
graph are our "clusters" — groups of accounts linked by hard-to-fake
structural resources, regardless of how their individual behavior looks.

This is intentionally lightweight (NetworkX connected components), NOT a
full GNN/TGNN — see research-notes.md §3 for why that scope was cut.

Run with: python -m app.graph.ring_detector   (builds graph, prints cluster stats)
"""

import pandas as pd
import networkx as nx

from app.db.database import SessionLocal
from app.db import models


def load_links(db):
    return pd.read_sql(db.query(models.DeviceAddressPaymentLink).statement, db.bind)


def build_graph(links: pd.DataFrame) -> nx.Graph:
    """
    Users are nodes. Two users get an edge if they share ANY of:
    device_id, address_id, payment_method_id.

    We add edges via shared "resource nodes" (device/address/payment as
    intermediate nodes), then project down to a user-user graph — this
    is more efficient than O(n^2) pairwise comparison for large datasets.
    """
    G = nx.Graph()

    # Add user nodes
    for user_id in links["user_id"].unique():
        G.add_node(("user", user_id))

    # Add resource nodes + edges (user <-> resource)
    for _, row in links.iterrows():
        user_node = ("user", row["user_id"])
        for resource_type, resource_col in [
            ("device", "device_id"),
            ("address", "address_id"),
            ("payment", "payment_method_id"),
        ]:
            resource_val = row[resource_col]
            if pd.isna(resource_val):
                continue
            resource_node = (resource_type, resource_val)
            G.add_edge(user_node, resource_node)

    return G


def project_to_user_graph(G: nx.Graph) -> nx.Graph:
    """
    Collapse the bipartite user<->resource graph into a user-user graph:
    two users get a direct edge if they share at least one resource node.
    """
    user_nodes = [n for n in G.nodes if n[0] == "user"]
    user_graph = nx.Graph()
    user_graph.add_nodes_from(user_nodes)

    for resource_node in [n for n in G.nodes if n[0] != "user"]:
        connected_users = list(G.neighbors(resource_node))
        # connect every pair of users sharing this resource
        for i in range(len(connected_users)):
            for j in range(i + 1, len(connected_users)):
                user_graph.add_edge(connected_users[i], connected_users[j])

    return user_graph


def get_cluster_info_for_all_users(user_graph: nx.Graph) -> pd.DataFrame:
    """
    Returns one row per user with:
      - cluster_size: size of their connected component (1 if isolated)
      - cluster_density: density of that component's subgraph
      - shared_device_count / shared_address_count / shared_payment_method_count
        (computed separately below, joined in)
    """
    rows = []
    components = list(nx.connected_components(user_graph))

    for component in components:
        subgraph = user_graph.subgraph(component)
        size = len(component)
        density = nx.density(subgraph) if size > 1 else 0.0

        for node in component:
            _, user_id = node
            rows.append({
                "user_id": user_id,
                "cluster_size": size,
                "cluster_density": round(density, 4),
            })

    return pd.DataFrame(rows)


def get_shared_counts(links: pd.DataFrame) -> pd.DataFrame:
    """
    Per-user counts of how many OTHER users share each of their
    device/address/payment identifiers. These feed directly into
    CaseEvidence.shared_device_count etc.
    """
    device_counts = links.groupby("device_id")["user_id"].transform("nunique")
    address_counts = links.groupby("address_id")["user_id"].transform("nunique")
    payment_counts = links.groupby("payment_method_id")["user_id"].transform("nunique")

    out = links[["user_id"]].copy()
    out["shared_device_count"] = device_counts - 1     # exclude self
    out["shared_address_count"] = address_counts - 1
    out["shared_payment_method_count"] = payment_counts - 1

    count_cols = ["shared_device_count", "shared_address_count", "shared_payment_method_count"]
    out[count_cols] = out[count_cols].clip(lower=0)
    return out


def get_cluster_info_for_user(user_graph: nx.Graph, user_id: str) -> dict:
    """Single-user version — used by the API to answer 'who is linked to whom'."""
    target_node = ("user", user_id)
    if target_node not in user_graph:
        return {"cluster_size": 1, "cluster_density": 0.0, "linked_user_ids": []}

    for component in nx.connected_components(user_graph):
        if target_node in component:
            subgraph = user_graph.subgraph(component)
            linked_ids = [uid for (_, uid) in component if uid != user_id]
            return {
                "cluster_size": len(component),
                "cluster_density": round(nx.density(subgraph), 4) if len(component) > 1 else 0.0,
                "linked_user_ids": linked_ids,
            }
    return {"cluster_size": 1, "cluster_density": 0.0, "linked_user_ids": []}


def get_full_graph():
    """Convenience for the API layer."""
    db = SessionLocal()
    links = load_links(db)
    db.close()
    G = build_graph(links)
    return project_to_user_graph(G)


def main():
    db = SessionLocal()
    links = load_links(db)
    db.close()

    G = build_graph(links)
    user_graph = project_to_user_graph(G)

    cluster_df = get_cluster_info_for_all_users(user_graph)
    shared_counts_df = get_shared_counts(links)

    graph_features = cluster_df.merge(shared_counts_df, on="user_id", how="outer").fillna({
        "cluster_size": 1, "cluster_density": 0.0,
        "shared_device_count": 0, "shared_address_count": 0, "shared_payment_method_count": 0
    })

    graph_features.to_csv("data/graph_features.csv", index=False)

    print(f"✅ Graph built: {user_graph.number_of_nodes()} users, "
          f"{user_graph.number_of_edges()} edges")
    multi_user_clusters = cluster_df[cluster_df["cluster_size"] > 1]["cluster_size"].value_counts()
    actual_cluster_count = (cluster_df[cluster_df["cluster_size"] > 1]
                             .groupby("cluster_size").size() // cluster_df[cluster_df["cluster_size"] > 1]["cluster_size"].unique()).sum() \
        if len(multi_user_clusters) else 0
    # simpler/more direct way: count distinct connected components with size>1
    n_actual_clusters = sum(1 for c in nx.connected_components(user_graph) if len(c) > 1)
    print(f"Clusters with >1 user (potential rings): {n_actual_clusters}")
    print(f"\nUsers-per-cluster-size breakdown:\n{multi_user_clusters.sort_index()}")
    print(f"\n✅ Saved -> data/graph_features.csv ({len(graph_features)} rows)")


if __name__ == "__main__":
    main()