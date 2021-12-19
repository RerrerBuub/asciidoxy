# Copyright (C) 2019-2021, TomTom (http://tomtom.com).
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for the generator's context."""

from pathlib import Path

import pytest

from asciidoxy.document import Package
from asciidoxy.generator.context import StackFrame, stacktrace
from asciidoxy.generator.errors import ConsistencyError, DuplicateAnchorError, UnknownAnchorError
from asciidoxy.generator.navigation import DocumentTreeNode
from asciidoxy.packaging import UnknownFileError, UnknownPackageError

from .builders import make_compound


def test_initial_document_is_registered(empty_context, document):
    assert empty_context.current_document is document
    assert document.relative_path in empty_context.documents
    assert empty_context.documents[document.relative_path] is document


def test_create_sub_context(empty_context):
    context = empty_context
    context.namespace = "ns"
    context.language = "lang"
    context.source_language = "java"
    context.warnings_are_errors = True
    context.multipage = True
    context.embedded = True
    context.env.variable = 42

    sub = context.sub_context()
    assert sub is not context

    assert sub.namespace == "ns"
    assert sub.language == "lang"
    assert sub.source_language == "java"

    assert sub.env is not context.env
    assert sub.env.variable == 42

    assert sub.warnings_are_errors is True
    assert sub.multipage is True
    assert sub.embedded is True

    assert sub.reference is context.reference
    assert sub.progress is context.progress

    assert sub.linked is context.linked
    assert sub.inserted is context.inserted
    assert sub.anchors is context.anchors
    assert sub.in_to_out_file_map is context.in_to_out_file_map
    assert sub.embedded_file_map is context.embedded_file_map
    assert sub.current_document is context.current_document
    assert sub.current_document_node is context.current_document_node
    assert sub.current_package is context.current_package
    assert sub.call_stack is context.call_stack
    assert sub.documents is context.documents

    assert sub.insert_filter is not context.insert_filter

    sub.namespace = "other"
    sub.language = "objc"
    sub.source_language = "python"
    sub.env.variable = 50
    assert context.namespace == "ns"
    assert context.language == "lang"
    assert context.source_language == "java"
    assert context.env.variable == 42

    assert "element" not in context.linked
    assert "element" not in context.inserted
    sub.linked["element"].append([])
    sub.inserted["element"] = Path("path")
    assert "element" in context.linked
    assert "element" in context.inserted


def test_file_with_element__different_file(empty_context):
    empty_context.multipage = True

    doc1 = empty_context.current_document.with_relative_path("file_1.adoc")
    empty_context.current_document = doc1
    empty_context.insert(make_compound(language="lang", name="type1"))
    empty_context.insert(make_compound(language="lang", name="type2"))

    doc2 = empty_context.current_document.with_relative_path("file_2.adoc")
    empty_context.current_document = doc2
    empty_context.insert(make_compound(language="lang", name="type3"))
    empty_context.insert(make_compound(language="lang", name="type4"))

    assert empty_context.file_with_element("lang-type1") is doc1
    assert empty_context.file_with_element("lang-type2") is doc1


def test_file_with_element__same_file(empty_context):
    empty_context.multipage = True

    doc1 = empty_context.current_document.with_relative_path("file_1.adoc")
    empty_context.current_document = doc1
    empty_context.insert(make_compound(language="lang", name="type1"))
    empty_context.insert(make_compound(language="lang", name="type2"))

    doc2 = empty_context.current_document.with_relative_path("file_2.adoc")
    empty_context.current_document = doc2
    empty_context.insert(make_compound(language="lang", name="type3"))
    empty_context.insert(make_compound(language="lang", name="type4"))

    assert empty_context.file_with_element("lang-type3") is None
    assert empty_context.file_with_element("lang-type4") is None


def test_file_with_element__not_in_singlepage(empty_context):
    empty_context.multipage = False

    empty_context.current_document_node.in_file = Path("file_1.adoc")
    empty_context.insert(make_compound(language="lang", name="type1"))
    empty_context.insert(make_compound(language="lang", name="type2"))

    empty_context.current_document_node.in_file = Path("file_2.adoc")
    empty_context.insert(make_compound(language="lang", name="type3"))
    empty_context.insert(make_compound(language="lang", name="type4"))

    assert empty_context.file_with_element("lang-type1") is None
    assert empty_context.file_with_element("lang-type2") is None
    assert empty_context.file_with_element("lang-type3") is None
    assert empty_context.file_with_element("lang-type4") is None


