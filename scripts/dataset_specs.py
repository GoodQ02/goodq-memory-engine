from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class DatasetSpec:
    """Descriptor for a dataset the pipeline cares about."""

    path: str
    name: Optional[str] = None
    split: Optional[str] = None
    gated: bool = False
    vendor_dirs: Sequence[str] = field(default_factory=tuple)
    description: Optional[str] = None
    load_kwargs: Dict[str, Any] = field(default_factory=dict)

    @property
    def cache_key(self) -> str:
        return self.path.replace('/', '___')

    @property
    def display_name(self) -> str:
        return f"{self.path}/{self.name}" if self.name else self.path


DEFAULT_VENDOR_ROOT = Path('L:/datasets/vendor')


DATASET_SPECS: List[DatasetSpec] = []


def add_dataset(
    path: str,
    *,
    configs: Sequence[Dict[str, Any]],
    gated: bool = False,
    vendor_dirs: Sequence[str] | None = None,
    description: Optional[str] = None,
    load_kwargs: Optional[Dict[str, Any]] = None,
) -> None:
    """Expand a high-level dataset configuration into explicit DatasetSpec rows."""

    base_vendor_dirs: Sequence[str] = vendor_dirs or ()
    base_kwargs: Dict[str, Any] = load_kwargs.copy() if load_kwargs else {}

    for cfg in configs:
        cfg_kwargs = base_kwargs.copy()
        if extras := cfg.get('load_kwargs'):
            cfg_kwargs.update(extras)
        DATASET_SPECS.append(
            DatasetSpec(
                path=path,
                name=cfg.get('name'),
                split=cfg.get('split'),
                gated=cfg.get('gated', gated),
                vendor_dirs=tuple(cfg.get('vendor_dirs', base_vendor_dirs)),
                description=cfg.get('description', description),
                load_kwargs=cfg_kwargs,
            )
        )


# ---------------------------------------------------------------------------
# Baseline corpora (always available offline)
# ---------------------------------------------------------------------------
add_dataset('emotion', configs=[{}])
add_dataset('glue', configs=[{'name': 'sst2', 'split': split} for split in ('train', 'validation')])
add_dataset('imdb', configs=[{'split': 'train'}])
add_dataset('wiki_qa', configs=[{'split': 'train'}])
add_dataset('wikitext', configs=[{'name': 'wikitext-103-raw-v1', 'split': split} for split in ('train', 'validation', 'test')])
add_dataset('wikimedia/wikipedia', configs=[{'name': '20231101.simple', 'split': 'train'}])

# ---------------------------------------------------------------------------
# STEM, reasoning, and QA
# ---------------------------------------------------------------------------
add_dataset(
    'lmms-lab/ScienceQA',
    configs=[{'name': 'ScienceQA-FULL', 'split': split} for split in ('train', 'validation', 'test')],
    load_kwargs={'trust_remote_code': True},
)
add_dataset('allenai/sciq', configs=[{'split': 'train'}])
add_dataset('allenai/ai2_arc', configs=[
    {'name': 'ARC-Challenge', 'split': 'train'},
    {'name': 'ARC-Easy', 'split': 'train'},
])
add_dataset('gsm8k', configs=[{'name': 'main', 'split': split} for split in ('train', 'test')])
add_dataset('cais/mmlu', configs=[
    {'name': 'all', 'split': 'auxiliary_train'},
    {'name': 'all', 'split': 'validation'},
])
add_dataset(
    'm-a-p/SuperGPQA',
    configs=[{'name': 'SuperGPQA', 'split': 'train'}],
    load_kwargs={'trust_remote_code': True},
)

