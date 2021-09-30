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
"""Parse brief and detailed descriptions from Doxygen XML."""

import logging

import xml.etree.ElementTree as ET

from abc import ABC, abstractmethod
from typing import List, Mapping, Optional, Tuple, Type, TypeVar, cast

logger = logging.getLogger(__name__)


def parse_description(xml_root: Optional[ET.Element], language_tag: str) -> "ParaContainer":
    """Parse a description from Doxygen XML.

    Expects either `briefdescription` or `detaileddescription`. In case of `detaileddescription` it
    can contain additional sections documenting parameters and return types.

    Args:
        xml_root: Element to start processing from.
        language_tag: Tag indicating the programming language.
    Returns:
        A container with description paragraphs and sections.
    """
    contents = ParaContainer(language_tag)
    if xml_root is not None:
        for xml_element in xml_root:
            _parse_description(xml_element, contents, language_tag)
        contents.normalize()
    return contents


def select_descriptions(brief: "ParaContainer", detailed: "ParaContainer") -> Tuple[str, str]:
    """Select the approprate brief and detailed descriptions.

    Sometimes one of the descriptions is missing. This method makes sure there is always at least
    a brief description.

    Args:
        brief: Brief description as found in the XML.
        detailed: Detailed description as found in the XML.

    Returns:
        brief: Brief description to use.
        detailed: Detailed description to use.
    """
    brief_adoc = brief.to_asciidoc()
    if brief_adoc:
        return brief_adoc, detailed.to_asciidoc()

    if detailed.contents:
        brief.contents.append(detailed.contents.pop(0))
    return brief.to_asciidoc(), detailed.to_asciidoc()


class AsciiDocContext:
    """Context for generating AsciiDoc.

    Some elements are context-aware. They need to adapt to the elements they are nested in.
    """
    def __init__(self):
        self.table_separators = []
        self.list_markers = []


class DescriptionElement(ABC):
    """A description in Doxygen XML is made up of several different XML elements. Each element
    requires its own conversion into AsciiDoc format.
    """
    language_tag: str

    def __init__(self, language_tag: str):
        self.language_tag = language_tag

    @abstractmethod
    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        """Convert the element, and all contained elements, to AsciiDoc format."""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}"

    @classmethod
    def from_xml(cls, xml_element: ET.Element, language_tag: str) -> "DescriptionElement":
        """Generate a description element from its XML counterpart.

        Information and attributes from XML can be used, but the contained text and the tail text
        are handled separately.
        """
        return cls(language_tag)

    def update_from_xml(self, xml_element: ET.Element):
        """Update the current element with information from another XML element.

        By default this method does nothing. To be implemented only by subclasses that support or
        require information from some if its children, without adding a new element for the child.
        """

    def add_text(self, text: str) -> None:
        """Add the text inside the XML element.

        By default the text is ignored. To be implemented only by subclasses that use the text.
        """

    def add_tail(self, parent: "NestedDescriptionElement", text: str) -> None:
        """Add the text after the closing tag of the element.

        By default the tail is ignored. To be used by subclasses that support tail text. The parent
        can be used to create additional elements for the tail text after the current element.
        """


class NestedDescriptionElement(DescriptionElement):
    """A description element that contains additional description elements.

    Attributes:
        contents: Additional description elements inside this element.
    """
    contents: List[DescriptionElement]

    def __init__(self, language_tag: str, *contents: DescriptionElement):
        super().__init__(language_tag)
        self.contents = list(contents)

    def append(self, content: DescriptionElement) -> None:
        if content:
            self.contents.append(content)

    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        return "".join(element.to_asciidoc(context) for element in self.contents)

    def normalize(self) -> None:
        for child in self.contents:
            if isinstance(child, NestedDescriptionElement):
                child.normalize()