def test_file_with_element__element_not_found(empty_context):
    empty_context.multipage = True
    assert empty_context.file_with_element("element-id-1") is None


def test_register_adoc_file(empty_context, input_file):
    out_file = empty_context.register_adoc_file(input_file)
    assert out_file.parent == input_file.parent
    assert out_file.name.endswith(input_file.name)
    assert out_file.name.startswith(".asciidoxy.")
    assert out_file != input_file


def test_register_adoc_file__always_returns_same_file(empty_context, input_file):
    out_file = empty_context.register_adoc_file(input_file)
    assert empty_context.register_adoc_file(input_file) == out_file


def test_register_adoc_file__embedded(empty_context, input_file):
    empty_context.embedded = True
    embedded_file = input_file.with_name("embedded.adoc")

    out_file = empty_context.register_adoc_file(embedded_file)
    assert out_file.parent == input_file.parent
    assert out_file.name.endswith(input_file.name)
    assert out_file != embedded_file


def test_register_adoc_file__embedded__always_returns_same_file(empty_context, input_file):
    empty_context.embedded = True
    embedded_file = input_file.with_name("embedded.adoc")

    out_file = empty_context.register_adoc_file(embedded_file)
    assert empty_context.register_adoc_file(embedded_file) == out_file


def test_register_adoc_file__embedded__can_be_embedded_in_multiple_files(empty_context, input_file):
    empty_context.embedded = True
    embedded_file = input_file.with_name("embedded.adoc")

    out_file = empty_context.register_adoc_file(embedded_file)

    other_input_file = input_file.with_name("other_file.adoc")
    empty_context.current_document_node.in_file = other_input_file

    assert empty_context.register_adoc_file(embedded_file) != out_file


def test_link_to_adoc_file__singlepage__known_file(empty_context, input_file):
    linked_file = input_file.with_name("linked_file.adoc")
    linked_out_file = empty_context.register_adoc_file(linked_file)
    assert empty_context.link_to_adoc_file(linked_file) == linked_out_file.relative_to(
        input_file.parent)


def test_link_to_adoc_file__singlepage__unknown_file(empty_context, input_file):
    linked_file = input_file.with_name("linked_file.adoc")
    assert empty_context.link_to_adoc_file(linked_file) == linked_file.relative_to(
        input_file.parent)


def test_link_to_adoc_file__singlepage__link_to_embedded_file(empty_context, input_file):
    empty_context.embedded = True
    linked_file = input_file.with_name("linked_file.adoc")
    linked_out_file = empty_context.register_adoc_file(linked_file)
    empty_context.embedded = False
    assert empty_context.link_to_adoc_file(linked_file) == linked_out_file.relative_to(
        input_file.parent)


def test_link_to_adoc_file__singlepage__multiple_times_embedded__link_different_file(
        empty_context, input_file):

    embedded_file = input_file.with_name("embedded_file.adoc")
    second_file = input_file.with_name("second_file.adoc")
    other_file = input_file.with_name("other_file.adoc")

    empty_context.embedded = True
    empty_context.register_adoc_file(embedded_file)
    empty_context.current_document_node.in_file = second_file
    empty_context.register_adoc_file(embedded_file)
    empty_context.embedded = False

    empty_context.current_document_node.in_file = other_file
    with pytest.raises(ConsistencyError):
        empty_context.link_to_adoc_file(embedded_file)


def test_link_to_adoc_file__singlepage__link_to_embedded_file__link_different_file(
        empty_context, input_file):

    embedded_file = input_file.with_name("embedded_file.adoc")
    other_file = input_file.with_name("other_file.adoc")

    empty_context.embedded = True
    empty_context.register_adoc_file(embedded_file)
    empty_context.embedded = False

    empty_context.current_document_node.in_file = other_file
    assert empty_context.link_to_adoc_file(embedded_file) == input_file.relative_to(
        input_file.parent)


def test_link_to_adoc_file__multipage__known_file(empty_context, input_file):
    empty_context.multipage = True
    linked_file = input_file.with_name("linked_file.adoc")
    empty_context.register_adoc_file(linked_file)
    assert empty_context.link_to_adoc_file(linked_file) == linked_file.relative_to(
        input_file.parent)