# ---------------------------------------------------------------------------
# Speech & audio datasets
# ---------------------------------------------------------------------------
common_voice_vendor = (str(DEFAULT_VENDOR_ROOT / 'common_voice_17_0'),)
add_dataset(
    'mozilla-foundation/common_voice_17_0',
    gated=True,
    vendor_dirs=common_voice_vendor,
    load_kwargs={'trust_remote_code': True},
    configs=[{'name': 'en', 'split': split} for split in ('train', 'validation', 'test')],
)
add_dataset(
    'openslr/librispeech_asr',
    configs=[
        {'name': 'clean', 'split': 'train.100'},
        {'name': 'clean', 'split': 'train.360'},
        {'name': 'clean', 'split': 'validation'},
        {'name': 'clean', 'split': 'test'},
        {'name': 'other', 'split': 'train.500'},
        {'name': 'other', 'split': 'validation'},
        {'name': 'other', 'split': 'test'},
    ],
)
add_dataset('speech_commands', configs=[{'name': 'v0.02', 'split': split} for split in ('train', 'validation', 'test')])
add_dataset('ashraq/esc50', configs=[{'split': 'train'}], load_kwargs={'trust_remote_code': True})
add_dataset('SparkAudio/voxbox', configs=[{'split': 'train'}], load_kwargs={'trust_remote_code': True})
add_dataset('superb', configs=[{'name': 'ks', 'split': split} for split in ('train', 'validation', 'test')], load_kwargs={'trust_remote_code': True})

# ---------------------------------------------------------------------------
# Vision datasets
# ---------------------------------------------------------------------------
coco_vendor = (str(DEFAULT_VENDOR_ROOT / 'coco2017'),)
add_dataset(
    'phiyodr/coco2017',
    vendor_dirs=coco_vendor,
    load_kwargs={'trust_remote_code': True},
    configs=[{'split': split} for split in ('train', 'validation', 'test')],
)
add_dataset(
    'HuggingFaceM4/COCO',
    gated=True,
    vendor_dirs=coco_vendor,
    load_kwargs={'trust_remote_code': True},
    configs=[{'name': '2014', 'split': split} for split in ('train', 'validation')],
)
add_dataset(
    'bitmind/lfw',
    vendor_dirs=(str(DEFAULT_VENDOR_ROOT / 'lfw'),),
    load_kwargs={'trust_remote_code': True},
    configs=[{'split': split} for split in ('train', 'test')],
)
add_dataset('MapSpaceORNL/north-america-landuse-3class-v1', configs=[{'split': 'train'}])
add_dataset('andersonluisamaral/geospatial_data_v2', configs=[{'split': 'train'}])
add_dataset('ibm-nasa-geospatial/hurricane', configs=[{'split': 'train'}])
add_dataset('rmayormartins/sunspot-hunter', configs=[{'split': 'train'}])
add_dataset('kwazzi-jack/mirabest-radio-astronomy-unofficial', configs=[{'split': 'train'}])

# ---------------------------------------------------------------------------
# Language understanding & sentiment
# ---------------------------------------------------------------------------
add_dataset('cardiffnlp/tweet_sentiment_multilingual', configs=[{'name': 'all', 'split': 'train'}])
add_dataset('xnli', configs=[{'name': 'en', 'split': 'train'}])
add_dataset('tatsu-lab/alpaca', configs=[{'split': 'train'}])
add_dataset('tweet_eval', configs=[{'name': 'sentiment', 'split': split} for split in ('train', 'validation', 'test')])
add_dataset('super_glue', configs=[{'name': 'rte', 'split': 'train'}])
add_dataset('squad', configs=[{'split': 'train'}])
add_dataset('race', configs=[{'name': 'middle', 'split': 'train'}])


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
def _directory_has_files(directory: Path) -> bool:
    try:
        for child in directory.rglob('*'):
            if child.is_file():
                return True
    except Exception:
        return False
    return False


def find_local_copy(spec: DatasetSpec, cache_root: Path) -> Optional[Dict[str, str]]:
    base_dir = cache_root / spec.cache_key
    if base_dir.exists() and _directory_has_files(base_dir):
        return {"path": str(base_dir), "source": "cache"}
    for vendor in spec.vendor_dirs:
        vendor_path = Path(vendor)
        if vendor_path.exists() and _directory_has_files(vendor_path):
            return {"path": str(vendor_path), "source": "vendor"}
    return None


__all__ = ["DatasetSpec", "DATASET_SPECS", "find_local_copy"]


