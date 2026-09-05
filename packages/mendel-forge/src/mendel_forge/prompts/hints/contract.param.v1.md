A parameter is a value a user or a rule needs to vary **across analyses**. Everything else is
plumbing.

A thread count the executor sets is not a parameter. A path the workflow computes is not a
parameter. An option the tool needs on every invocation is a baseline argument, not a choice
anybody should be asked to make — offering it as a parameter is a fake decision, and every fake
decision is a question a person has to answer for no benefit.

Every parameter needs a **route**: how the value reaches the tool. `ext.args` for a command-line
flag, a positional argument, a `meta` key the module translates itself, or a process directive. A
parameter with no route is a value that resolves and reaches nothing.

A default needs evidence and a reason. The tool's own documented default is evidence; what a
different tool does is not.
