"""Lossless JSON transport and exclusive atomic creation for evidence records."""
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import tempfile

TAG="__wfg_fraction__"


def encode(value):
    if isinstance(value,Fraction):
        return {TAG:{"numerator":str(value.numerator),"denominator":str(value.denominator)}}
    if value is None or isinstance(value,(bool,int,str)):return value
    if isinstance(value,float):
        if not math.isfinite(value):raise ValueError("nonfinite evidence number")
        return value
    if isinstance(value,(list,tuple)):return [encode(item) for item in value]
    if isinstance(value,dict):
        if TAG in value:raise ValueError("reserved exact Fraction transport tag in original dict")
        if any(not isinstance(key,str) for key in value):raise TypeError("JSON evidence keys must be strings")
        return {key:encode(item) for key,item in value.items()}
    raise TypeError("unsupported evidence type: "+type(value).__name__)


def decode(value):
    if isinstance(value,list):return [decode(item) for item in value]
    if isinstance(value,dict):
        if set(value)=={TAG}:
            body=value[TAG]
            if not isinstance(body,dict) or set(body)!={"numerator","denominator"}:raise ValueError("malformed exact Fraction tag")
            if not all(isinstance(body[k],str) for k in body):raise ValueError("Fraction components must be decimal strings")
            numerator=int(body["numerator"]);denominator=int(body["denominator"])
            if denominator<=0:raise ValueError("Fraction denominator must be positive")
            return Fraction(numerator,denominator)
        return {key:decode(item) for key,item in value.items()}
    return value


def preflight(value):
    # Roundtrip check compares normalized native containers and exact numbers.
    encoded=encode(value)
    payload=json.dumps(encoded,indent=2,ensure_ascii=False,allow_nan=False)+"\n"
    loaded=json.loads(payload)
    if encode(decode(loaded))!=encoded:raise ValueError("exact JSON roundtrip disagreement")
    return payload


def atomic_create(path,payload):
    """Exclusive publication, no partial target and no overwrite race."""
    path=Path(path)
    if path.exists():raise FileExistsError(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    descriptor,temp=tempfile.mkstemp(prefix="."+path.name+".transport-",dir=path.parent)
    try:
        with os.fdopen(descriptor,"w",encoding="utf-8") as output:
            output.write(payload);output.flush();os.fsync(output.fileno())
        os.link(temp,path)  # Atomic exclusive create in the same filesystem.
        directory_fd=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(directory_fd)
        finally:os.close(directory_fd)
    finally:
        try:os.unlink(temp)
        except FileNotFoundError:pass
