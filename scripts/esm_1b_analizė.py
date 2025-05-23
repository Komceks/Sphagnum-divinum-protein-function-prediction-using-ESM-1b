# -*- coding: utf-8 -*-
"""ESM-1b analizė.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1aaA7PtUZBtN-MPJ177XhrA1AvcdG2JG7

# Reikalingi paketai
"""

!pip install git+https://github.com/facebookresearch/esm.git@main biopython umap-learn hdbscan numpy torch

"""# Pasirenkame GPU įrenginį"""

import os
from Bio import SeqIO
import torch
import esm
import numpy as np

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print("Using device:", device)

"""# Užtikriname tik galimas amino rūgščių anotacijas"""

fasta_path = '/content/Smagellanicum_521_v1.1.protein_primaryTranscriptOnly.fa'

raw_records = list(SeqIO.parse(fasta_path, "fasta"))

MAX_LEN = 1022
cleaned_data = []
for rec in raw_records:
    seq = str(rec.seq)
    if len(seq) > MAX_LEN:
        continue
    seq = "".join([aa if aa in "ACDEFGHIKLMNPQRSTVWY" else "X" for aa in seq])
    cleaned_data.append((rec.id, seq))

print(f"Kept {len(cleaned_data)} / {len(raw_records)} sequences under {MAX_LEN} aa")

"""# Persisiunčiame ESM-1b modelį ir užkrauname"""

model, alphabet = esm.pretrained.esm1b_t33_650M_UR50S()
model = model.to(device)
model.eval()
batch_converter = alphabet.get_batch_converter()

"""# Prognozuojame baltymų funkcijas su T4 GPU"""

out_labels = []
out_embs   = []

