## 2014-08-04T05:18:19Z — krtisfranks (comment 1289, on definition 1975)

Overloaded

Presumably, this operator is overloaded, right? For example, it is typical
integer multiplication for integers, scalar multiplication for vectors,
and pointwise multiplication for functions; correct? (Modulo
context/definitions)


## 2015-11-10T06:16:24Z — krtisfranks (comment 2603, on definition 1975, in reply to 1289)

Re: Overloaded

krtisfranks wrote:
> Presumably, this operator is overloaded, right? For example, it is 
typical
> integer multiplication for integers, scalar multiplication for vectors,
> and pointwise multiplication for functions; correct? (Modulo
> context/definitions)


And should matrix multiplication  (of vectors or matrices as standard ly 
described) be considered "pi'i"?

In any case, I think that we should have an entry-wise/componentwise 
operator (de)convertion; that is, one which distributes an operator to each
term in a tuple (or which can go layers deeper) if valid. This idea is 
rather like the dot operators in MatLab, "@@" in Mathematica, and relates 
to vectorization.


## 2015-11-10T06:25:31Z — gleki (comment 2604, on definition 1975, in reply to 2603)

Re: Overloaded

krtisfranks wrote:
> krtisfranks wrote:
> > Presumably, this operator is overloaded, right? For example, it is 
> typical
> > integer multiplication for integers, scalar multiplication for vectors,
> > and pointwise multiplication for functions; correct? (Modulo
> > context/definitions)
> 
> 
> And should matrix multiplication  (of vectors or matrices as standard ly 
> described) be considered "pi'i"?
> 
> In any case, I think that we should have an entry-wise/componentwise 
> operator (de)convertion; that is, one which distributes an operator to 
each
> term in a tuple (or which can go layers deeper) if valid. This idea is 
> rather like the dot operators in MatLab, "@@" in Mathematica, and relates

> to vectorization.


It's a good idea to map words to less polysemous operators like in MatLab.

P.S. I wish you created more brivla rather than cmavo connectives.


## 2015-11-12T22:14:38Z — krtisfranks (comment 2606, on definition 1975, in reply to 2604)

Re: Overloaded

gleki wrote:
> krtisfranks wrote:
> > krtisfranks wrote:
> > > Presumably, this operator is overloaded, right? For example, it is 
> > typical
> > > integer multiplication for integers, scalar multiplication for 
vectors,
> > > and pointwise multiplication for functions; correct? (Modulo
> > > context/definitions)
> > 
> > 
> > And should matrix multiplication  (of vectors or matrices as standard 
ly 
> > described) be considered "pi'i"?
> > 
> > In any case, I think that we should have an entry-wise/componentwise 
> > operator (de)convertion; that is, one which distributes an operator to 
> each
> > term in a tuple (or which can go layers deeper) if valid. This idea is 
> > rather like the dot operators in MatLab, "@@" in Mathematica, and 
relates
> 
> > to vectorization.
> 
> 
> It's a good idea to map words to less polysemous operators like in 
MatLab.
> 
> P.S. I wish you created more brivla rather than cmavo connectives.

I agree.

Re: P.S.
Unfortunately, that is not really how the language works; mekso operators 
almost surely should be cmavo. There are a few cases for brivla being 
useful (such as with .{aigne}), but those ideas are not really operators. 
:/

