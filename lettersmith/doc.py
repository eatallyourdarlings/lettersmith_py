from pathlib import PurePath
import json
import hashlib
from collections import namedtuple
import pickle

import frontmatter
import yaml

from lettersmith.date import read_file_times, EPOCH, to_datetime
from lettersmith.file import write_file_deep
from lettersmith import path as pathtools
from lettersmith.util import replace, get, maps_if


_EMPTY_TUPLE = tuple()

Doc = namedtuple("Doc", (
    "id_path", "output_path", "input_path", "created", "modified",
    "title", "content", "section", "meta", "templates"
))
Doc.__doc__ = """
Docs are namedtuples that represent a document to be transformed,
and eventually written to disk.

Docs contain a content field — usually the whole contents of a
file. Since this can take up quite a bit of memory, it's typical to avoid
collecting all docs into memory. We usually load and transform them in
generator functions so that only one is in memory at a time.

For collecting many in memory, and cross-referencing, we use Stubs.
Stubs are meant to be stub docs. They contain just meta information
about the doc. You can turn a doc into a stub with
`lettersmith.stub.from_doc(doc)`.
"""


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
        created=to_datetime(created),
        modified=to_datetime(modified),
        title=str(title),
        content=str(content),
        section=str(section),
        meta=meta if meta is not None else {},
        templates=templates if templates is not None else _EMPTY_TUPLE
    )


@get.register(Doc)
def get_doc(doc, key, default=None):
    return getattr(doc, key, default)


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
    Loads a basic doc dictionary from a file path.
    `content` field will contain contents of file.
    Typically, you decorate the doc later with meta and other fields.

    Returns a doc.
    """
    file_created, file_modified = read_file_times(pathlike)
    with open(pathlike, 'r') as f:
        content = f.read()
    input_path = PurePath(pathlike)
    id_path = input_path.relative_to(relative_to)
    output_path = pathtools.to_nice_path(id_path)
    section = pathtools.tld(id_path)
    title = pathtools.to_title(input_path)
    return doc(
        id_path=id_path,
        output_path=output_path,
        input_path=input_path,
        created=file_created,
        modified=file_modified,
        title=title,
        section=section,
        meta={},
        content=content
    )


def from_stub(stub):
    """
    Create a doc dictionary from an stub dictionary.
    This doc dictionary will have an empty "content" field.

    If you want to load a doc from a file stub with an `input_path`,
    use `load_doc` instead.
    """
    return doc(
        id_path=stub.id_path,
        output_path=stub.output_path,
        input_path=stub.input_path,
        created=stub.created,
        modified=stub.modified,
        title=stub.title,
        section=stub.section,
        meta=stub.meta
    )


def to_json(doc):
    """
    Serialize a doc as JSON-serializable data
    """
    return {
        "@type": "doc",
        "id_path": doc.id_path,
        "output_path": doc.output_path,
        "input_path": doc.input_path,
        "created": doc.created.timestamp(),
        "modified": doc.modified.timestamp(),
        "title": doc.title,
        "section": doc.section,
        "content": doc.content,
        # TODO manually serialize meta?
        "meta": doc.meta,
        "templates": doc.templates
    }


def write(doc, output_dir):
    """
    Write a doc to the filesystem.

    Uses `doc.output_path` and `output_dir` to construct the output path.
    """
    write_file_deep(PurePath(output_dir).joinpath(doc.output_path), doc.content)


def uplift_meta(doc):
    """
    Reads "magic" fields in the meta and uplifts their values to doc
    properties.
    """
    return doc._replace(
        title=doc.meta.get("title", doc.title),
        created=to_datetime(doc.meta.get("created", doc.created)),
        modified=to_datetime(doc.meta.get("modified", doc.modified))
    )


def ext(*exts):
    """
    Create an extension predicate function.
    """
    def has_ext(doc):
        return pathtools.has_ext(doc.id_path, *exts)
    return has_ext


def maps_if_ext(*exts):
    """
    Decorate a doc mapping function so it will only map a doc if the
    doc's `id_path` has one of the extensions listed in the `*ext` args.
    If the doc does not have any of those extensions, it is left
    untouched.
    """
    return maps_if(ext(*exts))


def change_ext(doc, ext):
    """Change the extention on a doc's output_path, returning a new doc."""
    updated_path = PurePath(doc.output_path).with_suffix(ext)
    return doc._replace(output_path=str(updated_path))


class DocException(Exception):
    pass


def doc_exceptions(func):
    """
    Decorates a mapping function for docs, giving it a more useful
    exception message.
    """
    def map_doc(doc):
        try:
            return func(doc)
        except Exception as e:
            msg = (
                'Error encountered while mapping doc '
                '"{id_path}" with {module}.{func}.'
            ).format(
                id_path=doc.id_path,
                func=func.__qualname__,
                module=func.__module__
            )
            raise DocException(msg) from e
    map_doc.__wrapped__ = func
    return map_doc


@doc_exceptions
def parse_frontmatter(doc):
    meta, content = frontmatter.parse(doc.content)
    return doc._replace(
        meta=meta,
        content=content
    )


@doc_exceptions
def parse_yaml(doc):
    """
    Parse YAML in the doc's content property, placing it in meta
    and replacing content property with an empty string.
    """
    meta = yaml.load(doc.content)
    return doc._replace(
        meta=meta,
        content=""
    )


@doc_exceptions
def parse_json(doc):
    """
    Parse JSON in the doc's content property, placing it in meta
    and replacing content property with an empty string.
    """
    meta = json.loads(doc.content)
    return doc._replace(
        meta=meta,
        content=""
    )


def _hashstr(s):
    return hashlib.md5(str(s).encode()).hexdigest()


def _cache_path(id_path):
    """
    Read a doc ID path
    """
    return PurePath(_hashstr(id_path)).with_suffix('.pkl')


class Cache:
    """
    Memoized cache dump/load for docs
    """
    def __init__(self, cache_path):
        self.cache_path = PurePath(cache_path)

    def dump(self, doc):
        doc_cache_path = _cache_path(doc.id_path)
        with open(PurePath(self.cache_path, doc_cache_path), "wb") as f:
            pickle.dump(doc, f)
            return doc

    def load(self, stub):
        doc_cache_path = _cache_path(stub.id_path)
        with open(PurePath(self.cache_path, doc_cache_path), "rb") as f:
            return pickle.load(f)