BATCH_SIZE = 32
for i in range(0, len(cleaned_data), BATCH_SIZE):
    batch = cleaned_data[i:i+BATCH_SIZE]
    labels, seqs, tokens = batch_converter(batch)
    tokens = tokens.to(device)
    with torch.no_grad():
        results = model(tokens, repr_layers=[33], return_contacts=False)
    reps = results["representations"][33]
    for j, (lbl, seq) in enumerate(batch):
        emb = reps[j, 1:len(seq)+1].mean(0).cpu().numpy()
        out_labels.append(lbl)
        out_embs.append(emb)
    if (i//BATCH_SIZE) % 10 == 0:
        print(f"Processed {i+BATCH_SIZE} / {len(cleaned_data)} sequences")

embs_arr = np.stack(out_embs)
labels_arr = np.array(out_labels, dtype=object)
save_dir = '/content/esm_embeddings'
os.makedirs(save_dir, exist_ok=True)
np.save(os.path.join(save_dir, 'labels.npy'), labels_arr)
np.save(os.path.join(save_dir, 'embeddings.npy'), embs_arr)
print("Saved embeddings to", save_dir)

"""# Atliekame PCA sumažindami dimensijų kiekį iki 50 ir UMAP į 2 ašis."""

import umap
from sklearn.decomposition import PCA

embeddings = np.load("/content/embeddings.npy", allow_pickle=True)

pca = PCA(n_components=50, random_state=7)
emb_pca = pca.fit_transform(embeddings)

reducer = umap.UMAP(n_components=2, random_state=7, min_dist=0.1)
emb_umap = reducer.fit_transform(emb_pca)

print(emb_umap.shape)

"""# Klasterizuojame"""

import hdbscan

clusterer = hdbscan.HDBSCAN(min_cluster_size=20, min_samples=10)
labels_uv = clusterer.fit_predict(emb_umap)

"""# Atvaizduojame klasterius plokštumoje"""

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

labels = np.load("/content/labels.npy", allow_pickle=True)
df = pd.DataFrame({
    "umap1": emb_umap[:, 0],
    "umap2": emb_umap[:, 1],
    "cluster": labels_uv,
    "protein": labels
})
df.to_csv("proteome_umap.csv", index=False)

plt.figure(figsize=(8,6))
for c in df["cluster"].unique():
    mask = df["cluster"] == c
    plt.scatter(df.loc[mask, "umap1"], df.loc[mask, "umap2"],
                s=5, label=f"{c} klasteris" if c!=-1 else "Triukšmas", alpha=0.6)

plt.legend(markerscale=1.5, fontsize="small", ncol=4, bbox_to_anchor=(1,1))
plt.title("Sphagnum divinum Proteomo klasteriai")
plt.xlabel("UMAP 1"); plt.ylabel("UMAP 2")
plt.savefig("cluster_map.png", dpi=300, bbox_inches="tight")
plt.show()

"""# Viso klasterių"""

import pandas as pd
df = pd.read_csv("/content/proteome_umap.csv")
print(df['cluster'].nunique(dropna=True))

"""# Suliejame UMAP informaciją su anotacijomis"""

import pandas as pd

umap_df = pd.read_csv("/content/proteome_umap.csv")
anno_df = pd.read_csv("/content/Smagellanicum_521_v1.1.annotation_info.txt", sep="\t")

anno_df.columns = [c.lstrip("#") for c in anno_df.columns]
anno_df = anno_df.rename(columns={"peptideName": "protein"})
annotated = umap_df.merge(
    anno_df,
    on="protein",
    how="left",
    indicator=True
)
annotated.to_csv("proteome_umap_with_AF2_annotations.csv", index=False)
annotated.head(10)

"""# Patikriname klasterių grynumą"""

import pandas as pd
from collections import Counter

df = pd.read_csv("proteome_umap_with_AF2_annotations.csv")
purity_records = []

for cluster_id, sub in df.groupby("cluster"):
    labels = sub["Pfam"].dropna().tolist()
    if not labels:
        continue
    top_label, top_count = Counter(labels).most_common(1)[0]
    purity = top_count / len(sub)
    purity_records.append({
        "cluster": cluster_id,
        "cluster_size": len(sub),
        "top_Pfam": top_label,
        "top_count": top_count,
        "purity": purity
    })

purity_df = pd.DataFrame(purity_records).sort_values("purity", ascending=False)
purity_df.to_csv("cluster_purity.csv", index=False)

high_purity = purity_df[purity_df["purity"] >= 0.5]
print(high_purity)
low_purity = purity_df[purity_df["purity"] < 0.5]
print(low_purity)

low_purity.to_csv("low_purity_clusters.csv", index=False)
high_purity.to_csv("high_purity_clusters.csv", index=False)

"""# Atliekame Fisherio testą su GO identifikatoriais klasteriuose"""

import scipy.stats as stats

df["GO1"] = df["GO"].str.split(";", expand=True)[0].fillna("None")

results = []
clusters = df["cluster"].unique()
terms    = df["GO1"].unique()

for cluster_id in clusters:
    in_cluster = df["cluster"] == cluster_id
    for term in terms:
        in_term = df["GO1"] == term
        a = ((in_cluster) & (in_term)).sum()
        b = ((in_cluster) & (~in_term)).sum()
        c = ((~in_cluster) & (in_term)).sum()
        d = ((~in_cluster) & (~in_term)).sum()
        if a + b == 0 or a + c == 0:
            continue
        _, pval = stats.fisher_exact([[a,b],[c,d]], alternative="greater")

        if pval < 0.01:
            results.append({
                "cluster": cluster_id,
                "term": term,
                "count_in_cluster": a,
                "cluster_size": a+b,
                "p_value": pval
            })

enrich_df = pd.DataFrame(results).sort_values("p_value")
print(enrich_df.head())
enrich_df.to_csv("cluster_enrichments.csv", index=False)

"""# Atvaizduojame klasterius pagal jų grynumą"""

import matplotlib.pyplot as plt

df = pd.read_csv("proteome_umap_with_AF2_annotations.csv")
purity_df = pd.read_csv("cluster_purity.csv")

df = df.merge(purity_df[["cluster","purity"]], on="cluster", how="left")

mask_noise  = df["cluster"] == -1
mask_clusters = ~mask_noise

df_clusters = df[mask_clusters]
df_noise  = df[mask_noise]

plt.figure(figsize=(6,6))

plt.scatter(
    df_noise["umap1"],
    df_noise["umap2"],
    c="red",
    s=5,
    label="Triukšmas (-1 klasteriai)"
)
sc = plt.scatter(
    df_clusters["umap1"],
    df_clusters["umap2"],
    c=df_clusters["purity"],
    cmap="viridis",
    s=5,
    label="Klasteriai"
)
plt.colorbar(sc, label="Klasterių grynumas")

plt.legend(markerscale=4, fontsize="small", loc="best")
plt.title("Proteomo UMAP: Grynumo atvaizdavimas klasteriuose")
plt.xlabel("UMAP 1")
plt.ylabel("UMAP 2")
plt.tight_layout()
plt.savefig("cluster_map_with_purity.png", dpi=300, bbox_inches="tight")
plt.show()

"""# Sphmag13G047200

Nustatome baltymo klasterį. Bei visus baltymus esančius klasteryje.
"""

import pandas as pd

df = pd.read_csv("proteome_umap_with_AF2_annotations.csv")
target = "Sphmag13G047200.1.p"

mask_target = df["protein"] == target

if mask_target.sum() == 0:
    raise ValueError(f"{target} not found in the table.")

cluster_id = df.loc[mask_target, "cluster"].iloc[0]
print(f"{target} is in cluster {cluster_id}")
cluster_df = df[df["cluster"] == cluster_id]

print(f"\nAll proteins in cluster {cluster_id} (Overall: {cluster_df['protein'].nunique()} proteins):")
print(cluster_df[["protein", "arabi-defline"]].to_string(index=False))

"""Paryškiname klasterį UMAP'e"""

import pandas as pd
import matplotlib.pyplot as plt

cluster_of_interest = 18
df = pd.read_csv("/content/proteome_umap_with_AF2_annotations.csv")
df["in_cluster"] = df["cluster"] == cluster_of_interest

plt.figure(figsize=(6,6))
for flag, grp in df.groupby("in_cluster"):
    lbl = cluster_of_interest if flag else "Kiti"
    plt.scatter(grp["umap1"], grp["umap2"], s=5, label=lbl, alpha=0.6)
plt.legend(markerscale=4)
plt.title(f"Paryškintas {cluster_of_interest} klasteris")
plt.xlabel("UMAP 1")
plt.ylabel("UMAP 2")
plt.savefig(f"cluster_{cluster_of_interest}.png", dpi=300, bbox_inches="tight")
plt.show()

"""Surenkame GO identifikatorius"""

fisher_df = pd.read_csv("cluster_enrichments.csv")

target_cluster = 18
cluster_info = fisher_df.loc[fisher_df['cluster'] == target_cluster]
print(cluster_info)

"""Tikriname klasterio grynumą"""

purity_df = pd.read_csv("cluster_purity.csv")

target_cluster = 18
cluster_info = purity_df.loc[purity_df['cluster'] == target_cluster]
print(cluster_info)

"""# Sphmag01G194900 ir Sphmag02G160700

Nustatome baltymo klasterį. Bei visus baltymus esančius klasteryje.
"""

import pandas as pd

df = pd.read_csv("proteome_umap_with_AF2_annotations.csv")
target = "Sphmag02G160700.1.p"
# target = "Sphmag01G194900.1.p"
mask_target = df["protein"] == target

if mask_target.sum() == 0:
    raise ValueError(f"{target} not found in the table.")

cluster_id = df.loc[mask_target, "cluster"].iloc[0]
print(f"{target} is in cluster {cluster_id}")
cluster_df = df[df["cluster"] == cluster_id]

print(f"\nAll proteins in cluster {cluster_id} (Overall: {cluster_df['protein'].nunique()} proteins):")
print(cluster_df[["protein", "arabi-defline"]].to_string(index=False))

"""Ieškome Sphmag01G194900 kaimynų"""

import pandas as pd

def get_neighbors(df, center_protein, umap1_dist, umap2_dist):
    if center_protein not in df['protein'].values:
        raise ValueError(f"Center protein '{center_protein}' not found in the dataset.")

    center_row = df[df['protein'] == center_protein].iloc[0]
    center_umap1 = center_row['umap1']
    center_umap2 = center_row['umap2']

    mask = (
        df['umap1'].between(center_umap1 - umap1_dist, center_umap1 + umap1_dist) &
        df['umap2'].between(center_umap2 - umap2_dist, center_umap2 + umap2_dist)
    )
    neighbors = df[mask].copy()
    return neighbors[neighbors['protein'] != center_protein]

csv_path = 'proteome_umap_with_AF2_annotations.csv'
center_protein = 'Sphmag01G194900.1.p'
umap1_dist = 0.1
umap2_dist = 0.1

df = pd.read_csv(csv_path)

neighbors_df = get_neighbors(df, center_protein, umap1_dist, umap2_dist)

print(f"Found {len(neighbors_df)} neighbors of '{center_protein}' within "
      f"+/-{umap1_dist} in UMAP1 and +/-{umap2_dist} in UMAP2.")

print(neighbors_df[['protein', 'umap1', 'umap2']])

"""Išsaugome informaciją apie kaimynus"""

df = pd.read_csv("proteome_umap_with_AF2_annotations.csv")
proteins_of_interest = neighbors_df['protein'].tolist()
subset = df[df['protein'].isin(proteins_of_interest)]
print(subset)
subset.to_csv("Sphmag01G194900_neighbors.csv", index=False)

import pandas as pd
import matplotlib.pyplot as plt

proteins_of_interest = ['Sphmag01G194900.1.p', 'Sphmag02G160700.1.p']
df = pd.read_csv("/content/proteome_umap_with_AF2_annotations.csv")
df["is_in"] = df['protein'].isin(proteins_of_interest)

plt.figure(figsize=(6,6))
for flag, grp in df.groupby("is_in"):
    lbl = proteins_of_interest if flag else "Kiti"
    plt.scatter(grp["umap1"], grp["umap2"], s=5, label=lbl, alpha=0.6)
plt.legend(markerscale=4)
plt.title(f"Paryškinti {proteins_of_interest} baltymai")
plt.xlabel("UMAP 1")
plt.ylabel("UMAP 2")
plt.savefig(f"{proteins_of_interest[0]}_{proteins_of_interest[1]}.png", dpi=300, bbox_inches="tight")
plt.show()

"""# Sphmag08G106500

Nustatome baltymo klasterį. Bei visus baltymus esančius klasteryje.
"""

import pandas as pd

df = pd.read_csv("proteome_umap_with_AF2_annotations.csv")
target = "Sphmag08G106500.1.p"

mask_target = df["protein"] == target

if mask_target.sum() == 0:
    raise ValueError(f"{target} not found in the table.")

cluster_id = df.loc[mask_target, "cluster"].iloc[0]
print(f"{target} is in cluster {cluster_id}")
cluster_df = df[df["cluster"] == cluster_id]

print(f"\nAll proteins in cluster {cluster_id} (Overall: {cluster_df['protein'].nunique()} proteins):")
print(cluster_df[["protein", "arabi-defline"]].to_string(index=False))

"""Surenkame GO identifikatorius"""

fisher_df = pd.read_csv("cluster_enrichments.csv")

target_cluster = 220
cluster_info = fisher_df.loc[fisher_df['cluster'] == target_cluster]
print(cluster_info)

cluster_of_interest = 220
df = pd.read_csv("/content/proteome_umap_with_AF2_annotations.csv")
df["in_cluster"] = df["cluster"] == cluster_of_interest

plt.figure(figsize=(6,6))
for flag, grp in df.groupby("in_cluster"):
    lbl = cluster_of_interest if flag else "Kiti"
    plt.scatter(grp["umap1"], grp["umap2"], s=5, label=lbl, alpha=0.6)
plt.legend(markerscale=4)
plt.title(f"Paryškintas {cluster_of_interest} klasteris")
plt.xlabel("UMAP 1")
plt.ylabel("UMAP 2")
plt.savefig(f"cluster_{cluster_of_interest}.png", dpi=300, bbox_inches="tight")
plt.show()

"""# Sphmag01G192500"""

import pandas as pd

df = pd.read_csv("proteome_umap_with_AF2_annotations.csv")
target = "Sphmag01G192500.1.p"

mask_target = df["protein"] == target

if mask_target.sum() == 0:
    raise ValueError(f"{target} not found in the table.")

cluster_id = df.loc[mask_target, "cluster"].iloc[0]
print(f"{target} is in cluster {cluster_id}")
cluster_df = df[df["cluster"] == cluster_id]

print(f"\nAll proteins in cluster {cluster_id} (Overall: {cluster_df['protein'].nunique()} proteins):")
print(cluster_df[["protein", "arabi-defline"]].to_string(index=False))

fisher_df = pd.read_csv("cluster_enrichments.csv")

target_cluster = 205
cluster_info = fisher_df.loc[fisher_df['cluster'] == target_cluster]
print(cluster_info)
cluster_info.to_csv("205_cluster_info.csv")

import pandas as pd
import matplotlib.pyplot as plt

cluster_of_interest = 205
df = pd.read_csv("/content/proteome_umap_with_AF2_annotations.csv")
df["in_cluster"] = df["cluster"] == cluster_of_interest

plt.figure(figsize=(6,6))
for flag, grp in df.groupby("in_cluster"):
    lbl = cluster_of_interest if flag else "Kiti"
    plt.scatter(grp["umap1"], grp["umap2"], s=5, label=lbl, alpha=0.6)
plt.legend(markerscale=4)
plt.title(f"Paryškintas {cluster_of_interest} klasteris")
plt.xlabel("UMAP 1")
plt.ylabel("UMAP 2")
plt.savefig(f"cluster_{cluster_of_interest}.png", dpi=300, bbox_inches="tight")
plt.show()

"""# Sphmag01G058000"""

import pandas as pd

df = pd.read_csv("proteome_umap_with_AF2_annotations.csv")
target = "Sphmag01G058000.1.p"

mask_target = df["protein"] == target

if mask_target.sum() == 0:
    raise ValueError(f"{target} not found in the table.")

cluster_id = df.loc[mask_target, "cluster"].iloc[0]
print(f"{target} is in cluster {cluster_id}")
cluster_df = df[df["cluster"] == cluster_id]

print(f"\nAll proteins in cluster {cluster_id} (Overall: {cluster_df['protein'].nunique()} proteins):")
print(cluster_df[["protein", "arabi-defline"]].to_string(index=False))

fisher_df = pd.read_csv("cluster_enrichments.csv")

target_cluster = 41
cluster_info = fisher_df.loc[fisher_df['cluster'] == target_cluster]
print(cluster_info)

cluster_of_interest = 41
df = pd.read_csv("/content/proteome_umap_with_AF2_annotations.csv")
df["in_cluster"] = df["cluster"] == cluster_of_interest

plt.figure(figsize=(6,6))
for flag, grp in df.groupby("in_cluster"):
    lbl = cluster_of_interest if flag else "Kiti"
    plt.scatter(grp["umap1"], grp["umap2"], s=5, label=lbl, alpha=0.6)
plt.legend(markerscale=4)
plt.title(f"Paryškintas {cluster_of_interest} klasteris")
plt.xlabel("UMAP 1")
plt.ylabel("UMAP 2")
plt.savefig(f"cluster_{cluster_of_interest}.png", dpi=300, bbox_inches="tight")
plt.show()

"""# Kiti klasteriai"""

import pandas as pd

df = pd.read_csv("cluster_purity.csv")
mask_target = df["purity"] == 1.0

cluster_ids = df.loc[mask_target, "cluster"]
anno_df = pd.read_csv("proteome_umap_with_AF2_annotations.csv")
overall_df = anno_df[anno_df["cluster"].isin(cluster_ids)].copy()
for cluster_id in cluster_ids:
    subset = anno_df[anno_df['cluster'] == cluster_id]
    print(f"\nAll proteins in cluster {cluster_id} (Overall: {subset['protein'].nunique()} proteins):")
    print(subset[["protein", "arabi-defline"]].to_string(index=False))

import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("/content/proteome_umap_with_AF2_annotations.csv")
target_clusters = overall_df['cluster'].unique()
cmap = plt.get_cmap("tab20")
colors = {cl: cmap(i) for i, cl in enumerate(target_clusters)}

plt.figure(figsize=(6,6))
others = df[~df["cluster"].isin(target_clusters)]
plt.scatter(
    others["umap1"], others["umap2"],
    c="lightcyan", s=5, label="kiti klasteriai", alpha=0.6
)
for cl in target_clusters:
    sub = df[df["cluster"] == cl]
    plt.scatter(
        sub["umap1"], sub["umap2"],
        c=[colors[cl]],
        s=10,
        label=f"{cl} klasteris",
        alpha=0.8
    )

plt.legend(markerscale=2, fontsize="small", ncol=1, loc='upper left', bbox_to_anchor=(1, 1))
plt.title("Paryškinti 100% grynumo klasteriai")
plt.xlabel("UMAP 1")
plt.ylabel("UMAP 2")
plt.tight_layout()
plt.savefig(f"highlight_pure_clusters.png", dpi=300, bbox_inches="tight")
plt.show()