def test_link_to_adoc_file__multipage__unknown_file(empty_context, input_file):
    empty_context.multipage = True
    linked_file = input_file.with_name("linked_file.adoc")
    assert empty_context.link_to_adoc_file(linked_file) == linked_file.relative_to(
        input_file.parent)


def test_link_to_adoc_file__multipage__link_to_embedded_file(empty_context, input_file):
    empty_context.multipage = True
    empty_context.embedded = True
    linked_file = input_file.with_name("linked_file.adoc")
    linked_out_file = empty_context.register_adoc_file(linked_file)
    empty_context.embedded = False
    assert empty_context.link_to_adoc_file(linked_file) == linked_out_file.relative_to(
        input_file.parent)


def test_link_to_adoc_file__multipage__multiple_times_embedded__link_different_file(
        empty_context, input_file):

    embedded_file = input_file.with_name("embedded_file.adoc")
    second_file = input_file.with_name("second_file.adoc")
    other_file = input_file.with_name("other_file.adoc")

    empty_context.multipage = True
    empty_context.embedded = True
    empty_context.register_adoc_file(embedded_file)
    empty_context.current_document_node.in_file = second_file
    empty_context.register_adoc_file(embedded_file)
    empty_context.embedded = False

    empty_context.current_document_node.in_file = other_file
    with pytest.raises(ConsistencyError):
        empty_context.link_to_adoc_file(embedded_file)


def test_link_to_adoc_file__multipage__link_to_embedded_file__link_different_file(
        empty_context, input_file):

    embedded_file = input_file.with_name("embedded_file.adoc")
    other_file = input_file.with_name("other_file.adoc")

    empty_context.multipage = True
    empty_context.embedded = True
    empty_context.register_adoc_file(embedded_file)
    empty_context.embedded = False

    empty_context.current_document_node.in_file = other_file
    assert empty_context.link_to_adoc_file(embedded_file) == input_file.relative_to(
        input_file.parent)


def test_link_to_adoc_file__link_to_embedded_file__multiple_times_embedded__link_same_file(
        empty_context, input_file):

    embedded_file = input_file.with_name("embedded_file.adoc")
    second_file = input_file.with_name("second_file.adoc")

    empty_context.embedded = True
    input_linked_out_file = empty_context.register_adoc_file(embedded_file)
    empty_context.current_document_node.in_file = second_file
    second_linked_out_file = empty_context.register_adoc_file(embedded_file)
    empty_context.embedded = False

    empty_context.current_document_node.in_file = input_file
    assert empty_context.link_to_adoc_file(embedded_file) == input_linked_out_file.relative_to(
        input_file.parent)

    empty_context.current_document_node.in_file = second_file
    assert empty_context.link_to_adoc_file(embedded_file) == second_linked_out_file.relative_to(
        input_file.parent)


def test_docinfo_footer_file__singlepage(empty_context, input_file):
    footer_file = empty_context.docinfo_footer_file()
    assert footer_file.parent == input_file.parent
    assert footer_file.name == f".asciidoxy.{input_file.stem}-docinfo-footer.html"


def test_docinfo_footer_file__singlepage__included(empty_context, input_file):
    empty_context.register_adoc_file(input_file)

    included_file = input_file.with_name("sub_doc.adoc")
    empty_context.current_document_node = DocumentTreeNode(included_file,
                                                           empty_context.current_document_node)
    empty_context.register_adoc_file(included_file)

    footer_file = empty_context.docinfo_footer_file()
    assert footer_file.parent == input_file.parent
    assert footer_file.name == f".asciidoxy.{input_file.stem}-docinfo-footer.html"


def test_docinfo_footer_file__singlepage__embedded(empty_context, input_file):
    empty_context.register_adoc_file(input_file)

    embedded_file = input_file.with_name("sub_doc.adoc")
    empty_context.embedded = True
    empty_context.register_adoc_file(embedded_file)

    footer_file = empty_context.docinfo_footer_file()
    assert footer_file.parent == input_file.parent
    assert footer_file.name == f".asciidoxy.{input_file.stem}-docinfo-footer.html"


def test_docinfo_footer_file__multipage(empty_context, input_file):
    empty_context.multipage = True

    footer_file = empty_context.docinfo_footer_file()
    assert footer_file.parent == input_file.parent
    assert footer_file.name == f".asciidoxy.{input_file.stem}-docinfo-footer.html"


