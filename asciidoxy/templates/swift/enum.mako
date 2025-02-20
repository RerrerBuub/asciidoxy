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

################################################################################ Helper includes ##
<%!
from asciidoxy.templates.helpers import h1, tc
from asciidoxy.templates.swift.helpers import SwiftTemplateHelper
%>
<%
helper = SwiftTemplateHelper(api, element, insert_filter)
%>
######################################################################## Header and introduction ##
${h1(leveloffset, f"[[{element.id},{element.full_name}]]{element.name}")}
${api.inserted(element)}

[source,swift,subs="-specialchars,macros+"]
----
% if element.include:
#import &lt;${element.include}&gt;

% endif
enum ${element.full_name}
----

${element.brief}

${element.description}

[cols='h,5a']
|===

% for section_title, section_text in element.sections.items():
| ${section_title}
| ${section_text | tc}

% endfor
% for value in helper.enum_values(prot="public"):
${api.inserted(value)}
| [[${value.id},${value.name}]]${value.name}
|
${value.brief | tc}

${value.description | tc}

% endfor
|===