class ParaContainer(NestedDescriptionElement):
    """Element that contains a sequence of paragraphes."""
    def append(self, content: DescriptionElement) -> None:
        assert isinstance(content, (Para, ParaContainer))
        super().append(content)

    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        return "\n\n".join(
            element.to_asciidoc(context) for element in self.contents
            if element.to_asciidoc(context).strip())

    def normalize(self) -> None:
        new_contents: List[DescriptionElement] = []
        while self.contents:
            child = self.contents.pop(0)

            # Normalize ParaContainers and add them if not empty
            if isinstance(child, (Para, ParaContainer)):
                child.normalize()

            if isinstance(child, ParaContainer):
                child.normalize()
                if child.contents:
                    new_contents.append(child)
                continue

            assert isinstance(child, Para)

            # Paras and ParaContainers inside a Para need to be promoted to the current
            # ParaContainer. Split the existing content in separate Paras around other Paras and
            # ParaContainers

            # Clone the original Para for the initial non-Para content
            new_para = child.clone_without_contents()
            while child.contents and not isinstance(child.contents[0], (Para, ParaContainer)):
                new_para.append(child.contents.pop(0))
            new_contents.append(new_para)

            reassess = []
            while child.contents:
                # Promote Paras and ParaContainers
                while child.contents and isinstance(child.contents[0], (Para, ParaContainer)):
                    reassess.append(child.contents.pop(0))

                # Use the last Para to reasses, or clone the original Para for following non-Para
                # content
                if isinstance(reassess[-1], Para):
                    new_para = reassess.pop(-1)
                else:
                    new_para = child.clone_without_contents()
                while child.contents and not isinstance(child.contents[0], (Para, ParaContainer)):
                    new_para.append(child.contents.pop(0))
                reassess.append(new_para)
            self.contents = reassess + self.contents

        self.contents = new_contents

    SectionT = TypeVar("SectionT", bound="NamedSection")

    def pop_section(self, section_type: Type[SectionT], name: str) -> Optional[SectionT]:
        for i, child in enumerate(self.contents):
            # Mypy has some issues understanding that child is an instance of NamedSection,
            # requiring the explicit casts below
            if isinstance(child, section_type) and cast(ParaContainer.SectionT, child).name == name:
                return cast(ParaContainer.SectionT, self.contents.pop(i))
        return None


class Para(NestedDescriptionElement):
    """A single paragraph of text."""
    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        return super().to_asciidoc(context).strip()

    def clone_without_contents(self):
        return self.__class__(self.language_tag)

    def add_text(self, text: str) -> None:
        self.append(PlainText(self.language_tag, text))


class PlainText(DescriptionElement):
    """Plain text.

    Formatting may be applied by parent elements.

    Attributes:
        text: The plain text.
    """
    text: str

    def __init__(self, language_tag: str, text: str):
        super().__init__(language_tag)
        self.text = text

    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        return self.text.strip("\r\n")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {repr(self.text)}"

    def add_text(self, text: str) -> None:
        self.text += text


class LineBreak(DescriptionElement):
    """Line break.

    This breaks the current line, but not the paragraph.
    """
    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        return " +\n"


class Section(ParaContainer):
    """Collection of paragraphs with a title or header.

    Args:
        title: Title of the section. Shown as a discrete header before the paragraphs.
        level: Level of the header used for the section.
    """
    title: str
    level: int

    def __init__(self,
                 language_tag: str,
                 title: str = "",
                 level: int = 1,
                 *contents: DescriptionElement):
        super().__init__(language_tag, *contents)
        self.title = title
        self.level = level

    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        header = f"[discrete]\n{'=' * self.level} {self.title}"
        return f"{header}\n\n{super().to_asciidoc(context)}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: level={self.level}, {repr(self.title)}"

    @classmethod
    def from_xml(cls, xml_element: ET.Element, language_tag: str) -> "Section":
        level = int(xml_element.tag[4:])
        return cls(language_tag=language_tag, level=level)

    def update_from_xml(self, xml_element: ET.Element):
        if xml_element.tag == "title":
            assert xml_element.text
            self.title = xml_element.text.strip()


class NamedSection(ParaContainer):
    """Special paragraph indicating a section that can be retrieved by name.

    Attributes:
        name: Name of the section.
    """
    name: str

    def __init__(self, language_tag: str, name: str = "", *contents: DescriptionElement):
        super().__init__(language_tag, *contents)
        self.name = name


class Admonition(NamedSection):
    """Special paragraph indicating a text section that is either an admonition or sidebar."""
    ADMONITION_MAP = {
        "ATTENTION": "CAUTION",
        "NOTE": "NOTE",
        "REMARK": "NOTE",
        "WARNING": "WARNING",
    }

    def __init__(self, language_tag: str, name: str = "", *contents: DescriptionElement):
        super().__init__(language_tag, name, *contents)

    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        admonition = self.ADMONITION_MAP.get(self.name.upper())
        if admonition is None:
            return f".{self.name.capitalize()}\n[NOTE]\n====\n{super().to_asciidoc(context)}\n===="
        else:
            return f"[{admonition}]\n====\n{super().to_asciidoc(context)}\n===="

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self.name}"

    @classmethod
    def from_xml(cls, xml_element: ET.Element, language_tag: str) -> "Admonition":
        return cls(language_tag=language_tag, name=xml_element.get("kind", "").lower())

    def update_from_xml(self, xml_element: ET.Element):
        if xml_element.tag == "xreftitle":
            assert xml_element.text
            self.name = xml_element.text.lower()

    def add_tail(self, parent: NestedDescriptionElement, text: str):
        parent.append(Para(self.language_tag, PlainText(self.language_tag, text.lstrip())))