def test_docinfo_footer_file__multipage__included(empty_context, input_file):
    empty_context.multipage = True
    empty_context.register_adoc_file(input_file)

    included_file = input_file.with_name("sub_doc.adoc")
    empty_context.current_document_node = DocumentTreeNode(included_file,
                                                           empty_context.current_document_node)
    empty_context.register_adoc_file(included_file)

    footer_file = empty_context.docinfo_footer_file()
    assert footer_file.parent == input_file.parent
    assert footer_file.name == f".asciidoxy.{included_file.stem}-docinfo-footer.html"


def test_docinfo_footer_file__multipage__embedded(empty_context, input_file):
    empty_context.multipage = True
    empty_context.register_adoc_file(input_file)

    embedded_file = input_file.with_name("sub_doc.adoc")
    empty_context.embedded = True
    empty_context.register_adoc_file(embedded_file)

    footer_file = empty_context.docinfo_footer_file()
    assert footer_file.parent == input_file.parent
    assert footer_file.name == f".asciidoxy.{input_file.stem}-docinfo-footer.html"


def test_register_and_link_to_anchor__same_file(empty_context, input_file):
    empty_context.register_anchor("my-anchor", "anchor text", input_file)
    assert empty_context.link_to_anchor("my-anchor") == (Path(input_file.name), "anchor text")


def test_register_and_link_to_anchor__different_file(empty_context, input_file):
    other_file = input_file.with_name("other.adoc")
    empty_context.register_anchor("my-anchor", "anchor text", other_file)
    assert empty_context.link_to_anchor("my-anchor") == (Path(other_file.name), "anchor text")


def test_register_and_link_to_anchor__no_link_text(empty_context, input_file):
    empty_context.register_anchor("my-anchor", None, input_file)
    assert empty_context.link_to_anchor("my-anchor") == (Path(input_file.name), None)


def test_register_anchor__duplicate_name(empty_context, input_file):
    empty_context.register_anchor("my-anchor", None, input_file)
    with pytest.raises(DuplicateAnchorError):
        empty_context.register_anchor("my-anchor", None, input_file)


def test_link_to_anchor__unknown(empty_context, input_file):
    with pytest.raises(UnknownAnchorError):
        empty_context.link_to_anchor("my-anchor")


def test_link_to_element__single_link(empty_context, input_file):
    empty_context.push_stack("link(\"MyElement\")", input_file, Package.INPUT_PACKAGE_NAME)
    empty_context.link_to_element("my-element-id")
    empty_context.pop_stack()

    assert "my-element-id" in empty_context.linked
    assert empty_context.linked["my-element-id"] == [
        [
            StackFrame("link(\"MyElement\")", input_file, Package.INPUT_PACKAGE_NAME, False),
        ],
    ]


def test_link_to_element__multiple_links(empty_context, input_file):
    empty_context.push_stack("link(\"MyElement\")", input_file, Package.INPUT_PACKAGE_NAME)
    empty_context.link_to_element("my-element-id")
    empty_context.pop_stack()

    other_file = input_file.parent / "other_file.adoc"
    empty_context.push_stack("link(\"MyElement\")", other_file, Package.INPUT_PACKAGE_NAME)
    empty_context.link_to_element("my-element-id")
    empty_context.pop_stack()

    assert "my-element-id" in empty_context.linked
    assert empty_context.linked["my-element-id"] == [
        [
            StackFrame("link(\"MyElement\")", input_file, Package.INPUT_PACKAGE_NAME, False),
        ],
        [
            StackFrame("link(\"MyElement\")", other_file, Package.INPUT_PACKAGE_NAME, False),
        ],
    ]


def test_link_to_element__nested_call_stack(empty_context, input_file):
    empty_context.push_stack("include(\"other_file.adoc\")", input_file, Package.INPUT_PACKAGE_NAME)
    other_file = input_file.parent / "other_file.adoc"
    empty_context.push_stack("insert(\"MyElement\")", other_file)
    empty_context.push_stack("link(\"OtherElement\")")
    empty_context.link_to_element("other-element-id")
    empty_context.pop_stack()
    empty_context.pop_stack()
    empty_context.pop_stack()

    assert "other-element-id" in empty_context.linked
    assert empty_context.linked["other-element-id"] == [
        [
            StackFrame("include(\"other_file.adoc\")", input_file, Package.INPUT_PACKAGE_NAME,
                       False),
            StackFrame("insert(\"MyElement\")", other_file, None, False),
            StackFrame("link(\"OtherElement\")", None, None, False),
        ],
    ]


