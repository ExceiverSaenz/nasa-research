"""Which values need a check (BR-06, ADR-006) and which notes are information only."""

ACTION_FLAGS = ('fracture_stress_not_yield', 'yield_fracture_criterion_ambiguous')
INFO_SOURCES = ('derived_inputs', 'not_explicitly_reported')


def needs_check(flags, source_status, assignment_status):
    """True when the reviewer must resolve something: an ambiguous flag, a candidate-only source,
    or a record assignment that is not established."""
    return (any(f in ACTION_FLAGS for f in flags or ())
            or source_status == 'candidate_only'
            or assignment_status != 'established')


def action_codes(flags, source_status, assignment_status):
    """Codes behind needs_check, in a stable order (shown as "Check this")."""
    out = [f for f in flags or () if f in ACTION_FLAGS]
    if source_status == 'candidate_only':
        out.append('source:candidate_only')
    if assignment_status != 'established':
        out.append('assignment:' + str(assignment_status))
    return out


def info_codes(flags, source_status):
    """Codes shown as "About this value": every other flag and a derived or not-stated source."""
    out = [f for f in flags or () if f not in ACTION_FLAGS]
    if source_status in INFO_SOURCES:
        out.append('source:' + source_status)
    return out
