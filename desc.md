
# Quantitative Description and Data Collection Process

## Dataset purpose

This dataset was constructed for a project on the relationship between reading habits, access to reading infrastructure, and socio-economic conditions in France. It combines municipal geographic data with information on rent levels, income, libraries, bookshops, and population.

The dataset does not directly measure individual reading habits. Instead, library resources, borrowing activity, library visits, and bookshop presence are used as proxies for local reading access and reading-related activity.

## Unit of observation and dataset size

Each observation represents a French commune, identified primarily through its INSEE commune code (`<span>code_insee</span>`) and postal code (`<span>postalcode</span>`).

The current merged dataset contains:

* **34,868 observations**
* **190 variables**
* **34,844 rows with at least one missing value**
* **24 complete rows with no missing values**

The high proportion of rows containing at least one missing value is expected because libraries and bookshops are not present in every commune, and because some organisations do not report all operational indicators.

## Data sources

Six public datasets were collected and merged:

| Source                                 | Role in the dataset                                                                                                                                           | Number of variables retained |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| Postal-code and commune reference data | Geographic base dataset: commune name, INSEE code, postal code, region, department, population, density, coordinates, urban classification, and service level | 62                           |
| Rent data                              | Predicted rent per square metre, lower and upper estimates, observation counts, and model quality information                                                 | 13                           |
| Income data                            | Disposable-income distribution and inequality indicators at local level                                                                                       | 57                           |
| Library data                           | Library location, collections, loans, borrowers, staffing, facilities, cultural activities, expenditure, and opening information                              | 45                           |
| Bookshop data                          | Bookshop name, assortment, commune, department, and region                                                                                                    | 7                            |
| Population-history data                | Commune population history; only the 2023 population value was retained                                                                                       | 6                            |

The population-history source originally included annual population variables from 2013 to 2023. To limit redundancy, `<span>p13_pop</span>` through `<span>p22_pop</span>` were excluded and only `<span>p23_pop</span>` was retained.

## Meaning of the main variable groups

### Geographic and demographic variables

The base dataset includes commune name, `<span>code_insee</span>`, `<span>postalcode</span>`, department and region codes/names, population, area, density, coordinates, urban-unit classification, attraction-area classification, and service-equipment level.

These variables describe the geographic and demographic context of each commune and can be used as control variables in quantitative analysis.

### Reading-access and library variables

Library variables are prefixed with `<span>libraries_</span>`. Relevant examples include:

* `<span>libraries_nombre_de_livres</span>`: number of books held;
* `<span>libraries_nombre_de_prets</span>`: number of loans;
* `<span>libraries_nombre_d_emprunteurs</span>`: number of borrowers;
* `<span>libraries_nombre_d_entrees</span>`: number of library visits;
* `<span>libraries_nombre_de_places</span>`: number of places/seats;
* `<span>libraries_nb_postes_informatiques_publics</span>`: number of public computers;
* `<span>libraries_ouverture_le_dimanche</span>`: Sunday opening;
* `<span>libraries_connexion_wi_fi</span>`: Wi-Fi availability;
* library staff, volunteer, expenditure, collection, and cultural-activity indicators.

Bookshop variables are prefixed with `<span>bookshops_</span>` and describe bookshop availability and assortment. Together, library and bookshop variables provide proxies for access to books and reading infrastructure.

### Socio-economic variables

Rent variables are prefixed with `<span>rent_</span>`. The main measure is `<span>rent_loypredm2</span>`, the predicted rent per square metre. The dataset also includes lower and upper prediction bounds, observation counts, and model-fit information.

Income variables are prefixed with `<span>income_</span>`. They represent local income-distribution and inequality indicators. Some names appear shortened because the original income source uses abbreviated DBF field names; the source documentation should be consulted before assigning a precise interpretation to each individual income measure.

### Population-history variables

Population-history variables are prefixed with `<span>population_history_</span>`. The main analytical indicator is:

* `<span>population_history_p23_pop</span>`: population in 2023.

The remaining fields identify the relevant region, department, canton/administrative area, commune code, and commune name.

## Data collection and preprocessing

All sources were retrieved from public French open-data endpoints using HTTP requests. CSV files were read using automatic delimiter detection and encoding fallbacks for UTF-8, Windows-1252, and Latin-1. The income data were supplied as a ZIP archive containing a DBF attribute table; the DBF records were extracted and converted into a tabular dataset.

The postal-code/commune dataset was used as the reference table. This choice preserves the full set of 34,868 commune observations.

Postal codes were converted to strings and standardised to five characters so that leading zeroes were retained. Several datasets did not have a postal-code field:

* Rent data use `<span>INSEE_C</span>`;
* Income data use `<span>Code géog</span>`;
* Population-history data use `<span>codgeo</span>`.

For these datasets, postal codes were derived through a crosswalk from `<span>code_insee</span>` in the reference dataset. Library and bookshop data were merged using their own postal-code fields.

To avoid duplicate column names, variables from merged datasets were prefixed by source name, for example `<span>rent_</span>`, `<span>income_</span>`, `<span>libraries_</span>`, `<span>bookshops_</span>`, and `<span>population_history_</span>`.

When several records shared the same postal code, the first record was retained before merging. This prevents many-to-many joins from multiplying the number of commune observations. However, it means that library and bookshop information should be interpreted as linked local information rather than a complete sum of all facilities within a postal code.

## Missing data and limitations

Missingness is substantial, especially for bookshop and specialised library indicators. This is largely structural: many communes do not have a bookshop or library, while others have a facility but incomplete reporting.

For example, bookshop fields are missing in many communes because a bookshop is not present or not matched to that postal code. Some heritage-library variables are also more than 90% missing. These variables can be removed for a simpler analysis without materially affecting the project’s main focus.

The dataset supports analysis of associations between reading infrastructure and socio-economic conditions. It should not be used to make causal claims. In particular, the presence of a library or bookshop does not directly demonstrate that residents read more.