class Style(NestedDescriptionElement):
    """Apply a text style to contained elements.

    Attributes:
        kind: The kind of style to apply.
    """
    STYLE_MAP = {
        "emphasis": ("__", "__"),
        "bold": ("**", "**"),
        "computeroutput": ("``", "``"),
        "strike": ("+++<del>+++", "+++</del>+++"),
    }

    kind: str

    def __init__(self, language_tag: str, kind: str, *contents: DescriptionElement):
        super().__init__(language_tag, *contents)
        self.kind = kind

    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        style_start, style_end = self.STYLE_MAP.get(self.kind, ("", ""))
        return f"{style_start}{super().to_asciidoc(context)}{style_end}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self.kind}"

    @classmethod
    def from_xml(cls, xml_element: ET.Element, language_tag: str) -> "Style":
        return cls(language_tag=language_tag, kind=xml_element.tag)

    def add_text(self, text: str) -> None:
        self.append(PlainText(self.language_tag, text))

    def add_tail(self, parent: NestedDescriptionElement, text: str) -> None:
        parent.append(PlainText(self.language_tag, text))


class ListContainer(ParaContainer):
    """Paragraph that contains a list (bullet or ordered).

    Attributes:
        marker: Marker used for each list item.
    """

    marker: str

    def __init__(self, language_tag: str, marker: str, *contents: DescriptionElement):
        super().__init__(language_tag, *contents)
        self.marker = marker

    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        context = context or AsciiDocContext()

        if context.list_markers:
            if context.list_markers[-1].startswith(self.marker):
                marker = f"{context.list_markers[-1]}{self.marker}"
            else:
                marker = self.marker
        else:
            marker = self.marker

        context.list_markers.append(marker)
        ret = super().to_asciidoc(context)
        context.list_markers.pop(-1)

        return ret

    @classmethod
    def from_xml(cls, xml_element: ET.Element, language_tag: str) -> "ListContainer":
        if xml_element.tag == "orderedlist":
            marker = "."
        else:
            marker = "*"

        return cls(language_tag=language_tag, marker=marker)

    def add_tail(self, parent: NestedDescriptionElement, text: str) -> None:
        parent.append(Para(self.language_tag, PlainText(self.language_tag, text.lstrip())))


class ListItem(ParaContainer):
    """A single item in a bullet list.

    The item itself can contain multiple paragraphs.
    """
    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        assert context is not None
        assert context.list_markers
        marker = context.list_markers[-1]
        return f"{marker} {super().to_asciidoc(context)}"

    def add_text(self, text: str) -> None:
        """Ignore text outside paras."""

    def add_tail(self, parent: NestedDescriptionElement, text: str) -> None:
        """Ignore text outside paras."""


class ProgramListing(NestedDescriptionElement):
    """A block of code."""
    EXTENSION_MAPPING = {
        "py": "python",
        "kt": "kotlin",
        "mm": "objc",
        "unparsed": "",
    }

    filename: str

    def __init__(self, language_tag: str, filename: str, *contents: DescriptionElement):
        super().__init__(language_tag, *contents)
        self.filename = filename

    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        code = "\n".join(element.to_asciidoc(context) for element in self.contents)

        if self.filename:
            _, _, extension = self.filename.partition(".")
            language = self.EXTENSION_MAPPING.get(extension, extension)
        else:
            language = self.language_tag
        return f"[source,{language}]\n----\n{code}\n----"

    @classmethod
    def from_xml(cls, xml_element: ET.Element, language_tag: str) -> "ProgramListing":
        return cls(language_tag, xml_element.get("filename", ""))


class CodeLine(NestedDescriptionElement):
    """A single line in a block of code."""


class Verbatim(Para):
    """Piece of text to show verbatim.

    Args:
        text: Text to show.
    """
    text: str

    def __init__(self, language_tag: str, text: str = ""):
        super().__init__(language_tag)
        self.text = text

    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        stripped_text = self.text.strip("\r\n")
        return f"[source]\n----\n{stripped_text}\n----"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {repr(self.text)}"

    def clone_without_contents(self) -> "Verbatim":
        return self.__class__(self.language_tag, self.text)

    def add_text(self, text: str) -> None:
        self.text += text


