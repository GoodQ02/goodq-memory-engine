from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Dict, Any, List

# Load project .env so HF_TOKEN and related flags are picked up when invoked standalone
try:  # pragma: no cover
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore

from datasets import load_dataset

from dataset_specs import DATASET_SPECS, DatasetSpec, find_local_copy


def _dataset_cache_root() -> Path:
    cache = os.environ.get('HF_DATASETS_CACHE')
    if cache:
        return Path(cache)
    hf_home = os.environ.get('HF_HOME') or 'L:/models'
    return Path(hf_home) / 'hf' / 'datasets'


def _load_dataset(spec: DatasetSpec, cache_root: Path) -> Dict[str, Any]:
    load_kwargs: Dict[str, Any] = {
        'path': spec.path,
        'cache_dir': str(cache_root),
    }
    if spec.name:
        load_kwargs.setdefault('name', spec.name)
    if spec.split:
        load_kwargs.setdefault('split', spec.split)
    if spec.load_kwargs:
        for key, value in spec.load_kwargs.items():
            load_kwargs.setdefault(key, value)
    return load_dataset(**load_kwargs)


def _select_targets(dataset_name: str | None) -> List[DatasetSpec]:
    if dataset_name:
        name = dataset_name.strip().lower()
        return [
            s for s in DATASET_SPECS
            if s.path.lower() == name or s.display_name.lower() == name
        ]
    # Default: non-gated datasets only
    return [s for s in DATASET_SPECS if not s.gated]


def _download_with_retry(spec: DatasetSpec, cache_root: Path, retries: int = 3, base_delay: float = 5.0) -> Dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return _load_dataset(spec, cache_root)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            wait = base_delay * (2 ** (attempt - 1))
            print(f"WARNING: {spec.display_name} download error ({exc}); retry {attempt}/{retries} in {wait:.1f}s")
            if attempt < retries:
                time.sleep(wait)
    assert last_error is not None
    raise last_error


def main() -> None:
    # CLI args
    ap = argparse.ArgumentParser(description='Prefetch datasets into local cache')
    ap.add_argument('-DatasetName', '-d', '--dataset', dest='dataset', help='Specific dataset path/id to prefetch (e.g., coco)', required=False)
    args = ap.parse_args()

    # Ensure .env.local is loaded for HF_TOKEN/HF_* flags in standalone runs
    if load_dotenv:
        repo_root = Path(__file__).resolve().parents[1]
        env_file = repo_root / ".env.local"
        if env_file.exists():
            load_dotenv(env_file)

    cache_root = _dataset_cache_root()
    cache_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('HF_DATASETS_CACHE', str(cache_root))

    hf_token = os.environ.get('HF_TOKEN') or os.environ.get('HF_HUB_TOKEN')
    if hf_token:
        os.environ.setdefault('HF_TOKEN', hf_token)
        os.environ.setdefault('HF_HUB_ENABLE_HF_TRANSFER', '1')

    allow_gated = os.environ.get('HF_DOWNLOAD_GATED', '').strip() == '1'

    targets = _select_targets(args.dataset)
    if not targets:
        print(f"No matching datasets found for: {args.dataset}")
        return

    summary = []
    for spec in targets:
        display = spec.display_name
        local = find_local_copy(spec, cache_root)
        if local:
            source = local['source']
            print(f"[dataset] {display} already available via {source}: {local['path']}")
            summary.append({'dataset': display, 'status': f'ok_{source}', 'detail': local['path']})
            continue

        if spec.gated and not allow_gated and not args.dataset:
            msg = 'skipped (gated dataset; vendor locally or set HF_DOWNLOAD_GATED=1)'
            print(f"WARNING: {display} {msg}")
            summary.append({'dataset': display, 'status': 'skipped_gated_offline', 'detail': msg})
            continue

        if spec.gated and not hf_token:
            msg = 'skipped (gated dataset; configure HF_TOKEN)'
            print(f"WARNING: {display} {msg}")
            summary.append({'dataset': display, 'status': 'skipped_gated_no_token', 'detail': msg})
            continue

        print(f"[dataset] Downloading {display} split={spec.split or 'ALL'} into {cache_root}")
        try:
            ds = _download_with_retry(spec, cache_root)
            summary.append({'dataset': display, 'status': 'ok_downloaded', 'detail': str(ds)})
        except Exception as exc:  # noqa: BLE001
            msg = f"failed: {exc}"
            print(f"WARNING: {display} {msg}")
            summary.append({'dataset': display, 'status': 'error', 'detail': msg})
            continue

    print("\nDataset prefetch summary:")
    for item in summary:
        print(f" - {item['dataset']}: {item['status']} ({item['detail']})")


if __name__ == '__main__':
    main()
