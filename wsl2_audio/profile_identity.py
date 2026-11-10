"""Separate model locations from the byte-pinned analysis configuration."""
from copy import deepcopy


METHOD = 'model_manifest_without_locations_v1'


def model_identity(spec):
    value = deepcopy(spec)
    value.pop('path', None)
    return value


def profile_identity(profile):
    value = deepcopy(profile)
    for name in ('recognizer', 'speech_activity_model'):
        if name in value:
            value[name] = model_identity(value[name])
    for name, spec in value.get('enrichment', {}).get('models', {}).items():
        value['enrichment']['models'][name] = model_identity(spec)
    return value
