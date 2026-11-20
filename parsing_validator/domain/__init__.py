"""Domain: the user's decisions about a paper (blank state, catalogs and the rules a save must satisfy)."""
from .catalogs import DEFAULT_SETTINGS, OTHER
from .mathml import MathRenderer
from .rules import DecisionRulesViolation, check_state, validate_state
from .state import blank_state

__all__ = ['DEFAULT_SETTINGS', 'OTHER', 'DecisionRulesViolation', 'MathRenderer', 'blank_state', 'check_state',
           'validate_state']
