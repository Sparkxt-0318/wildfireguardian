"""Validate saved expanded channel groups without rediscovering vocabularies."""

import numpy as np


CHANNELS = (
    "weather.temperature_2m",
    "weather.wind_eastward_10m",
    "weather.wind_northward_10m",
    "terrain.slope_degrees",
    "vegetation.tree_cover_percent",
)

TRAINING_SOURCE_CHANNELS = CHANNELS + ("biome.biome_class",)


SCHEMA_KEYS = ("source_channels", "channel_info", "categorical_encoding",
               "categorical_classes", "channel_groups")


def one_hot_groups(schema):
    """Return complete categorical groups, accepting legacy continuous schemas."""
    if not any(key in schema for key in SCHEMA_KEYS):
        return {}
    if any(key not in schema for key in SCHEMA_KEYS):
        raise ValueError("The encoded channel schema is incomplete")
    if schema["categorical_encoding"] != "one_hot":
        raise ValueError("Trained categorical inputs must use one_hot encoding")
    channels, info = schema["channels"], schema["channel_info"]
    sources, groups = schema["source_channels"], schema["channel_groups"]
    classes = schema["categorical_classes"]
    if len(info) != len(channels) or len(sources) != len(set(sources)) or set(groups) != set(sources):
        raise ValueError("Encoded channel metadata does not match the ordered input schema")
    if list(dict.fromkeys(entry.get("source_channel") for entry in info)) != list(sources):
        raise ValueError("Source channel order differs from the expanded channel metadata")
    categorical = {}
    for source in sources:
        expected = [i for i, entry in enumerate(info) if entry.get("source_channel") == source]
        indices = groups[source]
        if list(indices) != expected or not expected:
            raise ValueError("Channel groups differ from their source channel metadata")
        if any(info[i].get("name") != channels[i] for i in indices):
            raise ValueError("Channel metadata names differ from the ordered inputs")
        encodings = {info[i].get("encoding") for i in indices}
        if encodings == {"one_hot"}:
            codes = classes.get(source)
            if (not isinstance(codes, (list, tuple)) or not codes
                    or any(type(code) is not int for code in codes)
                    or list(codes) != sorted(set(codes))):
                raise ValueError("One-hot class codes must be distinct ascending integers")
            if [info[i].get("class_code") for i in indices] != list(codes):
                raise ValueError("One-hot group codes differ from the frozen vocabulary")
            if [channels[i] for i in indices] != [f"{source}={code}" for code in codes]:
                raise ValueError("One-hot channel names differ from the frozen class codes")
            categorical[source] = tuple(indices)
        elif encodings != {"continuous"} or len(indices) != 1 or channels[indices[0]] != source:
            raise ValueError("Continuous channels or categorical encoding are inconsistent")
    if set(classes) != set(categorical):
        raise ValueError("Categorical vocabularies differ from the complete one-hot groups")
    return categorical


def validate_one_hot_array(environment, schema):
    """Require complete raw indicator vectors in an already valid training cache."""
    for source, indices in one_hot_groups(schema).items():
        values = environment[:, indices]
        if not np.isin(values, (0, 1)).all() or not (values.sum(axis=1) == 1).all():
            raise ValueError(f"Invalid complete one-hot input group: {source}")
