# DALAS dashboard

An interactive dashboard for exploring the project's French library data: collections, loans, borrowers, visits, geography, and matched socioeconomic context. Built with Dash, Plotly, and Dash AG Grid, extending the original `dashboard_project.py`.

## Run the dashboard

Requires **Python 3.10 or newer**. Keep `big_merged_dataset.csv` in the project folder alongside the Python files. The dashboard reads the existing file; running the merge notebook or downloading the original sources is not necessary.

```bash
python -m venv .venv
```

Activate the environment:

- **Windows PowerShell:** `.venv\Scripts\Activate.ps1`
- **Windows Command Prompt:** `.venv\Scripts\activate.bat`
- **macOS / Linux:** `source .venv/bin/activate`

Install the dashboard dependencies and start it:

```bash
python -m pip install -r requirements-dashboard.txt
python dashboard_project.py
```

Open **http://127.0.0.1:8050** in your browser. Stop the server with **Ctrl+C**. If port 8050 is occupied, run `python dashboard_project.py --port 8051` instead.

The dependency file is separate from `req.txt`, which belongs to the existing data-collection environment. Debug mode is off by default; use `--debug` while developing. File paths resolve relative to the Python files, so launching from another working directory also works.

Internet is needed to install packages and display the optional CARTO/OpenStreetMap basemap. The data, interface, tables, and other charts run locally without API keys or external fonts. Select **No basemap** to keep the coordinate plot interactive without map tiles.

### Sharing with the teacher

Send the following together:

- `dashboard_project.py`
- `dashboard_data.py`
- `assets/dashboard.css`
- `big_merged_dataset.csv`
- `requirements-dashboard.txt`
- `README.md`

**The dataset is ignored by Git in this repository.** Include it explicitly in your submission folder or ZIP. The dashboard cannot run from a Git clone alone without that file. There is no need to include `.venv`, notebook outputs, or caches.

## Explore

1. Filter by region, department, library/commune name, INSEE code, collection size, or data availability. Search ignores accents; all panels use the same filtered library set.
2. Switch between loans, borrowers, and visits. The KPI cards, collection comparison, and scatter plot follow the selected activity measure. The heatmap deliberately keeps all seven measures for comparison.
3. Explore the map, change its colour measure, and switch to **All territories** for overseas libraries. The default map focuses on metropolitan France, including Corsica; the other summaries still include all selected territories. The map caption states how many records are plotted or excluded.
4. Select a map point, scatter point, or table row to see library details. Compare activity against collection size, commune population, income, or rent. Log axes handle the wide range in counts; linear axes retain zeros.
5. Sort and paginate the records, or download the entire filtered subset as CSV. CSV export follows the sidebar filters and includes context fields; table sorting only changes the table's display order. IDs retain leading zeroes in the CSV text; spreadsheet software should import INSEE codes as text.
6. Expand **About the data & methodology** for definitions and limitations. Reset filters returns the full library set, preserving your chart preferences.

Two additional views round out the exploration: **Activity across areas** compares median activity and the middle 50% of values by region, switching to departments when just one region is selected. **What can we compare?** shows reporting coverage for eight relevant measures. Both follow the sidebar filters.

## Data choices and interpretation

The supplied file contains **34,868 commune rows**, **190 variables**, and **5,232 distinct library IDs**. The dashboard loads only the fields it needs, once at startup, and displays one record per library ID rather than repeatedly plotting postal-code links. It does not modify the source CSV or notebook.

The upstream merge groups sources by postal code and takes the first non-null value in each column. That can combine source records, and multiple communes share postal codes. Consequently, the retained libraries are a subset, not a national inventory. Deduplicating library IDs removes repeated links but cannot reconstruct records or facilities lost during merging.

- **Geography:** library coordinates; home commune labels and population are matched by the library's INSEE code, with library labels as fallbacks.
- **Income and rent:** matched separately by the source income/rent commune code to the library's home code. A neighbour's postal-code-linked value is not assigned. Unmatched values remain missing.
- **Income indicator:** `income_[DEC] Méd`, the declared-income median indicator. The merged file does not establish its exact statistical unit or vintage; consult the original source before a substantive income interpretation.
- **Rent:** `rent_loypredm2`, predicted rent in €/m². Decimal commas are converted to numbers. No affordability ratio is inferred.
- **Missingness:** missing, invalid, non-finite, and negative count values are excluded; valid zero counts are retained. Mean imputation is used only in the optional PCA projection; the other charts retain missingness. Missing libraries or unreported activity do not imply absent access or zero use.
- **Collection chart:** median activity by six explicit book-count bands, using libraries with both fields. Hover shows the reporting sample size.
- **Map:** counts use a log(1 + value) colour scale with raw-count labels; income and rent use linear scales. Scales remain fixed across filters. Grey points lack the selected measure. Coordinates outside valid ranges and (0, 0) are excluded.
- **Scatter plot:** shows all available pairs, with no sampling. Log axes exclude zero values and disclose the count; linear axes include them.
- **Heatmap:** Spearman rank correlations across seven selected measures, with pairwise deletion and a minimum of 10 paired values. Constants produce blank cells. Hover shows the paired count. Several libraries can share a commune's context; the observations are not fully independent.
- **Area comparison:** median and interquartile range of the selected activity measure, with at least five reporting libraries per area. Displays at most eight areas, chosen by reporting sample size. Unknown areas are excluded. The intervals describe variation between libraries, not uncertainty in the median; differences in library size and reporting affect the comparison.
- **Reporting coverage:** available versus missing values for books, loans, borrowers, visits, seats, population, income, and rent. The denominator is every selected library, including those with missing data. Valid zeros count as available. Context measures additionally require a source commune match.

The file does not retain a consistent observation year, so the dashboard does not invent a time series. Library use is an exploratory proxy, not a direct measure of individual reading habits, and correlations do not establish causes. Bookshop and population-history fields remain available in the original dataset but are outside this focused dashboard.

The visualization APIs follow the official [Dash documentation](https://dash.plotly.com/) and [Plotly map documentation](https://plotly.com/python/tile-maps/).

## Original exploration views

The dashboard combines the original team’s exploration controls with the newer map, regional comparisons, and coverage charts:

- **Scatter plots:** both axes can independently select books, loans, borrowers, visits, seats, computers, population, density, income, or rent. “Selected activity” keeps the Y-axis linked to the global activity selector. Linear and logarithmic scales remain available.
- **Book-count slider:** the Collection explorer moves through every actual book count in the filtered sample, with step 1 in the sorted list. Exact count preserves the original interaction; “Up to this count” offers a broader comparison. The slider resets to the middle available count after filtering. Empty and single-count selections disable it appropriately. Bubble area follows commune population with a minimum visible size; missing population uses small markers, and unmatched income uses grey. Counts of omitted values are shown. Both axes are linear to retain zero values.
- **Mean-activity histogram:** the collection chart now offers the original average-activity approach alongside the median, using explicit, readable collection bands. The plot and axis labels follow the selected statistic.
- **PCA:** an expandable panel restores the two-component projection. It uses seven named resource/activity/context measures, log(1 + value), transformed-mean imputation, and standardisation, excluding constant inputs. A NumPy SVD computes the same principal-component projection without another installation dependency. The model is fitted once to the full library sample so filtering never changes the coordinate system. Axes show explained variance, hover identifies imputation, and this view is optional rather than the dashboard’s main interpretation.

All restored point plots link to the existing library detail panel. The shared filters apply throughout. Identifiers and raw geographic coordinates are excluded from numerical comparison choices.
