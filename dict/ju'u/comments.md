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


## 2015-06-21T22:08:44Z — krtisfranks (comment 2071, on definition 1691, in reply to 2070)

Re: A more nailed-down definition

krtisfranks wrote:
> I propose that it be specified somewhere that the following 
interpretation 
> is to be made for ".a'y ju'u by" ("a base b"):
> 
> Let n, m be integers such that n, m > 0; let 'a' be represented by a 
string
> of digits, from left to right, (a_n, a_(n-1), ..., a_2, a_1, a_0, a_(-1),

> a_(-2), ..., a_(-m+1), a_(-m)), with a_n being leftmost and a_(-m) being 
> rightmost; let b be any number such that exponentiation of b by any 
integer
> in [-m, n] is defined (and preferably: strictly monotonic increasing fast

> enough with respect to increasing values in the exponent). Then: .a'y 
ju'u 
> by = (a_n, a_(n-1), ..., a_2, a_1, a_0, a_(-1), a_(-2), ..., a_(-m)) ju'y

> by = ((a_n)*(b^n)) + ((a_(n-1))*(b^(n-1))) + ... + ((a_2)*(b^2)) + 
> ((a_1)*(b^1)) + ((a_0)*(b^0)) + ((a_(-1))*(b^(-1))) + ((a_(-2))*(b^(-2)))
+
> ... + ((a_(-m+1))*(b^(-m+1))) + ((a_(-m))*(b^(-m))).


Oops: "[-m, n]" is supposed to be an interval from -m to n which includes 
both of those endpoints.


## 2015-06-21T22:26:54Z — krtisfranks (comment 2072, on definition 1691, in reply to 2070)

Re: A more nailed-down definition

krtisfranks wrote:
> I propose that it be specified somewhere that the following 
interpretation 
> is to be made for ".a'y ju'u by" ("a base b"):
> 
> Let n, m be integers such that n, m > 0; let 'a' be represented by a 
string
> of digits, from left to right, (a_n, a_(n-1), ..., a_2, a_1, a_0, a_(-1),

> a_(-2), ..., a_(-m+1), a_(-m)), with a_n being leftmost and a_(-m) being 
> rightmost; let b be any number such that exponentiation of b by any 
integer
> in [-m, n] is defined (and preferably: strictly monotonic increasing fast

> enough with respect to increasing values in the exponent). Then: .a'y 
ju'u 
> by = (a_n, a_(n-1), ..., a_2, a_1, a_0, a_(-1), a_(-2), ..., a_(-m)) ju'y

> by = ((a_n)*(b^n)) + ((a_(n-1))*(b^(n-1))) + ... + ((a_2)*(b^2)) + 
> ((a_1)*(b^1)) + ((a_0)*(b^0)) + ((a_(-1))*(b^(-1))) + ((a_(-2))*(b^(-2)))
+
> ... + ((a_(-m+1))*(b^(-m+1))) + ((a_(-m))*(b^(-m))).


In order to be clear, 'a' would normally be expressed with "{pi}" between 
digit 'a_0' and 'a_(-1)'. All other commas are technically "{pi'e}"'s, but 
I assumed for simplicity that the base for each digit was constant and such
that a_i is a single-digit number in that base for all i.

