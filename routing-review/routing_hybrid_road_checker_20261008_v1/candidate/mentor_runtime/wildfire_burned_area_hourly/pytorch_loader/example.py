"""Runnable DataLoader example; no training or downloads."""
import argparse
import json
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from .dataset import DEFAULT_ROOT, WildfireSequenceDataset, collate_fire_sequences


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data-root',type=Path,default=DEFAULT_ROOT)
    p.add_argument('--events',nargs='+')
    p.add_argument('--sequence-length',type=int,default=2)
    p.add_argument('--patch-size',type=int,nargs='+',default=[0],
                   help='0: original rectangle; one size: square patch; height width: rectangular patch')
    p.add_argument('--categorical-encoding',choices=['one_hot','raw'],default='one_hot')
    p.add_argument('--batch-size',type=int,default=1)
    p.add_argument('--workers',type=int,default=0)
    args = p.parse_args()
    if len(args.patch_size)==1:
        patch=args.patch_size[0] or None
    elif len(args.patch_size)==2:
        patch=tuple(args.patch_size)
    else:
        p.error('--patch-size expects one size or height width')
    dataset = WildfireSequenceDataset(args.data_root,events=args.events,
             sequence_length=args.sequence_length,patch_size=patch,
             categorical_encoding=args.categorical_encoding)
    try:
        loader = DataLoader(dataset,batch_size=args.batch_size,shuffle=False,
                            num_workers=args.workers,collate_fn=collate_fire_sequences,
                            multiprocessing_context='spawn' if args.workers else None)
        batch = next(iter(loader))
        summary = dict(events=len(dataset.event_ids),samples=len(dataset),
                       channels=len(dataset.channel_names),
                       source_channels=len(dataset.source_channel_names),
                       categorical_encoding=dataset.categorical_encoding,
                       input_shape=list(batch['features'].shape),
                       target_shape=list(batch['burned_area'].shape),
                       event_ids=batch['event_id'],
                       tensor_device=str(batch['features'].device),
                       valid_input_values=int(batch['feature_valid'].sum()),
                       pytorch_version=torch.__version__)
        print(json.dumps(summary,indent=2))
    finally:
        dataset.close()


if __name__ == '__main__': main()
