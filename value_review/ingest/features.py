"""Column labels for the feature ids of the extraction guide (llm_baseline/extraction_prompt.md).

Labels carry no unit: each value keeps the unit the paper reports (BR-05). The order is the guide's
order, used to sort columns in the interface.
"""

ELEMENTS = [
    ('c', 'C'), ('si', 'Si'), ('mn', 'Mn'), ('p', 'P'), ('s', 'S'), ('ni', 'Ni'), ('cr', 'Cr'), ('mo', 'Mo'),
    ('al', 'Al'), ('n', 'N'), ('ti', 'Ti'), ('fe', 'Fe'), ('nb', 'Nb'), ('b', 'B'), ('cu', 'Cu'), ('v', 'V'),
    ('mg', 'Mg'), ('y', 'Y'), ('zr', 'Zr'), ('zn', 'Zn'), ('w', 'W'), ('sn', 'Sn'), ('co', 'Co'), ('o', 'O'),
    ('ta', 'Ta'), ('h', 'H'),
]

FEATURES = (
    [('material', 'Material'), ('material_group', 'Material group')]
    + [('composition_' + k, sym + ' content') for k, sym in ELEMENTS]
    + [
        ('manufacturing', 'Manufacturing'),
        ('treatment', 'Treatment'),
        ('treatment_three_categories', 'Treatment category'),
        ('post_treatment_temperature', 'Post-treatment temperature'),
        ('post_treatment_time', 'Post-treatment time'),
        ('cooling', 'Cooling'),
        ('microstructure', 'Microstructure'),
        ('grain_size', 'Grain size'),
        ('irradiation_dose', 'Irradiation dose'),
        ('irradiation_temperature', 'Irradiation temperature'),
        ('irradiation_time', 'Irradiation time'),
        ('specimen_preparation', 'Specimen preparation'),
        ('specimen_size_type', 'Specimen size or type'),
        ('gauge_length', 'Gauge length'),
        ('thickness', 'Thickness'),
        ('fillet_radius', 'Fillet radius'),
        ('width', 'Width'),
        ('aspect_ratio_l_w', 'Aspect ratio (L/W)'),
        ('aspect_ratio_r_w', 'Aspect ratio (R/W)'),
        ('aspect_ratio_t_w', 'Aspect ratio (T/W)'),
        ('test_temperature', 'Test temperature'),
        ('strain_rate', 'Strain rate'),
        ('yield_strength', 'Yield strength'),
        ('ultimate_tensile_strength', 'Ultimate tensile strength'),
        ('uniform_elongation', 'Uniform elongation'),
        ('total_elongation', 'Total elongation'),
    ]
)

LABELS = dict(FEATURES)
ORDER = {fid: i for i, (fid, _) in enumerate(FEATURES)}


def label(feature_id):
    """The guide label, or a readable form of an id the guide does not list."""
    return LABELS.get(feature_id) or feature_id.replace('_', ' ').capitalize()


def sort_key(feature_id):
    return (ORDER.get(feature_id, len(ORDER)), feature_id)
