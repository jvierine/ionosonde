"""Compatibility imports for SciPy signal window functions."""

try:
    from scipy.signal.windows import blackmanharris, flattop, hann, tukey
except ImportError:  # SciPy versions that exposed windows in scipy.signal
    from scipy.signal import blackmanharris, flattop, hann, tukey