def test_insert__store_stacktrace(empty_context, input_file, document):
    empty_context.push_stack("include(\"other_file.adoc\")", input_file, Package.INPUT_PACKAGE_NAME)

    element = make_compound(id="cpp-my_element", name="MyElement")
    empty_context.insert(element)

    empty_context.pop_stack()

    assert element.id in empty_context.inserted
    assert empty_context.inserted[element.id] == (document, [
        StackFrame("include(\"other_file.adoc\")", input_file, Package.INPUT_PACKAGE_NAME, False),
    ])


def test_insert__duplicate(empty_context, input_file):
    empty_context.warnings_are_errors = True

    element = make_compound(id="cpp-my_element", name="MyElement")
    other_file = input_file.parent / "other_file.adoc"

    empty_context.push_stack("include(\"other_file.adoc\")", input_file)
    empty_context.insert(element)
    empty_context.pop_stack()

    empty_context.push_stack("insert(\"MyElement\")", other_file)
    with pytest.raises(ConsistencyError) as exc_info:
        empty_context.insert(element)
    empty_context.pop_stack()

    assert exc_info.value.msg == f"""\
Duplicate insertion of MyElement.
Trying to insert at:
  Commands in input files:
    {other_file}:
      insert("MyElement")
Previously inserted at:
  Commands in input files:
    {input_file}:
      include("other_file.adoc")"""


def test_find_document__input_pkg__explicit_file(file_builder):
    doc = file_builder.add_input_file("base/index.adoc", register=False)
    context = file_builder.context()

    new_doc = context.find_document(Package.INPUT_PACKAGE_NAME, doc.relative_path)
    assert new_doc.relative_path == doc.relative_path
    assert new_doc.package.name == Package.INPUT_PACKAGE_NAME

    known_doc = context.find_document(Package.INPUT_PACKAGE_NAME, doc.relative_path)
    assert known_doc.relative_path == doc.relative_path
    assert known_doc.package.name == Package.INPUT_PACKAGE_NAME

    assert new_doc is known_doc


def test_find_document__input_pkg__default_file(file_builder):
    doc = file_builder.add_input_file("base/index.adoc", register=False)
    context = file_builder.context()

    new_doc = context.find_document(Package.INPUT_PACKAGE_NAME, None)
    assert new_doc.relative_path == doc.relative_path
    assert new_doc.package.name == Package.INPUT_PACKAGE_NAME

    known_doc = context.find_document(Package.INPUT_PACKAGE_NAME, None)
    assert known_doc.relative_path == doc.relative_path
    assert known_doc.package.name == Package.INPUT_PACKAGE_NAME

    assert new_doc is known_doc


def test_find_document__input_pkg__file_not_found(file_builder):
    file_builder.add_input_file("base/index.adoc", register=False)
    context = file_builder.context()

    with pytest.raises(UnknownFileError):
        context.find_document(Package.INPUT_PACKAGE_NAME, Path("unknown.adoc"))
    with pytest.raises(UnknownFileError):
        context.find_document(Package.INPUT_PACKAGE_NAME, Path("unknown.adoc"))


def test_find_document__pkg__explicit_file(file_builder):
    file_builder.add_input_file("base/index.adoc", register=False)
    doc = file_builder.add_package_file("my-package", "nice-doc.adoc", register=False)
    context = file_builder.context()

    new_doc = context.find_document("my-package", doc.relative_path)
    assert new_doc.relative_path == doc.relative_path
    assert new_doc.package.name == "my-package"

    known_doc = context.find_document("my-package", doc.relative_path)
    assert known_doc.relative_path == doc.relative_path
    assert known_doc.package.name == "my-package"

    assert new_doc is known_doc


def test_find_document__pkg__file_not_found(file_builder):
    file_builder.add_input_file("base/index.adoc", register=False)
    file_builder.add_package_file("my-package", "nice-doc.adoc", register=False)
    context = file_builder.context()

    with pytest.raises(UnknownFileError):
        context.find_document("my-package", Path("other-file.adoc"))
    with pytest.raises(UnknownFileError):
        context.find_document("my-package", Path("other-file.adoc"))


