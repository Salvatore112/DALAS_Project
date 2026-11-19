import io
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import dashboard_data as data
import dashboard_project as dashboard


class DataTests(unittest.TestCase):
    def test_library_identity_and_context_are_not_postal_code_duplicates(self):
        rows = []
        for code, library_id, library_home, income_code, income in [
            ('00001', 'L1', '00002', '00001', '90000'),
            ('00002', 'L1', '00002', '00002', '21000'),
            ('00003', 'L2', '00003', '00001', '90000'),
        ]:
            row = {column: None for column in list(data.LIBRARY_COLUMNS) + data.CONTEXT_COLUMNS}
            row.update({'code_insee': code, 'nom_standard': 'Home ' + code,
                        'reg_nom': 'Region', 'dep_nom': 'Department', 'population': '100', 'densite': '20',
                        'libraries_\ufeffCode_bib': library_id, 'libraries_nom_de_l_etablissement': library_id,
                        'libraries_code_insee_commune': library_home, 'libraries_nombre_de_livres': '0',
                        'libraries_nombre_de_prets': '-2', 'libraries_Latitude': '48', 'libraries_Longitude': '2',
                        'income_Code géog': income_code, 'income_[DEC] Méd': income,
                        'rent_INSEE_C': income_code, 'rent_loypredm2': '10,5'})
            rows.append(row)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.csv'
            pd.DataFrame(rows).to_csv(path, index=False)
            libraries, metadata = data.load_data(path)
        one, two = libraries.set_index('id').loc[['L1', 'L2']].iloc
        self.assertEqual(len(libraries), 2)
        self.assertEqual(metadata['repeated_links'], 1)
        self.assertEqual(one.city, 'Home 00002')
        self.assertEqual(one.income, 21000)
        self.assertEqual(one.rent, 10.5)
        self.assertTrue(pd.isna(two.income))
        self.assertTrue(pd.isna(two.rent))
        self.assertEqual(one.books, 0)
        self.assertTrue(pd.isna(one.loans))

    def test_decimal_commas_non_finite_and_missing_values(self):
        values = data.numeric(pd.Series(['12,5', None, 'inf', 'text', '0']))
        self.assertEqual(values.iloc[0], 12.5)
        self.assertTrue(values.iloc[1:4].isna().all())
        self.assertEqual(values.iloc[4], 0)

    def test_search_is_accent_insensitive_and_literal(self):
        frame = dashboard.LIBRARIES
        self.assertEqual(data.filter_libraries(frame, search='médiathèque').index.tolist(),
                         data.filter_libraries(frame, search='mediatheque').index.tolist())
        self.assertTrue(data.filter_libraries(frame, search='[impossible.*').empty)

    def test_filters_intersect_and_missing_collections_remain_available(self):
        frame = dashboard.LIBRARIES
        subset = data.filter_libraries(frame, regions=['Bretagne'], collection='small', reporting='activity', metric='visits')
        self.assertGreater(len(subset), 0)
        self.assertTrue(subset.region.eq('Bretagne').all())
        self.assertTrue(subset.books.lt(5000).all())
        self.assertTrue(subset.visits.notna().all())
        missing = data.filter_libraries(frame, collection='missing')
        self.assertEqual(len(missing), frame.books.isna().sum())

    def test_collection_bands_include_zero_and_do_not_double_count_boundaries(self):
        frame = dashboard.LIBRARIES
        summary = data.collection_summary(frame, 'loans')
        self.assertEqual(summary['count'].sum(), frame[['books', 'loans']].notna().all(axis=1).sum())

    def test_correlation_uses_pairwise_counts_and_minimum(self):
        frame = pd.DataFrame({'a': range(12), 'b': [np.nan] * 3 + list(range(9)), 'c': range(12)})
        correlations, counts = data.correlation_summary(frame, ['a', 'b', 'c'])
        self.assertEqual(counts.loc['a', 'b'], 9)
        self.assertTrue(pd.isna(correlations.loc['a', 'b']))
        self.assertAlmostEqual(correlations.loc['a', 'c'], 1)


