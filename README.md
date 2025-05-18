# Sphagnum divinum baltymų funkcijų prognozavimas su ESM‐1b

Šioje repozitorijoje pasiekiami visi skriptai Sphagnum divinum baltymų funkcijų analizei.

Duomenų paruošimo skriptai yra `scripts/` direktorijoje. Taip pat pasiekiami [Google Colab](https://colab.research.google.com/drive/1aaA7PtUZBtN-MPJ177XhrA1AvcdG2JG7?usp=sharing). Duomenų failai bei diagramos yra `results/` direktorijoje. 

Įterpiniai pasiekiami [Google Drive](https://drive.google.com/drive/folders/1QqFhb3rWzk-tXvBAl7AMzbtd-OnT3x_O?usp=sharing).

## Python reikalavimai

- Python (≥ 3.11)
- Python paketai:
  - `torch`
  - `hdbscan`
  - `numpy`
  - `umap-learn`
  - `biopython`
  - `git+https://github.com/facebookresearch/esm.git@main`

Kaip instaliuoti paketus:
```r
!pip install git+https://github.com/facebookresearch/esm.git@main biopython umap-learn hdbscan numpy torch
```

## Naudojimas

1. Repozitorijos klonavimas:
   ```bash
   git clone https://github.com/Komceks/Sphagnum-divinum-protein-function-prediction-using-ESM-1b.git
   ```

2. Paleisti Jupyter užrašinę `scripts/` direktorijoje:
  ```bash
    jupyter notebook
  ```

## Gauti grafikai

### **cluster_map**: Sklaidos grafikas
- Klasterių atvaizdavimas plokštumoje.

### **cluster_map_with_purity**: Sklaidos grafikas
- Klasterių grynumo atvaizdavimas.

### **highlight_pure_clusters**: Sklaidos grafikas
- 100% grynumo klasterių atvaizdavimas.

### **pfam_cluster_quality_umap**: Sklaidos grafikas
- Klasterių grynumo atvaizdavimas. Mėlynai - >= 50% procentų sudarantys vienos baltymų šeimos klasteriai. Raudonai - < 50% procentų sudarantys vienos baltymų šeimos klasteriai. 

### **cluster_{N}**: Sklaidos grafikai 
- Klasterio N paryškinimas plokštumoje.