class Diagram(Para):
    """Textual description of a diagram that can be used to generate a picture.

    Attributes:
        generator: The generator required to create the diagram.
    """
    GENERATOR_MAP = {
        "dot": "graphviz",
    }
    generator: str

    def __init__(self, language_tag: str, generator: str, *contents: DescriptionElement):
        super().__init__(language_tag, *contents)
        self.generator = generator

    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        # Not using Para.to_asciidoc() due to extra stripping that needs to be avoided here
        generator = self.GENERATOR_MAP.get(self.generator, self.generator)
        return f"[{generator}]\n....\n{NestedDescriptionElement.to_asciidoc(self, context)}\n...."

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self.generator}"

    def clone_without_contents(self) -> "Diagram":
        return self.__class__(self.language_tag, self.generator)

    @classmethod
    def from_xml(cls, xml_element: ET.Element, language_tag: str) -> "Diagram":
        return cls(language_tag, xml_element.tag)

    def add_tail(self, parent: NestedDescriptionElement, text: str) -> None:
        parent.append(Para(self.language_tag, PlainText(self.language_tag, text.lstrip())))


class ParameterList(NamedSection):
    """Special section containing a list of parameter descriptions."""
    def __init__(self, language_tag: str, name: str, *contents: NestedDescriptionElement):
        super().__init__(language_tag, name, *contents)

    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        return ""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self.name}"

    @classmethod
    def from_xml(cls, xml_element: ET.Element, language_tag: str) -> "ParameterList":
        return cls(language_tag, xml_element.get("kind", ""))


class ParameterDescription(ParaContainer):
    """Description of a single parameter.

    Attributes:
        name: Name of the parameter.
        direction: If supported, whether this is an in-parameter, out-parameter, or both.
    """
    name: Optional[str]
    direction: Optional[str]

    def __init__(self, language_tag: str, *contents: DescriptionElement):
        super().__init__(language_tag, *contents)
        self.name = None
        self.direction = None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self.name or ''} [{self.direction or ''}]"

    def update_from_xml(self, xml_element: ET.Element) -> None:
        if xml_element.tag == "parametername":
            self.name = xml_element.text
            self.direction = xml_element.get("direction")


class Ref(NestedDescriptionElement):
    """Reference to an API element. This appears as a hyperlink.

    Attributes:
        refid: Unique identifier of the API element.
        kindref: The kind of API element referred to.
    """
    refid: str
    kindref: str

    def __init__(self, language_tag: str, refid: str, kindref: str, *contents: DescriptionElement):
        super().__init__(language_tag, *contents)
        self.refid = refid
        self.kindref = kindref

    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        return f"<<{self.language_tag}-{self.refid},{super().to_asciidoc(context)}>>"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self.kindref}[{self.refid}]"

    @classmethod
    def from_xml(cls, xml_element: ET.Element, language_tag: str) -> "Ref":
        return cls(language_tag, xml_element.get("refid", ""), xml_element.get("kindref", ""))

    def add_text(self, text: str) -> None:
        self.append(PlainText(self.language_tag, text))

    def add_tail(self, parent: NestedDescriptionElement, text: str) -> None:
        parent.append(PlainText(self.language_tag, text))


class Ulink(NestedDescriptionElement):
    """Link to an external URL. This appears as a hyperlink.

    All nested elements will be part of the link.

    Attributes:
        url: URL to link to.

    """
    url: str

    def __init__(self, language_tag: str, url: str, *contents: DescriptionElement):
        super().__init__(language_tag, *contents)
        self.url = url

    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        return f"{self.url}[{super().to_asciidoc(context)}]"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self.url}"

    @classmethod
    def from_xml(cls, xml_element: ET.Element, language_tag: str) -> "Ulink":
        return cls(language_tag, xml_element.get("url", ""))

    def add_text(self, text: str) -> None:
        self.append(PlainText(self.language_tag, text))

    def add_tail(self, parent: NestedDescriptionElement, text: str) -> None:
        parent.append(PlainText(self.language_tag, text))