def test_find_document__pkg__wrong_package_name(file_builder):
    file_builder.add_input_file("base/index.adoc", register=False)
    file_builder.add_package_file("my-package", "nice-doc.adoc", register=False)
    doc = file_builder.add_package_file("other-package", "other-doc.adoc", register=False)
    context = file_builder.context()

    with pytest.raises(UnknownFileError):
        context.find_document("my-package", doc.relative_path)
    with pytest.raises(UnknownFileError):
        context.find_document("my-package", doc.relative_path)


def test_find_document__pkg__package_name_must_match_for_known_files_too(file_builder):
    file_builder.add_input_file("base/index.adoc", register=False)
    doc = file_builder.add_package_file("my-package", "nice-doc.adoc", register=False)
    context = file_builder.context()

    new_doc = context.find_document("my-package", doc.relative_path)
    assert new_doc.relative_path == doc.relative_path
    assert new_doc.package.name == "my-package"

    with pytest.raises(UnknownFileError):
        context.find_document("other-package", doc.relative_path)


def test_find_document__pkg__unknown_package(file_builder):
    file_builder.add_input_file("base/index.adoc", register=False)
    doc = file_builder.add_package_file("my-package", "nice-doc.adoc", register=False)
    context = file_builder.context()

    with pytest.raises(UnknownPackageError):
        context.find_document("other-package", doc.relative_path)
    with pytest.raises(UnknownPackageError):
        context.find_document("other-package", doc.relative_path)


def test_find_document__pkg__default_file(file_builder):
    file_builder.add_input_file("base/index.adoc", register=False)
    doc = file_builder.add_package_default_file("my-package", "nice-doc.adoc", register=False)
    context = file_builder.context()

    new_doc = context.find_document("my-package", None)
    assert new_doc.relative_path == doc.relative_path
    assert new_doc.package.name == "my-package"

    known_doc = context.find_document("my-package", None)
    assert known_doc.relative_path == doc.relative_path
    assert known_doc.package.name == "my-package"

    assert new_doc is known_doc


def test_find_document__pkg__no_default_file(file_builder):
    file_builder.add_input_file("base/index.adoc", register=False)
    file_builder.add_package_file("my-package", "nice-doc.adoc", register=False)
    context = file_builder.context()

    with pytest.raises(UnknownFileError):
        context.find_document("my-package", None)
    with pytest.raises(UnknownFileError):
        context.find_document("my-package", None)


def test_stacktrace__external_only(input_file):
    other_file = input_file.parent / "other_file.adoc"

    trace = [
        StackFrame("include('other_file.adoc')", input_file, Package.INPUT_PACKAGE_NAME, False),
        StackFrame("insert('MyElement')", other_file, Package.INPUT_PACKAGE_NAME, False),
    ]
    assert stacktrace(trace) == f"""\
Commands in input files:
  {input_file}:
    include('other_file.adoc')
  {other_file}:
    insert('MyElement')"""


def test_stacktrace__external_only__other_package(input_file):
    other_file = input_file.parent / "other_file.adoc"

    trace = [
        StackFrame("include('other_file.adoc')", input_file, "pkga", False),
        StackFrame("insert('MyElement')", other_file, "pkgb", False),
    ]
    assert stacktrace(trace) == f"""\
Commands in input files:
  pkga:/{input_file}:
    include('other_file.adoc')
  pkgb:/{other_file}:
    insert('MyElement')"""


def test_stacktrace__external_and_internal(input_file):
    other_file = input_file.parent / "other_file.adoc"

    trace = [
        StackFrame("include('other_file.adoc')", input_file, Package.INPUT_PACKAGE_NAME, False),
        StackFrame("insert('MyElement')", other_file, Package.INPUT_PACKAGE_NAME, False),
        StackFrame("insert('OtherElement')", None, None, True),
        StackFrame("link('GreatElement')", None, None, True),
    ]
    assert stacktrace(trace) == f"""\
Commands in input files:
  {input_file}:
    include('other_file.adoc')
  {other_file}:
    insert('MyElement')
Internal AsciiDoxy commands:
    insert('OtherElement')
    link('GreatElement')"""


def test_stacktrace__internal_only(input_file):
    trace = [
        StackFrame("insert('OtherElement')", None, None, True),
        StackFrame("link('GreatElement')", None, None, True),
    ]
    assert stacktrace(trace) == """\
Internal AsciiDoxy commands:
    insert('OtherElement')
    link('GreatElement')"""


def test_stacktrace__empty(input_file):
    assert stacktrace([]) == ""
