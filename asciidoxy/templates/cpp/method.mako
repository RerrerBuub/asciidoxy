## Copyright (C) 2019-2021, TomTom (http://tomtom.com).
##
## Licensed under the Apache License, Version 2.0 (the "License");
## you may not use this file except in compliance with the License.
## You may obtain a copy of the License at
##
##   http://www.apache.org/licenses/LICENSE-2.0
##
## Unless required by applicable law or agreed to in writing, software
## distributed under the License is distributed on an "AS IS" BASIS,
## WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
## See the License for the specific language governing permissions and
## limitations under the License.
<%!
from asciidoxy.templates.helpers import h1
from asciidoxy.templates.cpp.helpers import CppTemplateHelper
from html import escape
%>

${h1(leveloffset, f"[[{element.id},{element.full_name}]]{element.name}")}
${api.inserted(element)}

[%autofit]
[source,cpp,subs="-specialchars,macros+"]
----
${escape(CppTemplateHelper(api).method_signature(element))}
----
<%include file="/cpp/_function.mako"/>