class Table(NestedDescriptionElement):
    """A table.

    Attributes:
        caption:   Optional caption for the table.
        cols:      The number of columns in the table.
    """
    caption: Optional[str]
    cols: str

    def __init__(self,
                 language_tag: str,
                 caption: Optional[str] = None,
                 cols: str = "1",
                 *contents: DescriptionElement):
        super().__init__(language_tag, *contents)
        self.caption = caption
        self.cols = cols

    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        context = context or AsciiDocContext()

        if len(context.table_separators) == 0:
            separator = "|"
        elif len(context.table_separators) > 0:
            separator = "!"
            if len(context.table_separators) > 1:
                logger.warning("Table nesting is only supported one level deep.")

        context.table_separators.append(separator)
        rows = "\n\n".join(element.to_asciidoc(context) for element in self.contents)
        context.table_separators.pop(-1)

        if self.caption:
            caption = f".{self.caption}\n"
        else:
            caption = ""

        options = f"[cols=\"{self.cols}*\", options=\"autowidth\"]"

        return f"{caption}{options}\n{separator}===\n\n{rows}\n\n{separator}==="

    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}: cols={self.cols}, " f"{self.caption}")

    @classmethod
    def from_xml(cls, xml_element: ET.Element, language_tag: str) -> "Table":
        return cls(language_tag, cols=xml_element.get("cols", "1"))

    def update_from_xml(self, xml_element: ET.Element) -> None:
        if xml_element.tag == "caption":
            self.caption = xml_element.text


class Row(NestedDescriptionElement):
    """A single row in a table."""
    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        return "\n".join(element.to_asciidoc(context) for element in self.contents)


class Entry(ParaContainer):
    """A single cell/entry in a table.

    Attributes:
        header:    Is this cell part of a header.
        rowspan:   The number of rows the cell spans. Not specified means 1.
        colspan:   The number of columns the cell spans. Not specified means 1.
    """
    header: Optional[str]
    rowspan: Optional[str]
    colspan: Optional[str]
    align: Optional[str]

    def __init__(self,
                 language_tag: str,
                 header: Optional[str] = None,
                 rowspan: Optional[str] = None,
                 colspan: Optional[str] = None,
                 align: Optional[str] = None,
                 *contents: DescriptionElement):
        super().__init__(language_tag, *contents)
        self.header = header
        self.rowspan = rowspan
        self.colspan = colspan
        self.align = align

    def add_text(self, text: str) -> None:
        """Ignore text outside paras."""

    def add_tail(self, parent: NestedDescriptionElement, text: str) -> None:
        """Ignore text outside paras."""

    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        assert context is not None
        assert context.table_separators
        separator = context.table_separators[-1]

        if self.header == "yes":
            style_operator = "h"
        else:
            style_operator = "a"

        if self.rowspan and self.colspan:
            span_operator = f"{self.colspan}.{self.rowspan}+"
        elif self.rowspan:
            span_operator = f".{self.rowspan}+"
        elif self.colspan:
            span_operator = f"{self.colspan}+"
        else:
            span_operator = ""

        align_operator = {"left": "", "center": "^", "right": ">", None: ""}.get(self.align, "")

        return (f"{span_operator}{align_operator}{style_operator}{separator} "
                f"{super().to_asciidoc(context)}")

    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}: header={self.header}, rowspan={self.rowspan}, "
                f"colspan={self.colspan}, align={self.align}")

    @classmethod
    def from_xml(cls, xml_element: ET.Element, language_tag: str) -> "Entry":
        return cls(language_tag, xml_element.get("thead", None), xml_element.get("rowspan", None),
                   xml_element.get("colspan", None), xml_element.get("align", None))


class Formula(DescriptionElement):
    """Formula in LatexMath format.

    Attributes:
        text: Contents of the formula.
    """
    text: str

    def __init__(self, language_tag: str, text: str = ""):
        super().__init__(language_tag)
        self.text = text

    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        stripped_text = self.text.strip("\r\n")
        if stripped_text.startswith(r"\[") and stripped_text.endswith(r"\]"):
            stripped_text = stripped_text[3:-3].strip()
        return f"latexmath:[{stripped_text}]"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {repr(self.text)}"

    def add_text(self, text: str) -> None:
        self.text += text

    def add_tail(self, parent: NestedDescriptionElement, text: str):
        parent.append(PlainText(self.language_tag, text))


