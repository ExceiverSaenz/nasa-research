"""The first schema, "Tensile properties", made once from the extraction guide's feature list (BR-S10, ADR-012).

It copies only what ``features.py`` holds: ids, labels and order. The groups are the sections of the Feature guide in
``llm_baseline/extraction_prompt.md``, and the 26 elements form the family "Chemical composition". No type, unit or
description is invented: every field is Text until the expert edits it (OQ-S03).
"""
from . import features

SEED_ID = 'tensile-properties'
SEED_NAME = 'Tensile properties'
FAMILY = {'family_id': 'composition', 'name': 'Chemical composition'}
SECTIONS = [
    ('g_material', 'Material and chemical composition',
     {'material', 'material_group'} | {'composition_' + k for k, _ in features.ELEMENTS}),
    ('g_treatment', 'Manufacturing, treatment, and irradiation',
     {'manufacturing', 'treatment', 'treatment_three_categories', 'post_treatment_temperature', 'post_treatment_time',
      'cooling', 'microstructure', 'grain_size', 'irradiation_dose', 'irradiation_temperature', 'irradiation_time'}),
    ('g_specimen', 'Specimen preparation and geometry',
     {'specimen_preparation', 'specimen_size_type', 'gauge_length', 'thickness', 'fillet_radius', 'width',
      'aspect_ratio_l_w', 'aspect_ratio_r_w', 'aspect_ratio_t_w'}),
    ('g_test', 'Tensile test conditions and results',
     {'test_temperature', 'strain_rate', 'yield_strength', 'ultimate_tensile_strength', 'uniform_elongation',
      'total_elongation'}),
]
_SYMBOL = {'composition_' + k: sym for k, sym in features.ELEMENTS}


def field(field_id, name):
    member = _SYMBOL.get(field_id)
    return {'field_id': field_id, 'name': name, 'description': '', 'type': 'text', 'unit': '', 'allowed': [],
            'multiple': False, 'formula': '', 'inputs': [], 'family': {**FAMILY, 'member': member} if member else None}


def seed_content():
    groups = [{'group_id': gid, 'name': name, 'fields': []} for gid, name, _ in SECTIONS]
    for feature_id, label in features.FEATURES:   # the guide's order
        index = next((i for i, (_, _, ids) in enumerate(SECTIONS) if feature_id in ids), len(SECTIONS) - 1)
        groups[index]['fields'].append(field(feature_id, label))
    return {'schema': 'value-review-schema/1', 'description': 'The features of the extraction guide (llm_baseline/extraction_prompt.md).',
            'groups': groups}
