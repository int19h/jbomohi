## 2021-01-29T07:01:58Z — krtisfranks (comment 3646, on definition 69442)

Why have two sumti slots?

We need only one with "{gi'e}" (or any other desired connective) internal
to the abstraction (id est: between "{ka}" and implicit/explicit "{kei}")
for an, I think, equivalent result. The flexibility with the connective,
if it present at all, is a strengthening of the definition, I think.


## 2021-01-29T07:43:26Z — zozeizeizeizeifaho (comment 3649, on definition 69442, in reply to 3646)

Re: Why have two sumti slots?

{kancusu'oi} and the others are meant to cover the meanings of quantifiers
when given two predicates. As in:

> su'o mlatu cu barda
> ro mlatu cu barda

where the first implies ∧ between {mlatu} and {barda} and the second
implies →.

You can find predicates for {su'oi} and {ro'oi} with one argument, without
the implied connective, at {suzdza} and {roldza}.


## 2021-01-30T21:12:50Z — krtisfranks (comment 3652, on definition 69442, in reply to 3649)

Re: Why have two sumti slots?

zozeizeizeizeifaho wrote:
> {kancusu'oi} and the others are meant to cover the meanings of
quantifiers
> when given two predicates. As in:
> 
> > su'o mlatu cu barda
> > ro mlatu cu barda
> 
> where the first implies ∧ between {mlatu} and {barda} and the second
> implies →.
> 
> You can find predicates for {su'oi} and {ro'oi} with one argument,
without
> the implied connective, at {suzdza} and {roldza}.

Okay, but why not make it arbitrarily many (including possibly infinitely
many)?


## 2021-01-31T09:28:57Z — zozeizeizeizeifaho (comment 3653, on definition 69442, in reply to 3652)

Re: Why have two sumti slots?

krtisfranks wrote:
> Okay, but why not make it arbitrarily many (including possibly
infinitely
> many)?

Since the quantifier grammar allows at most two predicates as arguments, I
hadn't thought about how they might generalize! Now that I do, I'm
confused.

{su'oi}'s expansion uses the associative ∧, and
> su'oi gi [ke'a] broda gi brode gi brodi [gi'i]
(forgive the grammar) would make sense as
> ∃x (broda(x) ∧ brode(x) ∧ brodi(x))

but what would
> ro'oi gi broda gi brode gi brodi
best mean?
> ?? ∀x ((broda(x) → brode(x)) → brodi(x))
> ?? ∀x (broda(x) → (brode(x) → brodi(x)))
> ?? ∀x (broda(x) → (brode(x) ∧ brodi(x)))


## 2021-02-01T07:36:24Z — krtisfranks (comment 3655, on definition 69442, in reply to 3653)

Re: Why have two sumti slots?

zozeizeizeizeifaho wrote:
> krtisfranks wrote:
> > Okay, but why not make it arbitrarily many (including possibly
> infinitely
> > many)?
> 
> Since the quantifier grammar allows at most two predicates as arguments,
I
> hadn't thought about how they might generalize! Now that I do, I'm
> confused.
> 
> {su'oi}'s expansion uses the associative ∧, and
> > su'oi gi [ke'a] broda gi brode gi brodi [gi'i]
> (forgive the grammar) would make sense as
> > ∃x (broda(x) ∧ brode(x) ∧ brodi(x))
> 
> but what would
> > ro'oi gi broda gi brode gi brodi
> best mean?
> > ?? ∀x ((broda(x) → brode(x)) → brodi(x))
> > ?? ∀x (broda(x) → (brode(x) → brodi(x)))
> > ?? ∀x (broda(x) → (brode(x) ∧ brodi(x)))


I actually think that "{ro'oi}" should not require and implication like
that at all. It might require implication, but it is not necessarily
structured in any of those ways. "∀x ∈ A, (P(x))" just means "x ∈ A ⇒
P(x)"; if "A" is omitted, then the universal set/set of discourse is meant
(where "set" can be replaced by "category", "object", or some other
structure, depending on context). The universal quantification is just the
first portion of this clause. But, if we are to include both pieces, then
I guess that I would say that "ro'oi(x, A, (P_1, P_2, P_3, ...))" would
mean "x ∈ A ⇒ (P_1 (x), & P_2 (x), & P_3 (x), ..."; we can, again, omit A.
A phrase "all cats" implicitly means "∀x ∈ A" where A is the set of only
and all cats, too.

Alternatively, we can take P_0 to be the proposition representing
membership in A, which would immediately narrow the range of relevant x
values from the universal set to A. This would introduce an asymmetry in
the the (now-ordered) list of propositions (because it would mean "∀x,
(P_0 (x) ⇒  (P_1 (x), & P_2 (x), & P_3 (x)))"), where "∀x" means "all x in
our discourse space". This would be, I think, the last option which you
outlined.

I am going off how I use it and have seen it be used. We can, of course,
define it in any manner which we want.

