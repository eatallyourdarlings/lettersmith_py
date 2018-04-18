from os import path
from pathlib import PurePath
import json
from datetime import datetime
from typing import NamedTuple, Union

import frontmatter

from lettersmith.date import parse_iso_8601, read_file_times, EPOCH
from lettersmith.file import write_file_deep
from lettersmith import yamltools
from lettersmith.stringtools import truncate, strip_html
from lettersmith import path as pathtools
from lettersmith.util import replace, get
from lettersmith import stub as Stub


_EMPTY_TUPLE = tuple()


class Doc(NamedTuple):
    """
    Docs are namedtuples that represent a document to be transformed,
    and eventually written to disk.

    Docs contain a content field — usually the whole contents of a
    file. Since this can take up quite a bit of memory, it's typical to avoid
    collecting all docs into memory. We usually load and transform them in
    generator functions so that only one is in memory at a time.

    For collecting many in memory, and cross-referencing, we use Stubs.
    Stubs are meant to be stub docs. They contain just meta information
    about the doc. You can turn a doc into a stub with `to_stub(doc)`.
    """
    id_path: str
    output_path: str
    input_path: Union[str, None]
    created: datetime
    modified: datetime
    title: str
    content: str
    section: str
    meta: dict
    templates: tuple


def doc(id_path, output_path,
    input_path=None, created=EPOCH, modified=EPOCH,
    title="", content="", section="", meta=None, templates=None):
    """
    Create a Doc tuple, populating it with sensible defaults
    """
    return Doc(
        id_path=str(id_path),
        output_path=str(output_path),
        input_path=str(input_path) if input_path is not None else None,
        created=created,
        modified=modified,
        title=str(title),
        content=str(content),
        section=str(section),
        meta=meta if meta is not None else {},
        templates=templates if templates is not None else _EMPTY_TUPLE
    )


@replace.register(Doc)
def replace_doc(doc, **kwargs):
    """
    Replace items in a Doc, returning a new Doc.
    """
    return doc._replace(**kwargs)


def replace_meta(doc, **kwargs):
    """
    Put a value into a doc's meta dictionary.
    Returns a new doc.
    """
    return replace(doc, meta=replace(doc.meta, **kwargs))


def load(pathlike, relative_to=""):
    """
    Loads a basic doc dictionary from a file path. This dictionary
    contains content string, and some basic information about the file.
    Typically, you decorate the doc later with meta and other fields.
    Create a doc dict, populating it with sensible defaults

    Returns a dictionary.
    """
    created, modified = read_file_times(pathlike)
    with open(pathlike) as f:
        meta, content = frontmatter.parse(f.read())
        input_path = PurePath(pathlike)
        id_path = input_path.relative_to(relative_to)
        output_path = pathtools.to_nice_path(id_path)
        section = pathtools.tld(id_path)
        title = meta.get("title", pathtools.to_title(input_path))
        return doc(
            id_path=id_path,
            output_path=output_path,
            input_path=input_path,
            created=created,
            modified=modified,
            title=title,
            section=section,
            meta=meta,
            content=content
        )


def to_stub(doc, max_len=250, suffix="..."):
    try:
        summary = doc.meta["summary"]
    except KeyError:
        summary = truncate(strip_html(doc.content), max_len, suffix)

    return Stub.stub(
        id_path=doc.id_path,
        output_path=doc.output_path,
        input_path=doc.input_path,
        created=doc.created,
        modified=doc.modified,
        title=doc.title,
        summary=summary,
        section=doc.section,
        meta=doc.meta
    )


def write(doc, output_dir):
    """
    Write a doc to the filesystem.

    Uses `doc.output_path` and `output_dir` to construct the output path.
    """
    write_file_deep(path.join(output_dir, doc.output_path), doc.content)


def change_ext(doc, ext):
    """Change the extention on a doc's output_path, returning a new doc."""
    updated_path = PurePath(doc.output_path).with_suffix(ext)
    return replace(doc, output_path=str(updated_path))


def with_path(glob):
    """
    Check if a path matches glob pattern.
    """
    def has_path(doc):
        return fnmatch(doc.id_path, glob)
    return has_path