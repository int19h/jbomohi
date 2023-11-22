## 2023-11-22T07:42:10Z — krtisfranks (comment 3793, on definition 73378)

Why not just "{pi'u}".

I thought that "pi'u" might be sufficient for this meaning; Lojban could
generalize the Cartesian product from a set operator to an arbitrary
operator. But if the input is a set which is treated as a number, then
there is ambiguity. So, I created this word.


## 2023-11-22T07:50:27Z — krtisfranks (comment 3794)

Utility

This word functions as "$\cdot$" herein:

Operator $\cdot: S \times S → S \times S$, such that $(a, b) \mapsto (a,
b)$.
In other words: $a \cdot b = (a, b)$.

Then, make such operator a big operator.

This then allows one to generate tuples of arbitrary size without
"$\dots$". For example:
$(x_1, x_2, \dots, x_n)$ is ambiguous because the rule of construction is
not specified and the ellipsis relies on intuition but is not technically
defined, whereas $\times_{i \in \[1, n\] \cap \mathbb{Z}} (x_i)$ is not
ambiguous. It also allows for extension to infinitely many terms via an
explicitly defined formula.

English mathematical writing usually lacks this degree of clarity.

