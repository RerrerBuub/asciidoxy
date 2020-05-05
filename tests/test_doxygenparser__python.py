# Copyright (C) 2019-2020, TomTom (http://tomtom.com).
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
"""Tests for parsing python from Doxygen XML files."""


def test_parse_python_class(parser_factory):
    parser = parser_factory("python/default")

    python_class = parser.api_reference.find("asciidoxy.geometry.Coordinate",
                                             kind="class",
                                             lang="python")
    assert python_class is not None
    assert python_class.id == "python-classasciidoxy_1_1geometry_1_1_coordinate"
    assert python_class.name == "Coordinate"
    assert python_class.full_name == "asciidoxy.geometry.Coordinate"
    assert python_class.language == "python"
    assert python_class.kind == "class"
    assert python_class.brief == "Class to hold information about a coordinate."
    assert python_class.description == "A coordinate has a latitude, longitude, and an altitude."
    assert python_class.namespace == "asciidoxy.geometry"

    assert len(python_class.members) == 5
    assert len(python_class.enumvalues) == 0

    member_names = sorted(m.name for m in python_class.members)
    assert member_names == sorted(["altitude", "latitude", "longitude", "is_valid", "__init__"])


def test_parse_python_class_with_nested_class(parser_factory):
    parser = parser_factory("python/default")

    python_class = parser.api_reference.find("asciidoxy.traffic.TrafficEvent",
                                             kind="class",
                                             lang="python")
    assert python_class is not None
    assert python_class.id == "python-classasciidoxy_1_1traffic_1_1_traffic_event"
    assert python_class.namespace == "asciidoxy.traffic"
    # one for nested class and one for enum
    assert len(python_class.inner_classes) == 2

    nested_class = python_class.inner_classes[0]
    assert nested_class.name == "asciidoxy.traffic.TrafficEvent.Severity"
    assert nested_class.namespace == "asciidoxy.traffic.TrafficEvent"
    assert nested_class.language == "python"
    assert nested_class.id == "python-classasciidoxy_1_1traffic_1_1_traffic_event_1_1_severity"
    # referred object will be set after parsing all classes, during phase of resolving references
    assert nested_class.referred_object is None

    nested_class = python_class.inner_classes[1]
    assert nested_class.name == "asciidoxy.traffic.TrafficEvent.TrafficEventData"
    assert nested_class.namespace == "asciidoxy.traffic.TrafficEvent"
    assert nested_class.id == ("python-classasciidoxy_1_1traffic_1_1_traffic_event_1_1_"
                               "traffic_event_data")
    assert nested_class.language == "python"
    # referred object will be set after parsing all classes, during phase of resolving references
    assert nested_class.referred_object is None

    parser.resolve_references()

    nested_class = python_class.inner_classes[0]
    assert nested_class.referred_object
    assert nested_class.referred_object.name == "Severity"
    assert nested_class.referred_object.kind == "class"

    nested_class = python_class.inner_classes[1]
    assert nested_class.referred_object
    assert nested_class.referred_object.name == "TrafficEventData"
    assert nested_class.referred_object.kind == "class"


def test_parse_python_method(parser_factory):
    parser = parser_factory("python/default")

    member = parser.api_reference.find("asciidoxy.traffic.TrafficEvent.update",
                                       kind="function",
                                       lang="python")

    assert member is not None
    assert member.id == ("python-classasciidoxy_1_1traffic_1_1_traffic_event_"
                         "1a3eb310fb6cb4929eabe8eea356e59f2e")
    assert member.name == "update"
    assert member.full_name == "asciidoxy.traffic.TrafficEvent.update"
    assert member.language == "python"
    assert member.kind == "function"
    assert member.definition == " bool asciidoxy.traffic.TrafficEvent.update"
    assert member.args == "(self, int cause, int delay)"
    assert member.brief == "Update the traffic event data."
    assert member.description == "Verifies the new information before updating."
    assert member.prot == "public"
    assert member.static is False
    assert member.namespace == "asciidoxy.traffic.TrafficEvent"

    assert len(member.params) == 3

    assert member.params[0].type
    assert member.params[0].type.name == "self"
    assert not member.params[0].name
    assert not member.params[0].description

    assert member.params[1].type
    assert member.params[1].type.name == "int"
    assert member.params[1].name == "cause"
    assert member.params[1].description == "New TPEG cause code."

    assert member.params[2].type
    assert member.params[2].type.name == "int"
    assert member.params[2].name == "delay"
    assert member.params[2].description == "New delay in seconds."

    assert len(member.exceptions) == 0
    assert len(member.enumvalues) == 0

    assert member.returns is not None
    assert member.returns.type is not None
    assert not member.returns.type.id
    assert not member.returns.type.kind
    assert member.returns.type.language == "python"
    assert member.returns.type.name == "bool"
    assert member.returns.type.namespace == "asciidoxy.traffic.TrafficEvent"
    assert not member.returns.type.prefix
    assert not member.returns.type.suffix
    assert len(member.returns.type.nested) == 0
    assert member.returns.description == "True if the update is valid."
