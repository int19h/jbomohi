## 2015-01-31T22:00:12Z — durka42 (comment 1663, on definition 16350)

formal grammar

I worked on formalizing these words for the camxes PEG. The result is
here: https://github.com/Ilmen-vodhr/ilmentufa/pull/86


## 2015-06-24T07:25:07Z — krtisfranks (comment 2087)

{le'ai} on its own

How do we know that {le'ai} is actually occurring on its own (which, I 
presume, means that it has no explicit terminator) rather than just quoting
an extremely long text? In Probability Theoretic language, there is no 
apparent stopping time.


## 2015-06-24T07:26:40Z — krtisfranks (comment 2088, in reply to 2087)

Re: {le'ai} on its own

krtisfranks wrote:
> How do we know that {le'ai} is actually occurring on its own (which, I 
> presume, means that it has no explicit terminator) rather than just 
quoting
> an extremely long text? In Probability Theoretic language, there is no 
> apparent stopping time.

Oops, I misunderstood. I thought {lo'ai} at every point even though I read 
or typed {le'ai}. Ignore me.


## 2015-06-24T21:09:11Z — durka42 (comment 2090, in reply to 2088)

Re: {le'ai} on its own

krtisfranks wrote:
> krtisfranks wrote:
> > How do we know that {le'ai} is actually occurring on its own (which, I 
> > presume, means that it has no explicit terminator) rather than just 
> quoting
> > an extremely long text? In Probability Theoretic language, there is no 
> > apparent stopping time.
> 
> Oops, I misunderstood. I thought {lo'ai} at every point even though I 
read 
> or typed {le'ai}. Ignore me.

For the record the way I (provisionally) implemented this in camxes-exp 
goes like this:

(LOhAI spaces? (!LOhAI !LEhAI any_word)*)? (LOhAI spaces? (!LOhAI !LEhAI 
any_word)*)? LEhAI spaces?

Basically, {lo'ai} and {sa'ai} are like {lo'u} in that they really can't 
occur on their own. But zero, one or two "lo'ai *"/"sa'ai *" clauses can 
come before a {le'ai}.

