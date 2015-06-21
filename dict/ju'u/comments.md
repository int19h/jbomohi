## 2015-06-21T22:07:36Z — krtisfranks (comment 2070, on definition 1691)

A more nailed-down definition

I propose that it be specified somewhere that the following interpretation 
is to be made for ".a'y ju'u by" ("a base b"):

Let n, m be integers such that n, m > 0; let 'a' be represented by a string
of digits, from left to right, (a_n, a_(n-1), ..., a_2, a_1, a_0, a_(-1), 
a_(-2), ..., a_(-m+1), a_(-m)), with a_n being leftmost and a_(-m) being 
rightmost; let b be any number such that exponentiation of b by any integer
in [-m, n] is defined (and preferably: strictly monotonic increasing fast 
enough with respect to increasing values in the exponent). Then: .a'y ju'u 
by = (a_n, a_(n-1), ..., a_2, a_1, a_0, a_(-1), a_(-2), ..., a_(-m)) ju'y 
by = ((a_n)*(b^n)) + ((a_(n-1))*(b^(n-1))) + ... + ((a_2)*(b^2)) + 
((a_1)*(b^1)) + ((a_0)*(b^0)) + ((a_(-1))*(b^(-1))) + ((a_(-2))*(b^(-2))) +
... + ((a_(-m+1))*(b^(-m+1))) + ((a_(-m))*(b^(-m))).