class DashboardTests(unittest.TestCase):
    def test_regional_comparison_uses_quartiles_and_minimum_sample(self):
        frame = pd.DataFrame({
            'region': ['A'] * 5 + ['B'] * 4,
            'department': ['A1'] * 5 + ['B1'] * 4,
            'loans': [0, 10, 20, 30, 40, 1, 2, 3, 4],
        })
        figure, note = dashboard.regional_figure(frame, 'loans')
        self.assertEqual(list(figure.data[0].y), ['A'])
        self.assertEqual(list(figure.data[0].x), [20])
        self.assertEqual(list(figure.data[0].error_x.array), [10])
        self.assertEqual(list(figure.data[0].error_x.arrayminus), [10])
        figure, note = dashboard.regional_figure(frame[frame.region.eq('A')], 'loans')
        self.assertEqual(list(figure.data[0].y), ['A1'])
        self.assertIn('departments', note)

    def test_coverage_counts_zero_as_available_and_uses_all_selected_libraries(self):
        columns = ['books', 'loans', 'borrowers', 'visits', 'seats', 'population', 'income', 'rent']
        frame = pd.DataFrame({column: [0, 10, np.nan, np.nan] for column in columns})
        frame['income'] = np.nan
        figure = dashboard.coverage_figure(frame)
        self.assertEqual(figure.data[0].x[0], 50)
        self.assertEqual(figure.data[0].x[6], 0)
        self.assertEqual(figure.data[1].x[6], 100)
        self.assertTrue(np.allclose(np.array(figure.data[0].x) + np.array(figure.data[1].x), 100))

    def test_new_views_handle_an_empty_selection(self):
        regional, note, coverage = dashboard.update_area_coverage([], 'visits')
        self.assertEqual(len(regional.layout.annotations), 1)
        self.assertEqual(len(coverage.layout.annotations), 1)

    def test_restored_scatter_supports_independent_axes(self):
        figure, note = dashboard.update_comparison(None, 'income', 'loans', 'linear', 'rent')
        expected = dashboard.LIBRARIES.dropna(subset=['income', 'rent'])
        self.assertEqual(len(figure.data[0].x), len(expected))
        self.assertEqual(figure.layout.yaxis.title.text, data.LABELS['rent'])

    def test_slider_exact_and_cumulative_selection_preserve_counts(self):
        frame = dashboard.LIBRARIES
        counts = dashboard.book_counts(frame)
        index = len(counts) // 2
        for mode in ['exact', 'upto']:
            figure, label, note = dashboard.slider_figure(frame, index, mode, 'visits')
            chosen = frame[frame.books.eq(counts[index]) if mode == 'exact' else frame.books.le(counts[index])]
            expected = chosen.dropna(subset=['visits'])
            self.assertEqual(sum(len(trace.x) for trace in figure.data), len(expected))
            actual = {row[0] for trace in figure.data for row in trace.customdata}
            self.assertEqual(actual, set(expected.id))

    def test_slider_handles_missing_counts_single_count_and_zero(self):
        self.assertTrue(dashboard.update_slider_options([])[3])
        zero = dashboard.LIBRARIES[dashboard.LIBRARIES.books.eq(0)]
        self.assertTrue(dashboard.update_slider_options(zero.index.tolist())[3])
        figure, label, note = dashboard.slider_figure(zero, 9999, 'exact', 'loans')
        self.assertEqual(label, 'Exactly 0 books')
        self.assertEqual(sum(len(trace.x) for trace in figure.data), zero.loans.notna().sum())
        figure, label, note = dashboard.slider_figure(zero.iloc[:0], 0, 'exact', 'loans')
        self.assertEqual(len(figure.layout.annotations), 1)

    def test_original_mean_summary_and_pca_are_available(self):
        frame = dashboard.LIBRARIES
        figure = dashboard.band_figure(frame, 'loans', 'mean')
        expected = frame.groupby('band', observed=False).loans.mean().reindex(data.BANDS)
        np.testing.assert_allclose(figure.data[0].x, expected, equal_nan=True)
        scores, explained, columns = dashboard.pca_model()
        self.assertTrue(np.isfinite(scores[['PC1', 'PC2']]).all().all())
        self.assertTrue(0 < sum(explained) <= 100)
        figure, note = dashboard.pca_figure(frame.iloc[:10])
        np.testing.assert_allclose(figure.data[0].x, scores.loc[frame.index[:10], 'PC1'])
        self.assertEqual(len(dashboard.update_pca([], True)[0].layout.annotations), 1)

    def test_actual_dataset_has_unique_library_ids(self):
        self.assertEqual(len(dashboard.LIBRARIES), 5232)
        self.assertTrue(dashboard.LIBRARIES.id.is_unique)
        self.assertEqual(dashboard.DATASET['communes'], 34868)

    def test_all_empty_views_render(self):
        for metric in ['loans', 'borrowers', 'visits']:
            result = dashboard.update_summaries([], metric)
            self.assertEqual(result[0], '0')
            self.assertEqual(result[10], [])
            for color in ['books', 'income', 'rent']:
                figure, note = dashboard.update_map([], color, 'all', [])
                self.assertEqual(len(figure.layout.annotations), 1)
            for scale in ['log', 'linear']:
                figure, note = dashboard.update_comparison([], 'books', metric, scale)
                self.assertEqual(len(figure.layout.annotations), 1)

    def test_log_scatter_removes_zeros_but_linear_preserves_them(self):
        frame = dashboard.LIBRARIES
        for scale in ['log', 'linear']:
            figure, note = dashboard.scatter_figure(frame, 'books', 'loans', scale)
            expected = frame.dropna(subset=['books', 'loans'])
            if scale == 'log':
                expected = expected[expected.books.gt(0) & expected.loans.gt(0)]
            self.assertEqual(len(figure.data[0].x), len(expected))

    def test_map_excludes_invalid_locations_and_respects_territories(self):
        frame = dashboard.LIBRARIES
        for extent in ['mainland', 'all']:
            figure, note = dashboard.map_figure(frame, 'income', extent, 'offline')
            expected = frame[frame.mappable & (frame.mainland if extent == 'mainland' else True)]
            self.assertEqual(sum(len(trace.lat) for trace in figure.data), len(expected))
            self.assertEqual(figure.layout.map.style, 'white-bg')

    def test_filtered_download_preserves_only_selected_records(self):
        result = dashboard.download_filtered(1, [0, 1])
        frame = pd.read_csv(io.StringIO(result['content']), dtype={'INSEE code': str})
        self.assertEqual(len(frame), 2)
        self.assertEqual(frame['Library ID'].tolist(), dashboard.LIBRARIES.loc[[0, 1], 'id'].tolist())
        self.assertIn('Predicted rent (€/m²)', frame.columns)
        self.assertNotIn('_search', frame.columns)

    def test_dash_routes_and_callback_serialization(self):
        client = dashboard.server.test_client()
        for route in ['/', '/_dash-layout', '/_dash-dependencies', '/assets/dashboard.css']:
            with client.get(route) as response:
                self.assertEqual(response.status_code, 200, route)
        key = next(key for key in dashboard.app.callback_map if 'stat-libraries.children' in key)
        outputs = dashboard.app.callback_map[key]['output']
        response = client.post('/_dash-update-component', json={
            'output': key,
            'outputs': [{'id': output.component_id, 'property': output.component_property} for output in outputs],
            'inputs': [{'id': 'filtered-ids', 'property': 'data', 'value': [0, 1]},
                       {'id': 'metric', 'property': 'value', 'value': 'loans'},
                       {'id': 'collection-statistic', 'property': 'value', 'value': 'median'}],
            'state': [], 'changedPropIds': ['filtered-ids.data'],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['response']['stat-libraries']['children'], '2')


if __name__ == '__main__':
    unittest.main()
