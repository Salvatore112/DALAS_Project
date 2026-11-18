from pathlib import Path
import unicodedata

import numpy as np
import pandas as pd

DATA_PATH = Path(__file__).resolve().parent / 'big_merged_dataset.csv'
LIBRARY_COLUMNS = {
    'libraries_\ufeffCode_bib': 'id',
    'libraries_nom_de_l_etablissement': 'name',
    'libraries_code_insee_commune': 'commune_code',
    'libraries_Ville': 'city',
    'libraries_Région': 'region',
    'libraries_Département': 'department',
    'libraries_Adresse': 'address',
    'libraries_Statut': 'status',
    'libraries_Latitude': 'latitude',
    'libraries_Longitude': 'longitude',
    'libraries_nombre_de_livres': 'books',
    'libraries_nombre_de_prets': 'loans',
    'libraries_nombre_d_emprunteurs': 'borrowers',
    'libraries_nombre_d_entrees': 'visits',
    'libraries_nombre_de_places': 'seats',
    'libraries_nb_postes_informatiques_publics': 'computers',
    'libraries_connexion_wi_fi': 'wifi',
    'libraries_ouverture_le_dimanche': 'sunday',
}
CONTEXT_COLUMNS = [
    'code_insee', 'nom_standard', 'reg_nom', 'dep_nom', 'population', 'densite',
    'income_Code géog', 'income_[DEC] Méd', 'rent_INSEE_C', 'rent_loypredm2',
]
LABELS = {
    'id': 'Library ID', 'name': 'Library', 'city': 'Commune',
    'commune_code': 'INSEE code', 'region': 'Region', 'department': 'Department',
    'address': 'Address', 'books': 'Books', 'loans': 'Loans',
    'borrowers': 'Borrowers', 'visits': 'Visits', 'seats': 'Seats',
    'computers': 'Public computers', 'population': 'Commune population',
    'density': 'Residents / km²', 'income': 'Income indicator (€)',
    'rent': 'Predicted rent (€/m²)', 'wifi': 'Wi-Fi', 'sunday': 'Sunday opening',
    'latitude': 'Latitude', 'longitude': 'Longitude', 'status': 'Library type',
}
BANDS = ['Under 2k', '2k–5k', '5k–10k', '10k–25k', '25k–50k', '50k+']


def normalize_text(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value).casefold())
                   if not unicodedata.combining(c))


def numeric(values):
    return pd.to_numeric(values.astype('string').str.replace(',', '.', regex=False),
                         errors='coerce').astype(float).replace([np.inf, -np.inf], np.nan)


def clean_codes(values):
    return values.astype('string').str.strip().str.replace(r'\.0$', '', regex=True).str.zfill(5)


def source_lookup(raw, code, value):
    return raw.dropna(subset=[code]).drop_duplicates(code).set_index(code)[value]


def load_data(path=DATA_PATH):
    if not Path(path).is_file():
        raise FileNotFoundError(f'Dataset not found: {path}. Keep big_merged_dataset.csv beside dashboard_project.py.')
    raw = pd.read_csv(path, usecols=list(LIBRARY_COLUMNS) + CONTEXT_COLUMNS, dtype='string')
    for col in ['code_insee', 'libraries_code_insee_commune', 'income_Code géog', 'rent_INSEE_C']:
        raw[col] = clean_codes(raw[col])
    libraries = (raw.loc[raw['libraries_\ufeffCode_bib'].notna(), list(LIBRARY_COLUMNS)]
                 .drop_duplicates('libraries_\ufeffCode_bib').rename(columns=LIBRARY_COLUMNS).copy())
    for col in ['latitude', 'longitude', 'books', 'loans', 'borrowers', 'visits', 'seats', 'computers']:
        libraries[col] = numeric(libraries[col])
        if col not in ['latitude', 'longitude']:
            libraries.loc[libraries[col] < 0, col] = np.nan
    libraries['name'] = libraries['name'].fillna('Unnamed library')
    for target, source in [('city', 'nom_standard'), ('region', 'reg_nom'), ('department', 'dep_nom')]:
        home = libraries['commune_code'].map(source_lookup(raw, 'code_insee', source))
        libraries[target] = home.fillna(libraries[target]).fillna('Unknown')
    for target, code, source in [
        ('population', 'code_insee', 'population'),
        ('density', 'code_insee', 'densite'),
        ('income', 'income_Code géog', 'income_[DEC] Méd'),
        ('rent', 'rent_INSEE_C', 'rent_loypredm2'),
    ]:
        libraries[target] = numeric(libraries['commune_code'].map(source_lookup(raw, code, source)))
        libraries.loc[libraries[target] < 0, target] = np.nan
    libraries['mappable'] = (libraries.latitude.between(-90, 90) & libraries.longitude.between(-180, 180)
                            & ~(libraries.latitude.eq(0) & libraries.longitude.eq(0)))
    libraries['mainland'] = (libraries.latitude.between(41, 52) & libraries.longitude.between(-6, 10))
    libraries['band'] = pd.cut(libraries.books, [0, 2000, 5000, 10000, 25000, 50000, np.inf],
                               labels=BANDS, right=False)
    libraries['_search'] = (libraries['name'] + ' ' + libraries['city'] + ' ' + libraries['commune_code']).map(normalize_text)
    libraries = libraries.sort_values(['region', 'city', 'name']).reset_index(drop=True)
    metadata = {
        'communes': len(raw), 'libraries': len(libraries),
        'repeated_links': int(raw['libraries_\ufeffCode_bib'].notna().sum()) - len(libraries),
        'regions': int(raw.reg_nom.nunique()),
    }
    return libraries, metadata


def filter_libraries(frame, regions=None, departments=None, search='', collection='all', reporting='all', metric='loans'):
    selected = frame
    if regions:
        selected = selected[selected.region.isin(regions)]
    if departments:
        selected = selected[selected.department.isin(departments)]
    if search and search.strip():
        selected = selected[selected._search.str.contains(normalize_text(search.strip()), regex=False, na=False)]
    ranges = {'small': (0, 5000), 'medium': (5000, 25000), 'large': (25000, np.inf)}
    if collection in ranges:
        lower, upper = ranges[collection]
        selected = selected[selected.books.ge(lower) & selected.books.lt(upper)]
    elif collection == 'missing':
        selected = selected[selected.books.isna()]
    if reporting == 'activity':
        selected = selected[selected[metric].notna()]
    elif reporting == 'context':
        selected = selected[selected.income.notna() & selected.rent.notna()]
    return selected


def collection_summary(frame, metric):
    return (frame.groupby('band', observed=False)[metric].agg(['median', 'count'])
            .reindex(BANDS).reset_index())


def correlation_summary(frame, columns, minimum=10):
    values = frame[columns]
    present = values.notna().astype(int)
    counts = present.T @ present
    return values.corr(method='spearman', min_periods=minimum), counts


def export_frame(frame):
    columns = [key for key in LABELS if key in frame]
    return frame[columns].rename(columns=LABELS)
