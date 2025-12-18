from __future__ import annotations
import argparse
import json
from typing import Any, Dict

from steps.common.config_loader import load_configs
from steps.common.memory import insert_link, upsert_scene, upsert_segment


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add-link")
    add.add_argument("parent_hash")
    add.add_argument("child_hash")
    add.add_argument("relation")
    add.add_argument("--timestamp", type=float, default=None)
    add.add_argument("--meta", default=None)
    sc = sub.add_parser("add-scene")
    sc.add_argument("video_hash")
    sc.add_argument("start", type=float)
    sc.add_argument("end", type=float)
    sc.add_argument("--meta", default=None)
    sg = sub.add_parser("add-segment")
    sg.add_argument("video_hash")
    sg.add_argument("start", type=float)
    sg.add_argument("end", type=float)
    sg.add_argument("--speaker", default=None)
    sg.add_argument("--meta", default=None)
    args = ap.parse_args()

    cfg = load_configs({})
    if args.cmd == "add-link":
        meta = args.meta
        if meta:
            try:
                json.loads(meta)
            except Exception:
                meta = json.dumps({"meta": meta})
        insert_link(cfg, args.parent_hash, args.child_hash, args.relation, args.timestamp, meta)
        print("ok")
        return
    if args.cmd == "add-scene":
        meta = args.meta
        meta_obj = None
        if meta:
            try:
                meta_obj = json.loads(meta)
            except Exception:
                meta_obj = {"meta": meta}
        sid = upsert_scene(cfg, args.video_hash, args.start, args.end, meta_obj)
        print(sid)
        return
    if args.cmd == "add-segment":
        meta = args.meta
        meta_obj = None
        if meta:
            try:
                meta_obj = json.loads(meta)
            except Exception:
                meta_obj = {"meta": meta}
        sid = upsert_segment(cfg, args.video_hash, args.start, args.end, args.speaker, meta_obj)
        print(sid)
        return


if __name__ == "__main__":
    main()