class Image(DescriptionElement):
    """Insert an image.

    Attributes:
        output_type: Output document type the image is meant for. For now we only support `html`.
        file_name:   Name if the image file. Must be available in the images of the package.
        alt_text:    Alternative text when the image cannot be loaded, or for accessibility.
        width:       Optional width to show the image with.
        height:      Optional height to show the image with.
        inline:      Yes if the image needs to be inlined in the text.
    """
    output_type: str
    file_name: str
    alt_text: str
    width: str
    height: str
    inline: str

    def __init__(self, language_tag: str, output_type: str, file_name: str, width: str, height: str,
                 inline: str):
        super().__init__(language_tag)
        self.output_type = output_type
        self.file_name = file_name
        self.alt_text = ""
        self.width = width
        self.height = height
        self.inline = inline

    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        if self.output_type != "html":
            return ""

        if self.width or self.height:
            options = f'"{self.alt_text}",{self.width},{self.height}'
        elif self.alt_text:
            options = f'"{self.alt_text}"'
        else:
            options = ""

        if self.inline == "yes":
            separator = ":"
        else:
            separator = "::"

        return f"image{separator}{self.file_name}[{options}]"

    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}: {self.output_type}->{self.file_name}, "
                f"{repr(self.alt_text)}, width={self.width}, height={self.height}, "
                f"inline={self.inline}")

    @classmethod
    def from_xml(cls, xml_element: ET.Element, language_tag: str) -> "Image":
        return cls(language_tag, xml_element.get("type", ""), xml_element.get("name", ""),
                   xml_element.get("width", ""), xml_element.get("height", ""),
                   xml_element.get("inline", "no"))

    def add_text(self, text: str) -> None:
        self.alt_text += text

    def add_tail(self, parent: NestedDescriptionElement, text: str):
        parent.append(PlainText(self.language_tag, text))


class BlockQuote(ParaContainer):
    """One or more paragraphs forming a quote."""
    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        return f"[quote]\n____\n{super().to_asciidoc(context)}\n____"


class HorizontalRuler(Para):
    """Horizontal ruler."""
    def to_asciidoc(self, context: AsciiDocContext = None) -> str:
        return "'''"


def _parse_description(xml_element: ET.Element, parent: NestedDescriptionElement,
                       language_tag: str):
    element = None

    # Map of element tags for which a new element is to be constructed and added the the parent.
    NEW_ELEMENT: Mapping[str, Type[DescriptionElement]] = {
        "blockquote": BlockQuote,
        "bold": Style,
        "codeline": CodeLine,
        "computeroutput": Style,
        "dot": Diagram,
        "emphasis": Style,
        "entry": Entry,
        "formula": Formula,
        "highlight": Style,
        "hruler": HorizontalRuler,
        "image": Image,
        "itemizedlist": ListContainer,
        "linebreak": LineBreak,
        "listitem": ListItem,
        "orderedlist": ListContainer,
        "para": Para,
        "parameteritem": ParameterDescription,
        "parameterlist": ParameterList,
        "plantuml": Diagram,
        "programlisting": ProgramListing,
        "ref": Ref,
        "row": Row,
        "sect1": Section,
        "sect2": Section,
        "sect3": Section,
        "sect4": Section,
        "sect5": Section,
        "sect6": Section,
        "sect7": Section,
        "sect8": Section,
        "sect9": Section,
        "simplesect": Admonition,
        "strike": Style,
        "table": Table,
        "ulink": Ulink,
        "verbatim": Verbatim,
        "xrefsect": Admonition,
    }

    # Map of element tags that update the parent element.
    UPDATE_PARENT = {
        "caption": Table,
        "parametername": ParameterDescription,
        "title": Section,
        "xreftitle": Admonition,
    }

    # Map of element tags for which the children update its parent.
    USE_PARENT = {
        "parameterdescription": ParameterDescription,
        "parameternamelist": ParameterDescription,
        "xrefdescription": Admonition,
    }

    if xml_element.tag in NEW_ELEMENT:
        element = NEW_ELEMENT[xml_element.tag].from_xml(xml_element, language_tag)

    elif xml_element.tag in UPDATE_PARENT:
        assert isinstance(parent, UPDATE_PARENT[xml_element.tag])
        parent.update_from_xml(xml_element)
        element = parent

    elif xml_element.tag in USE_PARENT:
        assert isinstance(parent, USE_PARENT[xml_element.tag])
        element = parent

    elif xml_element.tag == "sp":
        element = PlainText(language_tag, f" {xml_element.tail or ''}")

    else:
        logger.warning(f"Unsupported XML tag <{xml_element.tag}>. Please report an issue on GitHub"
                       " with example code.")

    if element is None:
        return
    if element is not parent:
        parent.append(element)

    if xml_element.text:
        element.add_text(xml_element.text)

    if xml_element.tail:
        element.add_tail(parent, xml_element.tail)

    for child in xml_element:
        assert isinstance(element, NestedDescriptionElement)
        _parse_description(child, element, language_tag)
