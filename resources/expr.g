expr = identifier /
       number /
       operator_call /
       <"("> expr <")"> /
       funcall

funcall = identifier ws* <"("> ws* expr (ws* <","> ws* expr)* ws* <")">

operator_call = expr ws* operator ws* expr

operator = "/" / "+" / "*" / "-"
<ws> = <#'\s+'>
identifier = #'[a-zA-Z_][a-zA-Z_0-9]*'
number = #'-*[0-9]+(\.[0-9]+)?'
