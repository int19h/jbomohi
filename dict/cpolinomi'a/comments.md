## 2014-01-21T19:23:52Z — krtisfranks (comment 905, on definition 44334)

Commentary

We now have a way to specify formal polynomials (as opposed to polynomial
functions). I propose that {tefsujme'o} be used strictly for the latter
situation and ve redefined accordingly.
I was thinking that we should generalize both definitions to be at least
usable for Laurent polynomials/series (resp.); perhaps for Taylor
expansions too.

We now have a word for coefficient of a polynomial, which was not
immediately clear before.


## 2014-12-25T05:18:45Z — krtisfranks (comment 1533)

terbri

The current definition is: x1 is a formal polynomial with coefficients x2
(ordered list) of degree x3 over structure/ring x4 (to which coefficients
x2 all belong) and in indeterminant x5

I am thinking that it should be:
y1 is a formal polynomial over structure/ring y2 (to which coefficients y5
all belong) and in indeterminant y3 that is of degree y4 with specific
coefficients y5 (ordered list, each element belongs to structure y2;
default is the list: (y1_0, y1_1, y1_1, ..., y1_((y4) + 1)) ).

This definition better matches the frequency with which higher math makes
uses of the various terbri.  Does anyone have any comments?


## 2015-04-19T19:14:41Z — krtisfranks (comment 1811, on definition 44334, in reply to 905)

Re: Commentary

krtisfranks wrote:
> We now have a way to specify formal polynomials (as opposed to polynomial
> functions). I propose that {tefsujme'o} be used strictly for the latter
> situation and ve redefined accordingly.
> I was thinking that we should generalize both definitions to be at least
> usable for Laurent polynomials/series (resp.); perhaps for Taylor
> expansions too.
> 
> We now have a word for coefficient of a polynomial, which was not
> immediately clear before.

I think that it may be better for the coefficients to be presentes in an 
ordered list with the first coefficient presented being the leading 
coefficient and then each subsequent coefficient being associated with the 
power of the variable decreased by one per entry in the list such that any 
nonspecified coefficients are assumed to be 0. In this way, the list would 
work more like {ki'o}; additionally, the leading coefficient is the most 
important one and should be easiest to reference and specify. (Note: the 
first coefficient specified would typically be forced to be nonzero under 
this proposal)


## 2015-04-20T16:57:06Z — gleki (comment 1812)

c- ?

what is c- in "c-polinomi'o" for?


## 2015-04-20T20:44:22Z — krtisfranks (comment 1813, in reply to 1812)

Re: c- ?

gleki wrote:
> what is c- in "c-polinomi'o" for?

I do not recall. I had a reason. :/


## 2016-04-30T18:04:26Z — krtisfranks (comment 2948, on definition 44334)

Some more issues

The indeterminate could be understood to belong to another structure 
(particularly, the domain, when understood as a function). But in algebra, 
this really is not necessary. I am not sure whether or not to support it.

I think that I am going to reverse the order of the coefficients, since we 
want the order to match the default of {po'i'oi} and the highest-degree 
coefficient is the most important one.

